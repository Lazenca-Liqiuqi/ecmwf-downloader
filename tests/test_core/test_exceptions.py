"""
ECMWF下载器异常类单元测试

测试所有自定义异常类的创建、属性和字符串表示。
"""

import pytest

from src.core.exceptions import (
    DownloadError,
    APIError,
    AccountPoolError,
    ProgressLoadError,
    ProgressSaveError,
    ConfigurationError,
    TaskValidationError,
)


class TestDownloadError:
    """测试DownloadError基类"""

    def test_create_with_message_only(self):
        """测试仅使用消息创建异常"""
        error = DownloadError("Test error message")
        assert error.message == "Test error message"
        assert error.details == {}
        assert str(error) == "Test error message"

    def test_create_with_details(self):
        """测试包含详细信息创建异常"""
        details = {"key": "value", "number": 123}
        error = DownloadError("Test error", details=details)
        assert error.message == "Test error"
        assert error.details == details


class TestAPIError:
    """测试APIError异常类"""

    def test_create_with_message_only(self):
        """测试仅使用消息创建API异常"""
        error = APIError("API failed")
        assert error.message == "API failed"
        assert error.status_code is None
        assert error.response_body is None

    def test_create_with_status_code(self):
        """测试包含HTTP状态码"""
        error = APIError("Unauthorized", status_code=401)
        assert error.status_code == 401
        assert error.details["status_code"] == 401

    def test_create_with_response_body(self):
        """测试包含响应体"""
        body = '{"error": "Invalid credentials"}'
        error = APIError("API failed", response_body=body)
        assert error.response_body == body
        assert error.details["response_body"] == body

    def test_create_with_all_fields(self):
        """测试包含所有字段"""
        error = APIError(
            message="Full error",
            status_code=403,
            response_body="Access denied"
        )
        assert error.message == "Full error"
        assert error.status_code == 403
        assert error.response_body == "Access denied"
        assert error.details == {
            "status_code": 403,
            "response_body": "Access denied"
        }


class TestAccountPoolError:
    """测试AccountPoolError异常类"""

    def test_create_with_message_only(self):
        """测试仅使用消息创建账号池异常"""
        error = AccountPoolError("No accounts available")
        assert error.message == "No accounts available"
        assert error.account_id is None
        assert error.available_count is None

    def test_create_with_account_id(self):
        """测试包含账号ID"""
        error = AccountPoolError("Account failed", account_id="account_1")
        assert error.account_id == "account_1"
        assert error.details["account_id"] == "account_1"

    def test_create_with_available_count(self):
        """测试包含可用账号数量"""
        error = AccountPoolError(
            "No accounts",
            available_count=0
        )
        assert error.available_count == 0
        assert error.details["available_count"] == 0

    def test_create_with_all_fields(self):
        """测试包含所有字段"""
        error = AccountPoolError(
            message="Account issue",
            account_id="account_2",
            available_count=2
        )
        assert error.message == "Account issue"
        assert error.account_id == "account_2"
        assert error.available_count == 2


class TestProgressLoadError:
    """测试ProgressLoadError异常类"""

    def test_create_with_message_only(self):
        """测试仅使用消息创建进度加载异常"""
        error = ProgressLoadError("Failed to load progress")
        assert error.message == "Failed to load progress"
        assert error.file_path is None
        assert error.original_error is None

    def test_create_with_file_path(self):
        """测试包含文件路径"""
        error = ProgressLoadError(
            "File not found",
            file_path="/path/to/progress.json"
        )
        assert error.file_path == "/path/to/progress.json"
        assert error.details["file_path"] == "/path/to/progress.json"

    def test_create_with_original_error(self):
        """测试包含原始异常"""
        original = ValueError("Invalid JSON")
        error = ProgressLoadError(
            "Parse error",
            original_error=original
        )
        assert error.original_error == original
        # details["original_error"]存储的是str(error)，即异常消息
        assert "Invalid JSON" in error.details["original_error"]


