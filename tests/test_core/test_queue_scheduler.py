"""
DownloadQueueScheduler 单元测试
"""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.config import AccountInfo, AccountStatus
from src.core.progress import ProgressManager, TaskStatus
from src.core.queue_scheduler import DownloadQueueScheduler


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """创建临时数据目录"""
    return tmp_path / "data"


@pytest.fixture
def progress_manager(temp_data_dir: Path) -> ProgressManager:
    """创建进度管理器"""
    return ProgressManager(data_dir=temp_data_dir)


@pytest.fixture
def mock_account_pool():
    """创建模拟账号池"""
    pool = MagicMock()
    pool.get_next_account.return_value = AccountInfo(
        id="test-account-1",
        email="test@example.com",
        key="test-key",
        url="https://test.url",
        status=AccountStatus.ACTIVE,
    )
    return pool


@pytest.fixture
def mock_start_callback():
    """创建模拟启动回调"""
    return MagicMock()


class TestDownloadQueueSchedulerInit:
    """测试调度器初始化"""

    def test_init_default_params(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试默认参数初始化"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
        )

        assert scheduler.max_workers == 3
        assert scheduler.poll_interval == 1.0
        assert scheduler.active_count == 0
        assert not scheduler.is_running

    def test_init_custom_params(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试自定义参数初始化"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
            max_workers=5,
            poll_interval=0.5,
        )

        assert scheduler.max_workers == 5
        assert scheduler.poll_interval == 0.5


class TestDownloadQueueSchedulerLifecycle:
    """测试调度器生命周期"""

    def test_start_and_stop(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试启动和停止"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
            poll_interval=0.1,
        )

        assert not scheduler.is_running

        scheduler.start()
        assert scheduler.is_running

        scheduler.stop()
        assert not scheduler.is_running

    def test_double_start_no_error(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试重复启动不会报错"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
        )

        scheduler.start()
        scheduler.start()  # 重复启动
        assert scheduler.is_running

        scheduler.stop()

    def test_double_stop_no_error(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试重复停止不会报错"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
        )

        scheduler.stop()  # 未启动就停止
        scheduler.stop()  # 重复停止


class TestDownloadQueueSchedulerQueue:
    """测试调度器队列处理"""

    def test_process_queued_task(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试处理 QUEUED 任务"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
            poll_interval=0.1,
        )

        # 创建任务并入队
        task = progress_manager.create_task(
            task_id="test-task-1",
            filename="test.grib",
        )
        progress_manager.enqueue("test-task-1")

        # 启动调度器
        scheduler.start()

        # 等待调度器处理
        time.sleep(0.3)

        # 验证回调被调用
        mock_start_callback.assert_called_once()
        call_args = mock_start_callback.call_args
        assert call_args[0][0] == "test-task-1"

        # 验证任务状态变为 DOWNLOADING
        updated_task = progress_manager.get_task("test-task-1")
        assert updated_task.status == TaskStatus.DOWNLOADING

        scheduler.stop()

    def test_respect_max_workers(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试并发限制"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
            max_workers=2,
            poll_interval=0.1,
        )

        # 创建 4 个任务并入队
        for i in range(4):
            progress_manager.create_task(
                task_id=f"test-task-{i}",
                filename=f"test{i}.grib",
            )
            progress_manager.enqueue(f"test-task-{i}")

        # 启动调度器
        scheduler.start()

        # 等待调度器处理
        time.sleep(0.3)

        # 验证只启动了 max_workers 个任务
        assert mock_start_callback.call_count == 2
        assert scheduler.active_count == 2

        scheduler.stop()

    def test_no_account_available(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试无可用账号时跳过任务"""
        # 模拟账号池抛出异常
        mock_account_pool.get_next_account.side_effect = Exception("No account")

        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
            poll_interval=0.1,
        )

        # 创建任务并入队
        progress_manager.create_task(
            task_id="test-task-1",
            filename="test.grib",
        )
        progress_manager.enqueue("test-task-1")

        # 启动调度器
        scheduler.start()

        # 等待调度器处理
        time.sleep(0.3)

        # 验证回调未被调用
        mock_start_callback.assert_not_called()

        # 任务状态保持 QUEUED
        task = progress_manager.get_task("test-task-1")
        assert task.status == TaskStatus.QUEUED

        scheduler.stop()


class TestDownloadQueueSchedulerCallbacks:
    """测试调度器回调"""

    def test_on_task_completed(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试任务完成回调"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
        )

        # 模拟活动任务
        scheduler._active_tasks.add("test-task-1")
        assert scheduler.active_count == 1

        # 调用完成回调
        scheduler.on_task_completed("test-task-1")
        assert scheduler.active_count == 0

    def test_on_task_completed_nonexistent(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试完成不存在的任务"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
        )

        # 完成一个不存在的任务（不应该报错）
        scheduler.on_task_completed("nonexistent-task")
        assert scheduler.active_count == 0


class TestDownloadQueueSchedulerEnqueueAll:
    """测试批量入队"""

    def test_enqueue_all_pending(
        self,
        progress_manager: ProgressManager,
        mock_account_pool,
        mock_start_callback,
    ):
        """测试批量入队所有 PENDING 任务"""
        scheduler = DownloadQueueScheduler(
            progress_manager=progress_manager,
            account_pool=mock_account_pool,
            start_download_callback=mock_start_callback,
        )

        # 创建多个任务
        for i in range(3):
            progress_manager.create_task(
                task_id=f"test-task-{i}",
                filename=f"test{i}.grib",
            )

        # 批量入队
        count = scheduler.enqueue_all_pending()
        assert count == 3

        # 验证所有任务都是 QUEUED 状态
        for i in range(3):
            task = progress_manager.get_task(f"test-task-{i}")
            assert task.status == TaskStatus.QUEUED
