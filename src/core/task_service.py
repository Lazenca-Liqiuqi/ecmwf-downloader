"""
任务服务模块

统一封装任务创建流程，将下载配置转换为任务并注册到进度管理器。
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from src.core.config import DownloadConfig
from src.core.progress import ProgressManager
from src.core.request_builder import DownloadRequest, RequestBuilder


class TaskService:
    """任务管理服务

    统一的任务创建入口，封装 ProgressManager 和 RequestBuilder。
    """

    def __init__(
        self,
        progress_manager: ProgressManager,
        request_builder: Optional[RequestBuilder] = None,
    ) -> None:
        """初始化任务服务。

        Args:
            progress_manager: 进度管理器实例。
            request_builder: 请求构建器实例，为空时自动创建。
        """
        self.progress_manager = progress_manager
        self.request_builder = request_builder or RequestBuilder()

    def create_single_task(
        self,
        config: DownloadConfig,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建单个下载任务。

        Args:
            config: 下载配置。
            metadata: 额外元数据。

        Returns:
            str: 新创建的任务ID。

        Raises:
            ValueError: 请求参数校验失败时抛出。
        """
        request = self.request_builder.build_request(config)
        self._validate_request_or_raise(request)

        task_id = self._generate_task_id()
        task_metadata = self._build_task_metadata(
            request=request,
            extra_metadata=metadata,
        )
        self.progress_manager.create_task(
            task_id=task_id,
            filename=request.filename,
            metadata=task_metadata,
        )
        return task_id

    def create_batch_tasks(
        self,
        config: DownloadConfig,
        split_strategy: Literal["month", "year", "none"] = "month",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """创建批量下载任务。

        Args:
            config: 下载配置。
            split_strategy: 拆分策略，支持 month/year/none。
            metadata: 额外元数据（应用到每个任务）。

        Returns:
            List[str]: 创建后的任务ID列表。

        Raises:
            ValueError: 请求参数校验失败时抛出。
        """
        requests = self.request_builder.build_batch_requests(config, split_strategy)
        task_ids: List[str] = []

        for request in requests:
            self._validate_request_or_raise(request)
            task_id = self._generate_task_id()
            task_metadata = self._build_task_metadata(
                request=request,
                extra_metadata=metadata,
            )
            self.progress_manager.create_task(
                task_id=task_id,
                filename=request.filename,
                metadata=task_metadata,
            )
            task_ids.append(task_id)

        return task_ids

    def preview_tasks(
        self,
        config: DownloadConfig,
        split_strategy: Literal["month", "year", "none"] = "month",
    ) -> List[Dict[str, Any]]:
        """预览将创建的任务（不实际创建任务）。

        Args:
            config: 下载配置。
            split_strategy: 拆分策略，支持 month/year/none。

        Returns:
            List[Dict[str, Any]]: 任务预览信息列表，每个元素包含：
                - dataset: 数据集
                - filename: 文件名
                - output_path: 输出路径
                - time_range: 时间范围
                - api_params: API参数

        Raises:
            ValueError: 请求参数校验失败时抛出。
        """
        requests = self.request_builder.build_batch_requests(config, split_strategy)
        preview_items: List[Dict[str, Any]] = []

        for request in requests:
            self._validate_request_or_raise(request)
            preview_items.append(
                {
                    "dataset": request.dataset,
                    "filename": request.filename,
                    "output_path": request.output_path,
                    "time_range": request.time_range.copy(),
                    "api_params": request.api_params.copy(),
                }
            )

        return preview_items

    @staticmethod
    def _generate_task_id() -> str:
        """生成任务ID（UUID4）。"""
        return str(uuid.uuid4())

    def _build_task_metadata(
        self,
        request: DownloadRequest,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """构建任务元数据。

        元数据包含下载执行所需参数、时间范围和用户传入扩展字段。

        Args:
            request: 下载请求对象。
            extra_metadata: 用户传入的附加元数据。

        Returns:
            Dict[str, Any]: 合并后的任务元数据。
        """
        metadata: Dict[str, Any] = dict(extra_metadata) if extra_metadata else {}
        metadata["download_params"] = self._build_download_params(request)
        metadata["time_range"] = request.time_range.copy()
        return metadata

    @staticmethod
    def _build_download_params(request: DownloadRequest) -> Dict[str, Any]:
        """构建可直接用于CDSClient.download的参数字典。"""
        api_params = request.api_params
        pressure_levels_raw = api_params.get("pressure_level")
        pressure_levels: Optional[List[int]] = None
        if isinstance(pressure_levels_raw, list):
            pressure_levels = [int(level) for level in pressure_levels_raw]

        days = request.time_range.get("days")
        normalized_days: Optional[List[int]] = days if days else None

        return {
            "dataset": request.dataset,
            "variables": list(api_params.get("variable", [])),
            "years": list(request.time_range.get("years", [])),
            "months": list(request.time_range.get("months", [])),
            "days": normalized_days,
            "times": list(api_params.get("time", [])) or None,
            "pressure_levels": pressure_levels,
            "area": api_params.get("area"),
            "output_path": Path(request.output_path),
            "product_type": api_params.get("product_type", "reanalysis"),
            "grid": api_params.get("grid", [2.5, 2]),
            "data_format": api_params.get("data_format", "netcdf"),
            "download_format": api_params.get("download_format", "unarchived"),
        }

    def _validate_request_or_raise(self, request: DownloadRequest) -> None:
        """校验请求对象，不通过时抛出异常。"""
        is_valid, errors = self.request_builder.validate_request(request)
        if not is_valid:
            error_text = "; ".join(errors)
            raise ValueError(f"下载请求校验失败: {error_text}")
