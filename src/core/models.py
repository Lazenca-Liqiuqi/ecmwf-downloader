"""
任务数据模型模块

定义任务状态、事件类型和任务信息等核心数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class TaskStatus(str, Enum):
    """任务状态枚举

    状态流转：
    PENDING → QUEUED → DOWNLOADING → COMPLETED/FAILED/CANCELLED
                      ↘ RETRYING ↗

    状态分类：
    - 非持久状态（需在启动时重置为 PENDING）：QUEUED, DOWNLOADING, RETRYING
    - 持久状态（加载后保持不变）：PENDING, COMPLETED, FAILED, CANCELLED
    """

    PENDING = "pending"  # 待下载（初始状态）
    QUEUED = "queued"  # 已入队（等待调度）
    DOWNLOADING = "downloading"  # 下载中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消
    RETRYING = "retrying"  # 重试中

    @classmethod
    def get_transient_statuses(cls) -> set:
        """获取非持久状态集合

        这些状态在应用崩溃后需要重置为 PENDING。

        Returns:
            set: 非持久状态集合
        """
        return {cls.QUEUED, cls.DOWNLOADING, cls.RETRYING}

    @classmethod
    def get_terminal_statuses(cls) -> set:
        """获取终态集合

        终态任务不能再转换到其他状态。只有 COMPLETED 是真正的终态。
        FAILED 和 CANCELLED 可以重试（转换到 PENDING）。

        Returns:
            set: 终态集合
        """
        return {cls.COMPLETED}

    @classmethod
    def get_finalizable_statuses(cls) -> set:
        """获取可终态化状态集合

        这些状态表示任务已结束（成功、失败或取消），但失败和取消可以重新入队。

        Returns:
            set: 可终态化状态集合
        """
        return {cls.COMPLETED, cls.FAILED, cls.CANCELLED}


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
