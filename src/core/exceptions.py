"""
ECMWF下载器自定义异常类

定义项目中所有自定义异常类型，用于错误分类和针对性处理。
"""

from typing import Optional


class DownloadError(Exception):
    """下载相关异常基类

    所有下载过程中的异常都应该继承此类。
    """

    def __init__(self, message: str, details: Optional[dict] = None):
        """初始化下载异常

        Args:
            message: 错误消息
            details: 错误详细信息（可选）
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """返回错误消息字符串"""
        return self.message


class APIError(DownloadError):
    """API调用异常

    当ECMWF CDS API调用失败时抛出。
    可能的原因：网络问题、API密钥无效、请求参数错误等。
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ):
        """初始化API异常

        Args:
            message: 错误消息
            status_code: HTTP状态码（可选）
            response_body: API响应内容（可选）
        """
        details = {}
        if status_code is not None:
            details["status_code"] = status_code
        if response_body is not None:
            details["response_body"] = response_body

        super().__init__(message, details)
        self.status_code = status_code
        self.response_body = response_body


class AccountPoolError(DownloadError):
    """账号池相关异常

    当账号池管理出现问题抛出。
    可能的原因：没有可用账号、所有账号已失效、账号配置错误等。
    """

    def __init__(
        self,
        message: str,
        account_id: Optional[str] = None,
        available_count: Optional[int] = None,
    ):
        """初始化账号池异常

        Args:
            message: 错误消息
            account_id: 相关账号ID（可选）
            available_count: 可用账号数量（可选）
        """
        details = {}
        if account_id is not None:
            details["account_id"] = account_id
        if available_count is not None:
            details["available_count"] = available_count

        super().__init__(message, details)
        self.account_id = account_id
        self.available_count = available_count


class ProgressLoadError(DownloadError):
    """进度加载异常

    当加载进度文件失败时抛出。
    可能的原因：文件不存在、文件损坏、JSON格式错误等。
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        """初始化进度加载异常

        Args:
            message: 错误消息
            file_path: 进度文件路径（可选）
            original_error: 原始异常对象（可选）
        """
        details = {}
        if file_path is not None:
            details["file_path"] = file_path
        if original_error is not None:
            details["original_error"] = str(original_error)

        super().__init__(message, details)
        self.file_path = file_path
        self.original_error = original_error


class ProgressSaveError(DownloadError):
    """进度保存异常

    当保存进度文件失败时抛出。
    可能的原因：磁盘空间不足、文件权限问题、IO错误等。
    """

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        """初始化进度保存异常

        Args:
            message: 错误消息
            file_path: 进度文件路径（可选）
            original_error: 原始异常对象（可选）
        """
        details = {}
        if file_path is not None:
            details["file_path"] = file_path
        if original_error is not None:
            details["original_error"] = str(original_error)

        super().__init__(message, details)
        self.file_path = file_path
        self.original_error = original_error


class ConfigurationError(DownloadError):
    """配置错误异常

    当配置验证失败时抛出。
    可能的原因：配置文件格式错误、必填项缺失、值类型错误、值范围错误等。
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        validation_error: Optional[str] = None,
    ):
        """初始化配置错误异常

        Args:
            message: 错误消息
            config_key: 配置项键名（可选）
            config_value: 配置项值（可选）
            validation_error: 验证错误详情（可选）
        """
        from typing import Any

        details = {}
        if config_key is not None:
            details["config_key"] = config_key
        if config_value is not None:
            details["config_value"] = str(config_value)
        if validation_error is not None:
            details["validation_error"] = validation_error

        super().__init__(message, details)
        self.config_key = config_key
        self.config_value = config_value
        self.validation_error = validation_error


class TaskValidationError(DownloadError):
    """任务验证异常

    当下载任务参数验证失败时抛出。
    可能的原因：年份范围错误、月份超出范围、气压层无效等。
    """

    def __init__(
        self,
        message: str,
        task_id: Optional[str] = None,
        invalid_params: Optional[dict] = None,
    ):
        """初始化任务验证异常

        Args:
            message: 错误消息
            task_id: 任务ID（可选）
            invalid_params: 无效参数字典（可选）
        """
        details = {}
        if task_id is not None:
            details["task_id"] = task_id
        if invalid_params is not None:
            details["invalid_params"] = invalid_params

        super().__init__(message, details)
        self.task_id = task_id
        self.invalid_params = invalid_params or {}
