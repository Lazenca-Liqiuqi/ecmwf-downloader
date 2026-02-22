"""
ECMWF下载器进度管理单元测试

测试进度管理器的线程安全操作、状态管理和持久化功能。
"""

import json
import tempfile
import threading
import time
from pathlib import Path
from typing import List
from datetime import datetime

import pytest

from src.core.progress import TaskStatus, TaskInfo, ProgressManager
from src.core.models import TaskEventType
from src.core.exceptions import ProgressLoadError, ProgressSaveError


@pytest.fixture
def temp_progress_file(tmp_path):
    """创建临时进度文件"""
    return tmp_path / "progress.json"


@pytest.fixture
def sample_progress_file(tmp_path):
    """创建包含示例数据的进度文件"""
    data = {
        "tasks": [
            {
                "task_id": "task_001",
                "filename": "data_2023_01.nc",
                "status": "completed",
                "progress": 100.0,
                "error_message": None,
                "retry_count": 0,
                "created_at": "2024-01-25T10:00:00",
                "started_at": "2024-01-25T10:00:05",
                "completed_at": "2024-01-25T10:05:30",
                "file_size": 1048576,
                "downloaded_size": 1048576,
                "account_id": "account_1",
                "metadata": {"year": 2023, "month": 1}
            },
            {
                "task_id": "task_002",
                "filename": "data_2023_02.nc",
                "status": "downloading",
                "progress": 45.5,
                "error_message": None,
                "retry_count": 1,
                "created_at": "2024-01-25T11:00:00",
                "started_at": "2024-01-25T11:00:05",
                "completed_at": None,
                "file_size": None,
                "downloaded_size": 524288,
                "account_id": "account_2",
                "metadata": {"year": 2023, "month": 2}
            },
            {
                "task_id": "task_003",
                "filename": "data_2023_03.nc",
                "status": "failed",
                "progress": 0.0,
                "error_message": "Connection timeout",
                "retry_count": 3,
                "created_at": "2024-01-25T12:00:00",
                "started_at": "2024-01-25T12:00:05",
                "completed_at": "2024-01-25T12:10:00",
                "file_size": None,
                "downloaded_size": 0,
                "account_id": None,
                "metadata": {"year": 2023, "month": 3}
            }
        ],
        "updated_at": "2024-01-25T12:10:00"
    }

    file_path = tmp_path / "sample_progress.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    return file_path


class TestTaskStatus:
    """测试TaskStatus枚举"""

    def test_status_values(self):
        """测试状态枚举值"""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.DOWNLOADING == "downloading"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
        assert TaskStatus.RETRYING == "retrying"


class TestTaskInfo:
    """测试TaskInfo数据类"""

    def test_create_task_info(self):
        """测试创建任务信息"""
        task = TaskInfo(
            task_id="task_001",
            filename="data.nc",
            status=TaskStatus.PENDING
        )

        assert task.task_id == "task_001"
        assert task.filename == "data.nc"
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0
        assert task.error_message is None
        assert task.retry_count == 0
        assert task.created_at is not None

    def test_to_dict(self):
        """测试转换为字典"""
        task = TaskInfo(
            task_id="task_001",
            filename="data.nc",
            status=TaskStatus.DOWNLOADING,
            progress=50.0,
            metadata={"key": "value"}
        )

        data = task.to_dict()

        assert data["task_id"] == "task_001"
        assert data["status"] == "downloading"
        assert data["progress"] == 50.0
        assert data["metadata"] == {"key": "value"}

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "task_id": "task_001",
            "filename": "data.nc",
            "status": "completed",
            "progress": 100.0,
            "error_message": None,
            "retry_count": 0,
            "created_at": "2024-01-25T10:00:00",
            "started_at": "2024-01-25T10:00:05",
            "completed_at": "2024-01-25T10:05:00",
            "file_size": 1024000,
            "downloaded_size": 1024000,
            "account_id": "account_1",
            "metadata": {}
        }

        task = TaskInfo.from_dict(data)

        assert task.task_id == "task_001"
        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100.0