class TestProgressSaveError:
    """测试ProgressSaveError异常类"""

    def test_create_with_message_only(self):
        """测试仅使用消息创建进度保存异常"""
        error = ProgressSaveError("Failed to save progress")
        assert error.message == "Failed to save progress"
        assert error.file_path is None
        assert error.original_error is None

    def test_create_with_file_path(self):
        """测试包含文件路径"""
        error = ProgressSaveError(
            "Write error",
            file_path="/path/to/progress.json"
        )
        assert error.file_path == "/path/to/progress.json"

    def test_create_with_original_error(self):
        """测试包含原始异常"""
        original = IOError("Disk full")
        error = ProgressSaveError(
            "Save failed",
            original_error=original
        )
        assert error.original_error == original


class TestConfigurationError:
    """测试ConfigurationError异常类"""

    def test_create_with_message_only(self):
        """测试仅使用消息创建配置异常"""
        error = ConfigurationError("Invalid configuration")
        assert error.message == "Invalid configuration"
        assert error.config_key is None
        assert error.config_value is None
        assert error.validation_error is None

    def test_create_with_config_key(self):
        """测试包含配置键名"""
        error = ConfigurationError(
            "Invalid value",
            config_key="max_retries"
        )
        assert error.config_key == "max_retries"
        assert error.details["config_key"] == "max_retries"

    def test_create_with_config_value(self):
        """测试包含配置值"""
        error = ConfigurationError(
            "Value out of range",
            config_value="abc"
        )
        assert error.config_value == "abc"

    def test_create_with_validation_error(self):
        """测试包含验证错误详情"""
        error = ConfigurationError(
            "Validation failed",
            validation_error="Value must be positive"
        )
        assert error.validation_error == "Value must be positive"

    def test_create_with_all_fields(self):
        """测试包含所有字段"""
        error = ConfigurationError(
            message="Config error",
            config_key="batch_size",
            config_value=100,
            validation_error="Must be <= 10"
        )
        assert error.message == "Config error"
        assert error.config_key == "batch_size"
        assert error.config_value == 100
        assert error.validation_error == "Must be <= 10"


class TestTaskValidationError:
    """测试TaskValidationError异常类"""

    def test_create_with_message_only(self):
        """测试仅使用消息创建任务验证异常"""
        error = TaskValidationError("Invalid task parameters")
        assert error.message == "Invalid task parameters"
        assert error.task_id is None
        assert error.invalid_params == {}

    def test_create_with_task_id(self):
        """测试包含任务ID"""
        error = TaskValidationError(
            "Task validation failed",
            task_id="task_001"
        )
        assert error.task_id == "task_001"
        assert error.details["task_id"] == "task_001"

    def test_create_with_invalid_params(self):
        """测试包含无效参数字典"""
        params = {"year": 1800, "month": 13}
        error = TaskValidationError(
            "Invalid parameters",
            invalid_params=params
        )
        assert error.invalid_params == params
        assert error.details["invalid_params"] == params

    def test_create_with_all_fields(self):
        """测试包含所有字段"""
        error = TaskValidationError(
            message="Validation error",
            task_id="task_002",
            invalid_params={"pressure_level": 1500}
        )
        assert error.message == "Validation error"
        assert error.task_id == "task_002"
        assert error.invalid_params == {"pressure_level": 1500}


class TestExceptionHierarchy:
    """测试异常继承关系"""

    def test_all_inherit_from_download_error(self):
        """测试所有异常都继承自DownloadError"""
        assert issubclass(APIError, DownloadError)
        assert issubclass(AccountPoolError, DownloadError)
        assert issubclass(ProgressLoadError, DownloadError)
        assert issubclass(ProgressSaveError, DownloadError)
        assert issubclass(ConfigurationError, DownloadError)
        assert issubclass(TaskValidationError, DownloadError)

    def test_catch_as_base_class(self):
        """测试可以通过基类捕获所有派生异常"""
        errors = [
            APIError("test"),
            AccountPoolError("test"),
            ProgressLoadError("test"),
            ProgressSaveError("test"),
            ConfigurationError("test"),
            TaskValidationError("test"),
        ]

        for error in errors:
            assert isinstance(error, DownloadError)

    def test_exception_catching_by_type(self):
        """测试可以按类型捕获特定异常"""
        try:
            raise APIError("API failed")
        except APIError:
            assert True  # 应该捕获到
        except AccountPoolError:
            assert False  # 不应该到这里

        try:
            raise AccountPoolError("Pool empty")
        except APIError:
            assert False  # 不应该到这里
        except AccountPoolError:
            assert True  # 应该捕获到
