"""
ECMWF下载器进度管理模块

实现线程安全的任务进度管理，支持持久化和观察者模式。
使用多文件存储策略，按任务状态分文件存储。
"""

import copy
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from src.core.exceptions import ProgressLoadError, ProgressSaveError
from src.core.models import TaskEventType, TaskInfo, TaskStatus
from src.core.progress_store import MultiFileTaskStore, TaskStore

logger = logging.getLogger(__name__)

# 合法状态转换映射：{当前状态: {允许转换的目标状态集合}}
# P0-2 修复：扩展失败转换路径，避免 update_status() 绕过校验
# 审查修复 #2：添加 DOWNLOADING -> QUEUED 路径，支持调度器启动失败回退
VALID_TRANSITIONS: Dict[TaskStatus, set] = {
    TaskStatus.PENDING: {
        TaskStatus.QUEUED,
        TaskStatus.FAILED,  # P0-2: 参数缺失等错误可直转失败
        TaskStatus.CANCELLED,
    },
    TaskStatus.QUEUED: {
        TaskStatus.DOWNLOADING,
        TaskStatus.PENDING,  # 用户取消入队
        TaskStatus.FAILED,   # P0-2: 调度失败
        TaskStatus.CANCELLED,
    },
    TaskStatus.DOWNLOADING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.RETRYING,
        TaskStatus.QUEUED,   # 审查修复 #2: 调度器启动失败回退
    },
    TaskStatus.RETRYING: {
        TaskStatus.DOWNLOADING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.PENDING,
        TaskStatus.QUEUED,  # P0-2: 重试失败时回队列等待
    },
    TaskStatus.COMPLETED: set(),  # 终态，不允许转换
    TaskStatus.FAILED: {TaskStatus.PENDING},  # 失败可重试
    TaskStatus.CANCELLED: {TaskStatus.PENDING},  # 取消可重新入队
}

if TYPE_CHECKING:
    pass


def _deep_copy_task(task: TaskInfo) -> TaskInfo:
    """深拷贝任务信息

    创建 TaskInfo 的完全独立副本，包括 metadata 等可变字段。

    Args:
        task: 原始任务信息

    Returns:
        TaskInfo: 深拷贝后的任务信息
    """
    # 创建新实例并深拷贝可变字段
    task_dict = task.__dict__.copy()
    task_dict["metadata"] = copy.deepcopy(task.metadata)
    return TaskInfo(**task_dict)