class TestProgressManagerInit:
    """测试ProgressManager初始化"""

    def test_init_without_file(self):
        """测试不使用文件初始化"""
        manager = ProgressManager(progress_file=None)

        assert manager.progress_file is None
        assert manager.get_task_count() == 0

    def test_init_with_new_file(self, temp_progress_file):
        """测试使用新文件初始化"""
        manager = ProgressManager(progress_file=temp_progress_file)

        assert manager.progress_file == temp_progress_file
        assert manager.get_task_count() == 0
        assert not temp_progress_file.exists()

    def test_init_with_existing_file(self, sample_progress_file):
        """测试使用现有文件初始化并加载"""
        manager = ProgressManager(progress_file=sample_progress_file)

        assert manager.get_task_count() == 3
        assert manager.get_task("task_001") is not None


class TestProgressManagerCreateTask:
    """测试创建任务"""

    def test_create_task(self, temp_progress_file):
        """测试创建新任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        task = manager.create_task(
            task_id="task_new",
            filename="new_data.nc",
            metadata={"year": 2024}
        )

        assert task.task_id == "task_new"
        assert task.status == TaskStatus.PENDING
        assert task.filename == "new_data.nc"
        assert manager.get_task_count() == 1

    def test_create_task_with_observer(self, temp_progress_file):
        """测试创建任务时通知观察者"""
        manager = ProgressManager(progress_file=temp_progress_file)

        notified = []

        def observer(task_id, task_info, event_type):
            notified.append((task_id, task_info.status, event_type))

        manager.register_observer(observer)

        manager.create_task(task_id="task_new", filename="data.nc")

        assert len(notified) == 1
        assert notified[0][0] == "task_new"
        assert notified[0][1] == TaskStatus.PENDING
        assert notified[0][2] == TaskEventType.CREATED


class TestProgressManagerUpdateStatus:
    """测试更新任务状态"""

    def test_update_status_to_downloading(self, temp_progress_file):
        """测试更新状态为下载中"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        manager.update_status("task_001", TaskStatus.DOWNLOADING)

        task = manager.get_task("task_001")
        assert task.status == TaskStatus.DOWNLOADING
        assert task.started_at is not None

    def test_update_status_to_completed(self, temp_progress_file):
        """测试更新状态为已完成"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")
        manager.update_status("task_001", TaskStatus.DOWNLOADING)

        manager.update_status("task_001", TaskStatus.COMPLETED)

        task = manager.get_task("task_001")
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_update_status_with_error_message(self, temp_progress_file):
        """测试更新状态时记录错误信息"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        manager.update_status(
            "task_001",
            TaskStatus.FAILED,
            error_message="Network error"
        )

        task = manager.get_task("task_001")
        assert task.status == TaskStatus.FAILED
        assert task.error_message == "Network error"

    def test_update_nonexistent_task_no_error(self, temp_progress_file):
        """测试更新不存在的任务不抛出异常"""
        manager = ProgressManager(progress_file=temp_progress_file)

        # 不应该抛出异常
        manager.update_status("nonexistent", TaskStatus.DOWNLOADING)


