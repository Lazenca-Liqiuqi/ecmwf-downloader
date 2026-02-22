"""
ECMWF下载器进度管理模块

实现线程安全的任务进度管理，支持持久化和观察者模式。
"""

import json
import os
import threading
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.core.exceptions import ProgressLoadError, ProgressSaveError


class TaskStatus(str, Enum):
    """任务状态枚举

    状态流转：
    PENDING → QUEUED → DOWNLOADING → COMPLETED/FAILED/CANCELLED
                      ↘ RETRYING ↗
    """

    PENDING = "pending"  # 待下载（初始状态）
    QUEUED = "queued"  # 已入队（等待调度）
    DOWNLOADING = "downloading"  # 下载中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消
    RETRYING = "retrying"  # 重试中


class TaskEventType(str, Enum):
    """任务事件类型枚举

    用于观察者模式中区分不同的事件类型。
    """

    CREATED = "created"  # 任务创建
    UPDATED = "updated"  # 任务更新（状态、进度等）
    DELETED = "deleted"  # 任务删除


@dataclass
class TaskInfo:
    """任务信息数据类

    记录单个下载任务的所有信息。
    """

    task_id: str  # 任务唯一标识
    filename: str  # 目标文件名
    status: TaskStatus  # 当前状态
    progress: float = 0.0  # 下载进度（0-100）
    error_message: Optional[str] = None  # 错误信息
    retry_count: int = 0  # 重试次数
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None  # 开始时间
    completed_at: Optional[str] = None  # 完成时间
    file_size: Optional[int] = None  # 文件大小（字节）
    downloaded_size: int = 0  # 已下载大小（字节）
    account_id: Optional[str] = None  # 使用的账号ID
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "task_id": self.task_id,
            "filename": self.filename,
            "status": self.status.value,
            "progress": self.progress,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "file_size": self.file_size,
            "downloaded_size": self.downloaded_size,
            "account_id": self.account_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskInfo":
        """从字典创建实例"""
        # 处理状态枚举
        if isinstance(data.get("status"), str):
            data["status"] = TaskStatus(data["status"])
        return cls(**data)


