"""
Schema 服务

封装数据集 Schema 的加载与约束更新操作。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.api.ecmwf_datastores_client import DatastoresService, DatastoresServiceError
from src.core.dataset_schema import DatasetSchema

logger = logging.getLogger(__name__)


@dataclass
class SchemaLoadResult:
    """Schema 加载结果

    Attributes:
        success: 是否成功
        schema: 加载的 Schema 对象（成功时）
        title: Schema 标题（成功时）
        field_count: 字段数量（成功时）
        error: 错误信息（失败时）
    """
    success: bool
    schema: Optional[DatasetSchema] = None
    title: str = ""
    field_count: int = 0
    error: str = ""


class SchemaService:
    """Schema 服务

    封装 DatastoresService 的 Schema 相关操作，提供更友好的接口。

    使用示例:
        service = SchemaService(url, key=key)
        result = service.load_schema("reanalysis-era5-pressure-levels")
        if result.success:
            print(f"加载成功: {result.title}")
    """

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        datastores_service: Optional[DatastoresService] = None,
    ):
        """初始化 Schema 服务

        可以通过两种方式初始化：
        1. 直接传入凭据 (url, key)
        2. 传入已创建的 DatastoresService 实例

        Args:
            url: API URL（可选）
            key: API 密钥（可选）
            datastores_service: 已创建的 DatastoresService 实例（可选）
        """
        if datastores_service is not None:
            self._service = datastores_service
        else:
            self._service = DatastoresService(
                url=url or "https://cds.climate.copernicus.eu/api",
                key=key,
            )

    def load_schema(self, dataset_id: str) -> SchemaLoadResult:
        """加载数据集 Schema

        Args:
            dataset_id: 数据集 ID

        Returns:
            SchemaLoadResult 对象，包含加载结果
        """
        try:
            schema = self._service.get_dataset_schema(dataset_id)
            return SchemaLoadResult(
                success=True,
                schema=schema,
                title=schema.title,
                field_count=len(schema.fields),
            )
        except DatastoresServiceError as e:
            return SchemaLoadResult(
                success=False,
                error=str(e),
            )
        except Exception as e:
            return SchemaLoadResult(
                success=False,
                error=f"未知错误: {str(e)}",
            )

    def apply_constraints(
        self,
        collection_id: str,
        selection: Dict[str, List[Any]],
    ) -> Dict[str, List[str]]:
        """应用约束获取更新后的字段可选值

        根据当前选择更新其他字段的可选值。

        Args:
            collection_id: 数据集 ID
            selection: 当前选择的字段-值映射

        Returns:
            更新后的字段可选值映射
        """
        try:
            return self._service.apply_constraints(collection_id, selection)
        except DatastoresServiceError as e:
            # 约束更新失败时返回空字典，不阻塞用户操作，但需要可观测性
            logger.warning("约束更新失败（DatastoresServiceError）: %s", e)
            return {}
        except Exception:
            logger.exception("约束更新异常（未知错误）")
            return {}

    @property
    def service(self) -> DatastoresService:
        """获取底层的 DatastoresService 实例"""
        return self._service
