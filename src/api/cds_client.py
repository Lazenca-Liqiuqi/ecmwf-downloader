"""
CDS API客户端实现

基于cdsapi库实现ECMWF Climate Data Store的API客户端。
"""

import os
import socket
import urllib3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import cdsapi

from src.api.base import BaseAPIClient
from src.core.exceptions import APIError

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CDSClient(BaseAPIClient):
    """CDS API客户端实现

    实现ECMWF Climate Data Store的API调用，支持ERA5等数据集下载。

    使用cdsapi库作为底层HTTP客户端。
    """

    # CDS API支持的ERA5数据集
    AVAILABLE_DATASETS = [
        "reanalysis-era5-pressure-levels",
        "reanalysis-era5-single-levels",
        "reanalysis-era5-land",
        "reanalysis-era5-land-monthly-means",
        "reanalysis-era5-monthly-means",
    ]

    # ERA5 pressure levels 常用变量
    PRESSURE_LEVELS_VARIABLES = [
        "u_component_of_wind",
        "v_component_of_wind",
        "temperature",
        "geopotential",
        "relative_humidity",
        "specific_humidity",
        "vertical_velocity",
        "divergence",
        "vorticity",
    ]

    # 默认气压层列表（hPa）
    DEFAULT_PRESSURE_LEVELS = [
        1, 2, 3, 5, 7, 10, 20, 30, 50, 70, 100, 125, 150, 175, 200,
        225, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750,
        775, 800, 825, 850, 875, 900, 925, 950, 975, 1000
    ]

    def __init__(self, account_info: Optional[Dict[str, Any]] = None):
        """初始化CDS客户端

        Args:
            account_info: 账号信息字典，必须包含：
                - email: 账号邮箱（用于显示标识，必填）
                - key: API密钥（UUID格式，必填）
                - url: API端点URL（可选，默认为CDS官方地址）
        """
        super().__init__(account_info)

        if not account_info or "key" not in account_info:
            raise ValueError("account_info必须包含key字段")
        if "email" not in account_info:
            raise ValueError("account_info必须包含email字段")

        self.email = account_info["email"]
        self.key = account_info["key"]
        self.url = account_info.get("url", "https://cds.climate.copernicus.eu/api")

        # 禁用代理（避免CDS API的代理检测问题）
        self._disable_proxy()

        # 创建cdsapi客户端（延迟创建，支持账号切换）
        self._client: Optional[cdsapi.Client] = None

    def _disable_proxy(self) -> None:
        """禁用系统代理设置

        CDS API不支持代理访问，需要清除所有代理环境变量。
        """
        os.environ["HTTP_PROXY"] = ""
        os.environ["HTTPS_PROXY"] = ""
        os.environ["NO_PROXY"] = "*"

    def _get_client(self) -> cdsapi.Client:
        """获取或创建cdsapi客户端实例

        Returns:
            cdsapi.Client: cdsapi客户端实例
        """
        if self._client is None:
            self._client = cdsapi.Client(
                url=self.url,
                key=self.key,
                timeout=1800,  # 30分钟超时
                verify=True,  # 启用SSL验证
            )
            # 设置socket超时
            socket.setdefaulttimeout(1800)
        return self._client

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
        output_path: Optional[Union[Path, str]] = None,
        **kwargs,
    ) -> Path:
        """下载数据到本地文件

        Args:
            dataset: 数据集标识符（如 "reanalysis-era5-pressure-levels"）
            variables: 要下载的变量列表（如 ["u_component_of_wind"]）
            years: 年份列表（如 [2020, 2021]）
            months: 月份列表（如 [1, 2, 3]）
            days: 日期列表（可选，如 [1, 15]）
            times: 时间点列表（可选，如 ["00:00", "12:00"]）
            pressure_levels: 气压层列表（可选，如 [500, 850, 1000]）
            area: 区域范围 [N, W, S, E]（可选）
            output_path: 输出文件路径（可选，支持Path或字符串，默认自动生成）
            **kwargs: 其他参数（data_format, download_format, product_type 等）

        Returns:
            Path: 下载文件的路径

        Raises:
            APIError: 下载失败时抛出
        """
        # 构建CDS API请求参数
        request = self._build_request(
            variables=variables,
            years=years,
            months=months,
            days=days,
            times=times,
            pressure_levels=pressure_levels,
            area=area,
            **kwargs,
        )

        # 生成输出文件路径
        if output_path is None:
            output_path = self._generate_output_path(dataset, years, months, variables)
        elif isinstance(output_path, str):
            output_path = Path(output_path)

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            client = self._get_client()

            # 执行下载
            result = client.retrieve(dataset, request)
            result.download(str(output_path))

            return output_path

        except Exception as e:
            # 解析并包装异常
            self._handle_error(e, dataset, request)
            # 上面会抛出APIError，这里不会执行到
            raise APIError(f"下载失败: {str(e)}")  # pragma: no cover

    def _build_request(
        self,
        variables: List[str],
        years: List[int],
        months: List[int],
        days: Optional[List[int]] = None,
        times: Optional[List[str]] = None,
        pressure_levels: Optional[List[int]] = None,
        area: Optional[List[float]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """构建CDS API请求参数

        Args:
            variables: 变量列表
            years: 年份列表
            months: 月份列表
            days: 日期列表（可选）
            times: 时间点列表（可选）
            pressure_levels: 气压层列表（可选）
            area: 区域范围（可选）
            **kwargs: 其他参数

        Returns:
            Dict[str, Any]: CDS API请求字典
        """
        request = {
            "product_type": kwargs.get("product_type", "reanalysis"),
            "variable": variables,
            "year": [str(y) for y in years],
            "month": [f"{m:02d}" for m in months],
            "data_format": kwargs.get("data_format", "netcdf"),
            "download_format": kwargs.get("download_format", "unarchived"),
        }

        # 添加日期（默认所有天）
        if days is None:
            request["day"] = [f"{d:02d}" for d in range(1, 32)]
        else:
            request["day"] = [f"{d:02d}" for d in days]

        # 添加时间点（默认4个时间点）
        if times is None:
            request["time"] = ["00:00", "06:00", "12:00", "18:00"]
        else:
            request["time"] = times

        # 添加气压层（如果提供）
        if pressure_levels is not None:
            request["pressure_level"] = [str(level) for level in pressure_levels]

        # 添加区域范围（如果提供）
        if area is not None:
            request["area"] = area

        # 添加网格分辨率（如果提供）
        if "grid" in kwargs and kwargs.get("grid") is not None:
            request["grid"] = kwargs["grid"]

        return request

    def _generate_output_path(
        self, dataset: str, years: List[int], months: List[int], variables: List[str]
    ) -> Path:
        """生成输出文件路径

        Args:
            dataset: 数据集标识符
            years: 年份列表
            months: 月份列表
            variables: 变量列表

        Returns:
            Path: 生成的文件路径
        """
        # 生成文件名
        var_suffix = "_".join(variables[:3])  # 最多取前3个变量
        year_str = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
        month_str = f"{months[0]:02d}-{months[-1]:02d}" if len(months) > 1 else f"{months[0]:02d}"

        filename = f"ERA5_{year_str}_{month_str}_{var_suffix}.nc"

        # 默认输出到当前目录
        return Path(filename)

    def check_connection(self) -> bool:
        """检查API连接状态

        尝试调用CDS API验证凭据是否有效。

        Returns:
            bool: 连接正常返回True，否则返回False

        Raises:
            APIError: 连接检查失败时抛出
        """
        try:
            client = self._get_client()

            # 尝试获取API状态（简单请求）
            # CDS没有专门的ping接口，这里用一个小请求测试
            client.session.get(f"{self.url}/tasks/")

            return True

        except Exception as e:
            raise APIError(
                f"API连接检查失败: {str(e)}",
                status_code=getattr(e, "status_code", None),
                response_body=str(e),
            )

    def get_available_datasets(self) -> List[str]:
        """获取该数据源支持的数据集列表

        Returns:
            List[str]: 可用数据集的标识符列表
        """
        return self.AVAILABLE_DATASETS.copy()

    def get_dataset_variables(self, dataset: str) -> List[str]:
        """获取指定数据集支持的变量列表

        Args:
            dataset: 数据集标识符

        Returns:
            List[str]: 可用变量的标识符列表

        Raises:
            APIError: 获取变量列表失败时抛出
        """
        # 根据数据集类型返回变量列表
        if "pressure-levels" in dataset:
            return self.PRESSURE_LEVELS_VARIABLES.copy()
        elif "single-levels" in dataset:
            # 单层变量（示例）
            return [
                "10m_u_component_of_wind",
                "10m_v_component_of_wind",
                "2m_temperature",
                "total_precipitation",
                "mean_sea_level_pressure",
            ]
        else:
            raise APIError(f"暂不支持数据集: {dataset}")

    def get_request_info(self, dataset: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取下载请求的元信息

        CDS API不直接提供预估文件大小，此方法返回基本信息。

        Args:
            dataset: 数据集标识符
            params: 请求参数字典

        Returns:
            Dict[str, Any]: 包含请求信息的字典
        """
        return {
            "dataset": dataset,
            "size": None,  # CDS API不提供预估大小
            "estimated_time": None,  # CDS API不提供预估时间
            "requires_otp": False,
            "pending": False,
            "params": params,
        }

    def _handle_error(self, error: Exception, dataset: str, request: Dict[str, Any]) -> None:
        """统一错误处理

        解析CDS API异常并抛出相应的APIError。

        Args:
            error: 原始异常对象
            dataset: 数据集标识符
            request: 请求参数字典

        Raises:
            APIError: 包装后的API异常
        """
        error_msg = str(error)
        status_code = None

        # 解析HTTP状态码
        if hasattr(error, "status_code"):
            status_code = error.status_code

        # 解析常见错误
        if "401" in error_msg or "Unauthorized" in error_msg:
            raise APIError(
                "API认证失败：请检查key是否正确",
                status_code=status_code,
                response_body=error_msg,
            )
        elif "403" in error_msg or "Forbidden" in error_msg:
            raise APIError(
                "API访问被拒绝：请检查账号是否有权限访问此数据集",
                status_code=status_code,
                response_body=error_msg,
            )
        elif "404" in error_msg or "not found" in error_msg.lower():
            raise APIError(
                f"数据集不存在：{dataset}",
                status_code=status_code,
                response_body=error_msg,
            )
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            raise APIError(
                "请求超时：网络连接不稳定或服务器响应缓慢",
                status_code=status_code,
                response_body=error_msg,
            )
        elif "connection" in error_msg.lower():
            raise APIError(
                "网络连接失败：请检查网络设置",
                status_code=status_code,
                response_body=error_msg,
            )
        else:
            # 通用错误
            raise APIError(
                f"CDS API调用失败：{error_msg}",
                status_code=status_code,
                response_body=error_msg,
            )

    def __repr__(self) -> str:
        """返回客户端的字符串表示"""
        mask_key = f"{self.key[:4]}...{self.key[-4:]}" if self.key else "unknown"
        return f"CDSClient(email={self.email}, key={mask_key})"
