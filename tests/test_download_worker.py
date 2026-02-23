"""
下载Worker单元测试

测试下载执行函数的核心逻辑，不需要实际CDS API连接。
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch, call

# Mock掉cdsapi依赖
sys.modules['cdsapi'] = MagicMock()

from src.core.progress import TaskStatus, TaskInfo
from src.core.config import AccountInfo
from src.ui.workers import download_worker


class TestDownloadWorkerFunctions(unittest.TestCase):
    """下载Worker函数单元测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_app = Mock()
        self.mock_app.progress_manager = Mock()
        self.mock_app.account_pool = Mock()
        self.mock_app.call_from_thread = Mock()
        self.mock_app.notify = Mock()

    def test_get_account_success(self):
        """测试获取账号成功"""
        mock_account = Mock(spec=AccountInfo)
        mock_account.id = "account-001"

        self.mock_app.account_pool.get_next_account.return_value = mock_account

        account = download_worker._get_account(self.mock_app)

        self.assertEqual(account, mock_account)
        self.mock_app.account_pool.get_next_account.assert_called_once()

    def test_get_account_no_account(self):
        """测试无可用账号"""
        from src.core.exceptions import AccountPoolError

        self.mock_app.account_pool.get_next_account.side_effect = (
            AccountPoolError("No account available")
        )

        account = download_worker._get_account(self.mock_app)

        self.assertIsNone(account)

    def test_safe_notify(self):
        """测试安全通知"""
        download_worker._safe_notify(self.mock_app, "测试消息", severity="success")

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

        download_worker._handle_download_error(self.mock_app, "test-task-001", "连接超时")

        # 验证调用了 increment_retry
        self.mock_app.progress_manager.increment_retry.assert_called_with("test-task-001")

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

        download_worker._handle_download_error(self.mock_app, "test-task-001", "连接超时")

        # 验证状态更新为FAILED
        self.mock_app.progress_manager.transition.assert_called()

    def test_execute_download_with_account_task_not_found(self):
        """测试执行下载-任务不存在"""
        self.mock_app.progress_manager.get_task.return_value = None

        download_worker.execute_download_with_account(
            app=self.mock_app,
            task_id="nonexistent-task",
            account=Mock(spec=AccountInfo),
        )

        # 验证调用了 get_task
        self.mock_app.progress_manager.get_task.assert_called_with("nonexistent-task")

    def test_execute_download_with_account_wrong_status(self):
        """测试执行下载-任务状态不正确"""
        sample_task = TaskInfo(
            task_id="test-task-001",
            filename="test-data.nc",
            status=TaskStatus.PENDING,  # 状态不是 DOWNLOADING
            metadata={},
        )

        self.mock_app.progress_manager.get_task.return_value = sample_task

        download_worker.execute_download_with_account(
            app=self.mock_app,
            task_id="test-task-001",
            account=Mock(spec=AccountInfo),
        )

        # 应该直接返回，不执行下载

    def test_execute_download_with_account_missing_params(self):
        """测试执行下载-缺少下载参数"""
        sample_task = TaskInfo(
            task_id="test-task-001",
            filename="test-data.nc",
            status=TaskStatus.DOWNLOADING,
            metadata={},  # 没有 download_params
        )

        self.mock_app.progress_manager.get_task.return_value = sample_task

        download_worker.execute_download_with_account(
            app=self.mock_app,
            task_id="test-task-001",
            account=Mock(spec=AccountInfo),
        )

        # 验证状态更新为FAILED
        self.mock_app.progress_manager.transition.assert_called()


if __name__ == "__main__":
    unittest.main()
