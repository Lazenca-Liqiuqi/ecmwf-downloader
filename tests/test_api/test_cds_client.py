"""
ECMWF下载器CDS API客户端单元测试

测试CDS API客户端的各项功能，包括请求构建、错误处理等。
"""

from pathlib import Path
from typing import List
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.api.cds_client import CDSClient
from src.core.exceptions import APIError


@pytest.fixture
def sample_account():
    """创建示例账号信息"""
    return {
        "uid": "test_uid",
        "key": "test_api_key",
        "url": "https://cds.climate.copernicus.eu/api"
    }


@pytest.fixture
def cds_client(sample_account):
    """创建CDS客户端实例"""
    return CDSClient(account_info=sample_account)


class TestCDSClientInit:
    """测试CDSClient初始化"""

    def test_init_with_required_fields(self):
        """测试使用必填字段初始化"""
        account = {
            "uid": "my_uid",
            "key": "my_key"
        }
        client = CDSClient(account_info=account)

        assert client.uid == "my_uid"
        assert client.key == "my_key"
        assert client.url == "https://cds.climate.copernicus.eu/api"

    def test_init_with_custom_url(self):
        """测试使用自定义URL初始化"""
        account = {
            "uid": "uid",
            "key": "key",
            "url": "https://custom.api.com"
        }
        client = CDSClient(account_info=account)

        assert client.url == "https://custom.api.com"

    def test_init_without_uid_raises_error(self):
        """测试缺少uid时抛出异常"""
        account = {"key": "key"}

        with pytest.raises(ValueError, match="account_info必须包含uid和key字段"):
            CDSClient(account_info=account)

    def test_init_without_key_raises_error(self):
        """测试缺少key时抛出异常"""
        account = {"uid": "uid"}

        with pytest.raises(ValueError, match="account_info必须包含uid和key字段"):
            CDSClient(account_info=account)

    def test_init_disables_proxy(self, sample_account):
        """测试初始化时禁用代理"""
        import os

        # 设置代理环境变量
        os.environ["HTTP_PROXY"] = "http://proxy.com"
        os.environ["HTTPS_PROXY"] = "http://proxy.com"

        CDSClient(account_info=sample_account)

        # 代理应该被清除
        assert os.environ.get("HTTP_PROXY") == ""
        assert os.environ.get("HTTPS_PROXY") == ""


class TestCDSClientBuildRequest:
    """测试请求参数构建"""

    def test_build_basic_request(self, cds_client):
        """测试构建基本请求"""
        request = cds_client._build_request(
            variables=["temperature"],
            years=[2023],
            months=[1]
        )

        assert request["variable"] == ["temperature"]
        assert request["year"] == ["2023"]
        assert request["month"] == ["01"]
        assert request["day"] == [f"{d:02d}" for d in range(1, 32)]
        assert request["time"] == ["00:00", "06:00", "12:00", "18:00"]

    def test_build_request_with_days(self, cds_client):
        """测试指定日期构建请求"""
        request = cds_client._build_request(
            variables=["temperature"],
            years=[2023],
            months=[1],
            days=[1, 15]
        )

        assert request["day"] == ["01", "15"]

    def test_build_request_with_times(self, cds_client):
        """测试指定时间点构建请求"""
        request = cds_client._build_request(
            variables=["temperature"],
            years=[2023],
            months=[1],
            times=["00:00", "12:00"]
        )

        assert request["time"] == ["00:00", "12:00"]

    def test_build_request_with_pressure_levels(self, cds_client):
        """测试指定气压层构建请求"""
        request = cds_client._build_request(
            variables=["temperature"],
            years=[2023],
            months=[1],
            pressure_levels=[500, 850, 1000]
        )

        assert request["pressure_level"] == ["500", "850", "1000"]

    def test_build_request_with_area(self, cds_client):
        """测试指定区域构建请求"""
        request = cds_client._build_request(
            variables=["temperature"],
            years=[2023],
            months=[1],
            area=[55, 70, 15, 140]
        )

        assert request["area"] == [55, 70, 15, 140]

    def test_build_request_with_custom_grid(self, cds_client):
        """测试自定义网格分辨率"""
        request = cds_client._build_request(
            variables=["temperature"],
            years=[2023],
            months=[1],
            grid=[1.0, 1.0]
        )

        assert request["grid"] == [1.0, 1.0]

    def test_build_request_with_custom_format(self, cds_client):
        """测试自定义数据格式"""
        request = cds_client._build_request(
            variables=["temperature"],
            years=[2023],
            months=[1],
            data_format="grib"
        )

        assert request["data_format"] == "grib"

    def test_build_request_multiple_years_months(self, cds_client):
        """测试多年多月请求"""
        request = cds_client._build_request(
            variables=["temperature"],
            years=[2022, 2023],
            months=[1, 2, 3]
        )

        assert request["year"] == ["2022", "2023"]
        assert request["month"] == ["01", "02", "03"]


