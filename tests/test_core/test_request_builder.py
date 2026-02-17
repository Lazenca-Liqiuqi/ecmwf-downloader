"""RequestBuilder 单元测试"""

from pathlib import Path

import pytest

from src.core.config import DatasetType, DownloadConfig
from src.core.request_builder import DownloadRequest, RequestBuilder


class TestRequestBuilder:
    """RequestBuilder 测试类"""

    @pytest.fixture
    def builder(self) -> RequestBuilder:
        """创建请求构建器实例"""
        return RequestBuilder()

    @pytest.fixture
    def sample_config(self, tmp_path: Path) -> DownloadConfig:
        """创建基础下载配置"""
        return DownloadConfig(
            dataset=DatasetType.ERA5_PRESSURE_LEVELS,
            variables=["temperature", "geopotential"],
            years=[2020, 2021],
            months=[1, 2],
            output_dir=tmp_path,
        )

    def test_build_request_basic(self, builder: RequestBuilder, sample_config: DownloadConfig) -> None:
        """测试 build_request 基本功能"""
        request = builder.build_request(sample_config)

        assert request.dataset == "reanalysis-era5-pressure-levels"
        assert request.output_path.parent == sample_config.output_dir
        assert request.output_path.name == request.filename
        assert request.filename.endswith(".nc")
        assert request.time_range == {"years": [2020, 2021], "months": [1, 2], "days": []}
        assert request.api_params["variable"] == ["temperature", "geopotential"]
        assert request.api_params["year"] == ["2020", "2021"]
        assert request.api_params["month"] == ["01", "02"]
        assert request.api_params["day"] == [f"{day:02d}" for day in range(1, 32)]
        assert request.api_params["time"] == ["00:00", "06:00", "12:00", "18:00"]

    def test_build_batch_requests_month_strategy(
        self,
        builder: RequestBuilder,
        sample_config: DownloadConfig,
    ) -> None:
        """测试按月拆分策略"""
        requests = builder.build_batch_requests(sample_config, split_strategy="month")

        assert len(requests) == 4
        actual_ranges = {(r.time_range["years"][0], r.time_range["months"][0]) for r in requests}
        assert actual_ranges == {(2020, 1), (2020, 2), (2021, 1), (2021, 2)}

    def test_build_batch_requests_year_strategy(
        self,
        builder: RequestBuilder,
        sample_config: DownloadConfig,
    ) -> None:
        """测试按年拆分策略"""
        requests = builder.build_batch_requests(sample_config, split_strategy="year")

        assert len(requests) == 2
        for request in requests:
            assert len(request.time_range["years"]) == 1
            assert request.time_range["months"] == [1, 2]
        assert {r.time_range["years"][0] for r in requests} == {2020, 2021}

    def test_build_batch_requests_none_strategy(
        self,
        builder: RequestBuilder,
        sample_config: DownloadConfig,
    ) -> None:
        """测试不拆分策略"""
        requests = builder.build_batch_requests(sample_config, split_strategy="none")

        assert len(requests) == 1
        assert requests[0].time_range["years"] == [2020, 2021]
        assert requests[0].time_range["months"] == [1, 2]

    def test_build_batch_requests_invalid_strategy(
        self,
        builder: RequestBuilder,
        sample_config: DownloadConfig,
    ) -> None:
        """测试无效拆分策略抛出异常"""
        with pytest.raises(ValueError, match="不支持的拆分策略"):
            builder.build_batch_requests(sample_config, split_strategy="invalid")  # type: ignore[arg-type]

    def test_validate_request_valid(self, builder: RequestBuilder, sample_config: DownloadConfig) -> None:
        """测试 validate_request 对合法请求返回成功"""
        request = builder.build_request(sample_config)

        is_valid, errors = builder.validate_request(request)

        assert is_valid is True
        assert errors == []

    def test_validate_request_missing_fields(self, builder: RequestBuilder) -> None:
        """测试 validate_request 对缺失字段返回错误列表"""
        request = DownloadRequest(
            dataset="",
            api_params={"product_type": "reanalysis"},
            output_path=Path(""),
            filename="",
            time_range={},
        )

        is_valid, errors = builder.validate_request(request)

        assert is_valid is False
        assert "dataset不能为空" in errors
        assert "filename不能为空" in errors
        # Path("") 会解析为当前目录，触发目录校验错误
        assert "output_path" in errors[2]  # output_path相关错误
        assert "api_params缺少必填字段: variable" in errors
        assert "api_params缺少必填字段: year" in errors
        assert "api_params缺少必填字段: month" in errors
        assert "api_params缺少必填字段: day" in errors
        assert "api_params缺少必填字段: time" in errors
        assert "time_range.years不能为空" in errors
        assert "time_range.months不能为空" in errors

    def test_preview_request(self, builder: RequestBuilder, sample_config: DownloadConfig) -> None:
        """测试 preview_request 预览文本生成"""
        request = builder.build_request(sample_config)

        preview = builder.preview_request(request)

        assert "=== 下载请求预览 ===" in preview
        assert f"数据集: {request.dataset}" in preview
        assert f"输出文件: {request.filename}" in preview
        assert "变量: temperature, geopotential" in preview
        assert "年份: [2020, 2021]" in preview
        assert "月份: [1, 2]" in preview
        assert "API参数:" in preview

    def test_filename_generation(self, builder: RequestBuilder, tmp_path: Path) -> None:
        """测试文件名生成与后缀格式"""
        nc_config = DownloadConfig(
            dataset=DatasetType.ERA5_PRESSURE_LEVELS,
            variables=["temperature"],
            years=[2020],
            months=[3],
            output_dir=tmp_path,
            output_format="netcdf",
        )
        grib_config = DownloadConfig(
            dataset=DatasetType.ERA5_PRESSURE_LEVELS,
            variables=["temperature"],
            years=[2020],
            months=[3],
            output_dir=tmp_path,
            output_format="grib",
        )

        nc_request = builder.build_request(nc_config)
        grib_request = builder.build_request(grib_config)

        assert nc_request.filename.startswith("ERA5_2020_03_temperature")
        assert nc_request.filename.endswith(".nc")
        assert grib_request.filename.startswith("ERA5_2020_03_temperature")
        assert grib_request.filename.endswith(".grib")

    def test_api_params_format(self, builder: RequestBuilder, tmp_path: Path) -> None:
        """测试 API 参数时间维度格式化"""
        config = DownloadConfig(
            dataset=DatasetType.ERA5_PRESSURE_LEVELS,
            variables=["temperature"],
            years=[2020],
            months=[1, 11],
            days=[1, 9, 31],
            times=["00:00", "12:00"],
            pressure_levels=[500, 850],
            area=[55, 70, 15, 140],
            output_dir=tmp_path,
        )

        request = builder.build_request(config)
        api_params = request.api_params

        assert api_params["year"] == ["2020"]
        assert api_params["month"] == ["01", "11"]
        assert api_params["day"] == ["01", "09", "31"]
        assert api_params["time"] == ["00:00", "12:00"]
        assert api_params["pressure_level"] == ["500", "850"]
        assert api_params["area"] == [55, 70, 15, 140]
        assert api_params["data_format"] == "netcdf"
        assert api_params["download_format"] == "unarchived"
