"""
API客户端抽象基类

定义所有数据源API客户端必须遵循的统一接口规范。
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class BaseAPIClient(ABC):
    """API客户端抽象基类

    为所有数据源API客户端定义统一的接口规范。
    具体实现类（如CDSClient）必须实现所有抽象方法。

    设计理念：
    - 接口隔离：上层模块（下载引擎）只需依赖此抽象接口
    - 可扩展性：新增数据源只需实现此接口，无需修改上层代码
    - 可测试性：可以创建Mock客户端用于单元测试
    """

    def __init__(self, account_info: Optional[Dict[str, Any]] = None):
        """初始化API客户端

        Args:
            account_info: 账号信息字典，包含认证凭据等
                - uid: 用户ID
                - key: API密钥
                - url: API端点URL（可选）
        """
        self.account_info = account_info or {}

    @abstractmethod
    def download(
        self,
        dataset: str,
        variables: List[str],
        years: List[int],
        months: List[int],
        days: Optional[List[int]] = None,
        times: Optional[List[str]] = None,
        pressure_levels: Optional[List[int]] = None,
        area: Optional[List[float]] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> Path:
        """下载数据到本地文件

        Args:
            dataset: 数据集标识符（如 "reanalysis-era5-pressure-levels"）
            variables: 要下载的变量列表（如 ["u", "v"]）
            years: 年份列表（如 [2020, 2021]）
            months: 月份列表（如 [1, 2, 3]）
            days: 日期列表（可选，如 [1, 15]）
            times: 时间点列表（可选，如 ["00:00", "12:00"]）
            pressure_levels: 气压层列表（可选，如 [500, 850, 1000]）
            area: 区域范围 [N, W, S, E]（可选）
            output_path: 输出文件路径（可选，默认自动生成）
            **kwargs: 其他数据源特定参数

        Returns:
            Path: 下载文件的路径

        Raises:
            APIError: 下载失败时抛出
        """
        pass

    @abstractmethod
    def check_connection(self) -> bool:
        """检查API连接状态

        验证账号凭据是否有效，网络连接是否正常。

        Returns:
            bool: 连接正常返回True，否则返回False

        Raises:
            APIError: 连接检查失败时抛出
        """
        pass

    @abstractmethod
    def get_available_datasets(self) -> List[str]:
        """获取该数据源支持的数据集列表

        Returns:
            List[str]: 可用数据集的标识符列表

        Raises:
            APIError: 获取数据集列表失败时抛出
        """
        pass

    @abstractmethod
    def get_dataset_variables(self, dataset: str) -> List[str]:
        """获取指定数据集支持的变量列表

        Args:
            dataset: 数据集标识符

        Returns:
            List[str]: 可用变量的标识符列表

        Raises:
            APIError: 获取变量列表失败时抛出
        """
        pass

    @abstractmethod
    def get_request_info(self, dataset: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取下载请求的元信息

        在执行下载前，可以查询请求的数据大小、预计时间等信息。

        Args:
            dataset: 数据集标识符
            params: 请求参数字典

        Returns:
            Dict[str, Any]: 包含以下键的字典：
                - size: 预计数据大小（字节）
                - estimated_time: 预计下载时间（秒）
                - requires_otp: 是否需要一次性密码（某些API）
                - pending: 是否处于等待队列

        Raises:
            APIError: 获取请求信息失败时抛出
        """
        pass

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """验证请求参数的有效性

        默认实现执行基本验证，子类可以重写以添加特定验证逻辑。

        Args:
            params: 请求参数字典

        Returns:
            bool: 参数有效返回True

        Raises:
            ValueError: 参数无效时抛出
        """
        # 基本验证：必需参数
        required_keys = ["dataset", "variables", "years", "months"]
        for key in required_keys:
            if key not in params or not params[key]:
                raise ValueError(f"缺少必需参数: {key}")

        return True

    def get_client_info(self) -> Dict[str, Any]:
        """获取客户端信息

        返回客户端的版本、支持的数据源等信息。

        Returns:
            Dict[str, Any]: 客户端信息字典
        """
        return {
            "client_type": self.__class__.__name__,
            "account_uid": self.account_info.get("uid", "unknown"),
            "api_url": self.account_info.get("url", "unknown"),
        }

    def __repr__(self) -> str:
        """返回客户端的字符串表示"""
        return f"{self.__class__.__name__}(uid={self.account_info.get('uid', 'unknown')})"