class TestCDSClientGenerateOutputPath:
    """测试输出路径生成"""

    def test_generate_output_path_basic(self, cds_client):
        """测试生成基本输出路径"""
        path = cds_client._generate_output_path(
            dataset="reanalysis-era5-pressure-levels",
            years=[2023],
            months=[1],
            variables=["temperature"]
        )

        assert "ERA5_2023_01_temperature" in str(path)
        assert path.suffix == ".nc"

    def test_generate_output_path_multiple_years(self, cds_client):
        """测试多年份输出路径"""
        path = cds_client._generate_output_path(
            dataset="reanalysis-era5-pressure-levels",
            years=[2022, 2023],
            months=[1],
            variables=["temperature"]
        )

        assert "2022-2023" in str(path)

    def test_generate_output_path_multiple_months(self, cds_client):
        """测试多月份输出路径"""
        path = cds_client._generate_output_path(
            dataset="reanalysis-era5-pressure-levels",
            years=[2023],
            months=[1, 2, 3],
            variables=["temperature"]
        )

        assert "01-03" in str(path)

    def test_generate_output_path_multiple_variables(self, cds_client):
        """�试多变量输出路径"""
        path = cds_client._generate_output_path(
            dataset="reanalysis-era5-pressure-levels",
            years=[2023],
            months=[1],
            variables=["temperature", "geopotential", "u_component_of_wind"]
        )

        # 应该包含前3个变量
        assert "temperature" in str(path)
        assert "geopotential" in str(path)


class TestCDSClientGetAvailableDatasets:
    """测试获取可用数据集"""

    def test_get_available_datasets(self, cds_client):
        """测试返回所有支持的数据集"""
        datasets = cds_client.get_available_datasets()

        assert len(datasets) == 5
        assert "reanalysis-era5-pressure-levels" in datasets
        assert "reanalysis-era5-single-levels" in datasets
        assert "reanalysis-era5-land" in datasets


class TestCDSClientGetDatasetVariables:
    """测试获取数据集变量"""

    def test_get_pressure_levels_variables(self, cds_client):
        """测试获取气压层数据集变量"""
        variables = cds_client.get_dataset_variables("reanalysis-era5-pressure-levels")

        assert len(variables) == 9
        assert "temperature" in variables
        assert "geopotential" in variables
        assert "u_component_of_wind" in variables

    def test_get_single_levels_variables(self, cds_client):
        """测试获取单层数据集变量"""
        variables = cds_client.get_dataset_variables("reanalysis-era5-single-levels")

        assert len(variables) == 5
        assert "2m_temperature" in variables
        assert "total_precipitation" in variables

    def test_get_unsupported_dataset_variables(self, cds_client):
        """测试不支持的数据集抛出异常"""
        with pytest.raises(APIError, match="暂不支持数据集"):
            cds_client.get_dataset_variables("unsupported-dataset")


class TestCDSClientGetRequestInfo:
    """测试获取请求信息"""

    def test_get_request_info(self, cds_client):
        """测试获取请求元信息"""
        params = {
            "variable": ["temperature"],
            "year": ["2023"]
        }
        info = cds_client.get_request_info(
            dataset="reanalysis-era5-pressure-levels",
            params=params
        )

        assert info["dataset"] == "reanalysis-era5-pressure-levels"
        assert info["params"] == params
        # CDS API不提供预估大小和时间
        assert info["size"] is None
        assert info["estimated_time"] is None
        assert info["requires_otp"] is False
        assert info["pending"] is False


class TestCDSClientHandleError:
    """测试错误处理"""

    def test_handle_401_error(self, cds_client):
        """测试处理401认证错误"""
        error = MagicMock()
        error.status_code = 401
        error.__str__.return_value = "Unauthorized"

        with pytest.raises(APIError, match="API认证失败"):
            cds_client._handle_error(
                error,
                "reanalysis-era5-pressure-levels",
                {}
            )

    def test_handle_403_error(self, cds_client):
        """测试处理403权限错误"""
        error = MagicMock()
        error.status_code = 403
        error.__str__.return_value = "Forbidden"

        with pytest.raises(APIError, match="API访问被拒绝"):
            cds_client._handle_error(
                error,
                "reanalysis-era5-pressure-levels",
                {}
            )

    def test_handle_404_error(self, cds_client):
        """测试处理404未找到错误"""
        error = MagicMock()
        error.__str__.return_value = "Dataset not found"

        with pytest.raises(APIError, match="数据集不存在"):
            cds_client._handle_error(
                error,
                "reanalysis-era5-pressure-levels",
                {}
            )

    def test_handle_timeout_error(self, cds_client):
        """测试处理超时错误"""
        error = MagicMock()
        error.__str__.return_value = "Request timed out"

        with pytest.raises(APIError, match="请求超时"):
            cds_client._handle_error(
                error,
                "reanalysis-era5-pressure-levels",
                {}
            )

    def test_handle_connection_error(self, cds_client):
        """测试处理连接错误"""
        error = MagicMock()
        error.__str__.return_value = "Connection failed"

        with pytest.raises(APIError, match="网络连接失败"):
            cds_client._handle_error(
                error,
                "reanalysis-era5-pressure-levels",
                {}
            )

    def test_handle_generic_error(self, cds_client):
        """测试处理通用错误"""
        error = MagicMock()
        error.__str__.return_value = "Unknown error occurred"
        error.status_code = 500

        with pytest.raises(APIError, match="CDS API调用失败"):
            cds_client._handle_error(
                error,
                "reanalysis-era5-pressure-levels",
                {}
            )


