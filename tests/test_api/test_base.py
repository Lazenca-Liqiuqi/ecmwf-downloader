"""
ECMWF下载器API抽象基类单元测试

测试BaseAPIClient抽象接口的定义和默认实现。
"""

from abc import ABC
from typing import List
from unittest.mock import MagicMock

import pytest

from src.api.base import BaseAPIClient


class TestBaseAPIClientAbstract:
    """测试BaseAPIClient抽象方法"""

    def test_is_abstract_class(self):
        """测试是抽象类"""
        assert issubclass(BaseAPIClient, ABC)

    def test_download_is_abstract(self):
        """测试download是抽象方法"""
        assert hasattr(BaseAPIClient, "download")

    def test_check_connection_is_abstract(self):
        """测试check_connection是抽象方法"""
        assert hasattr(BaseAPIClient, "check_connection")

    def test_get_available_datasets_is_abstract(self):
        """测试get_available_datasets是抽象方法"""
        assert hasattr(BaseAPIClient, "get_available_datasets")

    def test_get_dataset_variables_is_abstract(self):
        """测试get_dataset_variables是抽象方法"""
        assert hasattr(BaseAPIClient, "get_dataset_variables")

    def test_get_request_info_is_abstract(self):
        """测试get_request_info是抽象方法"""
        assert hasattr(BaseAPIClient, "get_request_info")

    def test_cannot_instantiate_directly(self):
        """测试不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            BaseAPIClient(account_info=None)


class TestConcreteAPIClient:
    """测试具体实现类"""

    def test_can_create_concrete_implementation(self):
        """测试可以创建具体实现"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(
                self,
                dataset: str,
                variables: List[str],
                years: List[int],
                months: List[int],
                **kwargs
            ):
                pass

            def check_connection(self) -> bool:
                return True

            def get_available_datasets(self) -> List[str]:
                return ["dataset1", "dataset2"]

            def get_dataset_variables(self, dataset: str) -> List[str]:
                return ["var1", "var2"]

            def get_request_info(self, dataset: str, params: dict) -> dict:
                return {"dataset": dataset, "params": params}

        # 应该可以实例化
        client = ConcreteAPIClient(account_info=None)

        assert client.check_connection() is True
        assert client.get_available_datasets() == ["dataset1", "dataset2"]


class TestBaseAPIClientInit:
    """测试BaseAPIClient初始化"""

    def test_init_with_account_info(self):
        """测试使用账号信息初始化"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        account = {"email": "test@example.com", "key": "key"}
        client = ConcreteAPIClient(account_info=account)

        assert client.account_info == account

    def test_init_without_account_info(self):
        """测试不使用账号信息初始化（默认为空字典）"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        client = ConcreteAPIClient(account_info=None)

        # BaseAPIClient的实现会将None转换为空字典
        assert client.account_info == {}


class TestValidateParams:
    """测试参数验证方法"""

    def test_validate_params_with_valid_data(self):
        """测试验证有效参数"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        client = ConcreteAPIClient(account_info=None)

        # 不应该抛出异常
        params = {
            "dataset": "test-dataset",
            "variables": ["temperature"],
            "years": [2023],
            "months": [1, 2, 3]
        }
        client.validate_params(params)

    def test_validate_params_with_missing_dataset(self):
        """测试验证缺少dataset参数"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        client = ConcreteAPIClient(account_info=None)

        with pytest.raises(ValueError, match="缺少必需参数"):
            client.validate_params({
                "variables": ["temperature"],
                "years": [2023],
                "months": [1]
            })

    def test_validate_params_with_empty_variables(self):
        """测试验证空变量列表"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        client = ConcreteAPIClient(account_info=None)

        with pytest.raises(ValueError, match="缺少必需参数"):
            client.validate_params({
                "dataset": "test",
                "variables": [],
                "years": [2023],
                "months": [1]
            })

    def test_validate_params_with_empty_years(self):
        """测试验证空年份列表"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        client = ConcreteAPIClient(account_info=None)

        with pytest.raises(ValueError, match="缺少必需参数"):
            client.validate_params({
                "dataset": "test",
                "variables": ["temp"],
                "years": [],
                "months": [1]
            })

    def test_validate_params_with_empty_months(self):
        """测试验证空月份列表"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        client = ConcreteAPIClient(account_info=None)

        with pytest.raises(ValueError, match="缺少必需参数"):
            client.validate_params({
                "dataset": "test",
                "variables": ["temp"],
                "years": [2023],
                "months": []
            })


class TestGetClientInfo:
    """测试获取客户端信息"""

    def test_get_client_info(self):
        """测试获取客户端信息"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        account = {
            "email": "test@example.com",
            "key": "test_key",
            "url": "https://api.example.com"
        }
        client = ConcreteAPIClient(account_info=account)

        info = client.get_client_info()

        assert info["client_type"] == "ConcreteAPIClient"
        assert info["account_email"] == "test@example.com"
        assert info["api_url"] == "https://api.example.com"


class TestRepr:
    """测试字符串表示"""

    def test_repr_without_account_info(self):
        """测试无账号信息时的字符串表示"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        client = ConcreteAPIClient(account_info=None)

        repr_str = repr(client)

        assert "ConcreteAPIClient" in repr_str
        # account_info是空字典时，email会返回"unknown"
        assert "email=unknown" in repr_str

    def test_repr_with_account_info(self):
        """测试有账号信息时的字符串表示"""

        class ConcreteAPIClient(BaseAPIClient):
            def download(self, dataset, variables, years, months, **kwargs):
                pass

            def check_connection(self):
                pass

            def get_available_datasets(self):
                pass

            def get_dataset_variables(self, dataset):
                pass

            def get_request_info(self, dataset, params):
                pass

        account = {"email": "my@example.com", "key": "my_key"}
        client = ConcreteAPIClient(account_info=account)

        repr_str = repr(client)

        assert "ConcreteAPIClient" in repr_str
        assert "email=my@example.com" in repr_str
