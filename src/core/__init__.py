"""
ECMWF Downloader 核心模块

提供配置管理、进度跟踪、请求构建和任务服务等核心功能。
"""

from src.core.account_pool import AccountInfo, AccountPoolConfig, AccountStatus
from src.core.config import (
    AppConfig,
    ConcurrencyConfig,
    DatasetType,
    DownloadConfig,
    LoggingConfig,
    ProgressConfig,
)
from src.core.exceptions import (
    AccountPoolError,
    APIError,
    ConfigurationError,
    DownloadError,
    ProgressLoadError,
    ProgressSaveError,
    TaskValidationError,
)
from src.core.models import TaskEventType, TaskInfo, TaskStatus
from src.core.progress import ProgressManager
from src.core.progress_store import MultiFileTaskStore, SingleFileTaskStore, TaskStore
from src.core.request_builder import DownloadRequest, RequestBuilder
from src.core.task_service import TaskService

__all__ = [
    # 配置类
    "AppConfig",
    "ConcurrencyConfig",
    "DatasetType",
    "DownloadConfig",
    "LoggingConfig",
    "ProgressConfig",
    # 账号管理
    "AccountInfo",
    "AccountPoolConfig",
    "AccountStatus",
    # 异常类
    "DownloadError",
    "APIError",
    "AccountPoolError",
    "ProgressLoadError",
    "ProgressSaveError",
    "ConfigurationError",
    "TaskValidationError",
    # 数据模型
    "TaskInfo",
    "TaskStatus",
    "TaskEventType",
    # 进度管理
    "ProgressManager",
    # 存储层
    "TaskStore",
    "SingleFileTaskStore",
    "MultiFileTaskStore",
    # 请求构建
    "DownloadRequest",
    "RequestBuilder",
    # 任务服务
    "TaskService",
]
