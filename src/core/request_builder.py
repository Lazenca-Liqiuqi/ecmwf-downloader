"""
下载请求构建器模块

负责将下载配置转换为可执行的CDS请求对象，并支持批量拆分与校验。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from src.core.config import DownloadConfig


@dataclass
class DownloadRequest:
    """下载请求数据类"""

    dataset: str
    api_params: Dict[str, Any]
    output_path: Path
    filename: str
    time_range: Dict[str, List]


class RequestBuilder:
    """下载请求构建器"""

    def build_request(self, config: DownloadConfig) -> DownloadRequest:
        """从配置构建单个下载请求。

        Args:
            config: 下载配置对象。

        Returns:
            DownloadRequest: 构建完成的单个下载请求对象。
        """
        return self._build_single_request(
            config=config,
            years=config.years,
            months=config.months,
        )

    def build_batch_requests(
        self,
        config: DownloadConfig,
        split_strategy: Literal["month", "year", "none"] = "month",
    ) -> List[DownloadRequest]:
        """构建批量下载请求（支持按月/年拆分）。

        Args:
            config: 下载配置对象。
            split_strategy: 拆分策略，支持：
                - "month": 按月拆分，每个年-月生成一个请求。
                - "year": 按年拆分，每年一个请求，月份沿用配置。
                - "none": 不拆分，仅生成一个请求。

        Returns:
            List[DownloadRequest]: 拆分后的请求列表。

        Raises:
            ValueError: 传入不支持的拆分策略时抛出。
        """
        if split_strategy == "none":
            return [self.build_request(config)]

        if split_strategy == "year":
            return [
                self._build_single_request(config=config, years=[year], months=config.months)
                for year in config.years
            ]

        if split_strategy == "month":
            requests: List[DownloadRequest] = []
            for year in config.years:
                for month in config.months:
                    requests.append(
                        self._build_single_request(
                            config=config,
                            years=[year],
                            months=[month],
                        )
                    )
            return requests

        raise ValueError(f"不支持的拆分策略: {split_strategy}")

    def validate_request(self, request: DownloadRequest) -> Tuple[bool, List[str]]:
        """验证请求参数完整性。

        Args:
            request: 待校验的下载请求对象。

        Returns:
            Tuple[bool, List[str]]: 第一个值表示是否通过校验，第二个值为错误信息列表。
        """
        errors: List[str] = []
        required_api_fields = ["product_type", "variable", "year", "month", "day", "time"]

        if not request.dataset:
            errors.append("dataset不能为空")

        if not request.filename:
            errors.append("filename不能为空")

        # 显式校验路径：Path("") 会转换为当前目录而非空值
        if not request.output_path or str(request.output_path).strip() == "":
            errors.append("output_path不能为空")
        elif request.output_path.is_dir():
            errors.append("output_path必须指向文件路径，不能是目录")

        if not request.api_params:
            errors.append("api_params不能为空")
        else:
            for field in required_api_fields:
                if field not in request.api_params:
                    errors.append(f"api_params缺少必填字段: {field}")

        if "years" not in request.time_range or not request.time_range.get("years"):
            errors.append("time_range.years不能为空")

        if "months" not in request.time_range or not request.time_range.get("months"):
            errors.append("time_range.months不能为空")

        return len(errors) == 0, errors

    def preview_request(self, request: DownloadRequest) -> str:
        """生成请求预览文本。

        Args:
            request: 下载请求对象。

        Returns:
            str: 人类可读的请求预览文本。
        """
        years = request.time_range.get("years", [])
        months = request.time_range.get("months", [])
        days = request.time_range.get("days", [])
        variables = request.api_params.get("variable", [])
        times = request.api_params.get("time", [])

        lines = [
            "=== 下载请求预览 ===",
            f"数据集: {request.dataset}",
            f"输出文件: {request.filename}",
            f"输出路径: {request.output_path}",
            f"变量: {', '.join(variables)}" if variables else "变量: -",
            f"年份: {years}",
            f"月份: {months}",
            f"日期: {days}" if days else "日期: 全月",
            f"时间: {times}" if times else "时间: -",
            "--------------------",
            f"API参数: {request.api_params}",
        ]
        return "\n".join(lines)

    def _build_single_request(
        self,
        config: DownloadConfig,
        years: List[int],
        months: List[int],
    ) -> DownloadRequest:
        """构建单个拆分后的下载请求。"""
        api_params = self._build_api_params(
            variables=config.variables,
            years=years,
            months=months,
            days=config.days,
            times=config.times,
            pressure_levels=config.pressure_levels,
            area=config.area,
            product_type=config.product_type,
            data_format=config.data_format,
            download_format=config.download_format,
        )

        filename = self._generate_filename(
            years=years,
            months=months,
            variables=config.variables,
            output_format=config.data_format,
        )
        output_path = config.output_dir / filename
        time_range: Dict[str, List] = {
            "years": years,
            "months": months,
            "days": config.days or [],
        }

        return DownloadRequest(
            dataset=config.dataset,
            api_params=api_params,
            output_path=output_path,
            filename=filename,
            time_range=time_range,
        )

    def _build_api_params(
        self,
        variables: List[str],
        years: List[int],
        months: List[int],
        days: Optional[List[int]] = None,
        times: Optional[List[str]] = None,
        pressure_levels: Optional[List[int]] = None,
        area: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """构建CDS API参数。

        该逻辑与CDSClient._build_request保持一致，保证请求结构兼容。
        """
        # product_type 统一转换为列表形式以符合 CDS API 预期格式
        product_type = kwargs.get("product_type", ["reanalysis"])
        if isinstance(product_type, str):
            product_type = [product_type]

        request: Dict[str, Any] = {
            "product_type": product_type,
            "variable": variables,
            "year": [str(y) for y in years],
            "month": [f"{m:02d}" for m in months],
            "data_format": kwargs.get("data_format", "netcdf"),
            "download_format": kwargs.get("download_format", "unarchived"),
        }

        # 日期默认补齐为1-31，与现有CDS客户端行为一致。
        if days is None:
            request["day"] = [f"{d:02d}" for d in range(1, 32)]
        else:
            request["day"] = [f"{d:02d}" for d in days]

        # 时间默认使用4个时次，与现有CDS客户端行为一致。
        if times is None:
            request["time"] = ["00:00", "06:00", "12:00", "18:00"]
        else:
            request["time"] = times

        if pressure_levels is not None:
            request["pressure_level"] = [str(level) for level in pressure_levels]

        if area is not None:
            request["area"] = area

        return request

    def _generate_filename(
        self,
        years: List[int],
        months: List[int],
        variables: List[str],
        output_format: str,
    ) -> str:
        """生成输出文件名。"""
        var_suffix = "_".join(variables[:3])
        year_str = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
        month_str = f"{months[0]:02d}-{months[-1]:02d}" if len(months) > 1 else f"{months[0]:02d}"
        suffix = self._resolve_file_suffix(output_format)
        return f"ERA5_{year_str}_{month_str}_{var_suffix}{suffix}"

    @staticmethod
    def _resolve_file_suffix(output_format: str) -> str:
        """根据输出格式推导文件后缀。"""
        normalized = output_format.lower()
        if normalized == "netcdf":
            return ".nc"
        if normalized == "grib":
            return ".grib"
        return f".{normalized}"