class TestProgressManagerTransition:
    """测试状态转换"""

    def test_transition_pending_to_queued(self, temp_progress_file):
        """测试 PENDING → QUEUED 合法转换"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        result = manager.transition("task_001", TaskStatus.QUEUED)

        assert result is True
        task = manager.get_task("task_001")
        assert task.status == TaskStatus.QUEUED

    def test_transition_queued_to_downloading(self, temp_progress_file):
        """测试 QUEUED → DOWNLOADING 合法转换"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")
        manager.transition("task_001", TaskStatus.QUEUED)

        result = manager.transition("task_001", TaskStatus.DOWNLOADING)

        assert result is True
        task = manager.get_task("task_001")
        assert task.status == TaskStatus.DOWNLOADING
        assert task.started_at is not None

    def test_transition_downloading_to_completed(self, temp_progress_file):
        """测试 DOWNLOADING → COMPLETED 合法转换"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")
        manager.transition("task_001", TaskStatus.QUEUED)
        manager.transition("task_001", TaskStatus.DOWNLOADING)

        result = manager.transition("task_001", TaskStatus.COMPLETED)

        assert result is True
        task = manager.get_task("task_001")
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_transition_invalid_raises_error(self, temp_progress_file):
        """测试非法状态转换抛出异常"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        # PENDING → DOWNLOADING 是非法的（必须先 QUEUED）
        with pytest.raises(ValueError, match="非法状态转换"):
            manager.transition("task_001", TaskStatus.DOWNLOADING)

    def test_transition_from_terminal_fails(self, temp_progress_file):
        """测试从终态转换失败"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")
        manager.transition("task_001", TaskStatus.QUEUED)
        manager.transition("task_001", TaskStatus.DOWNLOADING)
        manager.transition("task_001", TaskStatus.COMPLETED)

        # COMPLETED 是终态，不能转换
        with pytest.raises(ValueError, match="非法状态转换"):
            manager.transition("task_001", TaskStatus.PENDING)

    def test_transition_nonexistent_task_returns_false(self, temp_progress_file):
        """测试转换不存在的任务返回 False"""
        manager = ProgressManager(progress_file=temp_progress_file)

        result = manager.transition("nonexistent", TaskStatus.QUEUED)

        assert result is False


class TestProgressManagerEnqueue:
    """测试入队操作"""

    def test_enqueue_pending_task(self, temp_progress_file):
        """测试入队 PENDING 任务"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        result = manager.enqueue("task_001")

        assert result is True
        task = manager.get_task("task_001")
        assert task.status == TaskStatus.QUEUED

    def test_enqueue_non_pending_raises_error(self, temp_progress_file):
        """测试入队非 PENDING 任务抛出异常"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")
        manager.transition("task_001", TaskStatus.QUEUED)

        # QUEUED 任务不能再入队
        with pytest.raises(ValueError, match="非法状态转换"):
            manager.enqueue("task_001")

    def test_enqueue_all_pending(self, temp_progress_file):
        """测试批量入队所有 PENDING 任务"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data1.nc")
        manager.create_task(task_id="task_002", filename="data2.nc")
        manager.create_task(task_id="task_003", filename="data3.nc")
        # 将 task_002 入队，剩下两个 PENDING
        manager.enqueue("task_002")

        count = manager.enqueue_all_pending()

        assert count == 2
        assert manager.get_task("task_001").status == TaskStatus.QUEUED
        assert manager.get_task("task_002").status == TaskStatus.QUEUED
        assert manager.get_task("task_003").status == TaskStatus.QUEUED

    def test_enqueue_notifies_observer(self, temp_progress_file):
        """测试入队时通知观察者"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        notified = []

        def observer(task_id, task_info, event_type):
            notified.append((task_id, task_info.status, event_type))

        manager.register_observer(observer)
        manager.enqueue("task_001")

        assert len(notified) == 1
        assert notified[0][0] == "task_001"
        assert notified[0][1] == TaskStatus.QUEUED


class TestProgressManagerReconcile:
    """测试加载时状态修复"""

    def test_reconcile_downloading_to_pending(self, tmp_path):
        """测试 DOWNLOADING 状态被修复为 PENDING"""
        # 创建包含 DOWNLOADING 状态的测试文件
        progress_file = tmp_path / "progress.json"
        data = {
            "tasks": [
                {
                    "task_id": "task_001",
                    "filename": "data.nc",
                    "status": "downloading",
                    "progress": 50.0,
                    "account_id": "account_1",
                    "retry_count": 0,
                    "created_at": "2024-01-25T10:00:00",
                    "started_at": "2024-01-25T10:00:05",
                    "completed_at": None,
                    "file_size": None,
                    "downloaded_size": 512,
                    "metadata": {},
                }
            ]
        }
        import json
        with open(progress_file, "w") as f:
            json.dump(data, f)

        manager = ProgressManager(progress_file=progress_file)

        task = manager.get_task("task_001")
        assert task.status == TaskStatus.PENDING
        assert task.progress == 50.0  # 进度保留
        assert task.account_id is None  # account_id 被清空

    def test_reconcile_queued_to_pending(self, tmp_path):
        """测试 QUEUED 状态被修复为 PENDING"""
        progress_file = tmp_path / "progress.json"
        data = {
            "tasks": [
                {
                    "task_id": "task_001",
                    "filename": "data.nc",
                    "status": "queued",
                    "progress": 0.0,
                    "account_id": None,
                    "retry_count": 0,
                    "created_at": "2024-01-25T10:00:00",
                    "started_at": None,
                    "completed_at": None,
                    "file_size": None,
                    "downloaded_size": 0,
                    "metadata": {},
                }
            ]
        }
        import json
        with open(progress_file, "w") as f:
            json.dump(data, f)

        manager = ProgressManager(progress_file=progress_file)

        task = manager.get_task("task_001")
        assert task.status == TaskStatus.PENDING

    def test_reconcile_preserves_terminal_states(self, tmp_path):
        """测试终态任务不被修复"""
        progress_file = tmp_path / "progress.json"
        data = {
            "tasks": [
                {
                    "task_id": "task_001",
                    "filename": "data.nc",
                    "status": "completed",
                    "progress": 100.0,
                    "account_id": "account_1",
                    "retry_count": 0,
                    "created_at": "2024-01-25T10:00:00",
                    "started_at": "2024-01-25T10:00:05",
                    "completed_at": "2024-01-25T10:05:00",
                    "file_size": 1024,
                    "downloaded_size": 1024,
                    "metadata": {},
                },
                {
                    "task_id": "task_002",
                    "filename": "data2.nc",
                    "status": "failed",
                    "progress": 30.0,
                    "error_message": "Timeout",
                    "account_id": None,
                    "retry_count": 3,
                    "created_at": "2024-01-25T10:00:00",
                    "started_at": "2024-01-25T10:00:05",
                    "completed_at": "2024-01-25T10:05:00",
                    "file_size": None,
                    "downloaded_size": 300,
                    "metadata": {},
                },
            ]
        }
        import json
        with open(progress_file, "w") as f:
            json.dump(data, f)

        manager = ProgressManager(progress_file=progress_file)

        # COMPLETED 和 FAILED 状态保持不变
        assert manager.get_task("task_001").status == TaskStatus.COMPLETED
        assert manager.get_task("task_001").account_id == "account_1"
        assert manager.get_task("task_002").status == TaskStatus.FAILED

    def test_reconcile_clears_started_at(self, tmp_path):
        """测试 reconcile 清空 started_at"""
        progress_file = tmp_path / "progress.json"
        data = {
            "tasks": [
                {
                    "task_id": "task_001",
                    "filename": "data.nc",
                    "status": "downloading",
                    "progress": 50.0,
                    "account_id": "account_1",
                    "retry_count": 0,
                    "created_at": "2024-01-25T10:00:00",
                    "started_at": "2024-01-25T10:00:05",
                    "completed_at": None,
                    "file_size": None,
                    "downloaded_size": 512,
                    "metadata": {},
                }
            ]
        }
        import json
        with open(progress_file, "w") as f:
            json.dump(data, f)

        manager = ProgressManager(progress_file=progress_file)

        task = manager.get_task("task_001")
        assert task.status == TaskStatus.PENDING
        assert task.started_at is None  # started_at 被清空

    def test_reconcile_retrying_to_pending(self, tmp_path):
        """测试 RETRYING 状态被修复为 PENDING"""
        progress_file = tmp_path / "progress.json"
        data = {
            "tasks": [
                {
                    "task_id": "task_001",
                    "filename": "data.nc",
                    "status": "retrying",
                    "progress": 30.0,
                    "account_id": "account_1",
                    "retry_count": 2,
                    "created_at": "2024-01-25T10:00:00",
                    "started_at": "2024-01-25T10:00:05",
                    "completed_at": None,
                    "file_size": None,
                    "downloaded_size": 300,
                    "metadata": {},
                }
            ]
        }
        import json
        with open(progress_file, "w") as f:
            json.dump(data, f)

        manager = ProgressManager(progress_file=progress_file)

        task = manager.get_task("task_001")
        assert task.status == TaskStatus.PENDING
        assert task.account_id is None
        assert task.started_at is None
        assert task.retry_count == 2  # retry_count 保留

    def test_transition_failed_to_pending_clears_fields(self, temp_progress_file):
        """测试 FAILED → PENDING 清空终态相关字段"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")
        manager.transition("task_001", TaskStatus.QUEUED)
        manager.transition("task_001", TaskStatus.DOWNLOADING)
        manager.transition("task_001", TaskStatus.FAILED, "Connection timeout")

        # 验证终态字段已设置
        task = manager.get_task("task_001")
        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None
        assert task.error_message == "Connection timeout"

        # 重新入队
        manager.transition("task_001", TaskStatus.PENDING)

        task = manager.get_task("task_001")
        assert task.status == TaskStatus.PENDING
        assert task.completed_at is None  # 被清空
        assert task.started_at is None  # 被清空
        assert task.error_message is None  # 被清空

    def test_transition_cancelled_to_pending_clears_fields(self, temp_progress_file):
        """测试 CANCELLED → PENDING 清空终态相关字段"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")
        manager.transition("task_001", TaskStatus.QUEUED)
        manager.transition("task_001", TaskStatus.CANCELLED)

        # 验证终态字段已设置
        task = manager.get_task("task_001")
        assert task.status == TaskStatus.CANCELLED
        assert task.completed_at is not None

        # 重新入队
        manager.transition("task_001", TaskStatus.PENDING)

        task = manager.get_task("task_001")
        assert task.status == TaskStatus.PENDING
        assert task.completed_at is None  # 被清空
        assert task.started_at is None  # 被清空


class TestProgressManagerUpdateProgress:
    """测试更新任务进度"""

    def test_update_progress(self, temp_progress_file):
        """测试更新进度"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        manager.update_progress("task_001", 50.0)

        task = manager.get_task("task_001")
        assert task.progress == 50.0

    def test_update_progress_clamped(self, temp_progress_file):
        """测试进度值被限制在0-100范围内"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        manager.update_progress("task_001", -10.0)
        task = manager.get_task("task_001")
        assert task.progress == 0.0

        manager.update_progress("task_001", 150.0)
        task = manager.get_task("task_001")
        assert task.progress == 100.0

    def test_update_progress_with_downloaded_size(self, temp_progress_file):
        """测试更新进度时包含已下载大小"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        manager.update_progress("task_001", 25.0, downloaded_size=256000)

        task = manager.get_task("task_001")
        assert task.progress == 25.0
        assert task.downloaded_size == 256000