class ProgressManager:
    """进度管理器

    管理所有下载任务的进度和状态，提供线程安全的操作接口。
    支持持久化到多文件 JSON 存储和观察者模式。

    存储策略：
    - 使用 MultiFileTaskStore 按状态分文件存储
    - 可通过 data_dir 参数指定数据目录
    - 可通过 store 参数注入自定义存储实现
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        store: Optional[TaskStore] = None,
    ):
        """初始化进度管理器

        Args:
            data_dir: 数据目录路径（用于多文件存储，默认为 data/）
            store: 自定义存储实现（优先级高于 data_dir）

        Note:
            如果同时提供 store 和 data_dir，优先使用 store。
            如果只提供 data_dir，会自动创建 MultiFileTaskStore。
        """
        self._store: Optional[TaskStore] = store

        # 如果只提供了 data_dir，创建多文件存储
        if self._store is None and data_dir is not None:
            self._store = MultiFileTaskStore(data_dir)

        self.tasks: Dict[str, TaskInfo] = {}

        # 线程安全锁（使用RLock支持同线程重入）
        self._lock = threading.RLock()

        # 观察者列表（进度变化时调用的回调函数）
        # 回调签名：(task_id: str, task_info: TaskInfo, event_type: TaskEventType) -> None
        self._observers: List[Callable[[str, TaskInfo, "TaskEventType"], None]] = []

        # 如果有存储，则加载
        if self._store is not None:
            self.load()

    @property
    def data_dir(self) -> Optional[Path]:
        """获取数据目录路径

        Returns:
            Optional[Path]: 多文件存储的数据目录
        """
        if isinstance(self._store, MultiFileTaskStore):
            return self._store.data_dir
        return None

    @property
    def store(self) -> Optional[TaskStore]:
        """获取存储实例

        Returns:
            Optional[TaskStore]: 存储实现
        """
        return self._store

    def load(self) -> None:
        """从存储加载进度

        加载后会自动执行状态修复（reconcile），将非持久状态重置为 PENDING。
        如果有任务被修复，会自动保存到存储以保持一致性。

        Raises:
            ProgressLoadError: 文件读取失败或格式错误
        """
        if self._store is None:
            return

        with self._lock:
            self.tasks = self._store.load()
            reconciled_count = self._reconcile_tasks()

        # 如果有任务被修复，保存以保持存储一致性
        if reconciled_count > 0:
            try:
                self.save()
            except ProgressSaveError as e:
                # 审查修复 #7：记录保存失败日志
                logger.error(
                    f"[ProgressManager] load() reconcile 后保存失败: error={e}"
                )

    def _reconcile_tasks(self) -> int:
        """修复任务状态

        将非持久状态（QUEUED, DOWNLOADING, RETRYING）重置为 PENDING。
        这在应用启动时调用，用于处理崩溃后遗留的不一致状态。

        P1-2 修复：完整清理所有运行时字段。

        Returns:
            int: 被修复的任务数量

        Note:
            此方法应在锁内调用。
        """
        transient_statuses = TaskStatus.get_transient_statuses()
        reconciled_count = 0

        for task in self.tasks.values():
            if task.status in transient_statuses:
                task.status = TaskStatus.PENDING

                # P1-2 修复：完整清理运行时字段
                task.account_id = None
                task.started_at = None
                task.progress = 0.0
                task.downloaded_size = 0
                task.error_message = None

                # 清理 metadata 中的重试时间
                if "next_retry_at" in task.metadata:
                    del task.metadata["next_retry_at"]

                reconciled_count += 1

        return reconciled_count

    def save(self) -> None:
        """保存进度到存储

        Raises:
            ProgressSaveError: 文件保存失败
        """
        if self._store is None:
            return

        with self._lock:
            self._store.save(self.tasks)

    def save_task(self, task_id: str) -> None:
        """保存单个任务到存储

        对于多文件存储，此方法比 save() 更高效。
        对于单文件存储，此方法会重写整个文件。

        Args:
            task_id: 任务ID

        Raises:
            ProgressSaveError: 文件保存失败
            KeyError: 任务不存在
        """
        if self._store is None:
            return

        with self._lock:
            if task_id not in self.tasks:
                raise KeyError(f"任务不存在: {task_id}")
            self._store.save_task(task_id, self.tasks[task_id])

    def create_task(
        self,
        task_id: str,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskInfo:
        """创建新任务

        Args:
            task_id: 任务唯一标识
            filename: 目标文件名
            metadata: 额外元数据

        Returns:
            TaskInfo: 创建的任务信息
        """
        with self._lock:
            task = TaskInfo(
                task_id=task_id,
                filename=filename,
                status=TaskStatus.PENDING,
                metadata=metadata or {},
            )
            self.tasks[task_id] = task
            # 构造快照用于锁外通知（深拷贝避免外部修改）
            task_snapshot = _deep_copy_task(task)

        # 锁外通知观察者（避免死锁）
        self._notify_observers(task_id, task_snapshot, TaskEventType.CREATED)

        return task

    def can_transition(self, current_status: TaskStatus, target_status: TaskStatus) -> bool:
        """检查状态转换是否合法

        Args:
            current_status: 当前状态
            target_status: 目标状态

        Returns:
            bool: 是否允许转换
        """
        if current_status not in VALID_TRANSITIONS:
            return False
        return target_status in VALID_TRANSITIONS[current_status]

    def transition(
        self,
        task_id: str,
        target_status: TaskStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """安全的状态转换

        验证状态转换是否合法，合法则执行转换并通知观察者。

        P0-4 修复：在关键状态转换时持久化到磁盘。
        审查修复 #1：落盘移到锁内，避免并发乱序覆盖。

        Args:
            task_id: 任务ID
            target_status: 目标状态
            error_message: 错误信息（可选，用于 FAILED 状态）

        Returns:
            bool: 是否成功转换

        Raises:
            ValueError: 状态转换不合法时抛出
        """
        task_snapshot = None

        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return False

            current_status = task.status

            # 验证状态转换
            if not self.can_transition(current_status, target_status):
                raise ValueError(
                    f"非法状态转换: {current_status.value} → {target_status.value}"
                )

            # 执行状态转换
            task.status = target_status

            # 更新时间戳
            if target_status == TaskStatus.DOWNLOADING and task.started_at is None:
                task.started_at = datetime.now().isoformat()
            elif target_status in TaskStatus.get_finalizable_statuses():
                task.completed_at = datetime.now().isoformat()
            elif target_status == TaskStatus.PENDING:
                # 重新入队时清空终态相关字段
                task.completed_at = None
                task.started_at = None
                task.error_message = None

            # 记录错误信息
            if error_message is not None:
                task.error_message = error_message

            # 构造快照（用于通知和持久化）
            task_snapshot = _deep_copy_task(task)

            # 审查修复 #1：在锁内持久化，避免并发乱序
            # 终态、入队、开始下载、重试时需要持久化
            should_persist = target_status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
                TaskStatus.QUEUED,
                TaskStatus.DOWNLOADING,
                TaskStatus.RETRYING,
            )

            if should_persist and self._store is not None:
                try:
                    self._store.save_task(task_id, task_snapshot)
                except Exception as e:
                    # 审查修复 #7：记录持久化失败日志，便于问题排查
                    logger.error(
                        f"[ProgressManager] transition() 持久化失败: "
                        f"task_id={task_id}, status={target_status.value}, error={e}"
                    )

        # 锁外通知观察者（避免死锁）
        if task_snapshot is not None:
            self._notify_observers(task_id, task_snapshot, TaskEventType.UPDATED)

        return True

    def enqueue(self, task_id: str) -> bool:
        """将任务入队

        将 PENDING 状态的任务转换为 QUEUED 状态，准备被调度器调度。

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功入队

        Raises:
            ValueError: 任务状态不是 PENDING 时抛出
        """
        return self.transition(task_id, TaskStatus.QUEUED)

    def enqueue_all_pending(self) -> int:
        """将所有 PENDING 任务入队

        Returns:
            int: 成功入队的任务数量
        """
        enqueued_count = 0
        task_ids_to_enqueue = []

        with self._lock:
            for task_id, task in self.tasks.items():
                if task.status == TaskStatus.PENDING:
                    task_ids_to_enqueue.append(task_id)

        for task_id in task_ids_to_enqueue:
            try:
                self.enqueue(task_id)
                enqueued_count += 1
            except ValueError:
                # 忽略转换失败的任务
                pass

        return enqueued_count

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """更新任务状态

        审查修复 #5：此方法绕过状态机校验，应优先使用 transition()。
        保留此方法仅用于降级场景，调用时会记录告警日志。
        P1-1 修复：将告警挪到确认任务存在之后，避免无效告警噪声。

        Args:
            task_id: 任务ID
            status: 新状态
            error_message: 错误信息（可选）

        Warning:
            此方法不校验状态转换合法性，不持久化。应优先使用 transition()。
        """
        task_snapshot = None
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return

            # P1-1 修复：仅在实际执行更新时记录告警，避免对不存在任务产生噪声
            logger.warning(
                f"[ProgressManager] update_status() 绕过状态机校验: "
                f"task_id={task_id}, status={status.value}。建议使用 transition() 方法。"
            )

            task.status = status

            # 更新时间戳
            if status == TaskStatus.DOWNLOADING and task.started_at is None:
                task.started_at = datetime.now().isoformat()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                task.completed_at = datetime.now().isoformat()

            # 记录错误信息
            if error_message is not None:
                task.error_message = error_message

            # 构造快照用于锁外通知（深拷贝避免外部修改）
            task_snapshot = _deep_copy_task(task)

        # 锁外通知观察者（避免死锁）
        if task_snapshot is not None:
            self._notify_observers(task_id, task_snapshot, TaskEventType.UPDATED)

    def update_progress(
        self,
        task_id: str,
        progress: float,
        downloaded_size: Optional[int] = None,
    ) -> None:
        """更新任务进度

        Args:
            task_id: 任务ID
            progress: 进度百分比（0-100）
            downloaded_size: 已下载大小（可选）
        """
        task_snapshot = None
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return

            task.progress = max(0.0, min(100.0, progress))
            if downloaded_size is not None:
                task.downloaded_size = downloaded_size

            # 构造快照用于锁外通知（深拷贝避免外部修改）
            task_snapshot = _deep_copy_task(task)

        # 锁外通知观察者（避免死锁）
        if task_snapshot is not None:
            self._notify_observers(task_id, task_snapshot, TaskEventType.UPDATED)

    def increment_retry(self, task_id: str) -> int:
        """增加任务的重试计数

        P0-1 修复：只递增计数，不改状态。
        状态转换由调用方通过 transition() 统一处理。

        Args:
            task_id: 任务ID

        Returns:
            int: 更新后的重试次数
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return 0

            task.retry_count += 1
            return task.retry_count

    def set_account(self, task_id: str, account_id: str) -> None:
        """设置任务使用的账号

        P1-4 修复：设置账号后通知观察者，让 UI 能看到账号变化。

        Args:
            task_id: 任务ID
            account_id: 账号ID
        """
        task_snapshot = None
        with self._lock:
            task = self.tasks.get(task_id)
            if task is not None:
                task.account_id = account_id
                # P1-4 修复：构造快照用于锁外通知
                task_snapshot = _deep_copy_task(task)

        # P1-4 修复：锁外通知观察者
        if task_snapshot is not None:
            self._notify_observers(task_id, task_snapshot, TaskEventType.UPDATED)

    def update_task_metadata(self, task_id: str, metadata_updates: Dict[str, Any]) -> None:
        """更新任务的元数据

        P1-1 修复：支持更新 metadata 中的字段（如 next_retry_at）。

        Args:
            task_id: 任务ID
            metadata_updates: 要更新的元数据键值对
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task is not None:
                task.metadata.update(metadata_updates)

    def reset_task_for_retry(self, task_id: str) -> None:
        """重置任务的运行时字段，准备重新下载

        审查修复 #3：在 UI 重试时清零 retry_count 和其他运行时字段。
        审查修复 #6：添加观察者通知和持久化，确保 UI 刷新和数据一致性。

        P1-风险2 修复：明确适用边界。

        Warning:
            此方法仅重置字段，不改变任务状态。推荐使用 retry_task() 进行原子化重试操作。
            此方法适用于以下特定场景：
            - 需要单独重置运行时字段但不立即入队的场景
            - 内部流程中需要分步操作的场景

            对于常规的"重试失败任务"场景，请使用 retry_task() 方法，它会：
            - 原子化完成"重置字段 + 转 PENDING + 入队"
            - 避免中间态落盘
            - 只触发一次观察者通知

        Args:
            task_id: 任务ID
        """
        task_snapshot = None
        with self._lock:
            task = self.tasks.get(task_id)
            if task is not None:
                task.retry_count = 0
                task.progress = 0.0
                task.downloaded_size = 0
                task.account_id = None
                task.started_at = None
                task.completed_at = None
                task.error_message = None
                # 清理 metadata 中的重试时间
                if "next_retry_at" in task.metadata:
                    del task.metadata["next_retry_at"]

                # 审查修复 #6：构造快照用于锁外通知
                task_snapshot = _deep_copy_task(task)

                # 审查修复 #6：在锁内持久化重置后的状态
                if self._store is not None:
                    try:
                        self._store.save_task(task_id, task_snapshot)
                    except Exception as e:
                        # 审查修复 #7：记录持久化失败日志
                        logger.error(
                            f"[ProgressManager] reset_task_for_retry() 持久化失败: "
                            f"task_id={task_id}, error={e}"
                        )

        # 审查修复 #6：锁外通知观察者，确保 UI 刷新
        if task_snapshot is not None:
            self._notify_observers(task_id, task_snapshot, TaskEventType.UPDATED)

    def retry_task(self, task_id: str) -> bool:
        """原子化重试任务：重置字段 + 转 PENDING + 入队

        P1-2 修复：将"重置字段 + 转 PENDING + 入队"封装为原子操作，
        避免中间态落盘和多次观察者通知。

        P1-风险1 修复：添加 can_transition() 断言检查，确保状态机规则变更时自动校验。

        仅允许 FAILED/CANCELLED 状态的任务调用此方法。

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功启动重试

        Raises:
            ValueError: 任务状态不是 FAILED/CANCELLED 时抛出，或状态转换不合法时抛出
        """
        task_snapshot = None
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return False

            current_status = task.status

            # 仅允许 FAILED/CANCELLED 状态重试
            if current_status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                raise ValueError(
                    f"只能重试失败或已取消的任务，当前状态: {current_status.value}"
                )

            # P1-风险1 修复：断言状态转换合法性，确保状态机规则变更时自动校验
            if not self.can_transition(current_status, TaskStatus.PENDING):
                raise ValueError(
                    f"非法状态转换: {current_status.value} → {TaskStatus.PENDING.value}"
                )
            if not self.can_transition(TaskStatus.PENDING, TaskStatus.QUEUED):
                raise ValueError(
                    f"非法状态转换: {TaskStatus.PENDING.value} → {TaskStatus.QUEUED.value}"
                )

            # 步骤1：重置运行时字段
            task.retry_count = 0
            task.progress = 0.0
            task.downloaded_size = 0
            task.account_id = None
            task.started_at = None
            task.completed_at = None
            task.error_message = None
            if "next_retry_at" in task.metadata:
                del task.metadata["next_retry_at"]

            # 步骤2：转换状态到 PENDING（清理终态字段）
            task.status = TaskStatus.PENDING

            # 步骤3：转换状态到 QUEUED
            task.status = TaskStatus.QUEUED

            # 构造最终快照
            task_snapshot = _deep_copy_task(task)

            # 一次持久化（最终状态：QUEUED）
            if self._store is not None:
                try:
                    self._store.save_task(task_id, task_snapshot)
                except Exception as e:
                    logger.error(
                        f"[ProgressManager] retry_task() 持久化失败: "
                        f"task_id={task_id}, error={e}"
                    )

        # 一次观察者通知
        if task_snapshot is not None:
            self._notify_observers(task_id, task_snapshot, TaskEventType.UPDATED)

        return True

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息（深拷贝副本）

        Args:
            task_id: 任务ID

        Returns:
            Optional[TaskInfo]: 任务信息的深拷贝副本，如果不存在则返回None
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return None
            # 返回深拷贝副本避免外部修改
            return _deep_copy_task(task)

    def get_all_tasks(self) -> List[TaskInfo]:
        """获取所有任务（深拷贝副本列表）

        Returns:
            List[TaskInfo]: 所有任务的深拷贝副本列表
        """
        with self._lock:
            return [_deep_copy_task(task) for task in self.tasks.values()]

    def get_tasks_by_status(self, status: TaskStatus) -> List[TaskInfo]:
        """根据状态筛选任务（深拷贝副本）

        Args:
            status: 任务状态

        Returns:
            List[TaskInfo]: 符合条件的深拷贝任务列表
        """
        with self._lock:
            return [
                _deep_copy_task(task)
                for task in self.tasks.values()
                if task.status == status
            ]

    def delete_task(self, task_id: str) -> bool:
        """删除任务

        审查修复 #4：删除任务时同步持久化到存储层，避免重启后任务"复活"。

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功删除
        """
        task_snapshot = None
        with self._lock:
            if task_id not in self.tasks:
                return False

            # 保存任务信息深拷贝副本（用于锁外通知观察者）
            task_snapshot = _deep_copy_task(self.tasks[task_id])
            del self.tasks[task_id]

            # 审查修复 #4：在锁内同步删除存储层记录
            if self._store is not None:
                try:
                    self._store.delete_task(task_id)
                except Exception as e:
                    # 审查修复 #7：记录存储层删除失败日志
                    logger.error(
                        f"[ProgressManager] delete_task() 存储层删除失败: "
                        f"task_id={task_id}, error={e}"
                    )

        # 锁外通知观察者（避免死锁）
        if task_snapshot is not None:
            self._notify_observers(task_id, task_snapshot, TaskEventType.DELETED)

        return True

    def clear_completed(self) -> int:
        """清除所有已完成的任务

        Returns:
            int: 清除的任务数量
        """
        with self._lock:
            to_delete = [
                task_id
                for task_id, task in self.tasks.items()
                if task.status == TaskStatus.COMPLETED
            ]
            for task_id in to_delete:
                del self.tasks[task_id]
            return len(to_delete)

    def clear_all(self) -> None:
        """清除所有任务"""
        with self._lock:
            self.tasks.clear()

    def get_summary(self) -> dict:
        """获取进度摘要统计

        Returns:
            dict: 包含统计信息的字典
        """
        with self._lock:
            total = len(self.tasks)
            if total == 0:
                return {
                    "total_tasks": 0,
                    "pending": 0,
                    "queued": 0,
                    "downloading": 0,
                    "completed": 0,
                    "failed": 0,
                    "cancelled": 0,
                    "retrying": 0,
                    "overall_progress": 0.0,
                }

            status_counts = {status: 0 for status in TaskStatus}
            total_progress = 0.0

            for task in self.tasks.values():
                status_counts[task.status] += 1
                total_progress += task.progress

            return {
                "total_tasks": total,
                "pending": status_counts[TaskStatus.PENDING],
                "queued": status_counts[TaskStatus.QUEUED],
                "downloading": status_counts[TaskStatus.DOWNLOADING],
                "completed": status_counts[TaskStatus.COMPLETED],
                "failed": status_counts[TaskStatus.FAILED],
                "cancelled": status_counts[TaskStatus.CANCELLED],
                "retrying": status_counts[TaskStatus.RETRYING],
                "overall_progress": total_progress / total,
            }

    def register_observer(
        self, callback: Callable[[str, TaskInfo, "TaskEventType"], None]
    ) -> None:
        """注册观察者

        当任务状态或进度变化时，会调用所有已注册的回调函数。

        Args:
            callback: 回调函数，签名为 (task_id: str, task_info: TaskInfo, event_type: TaskEventType) -> None
        """
        with self._lock:
            self._observers.append(callback)

    def unregister_observer(self, callback: Callable[[str, TaskInfo, "TaskEventType"], None]) -> None:
        """取消注册观察者

        Args:
            callback: 要取消的回调函数
        """
        with self._lock:
            if callback in self._observers:
                self._observers.remove(callback)

    def _notify_observers(
        self, task_id: str, task_info: TaskInfo, event_type: TaskEventType
    ) -> None:
        """通知所有观察者

        Args:
            task_id: 任务ID
            task_info: 任务信息快照
            event_type: 事件类型（CREATED/UPDATED/DELETED）
        """
        # 复制观察者列表（避免在通知过程中被修改）
        with self._lock:
            observers_copy = list(self._observers)

        # 在锁外调用观察者，避免死锁
        for observer in observers_copy:
            try:
                observer(task_id, task_info, event_type)
            except Exception:
                # 观察者异常不应影响进度管理
                pass

    def get_pending_tasks(self) -> List[TaskInfo]:
        """获取所有待处理的任务（PENDING和RETRYING）

        Returns:
            List[TaskInfo]: 待处理任务的深拷贝列表
        """
        with self._lock:
            return [
                _deep_copy_task(task)
                for task in self.tasks.values()
                if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING, TaskStatus.QUEUED)
            ]

    def get_active_tasks(self) -> List[TaskInfo]:
        """获取所有活动任务（DOWNLOADING）

        Returns:
            List[TaskInfo]: 活动任务列表
        """
        return self.get_tasks_by_status(TaskStatus.DOWNLOADING)

    def has_pending_tasks(self) -> bool:
        """检查是否有待处理任务

        Returns:
            bool: 是否有待处理任务
        """
        with self._lock:
            return any(
                task.status in (TaskStatus.PENDING, TaskStatus.RETRYING)
                for task in self.tasks.values()
            )

    def get_task_count(self) -> int:
        """获取任务总数

        Returns:
            int: 任务总数
        """
        with self._lock:
            return len(self.tasks)
