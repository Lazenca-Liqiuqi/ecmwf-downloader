"""
DatastoresService API 服务层单元测试

测试 ecmwf-datastores-client 的封装功能。
"""

import pytest
from unittest.mock import MagicMock, patch

from src.api.ecmwf_datastores_client import (
    DatastoresService,
    DatastoresServiceError,
)
from src.core.dataset_schema import FieldType


class TestDatastoresServiceInit:
    """测试 DatastoresService 初始化"""

    def test_create_with_credentials(self):
        """测试使用凭据创建服务"""
        service = DatastoresService(
            url="https://test.api.com",
            key="test_key",
        )
        assert service.url == "https://test.api.com"
        assert service.key == "test_key"

    def test_create_without_credentials(self):
        """测试不使用凭据创建服务"""
        service = DatastoresService()
        assert service.key is None


class TestDatastoresServiceGetClient:
    """测试客户端获取"""

    def test_get_client_import_error(self):
        """测试 ecmwf-datastores-client 未安装时的错误"""
        service = DatastoresService()

        with patch.dict("sys.modules", {"ecmwf.datastores": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(DatastoresServiceError) as exc_info:
                    service._get_client()
                assert "未安装" in str(exc_info.value)


class TestDatastoresServiceCheckConnection:
    """测试连接检查"""

    def test_check_connection_success(self):
        """测试连接成功"""
        service = DatastoresService()

        mock_client = MagicMock()
        mock_client.get_collections.return_value = []

        with patch.object(service, "_get_client", return_value=mock_client):
            result = service.check_connection()
            assert result is True

    def test_check_connection_failure(self):
        """测试连接失败"""
        service = DatastoresService()

        with patch.object(service, "_get_client", side_effect=Exception("Connection failed")):
            result = service.check_connection()
            assert result is False


class TestDatastoresServiceGetAvailableDatasets:
    """测试获取可用数据集列表"""

    def test_get_available_datasets_success(self):
        """测试成功获取数据集列表"""
        service = DatastoresService()

        # 模拟返回的数据集
        mock_collection = MagicMock()
        mock_collection.id = "test-dataset"
        mock_collection.title = "Test Dataset"

        mock_client = MagicMock()
        mock_client.get_collections.return_value = [mock_collection]

        with patch.object(service, "_get_client", return_value=mock_client):
            datasets = service.get_available_datasets()

            assert len(datasets) == 1
            assert datasets[0]["id"] == "test-dataset"
            assert datasets[0]["title"] == "Test Dataset"

    def test_get_available_datasets_empty(self):
        """测试获取空数据集列表"""
        service = DatastoresService()

        mock_client = MagicMock()
        mock_client.get_collections.return_value = []

        with patch.object(service, "_get_client", return_value=mock_client):
            datasets = service.get_available_datasets()
            assert datasets == []

    def test_get_available_datasets_error(self):
        """测试获取数据集列表失败"""
        service = DatastoresService()

        with patch.object(service, "_get_client", side_effect=Exception("Error")):
            datasets = service.get_available_datasets()
            assert datasets == []


class TestDatastoresServiceGetDatasetSchema:
    """测试获取数据集 Schema"""

    def test_get_dataset_schema_success(self):
        """测试成功获取 Schema"""
        service = DatastoresService()

        # 模拟 collection 对象
        mock_collection = MagicMock()
        mock_collection.id = "test-dataset"
        mock_collection.title = "Test Dataset"
        mock_collection.description = "A test dataset"
        mock_collection.form = [
            {"name": "variable", "type": "StringArrayWidget", "required": True},
            {"name": "year", "type": "IntegerArrayWidget", "required": True},
        ]
        mock_collection.constraints = {
            "variable": ["u", "v"],
            "year": ["2020", "2021"],
        }

        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection

        with patch.object(service, "_get_client", return_value=mock_client):
            schema = service.get_dataset_schema("test-dataset")

            assert schema.collection_id == "test-dataset"
            assert schema.title == "Test Dataset"
            assert len(schema.fields) == 2
            assert schema.constraints == {"variable": ["u", "v"], "year": ["2020", "2021"]}

    def test_get_dataset_schema_error(self):
        """测试获取 Schema 失败"""
        service = DatastoresService()

        with patch.object(service, "_get_client", side_effect=Exception("Network error")):
            with pytest.raises(DatastoresServiceError) as exc_info:
                service.get_dataset_schema("invalid-dataset")
            assert "获取数据集 Schema 失败" in str(exc_info.value)

    def test_get_dataset_schema_no_form(self):
        """测试 Schema 没有 form 属性时使用默认字段"""
        service = DatastoresService()

        mock_collection = MagicMock()
        mock_collection.id = "test-dataset"
        mock_collection.title = "Test Dataset"
        # 没有 form 属性
        del mock_collection.form

        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection

        with patch.object(service, "_get_client", return_value=mock_client):
            schema = service.get_dataset_schema("test-dataset")
            # 应该使用默认字段
            assert len(schema.fields) > 0


class TestDatastoresServiceApplyConstraints:
    """测试应用约束"""

    def test_apply_constraints_success(self):
        """测试成功应用约束"""
        service = DatastoresService()

        # 模拟约束返回结果
        mock_result = {
            "day": ["01", "02", "03"],
            "variable": ["u", "v", "t"],
        }
        mock_client = MagicMock()
        mock_client.apply_constraints.return_value = mock_result

        with patch.object(service, "_get_client", return_value=mock_client):
            constraints = service.apply_constraints(
                "test-dataset",
                {"year": "2020", "month": "02"},
            )

            assert "day" in constraints
            assert len(constraints["day"]) == 3

    def test_apply_constraints_with_list_values(self):
        """测试约束计算使用列表值"""
        service = DatastoresService()

        mock_result = {"day": ["01", "02"]}
        mock_client = MagicMock()
        mock_client.apply_constraints.return_value = mock_result

        with patch.object(service, "_get_client", return_value=mock_client):
            service.apply_constraints(
                "test-dataset",
                {"year": ["2020", "2021"]},  # 列表值
            )

            # 验证调用参数被正确格式化
            call_args = mock_client.apply_constraints.call_args
            assert call_args is not None

    def test_apply_constraints_error(self):
        """测试约束计算失败"""
        service = DatastoresService()

        with patch.object(service, "_get_client", side_effect=Exception("API error")):
            with pytest.raises(DatastoresServiceError) as exc_info:
                service.apply_constraints("test-dataset", {})
            assert "约束计算失败" in str(exc_info.value)


class TestDatastoresServiceHelpers:
    """测试辅助方法"""

    def test_format_selection_strings(self):
        """测试格式化选择值（字符串）"""
        service = DatastoresService()

        selection = {"year": "2020", "month": ["01", "02"]}
        formatted = service._format_selection(selection)

        assert formatted["year"] == "2020"
        assert formatted["month"] == ["01", "02"]

    def test_format_selection_integers(self):
        """测试格式化选择值（整数）"""
        service = DatastoresService()

        selection = {"year": 2020, "values": [1, 2, 3]}
        formatted = service._format_selection(selection)

        assert formatted["year"] == "2020"
        assert formatted["values"] == ["1", "2", "3"]

    def test_parse_constraints_result_dict(self):
        """测试解析约束结果（字典）"""
        service = DatastoresService()

        result = {
            "day": ["01", "02", "03"],
            "variable": ["u", "v"],
        }
        constraints = service._parse_constraints_result(result)

        assert constraints["day"] == ["01", "02", "03"]
        assert constraints["variable"] == ["u", "v"]

    def test_parse_constraints_result_nested(self):
        """测试解析约束结果（嵌套结构）"""
        service = DatastoresService()

        result = {
            "day": {"values": ["01", "02"]},
        }
        constraints = service._parse_constraints_result(result)

        assert constraints["day"] == ["01", "02"]

    def test_get_default_fields(self):
        """测试获取默认字段"""
        service = DatastoresService()
        fields = service._get_default_fields()

        assert len(fields) > 0
        field_names = [f.name for f in fields]
        assert "variable" in field_names
        assert "year" in field_names
        assert "month" in field_names