class TestProgressManagerRetry:
    """测试重试操作"""

    def test_increment_retry(self, temp_progress_file):
        """测试增加重试计数"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        count = manager.increment_retry("task_001")

        assert count == 1

        task = manager.get_task("task_001")
        assert task.retry_count == 1
        assert task.status == TaskStatus.RETRYING

    def test_increment_retry_multiple(self, temp_progress_file):
        """测试多次增加重试计数"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        manager.increment_retry("task_001")
        manager.increment_retry("task_001")
        manager.increment_retry("task_001")

        task = manager.get_task("task_001")
        assert task.retry_count == 3


class TestProgressManagerAccount:
    """测试账号关联"""

    def test_set_account(self, temp_progress_file):
        """测试设置任务使用的账号"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        manager.set_account("task_001", "account_1")

        task = manager.get_task("task_001")
        assert task.account_id == "account_1"


class TestProgressManagerQuery:
    """测试查询操作"""

    def test_get_task(self, temp_progress_file):
        """测试获取单个任务"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(
            task_id="task_001",
            filename="data.nc",
            metadata={"key": "value"}
        )

        task = manager.get_task("task_001")

        assert task is not None
        assert task.task_id == "task_001"
        assert task.metadata == {"key": "value"}

    def test_get_task_returns_copy(self, temp_progress_file):
        """测试获取任务返回副本"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        task = manager.get_task("task_001")
        task.progress = 99.0

        # 原始任务不应改变
        original = manager.get_task("task_001")
        assert original.progress == 0.0

    def test_get_task_nonexistent(self, temp_progress_file):
        """测试获取不存在的任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        task = manager.get_task("nonexistent")
        assert task is None

    def test_get_all_tasks(self, temp_progress_file):
        """测试获取所有任务"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data1.nc")
        manager.create_task(task_id="task_002", filename="data2.nc")
        manager.create_task(task_id="task_003", filename="data3.nc")

        tasks = manager.get_all_tasks()

        assert len(tasks) == 3
        assert [t.task_id for t in tasks] == ["task_001", "task_002", "task_003"]

    def test_get_tasks_by_status(self, temp_progress_file):
        """测试按状态筛选任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        manager.create_task(task_id="task_001", filename="data1.nc")
        t2 = manager.create_task(task_id="task_002", filename="data2.nc")
        manager.update_status("task_002", TaskStatus.DOWNLOADING)
        manager.create_task(task_id="task_003", filename="data3.nc")

        pending_tasks = manager.get_tasks_by_status(TaskStatus.PENDING)
        downloading_tasks = manager.get_tasks_by_status(TaskStatus.DOWNLOADING)

        assert len(pending_tasks) == 2
        assert len(downloading_tasks) == 1
        assert downloading_tasks[0].task_id == "task_002"

    def test_get_pending_tasks(self, temp_progress_file):
        """测试获取待处理任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        manager.create_task(task_id="task_001", filename="data1.nc")
        manager.create_task(task_id="task_002", filename="data2.nc")
        manager.update_status("task_002", TaskStatus.DOWNLOADING)
        t3 = manager.create_task(task_id="task_003", filename="data3.nc")
        manager.update_status("task_003", TaskStatus.RETRYING)

        pending = manager.get_pending_tasks()

        assert len(pending) == 2  # PENDING和RETRYING
        assert {t.task_id for t in pending} == {"task_001", "task_003"}

    def test_get_active_tasks(self, temp_progress_file):
        """测试获取活动任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        manager.create_task(task_id="task_001", filename="data1.nc")
        manager.create_task(task_id="task_002", filename="data2.nc")
        manager.update_status("task_002", TaskStatus.DOWNLOADING)

        active = manager.get_active_tasks()

        assert len(active) == 1
        assert active[0].task_id == "task_002"

    def test_has_pending_tasks(self, temp_progress_file):
        """测试检查是否有待处理任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        assert not manager.has_pending_tasks()

        manager.create_task(task_id="task_001", filename="data.nc")
        assert manager.has_pending_tasks()

    def test_get_summary(self, temp_progress_file):
        """测试获取摘要统计"""
        manager = ProgressManager(progress_file=temp_progress_file)

        manager.create_task(task_id="task_001", filename="data1.nc")
        manager.create_task(task_id="task_002", filename="data2.nc")
        manager.update_status("task_002", TaskStatus.DOWNLOADING)
        manager.update_progress("task_002", 50.0)  # 设置进度
        manager.create_task(task_id="task_003", filename="data3.nc")
        manager.update_status("task_003", TaskStatus.COMPLETED)
        manager.update_progress("task_003", 100.0)  # 设置进度

        summary = manager.get_summary()

        assert summary["total_tasks"] == 3
        assert summary["pending"] == 1
        assert summary["downloading"] == 1
        assert summary["completed"] == 1
        # overall_progress = (0.0 + 50.0 + 100.0) / 3 = 50.0
        assert summary["overall_progress"] > 0


class TestProgressManagerDelete:
    """测试删除操作"""

    def test_delete_task(self, temp_progress_file):
        """测试删除任务"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")
        manager.create_task(task_id="task_002", filename="data2.nc")

        result = manager.delete_task("task_001")

        assert result is True
        assert manager.get_task_count() == 1
        assert manager.get_task("task_001") is None

    def test_delete_nonexistent_task(self, temp_progress_file):
        """测试删除不存在的任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        result = manager.delete_task("nonexistent")

        assert result is False

    def test_clear_completed(self, temp_progress_file):
        """测试清除已完成任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        manager.create_task(task_id="task_001", filename="data1.nc")
        manager.update_status("task_001", TaskStatus.COMPLETED)
        manager.create_task(task_id="task_002", filename="data2.nc")
        manager.create_task(task_id="task_003", filename="data3.nc")
        manager.update_status("task_003", TaskStatus.COMPLETED)

        count = manager.clear_completed()

        assert count == 2
        assert manager.get_task_count() == 1
        assert manager.get_task("task_002") is not None

    def test_clear_all(self, temp_progress_file):
        """测试清除所有任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        manager.create_task(task_id="task_001", filename="data1.nc")
        manager.create_task(task_id="task_002", filename="data2.nc")

        manager.clear_all()

        assert manager.get_task_count() == 0


class TestProgressManagerPersistence:
    """测试持久化功能"""

    def test_save_to_file(self, temp_progress_file):
        """测试保存到文件"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(
            task_id="task_001",
            filename="data.nc",
            metadata={"year": 2023}
        )

        manager.save()

        assert temp_progress_file.exists()

        # 验证文件内容
        with open(temp_progress_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_id"] == "task_001"
        assert "updated_at" in data

    def test_load_from_file(self, sample_progress_file):
        """测试从文件加载（非持久状态会被 reconcile）"""
        manager = ProgressManager(progress_file=sample_progress_file)

        assert manager.get_task_count() == 3

        # 终态任务保持不变
        task_001 = manager.get_task("task_001")
        assert task_001.status == TaskStatus.COMPLETED
        assert task_001.progress == 100.0

        # DOWNLOADING 状态被 reconcile 为 PENDING
        task_002 = manager.get_task("task_002")
        assert task_002.status == TaskStatus.PENDING
        assert task_002.progress == 45.5  # 进度保留
        assert task_002.account_id is None  # account_id 被清空

        # FAILED 状态是终态，保持不变
        task_003 = manager.get_task("task_003")
        assert task_003.status == TaskStatus.FAILED

    def test_save_without_file_no_error(self):
        """测试不指定文件时保存不抛出异常"""
        manager = ProgressManager(progress_file=None)
        manager.create_task(task_id="task_001", filename="data.nc")

        # 不应该抛出异常
        manager.save()


class TestProgressManagerObservers:
    """测试观察者模式"""

    def test_register_observer(self, temp_progress_file):
        """测试注册观察者"""
        manager = ProgressManager(progress_file=temp_progress_file)

        notified = []

        def observer(task_id, task_info, event_type):
            notified.append((task_id, task_info.status, event_type))

        manager.register_observer(observer)

        manager.create_task(task_id="task_001", filename="data.nc")
        manager.update_status("task_001", TaskStatus.DOWNLOADING)
        manager.update_progress("task_001", 50.0)

        assert len(notified) == 3

    def test_unregister_observer(self, temp_progress_file):
        """测试取消注册观察者"""
        manager = ProgressManager(progress_file=temp_progress_file)

        notified = []

        def observer(task_id, task_info, event_type):
            notified.append(task_id)

        manager.register_observer(observer)
        manager.unregister_observer(observer)

        manager.create_task(task_id="task_001", filename="data.nc")

        assert len(notified) == 0

    def test_observer_exception_doesnt_affect_manager(self, temp_progress_file):
        """测试观察者异常不影响进度管理器"""
        manager = ProgressManager(progress_file=temp_progress_file)

        def failing_observer(task_id, task_info):
            raise RuntimeError("Observer error")

        def working_observer(task_id, task_info):
            pass

        manager.register_observer(failing_observer)
        manager.register_observer(working_observer)

        # 不应该抛出异常
        manager.create_task(task_id="task_001", filename="data.nc")
        manager.update_status("task_001", TaskStatus.DOWNLOADING)


class TestProgressManagerThreadSafety:
    """测试线程安全"""

    def test_concurrent_task_updates(self, temp_progress_file):
        """测试多线程并发更新任务"""
        manager = ProgressManager(progress_file=temp_progress_file)
        manager.create_task(task_id="task_001", filename="data.nc")

        num_threads = 10
        num_iterations = 100

        def update_progress():
            for i in range(num_iterations):
                progress = (i / num_iterations) * 100
                manager.update_progress("task_001", progress)

        threads = [
            threading.Thread(target=update_progress)
            for _ in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 操作应该成功，没有数据竞争
        task = manager.get_task("task_001")
        assert task is not None

    def test_concurrent_task_creation(self, temp_progress_file):
        """测试多线程并发创建任务"""
        manager = ProgressManager(progress_file=temp_progress_file)

        num_threads = 10
        num_tasks = 10

        def create_tasks():
            for i in range(num_tasks):
                task_id = f"task_{threading.get_ident()}_{i}"
                manager.create_task(task_id=task_id, filename=f"data_{i}.nc")

        threads = [
            threading.Thread(target=create_tasks)
            for _ in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有任务都应该创建成功
        assert manager.get_task_count() == num_threads * num_tasks