class ProgressManager:
    """进度管理器

    管理所有下载任务的进度和状态，提供线程安全的操作接口。
    支持持久化到JSON文件和观察者模式。
    """

    def __init__(self, progress_file: Optional[Path] = None):
        """初始化进度管理器

        Args:
            progress_file: 进度文件路径，如果为None则不启用持久化
        """
        self.progress_file = progress_file
        self.tasks: Dict[str, TaskInfo] = {}

        # 线程安全锁（使用RLock支持同线程重入）
        self._lock = threading.RLock()

        # 观察者列表（进度变化时调用的回调函数）
        # 回调签名：(task_id: str, task_info: TaskInfo, event_type: TaskEventType) -> None
        self._observers: List[Callable[[str, TaskInfo, "TaskEventType"], None]] = []

        # 如果提供了进度文件，则加载
        if progress_file is not None and progress_file.exists():
            self.load()

    def load(self) -> None:
        """从文件加载进度

        Raises:
            ProgressLoadError: 文件读取失败或格式错误
        """
        if self.progress_file is None:
            return

        try:
            with self._lock:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 解析任务列表
                tasks_data = data.get("tasks", [])
                self.tasks = {
                    task_data["task_id"]: TaskInfo.from_dict(task_data)
                    for task_data in tasks_data
                }

        except FileNotFoundError:
            # 文件不存在是正常情况，首次运行时创建
            self.tasks = {}
        except json.JSONDecodeError as e:
            raise ProgressLoadError(
                f"进度文件JSON格式错误: {e}",
                file_path=str(self.progress_file),
                original_error=e,
            )
        except Exception as e:
            raise ProgressLoadError(
                f"加载进度文件失败: {e}",
                file_path=str(self.progress_file),
                original_error=e,
            )

    def save(self) -> None:
        """保存进度到文件

        Raises:
            ProgressSaveError: 文件保存失败
        """
        if self.progress_file is None:
            return

        try:
            with self._lock:
                # 转换为字典格式
                data = {
                    "tasks": [task.to_dict() for task in self.tasks.values()],
                    "updated_at": datetime.now().isoformat(),
                }

                self.progress_file.parent.mkdir(parents=True, exist_ok=True)

                # 原子写入：先写入同目录临时文件，再用 os.replace 原子替换目标文件
                tmp_fd, tmp_path = tempfile.mkstemp(
                    prefix=f"{self.progress_file.name}.",
                    suffix=".tmp",
                    dir=str(self.progress_file.parent),
                )
                try:
                    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                        f.write("\n")
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(tmp_path, self.progress_file)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except FileNotFoundError:
                        pass

        except Exception as e:
            raise ProgressSaveError(
                f"保存进度文件失败: {e}",
                file_path=str(self.progress_file),
                original_error=e,
            )

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
            # 构造快照用于锁外通知
            task_snapshot = TaskInfo(**task.__dict__)

        # 锁外通知观察者（避免死锁）
        self._notify_observers(task_id, task_snapshot, TaskEventType.CREATED)

        return task

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            error_message: 错误信息（可选）
        """
        task_snapshot = None
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return

            task.status = status

            # 更新时间戳
            if status == TaskStatus.DOWNLOADING and task.started_at is None:
                task.started_at = datetime.now().isoformat()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                task.completed_at = datetime.now().isoformat()

            # 记录错误信息
            if error_message is not None:
                task.error_message = error_message

            # 构造快照用于锁外通知
            task_snapshot = TaskInfo(**task.__dict__)

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

            # 构造快照用于锁外通知
            task_snapshot = TaskInfo(**task.__dict__)

        # 锁外通知观察者（避免死锁）
        if task_snapshot is not None:
            self._notify_observers(task_id, task_snapshot, TaskEventType.UPDATED)

    def increment_retry(self, task_id: str) -> int:
        """增加任务的重试计数

        Args:
            task_id: 任务ID

        Returns:
            int: 更新后的重试次数
        """
        task_snapshot = None
        retry_count = 0
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return 0

            task.retry_count += 1
            task.status = TaskStatus.RETRYING
            retry_count = task.retry_count

            # 构造快照用于锁外通知
            task_snapshot = TaskInfo(**task.__dict__)

        # 锁外通知观察者（避免死锁）
        if task_snapshot is not None:
            self._notify_observers(task_id, task_snapshot, TaskEventType.UPDATED)

        return retry_count

    def set_account(self, task_id: str, account_id: str) -> None:
        """设置任务使用的账号

        Args:
            task_id: 任务ID
            account_id: 账号ID
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task is not None:
                task.account_id = account_id

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息（副本）

        Args:
            task_id: 任务ID

        Returns:
            Optional[TaskInfo]: 任务信息的副本，如果不存在则返回None
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return None
            # 返回副本避免外部修改
            return TaskInfo(**task.__dict__)

    def get_all_tasks(self) -> List[TaskInfo]:
        """获取所有任务（副本列表）

        Returns:
            List[TaskInfo]: 所有任务的副本列表
        """
        with self._lock:
            return [TaskInfo(**task.__dict__) for task in self.tasks.values()]

    def get_tasks_by_status(self, status: TaskStatus) -> List[TaskInfo]:
        """根据状态筛选任务

        Args:
            status: 任务状态

        Returns:
            List[TaskInfo]: 符合条件的任务列表
        """
        with self._lock:
            return [
                TaskInfo(**task.__dict__)
                for task in self.tasks.values()
                if task.status == status
            ]

    def delete_task(self, task_id: str) -> bool:
        """删除任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功删除
        """
        task_snapshot = None
        with self._lock:
            if task_id not in self.tasks:
                return False

            # 保存任务信息副本（用于锁外通知观察者）
            task_snapshot = TaskInfo(**self.tasks[task_id].__dict__)
            del self.tasks[task_id]

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
            List[TaskInfo]: 待处理任务列表
        """
        with self._lock:
            return [
                TaskInfo(**task.__dict__)
                for task in self.tasks.values()
                if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING)
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