class TestCDSClientRepr:
    """测试字符串表示"""

    def test_repr_masks_key(self, sample_account):
        """测试字符串表示中密钥被遮蔽"""
        client = CDSClient(account_info=sample_account)

        repr_str = repr(client)

        assert "CDSClient" in repr_str
        assert "test_uid" in repr_str
        assert "test_" in repr_str  # 密钥应该被部分遮蔽
        assert "api_key" not in repr_str  # 完整密钥不应出现


class TestCDSClientDownload:
    """测试下载功能"""

    @patch("src.api.cds_client.cdsapi.Client")
    def test_download_success(self, mock_client_class, cds_client, tmp_path):
        """测试成功下载"""
        # Mock cdsapi客户端
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_result = MagicMock()
        mock_result.download = MagicMock()
        mock_client.retrieve.return_value = mock_result

        # 执行下载
        output_path = tmp_path / "output.nc"
        result = cds_client.download(
            dataset="reanalysis-era5-pressure-levels",
            variables=["temperature"],
            years=[2023],
            months=[1],
            output_path=output_path
        )

        assert result == output_path
        mock_client.retrieve.assert_called_once()
        mock_result.download.assert_called_once_with(str(output_path))

    @patch("src.api.cds_client.cdsapi.Client")
    def test_download_creates_output_dir(self, mock_client_class, cds_client):
        """测试下载时自动创建输出目录"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_result = MagicMock()
        mock_result.download = MagicMock()
        mock_client.retrieve.return_value = mock_result

        output_path = Path("/tmp/nonexistent/nested/output.nc")

        cds_client.download(
            dataset="reanalysis-era5-pressure-levels",
            variables=["temperature"],
            years=[2023],
            months=[1],
            output_path=output_path
        )

        assert output_path.parent.exists()

    @patch("src.api.cds_client.cdsapi.Client")
    def test_download_with_error(self, mock_client_class, cds_client):
        """测试下载失败抛出APIError"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # 模拟API错误
        error = Exception("401 Client Error: Unauthorized")
        mock_client.retrieve.side_effect = error

        with pytest.raises(APIError):
            cds_client.download(
                dataset="reanalysis-era5-pressure-levels",
                variables=["temperature"],
                years=[2023],
                months=[1]
            )


class TestCDSClientCheckConnection:
    """测试连接检查"""

    @patch("src.api.cds_client.cdsapi.Client")
    def test_check_connection_success(self, mock_client_class, cds_client):
        """测试连接检查成功"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_session = MagicMock()
        mock_session.get.return_value = MagicMock()
        mock_client.session = mock_session

        result = cds_client.check_connection()

        assert result is True
        mock_session.get.assert_called_once()

    @patch("src.api.cds_client.cdsapi.Client")
    def test_check_connection_failure(self, mock_client_class, cds_client):
        """测试连接检查失败"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection failed")
        mock_client.session = mock_session

        with pytest.raises(APIError, match="API连接检查失败"):
            cds_client.check_connection()


class TestCDSClientLazyClient:
    """测试延迟创建客户端"""

    def test_client_not_created_on_init(self, sample_account):
        """测试初始化时不创建cdsapi客户端"""
        client = CDSClient(account_info=sample_account)

        assert client._client is None

    @patch("src.api.cds_client.cdsapi.Client")
    def test_client_created_on_first_use(self, mock_client_class, sample_account):
        """测试首次使用时创建客户端"""
        client = CDSClient(account_info=sample_account)

        mock_cdsapi_client = MagicMock()
        mock_client_class.return_value = mock_cdsapi_client

        # 调用需要客户端的方法
        client._get_client()

        assert client._client is not None
        mock_client_class.assert_called_once()


class TestCDSClientDefaults:
    """测试默认值常量"""

    def test_available_datasets_constant(self):
        """测试可用数据集常量"""
        assert "reanalysis-era5-pressure-levels" in CDSClient.AVAILABLE_DATASETS
        assert "reanalysis-era5-single-levels" in CDSClient.AVAILABLE_DATASETS

    def test_pressure_levels_variables_constant(self):
        """测试气压层变量常量"""
        assert "temperature" in CDSClient.PRESSURE_LEVELS_VARIABLES
        assert "geopotential" in CDSClient.PRESSURE_LEVELS_VARIABLES
        assert "u_component_of_wind" in CDSClient.PRESSURE_LEVELS_VARIABLES

    def test_default_pressure_levels_constant(self):
        """测试默认气压层常量"""
        assert 500 in CDSClient.DEFAULT_PRESSURE_LEVELS
        assert 850 in CDSClient.DEFAULT_PRESSURE_LEVELS
        assert 1000 in CDSClient.DEFAULT_PRESSURE_LEVELS
        assert len(CDSClient.DEFAULT_PRESSURE_LEVELS) == 37
