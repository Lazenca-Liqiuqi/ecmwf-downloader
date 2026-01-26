"""
下载Worker单元测试

测试DownloadWorker的核心逻辑，不需要实际CDS API连接。
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch

# Mock掉cdsapi依赖
sys.modules['cdsapi'] = MagicMock()

from src.core.progress import TaskStatus, TaskInfo
from src.ui.workers.download_worker import DownloadWorker


class TestDownloadWorker(unittest.TestCase):
    """DownloadWorker单元测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_app = Mock()
        self.mock_app.progress_manager = Mock()
        self.mock_app.account_pool = Mock()
        self.mock_app.call_from_thread = Mock()
        self.mock_app.notify = Mock()

        self.worker = DownloadWorker(self.mock_app)

    def test_worker_init(self):
        """测试Worker初始化"""
        self.assertEqual(self.worker.app, self.mock_app)

    def test_get_account_success(self):
        """测试获取账号成功"""
        # 模拟账号
        mock_account = Mock()
        mock_account.account_id = "account-001"

        self.mock_app.account_pool.get_next_account.return_value = mock_account

        account = self.worker._get_account()

        self.assertEqual(account, mock_account)
        self.mock_app.account_pool.get_next_account.assert_called_once()

    def test_get_account_no_account(self):
        """测试无可用账号"""
        from src.core.exceptions import AccountPoolError

        self.mock_app.account_pool.get_next_account.side_effect = (
            AccountPoolError("No account available")
        )

        account = self.worker._get_account()

        self.assertIsNone(account)

    def test_safe_notify(self):
        """测试安全通知"""
        self.worker._safe_notify("测试消息", severity="success")

        # 验证call_from_thread被调用
        self.mock_app.call_from_thread.assert_called_once()
        args = self.mock_app.call_from_thread.call_args[0]
        self.assertEqual(args[0], self.mock_app.notify)
        self.assertEqual(args[1], "测试消息")

    def test_handle_download_error_with_retry(self):
        """测试错误处理-可以重试"""
        sample_task = TaskInfo(
            task_id="test-task-001",
            filename="test-data.nc",
            status=TaskStatus.FAILED,
            retry_count=1,
            metadata={"max_retries": 3},
        )

        self.mock_app.progress_manager.get_task.return_value = sample_task
        self.mock_app.progress_manager.increment_retry.return_value = 2

        self.worker._handle_download_error("test-task-001", "连接超时")

        # 验证状态更新为RETRYING
        self.mock_app.progress_manager.update_status.assert_called_with(
            "test-task-001", TaskStatus.RETRYING
        )

    def test_handle_download_error_max_retries(self):
        """测试错误处理-达到最大重试次数"""
        sample_task = TaskInfo(
            task_id="test-task-001",
            filename="test-data.nc",
            status=TaskStatus.FAILED,
            retry_count=3,  # 已达到最大重试次数
            metadata={"max_retries": 3},
        )

        self.mock_app.progress_manager.get_task.return_value = sample_task

        self.worker._handle_download_error("test-task-001", "连接超时")

        # 验证状态更新为FAILED
        self.mock_app.progress_manager.update_status.assert_called_with(
            "test-task-001", TaskStatus.FAILED, "连接超时"
        )


if __name__ == "__main__":
    unittest.main()
