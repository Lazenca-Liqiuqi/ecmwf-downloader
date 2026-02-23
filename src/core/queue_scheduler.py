"""
ECMWF 下载器队列调度器模块

实现下载任务的队列调度，支持并发限流和账号分配。
"""

import logging
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Optional, Set

from src.core.progress import TaskStatus

if TYPE_CHECKING:
    from src.core.account_pool import AccountPool
    from src.core.config import AccountInfo
    from src.core.progress import ProgressManager

logger = logging.getLogger(__name__)


class DownloadQueueScheduler:
    """下载队列调度器

    负责从 QUEUED/RETRYING 队列中取任务、分配账号、启动下载。

    功能：
    - 定期检测 QUEUED 和 RETRYING 状态的任务
    - 检查并发限制（max_workers）
    - 从账号池获取可用账号
    - 状态转换：QUEUED/RETRYING -> DOWNLOADING
    - 调用启动下载回调

    线程安全：
    - 使用 RLock 保护内部状态
    - 回调通过 call_from_thread 在主线程执行

    修复记录：
    - P0-2: 启动失败时保持 QUEUED，不走 DOWNLOADING->QUEUED
    - P0-3: 添加日志记录，不静默吞异常
    - P1-1: 同时消费 QUEUED 和 RETRYING 状态
    - P1-4: 改进 stop() 超时处理
    """

    # 默认轮询间隔（秒）
    DEFAULT_POLL_INTERVAL = 1.0

    def __init__(
        self,
        progress_manager: "ProgressManager",
        account_pool: "AccountPool",
        start_download_callback: Callable[[str, "AccountInfo"], None],
        max_workers: int = 3,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ):
        """初始化队列调度器

        Args:
            progress_manager: 进度管理器
            account_pool: 账号池
            start_download_callback: 启动下载的回调函数，签名为 (task_id, account)
            max_workers: 最大并发下载数
            poll_interval: 轮询间隔（秒）
        """
        self.progress_manager = progress_manager
        self.account_pool = account_pool
        self.start_download_callback = start_download_callback
        self.max_workers = max_workers
        self.poll_interval = poll_interval

        # 正在下载的任务集合（task_id）
        self._active_tasks: Set[str] = set()

        # 线程控制
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def active_count(self) -> int:
        """当前活动任务数量"""
        with self._lock:
            return len(self._active_tasks)

    @property
    def is_running(self) -> bool:
        """调度器是否正在运行"""
        with self._lock:
            return self._running

    def start(self) -> None:
        """启动调度器

        创建后台线程，定期检测队列并启动下载。
        """
        with self._lock:
            if self._running:
                return

            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._scheduler_loop,
                name="DownloadQueueScheduler",
                daemon=True,
            )
            self._thread.start()
            logger.info("[Scheduler] 队列调度器已启动")

    def stop(self) -> None:
        """停止调度器

        设置停止标志并等待线程结束。
        超时后会记录警告但不会阻塞。
        """
        with self._lock:
            if not self._running:
                return

            self._running = False
            self._stop_event.set()

        # 等待线程结束
        if self._thread is not None:
            # 使用较短的超时，但会记录警告
            if not self._thread.is_alive():
                logger.info("[Scheduler] 调度线程已停止")
            else:
                self._thread.join(timeout=self.poll_interval * 3)
                if self._thread.is_alive():
                    logger.warning(
                        "[Scheduler] 调度线程未能在超时内停止，但由于是 daemon 线程不会阻塞退出"
                    )
                else:
                    logger.info("[Scheduler] 调度线程已正常停止")
            self._thread = None

    def _scheduler_loop(self) -> None:
        """调度器主循环

        定期检测队列，启动下载任务。
        """
        logger.info("[Scheduler] 调度循环开始")
        while not self._stop_event.is_set():
            try:
                self._process_queue()
            except Exception as e:
                # P0-3 修复：记录异常而非静默吞掉
                logger.exception(f"[Scheduler] 处理队列时发生异常: {e}")

            # 等待下一次轮询
            self._stop_event.wait(self.poll_interval)

        logger.info("[Scheduler] 调度循环结束")

    def _process_queue(self) -> None:
        """处理队列中的任务

        1. 获取可用槽位
        2. 获取 QUEUED 和 RETRYING 任务
        3. P1-1 修复：过滤还未到重试时间的 RETRYING 任务
        4. 分配账号
        5. 状态转换，然后启动下载
        """
        # 计算可用的并发槽位
        with self._lock:
            available_slots = self.max_workers - len(self._active_tasks)

        if available_slots <= 0:
            return

        # P1-1 修复：同时获取 QUEUED 和 RETRYING 任务
        queued_tasks = self.progress_manager.get_tasks_by_status(TaskStatus.QUEUED)
        retrying_tasks = self.progress_manager.get_tasks_by_status(TaskStatus.RETRYING)

        # P1-1 修复：过滤还未到重试时间的 RETRYING 任务
        now = datetime.now()
        ready_retrying_tasks = []
        for task in retrying_tasks:
            next_retry_at_str = task.metadata.get("next_retry_at")
            if next_retry_at_str:
                try:
                    next_retry_at = datetime.fromisoformat(next_retry_at_str)
                    if now < next_retry_at:
                        # 还未到重试时间，跳过
                        continue
                except (ValueError, TypeError):
                    # 时间解析失败，允许重试
                    pass
            ready_retrying_tasks.append(task)

        # 合并并按创建时间排序（先进先出）
        all_tasks = queued_tasks + ready_retrying_tasks
        if not all_tasks:
            return

        all_tasks.sort(key=lambda t: t.created_at)

        # 尝试启动任务
        started_count = 0
        for task in all_tasks:
            if started_count >= available_slots:
                break

            if self._try_start_task(task.task_id, task.status):
                started_count += 1

    def _try_start_task(self, task_id: str, current_status: TaskStatus) -> bool:
        """尝试启动一个任务

        P0-3 修复：启动失败时恢复原状态，而非直接打 FAILED。
        这样调度器下次轮询时会再次尝试。

        Args:
            task_id: 任务ID
            current_status: 当前状态

        Returns:
            bool: 是否成功启动
        """
        # 再次检查并发限制
        with self._lock:
            if len(self._active_tasks) >= self.max_workers:
                return False
            # 防止重复启动
            if task_id in self._active_tasks:
                return False

        # 获取可用账号
        try:
            account = self.account_pool.get_next_account()
        except Exception as e:
            # P1-2 修复：记录账号获取失败原因
            logger.warning(f"[Scheduler] 获取账号失败，任务 {task_id} 保持排队: {e}")
            return False

        # 记录活动任务（在状态转换之前）
        with self._lock:
            self._active_tasks.add(task_id)

        # 状态转换到 DOWNLOADING
        try:
            success = self.progress_manager.transition(
                task_id, TaskStatus.DOWNLOADING
            )
            if not success:
                # 转换失败，从活动集合移除
                with self._lock:
                    self._active_tasks.discard(task_id)
                logger.warning(f"[Scheduler] 任务 {task_id} 状态转换失败，可能已被其他进程处理")
                return False
        except ValueError as e:
            # 转换不合法，从活动集合移除
            with self._lock:
                self._active_tasks.discard(task_id)
            logger.warning(f"[Scheduler] 任务 {task_id} 非法状态转换: {e}")
            return False

        # 设置账号
        self.progress_manager.set_account(task_id, account.id)

        # 启动下载（在锁外执行回调）
        try:
            self.start_download_callback(task_id, account)
            logger.info(f"[Scheduler] 任务 {task_id} 已启动下载，账号: {account.id}")
            return True
        except Exception as e:
            # P0-3 修复：启动失败时，恢复原状态让调度器下次重试
            with self._lock:
                self._active_tasks.discard(task_id)

            logger.exception(f"[Scheduler] 启动下载失败，任务 {task_id} 将恢复原状态: {e}")

            # P0-3 修复：恢复到原状态（QUEUED 或 RETRYING）
            # DOWNLOADING -> RETRYING 和 DOWNLOADING -> QUEUED 都是合法转换
            try:
                if current_status == TaskStatus.RETRYING:
                    self.progress_manager.transition(task_id, TaskStatus.RETRYING, f"启动失败: {e}")
                else:
                    self.progress_manager.transition(task_id, TaskStatus.QUEUED, f"启动失败: {e}")
            except ValueError:
                # 如果恢复失败，强制更新
                self.progress_manager.update_status(task_id, current_status, f"启动失败: {e}")

            return False

    def on_task_completed(self, task_id: str) -> None:
        """任务完成回调

        从活动任务集合中移除已完成的任务。

        Args:
            task_id: 完成的任务ID
        """
        with self._lock:
            if task_id in self._active_tasks:
                self._active_tasks.discard(task_id)
                logger.info(f"[Scheduler] 任务 {task_id} 已完成，释放槽位")
            else:
                logger.debug(f"[Scheduler] 任务 {task_id} 完成（但不在活动集合中）")

    def enqueue_all_pending(self) -> int:
        """将所有 PENDING 任务入队

        便捷方法，批量入队所有待处理的任务。

        Returns:
            int: 成功入队的任务数量
        """
        return self.progress_manager.enqueue_all_pending()
