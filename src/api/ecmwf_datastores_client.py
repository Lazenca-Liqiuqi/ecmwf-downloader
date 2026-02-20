"""
ECMWF Datastores 客户端服务层

封装 ecmwf-datastores-client 官方库，提供数据集 Schema 获取和约束计算功能。
"""

import logging
from typing import Any, Dict, List, Optional

from src.core.dataset_schema import (
    DatasetSchema,
    FormFieldDefinition,
)

logger = logging.getLogger(__name__)


class DatastoresServiceError(Exception):
    """Datastores 服务异常"""

    pass


class DatastoresService:
    """ECMWF Datastores 服务层

    封装 ecmwf-datastores-client 库，提供以下功能：
    1. 获取数据集 Schema（字段定义和初始约束）
    2. 应用约束计算（根据已选值更新其他字段的可选值）

    使用方式：
        service = DatastoresService(url, key)
        schema = service.get_dataset_schema("reanalysis-era5-pressure-levels")
        constraints = service.apply_constraints("reanalysis-era5-pressure-levels", {"year": "2000"})
    """

    def __init__(
        self,
        url: str = "https://cds.climate.copernicus.eu/api",
        key: Optional[str] = None,
    ):
        """初始化 Datastores 服务

        Args:
            url: API 地址
            key: API 密钥（UUID 格式）
        """
        self.url = url
        self.key = key
        self._client = None

    def _get_client(self):
        """获取或创建 ecmwf-datastores 客户端

        延迟初始化，只在首次使用时创建客户端。

        Returns:
            Client: ecmwf-datastores 客户端实例

        Raises:
            DatastoresServiceError: 客户端初始化失败
        """
        if self._client is not None:
            return self._client

        try:
            from ecmwf.datastores import Client

            # 构建完整的 key 字符串
            # 直接使用 key（UUID 格式）；如果为 None，客户端会尝试从配置文件读取
            full_key = self.key or None

            # 创建客户端，提供 url 避免 FileNotFoundError
            self._client = Client(
                url=self.url,
                key=full_key,  # 如果为 None，客户端会尝试从配置文件读取
            )

            logger.info("ECMWF Datastores 客户端初始化成功")
            return self._client

        except ImportError:
            raise DatastoresServiceError(
                "ecmwf-datastores-client 未安装，请运行: pip install ecmwf-datastores-client"
            )
        except FileNotFoundError as e:
            raise DatastoresServiceError(
                "未找到 API 配置文件。请配置 ECMWF 凭据：\n"
                "1. 创建 ~/.ecmwfdatastoresrc 文件，内容格式：\n"
                "   url: https://cds.climate.copernicus.eu/api\n"
                "   key: your-api-key\n"
                "2. 或设置环境变量 ECMWF_DATASTORES_URL 和 ECMWF_DATASTORES_KEY"
            )
        except Exception as e:
            raise DatastoresServiceError(f"初始化客户端失败: {str(e)}")

    def check_connection(self) -> bool:
        """检查 API 连接状态

        Returns:
            bool: 连接正常返回 True，否则返回 False
        """
        try:
            client = self._get_client()
            # 尝试获取集合列表来验证连接
            _ = client.get_collections(limit=1)
            return True
        except Exception as e:
            logger.error(f"连接检查失败: {str(e)}")
            return False

    def get_available_datasets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取可用的数据集列表

        Args:
            limit: 最大返回数量

        Returns:
            List[Dict[str, Any]]: 数据集信息列表，每个元素包含 id, title, description
        """
        try:
            client = self._get_client()
            collections = client.get_collections(limit=limit)

            datasets = []
            for collection in collections:
                datasets.append({
                    "id": collection.id,
                    "title": getattr(collection, "title", collection.id),
                    "description": getattr(collection, "description", ""),
                })

            return datasets

        except Exception as e:
            logger.error(f"获取数据集列表失败: {str(e)}")
            return []

    def get_dataset_schema(self, collection_id: str) -> DatasetSchema:
        """获取数据集 Schema

        内部调用：
        - collection = client.get_collection(collection_id)
        - 解析 collection 的 form 和 constraints

        Args:
            collection_id: 数据集 ID（如 "reanalysis-era5-pressure-levels"）

        Returns:
            DatasetSchema: 数据集 Schema 对象

        Raises:
            DatastoresServiceError: 获取 Schema 失败
        """
        try:
            client = self._get_client()
            collection = client.get_collection(collection_id)

            # 获取集合基本信息
            title = getattr(collection, "title", collection_id)
            description = getattr(collection, "description", "")

            # 解析字段定义
            fields = self._parse_collection_fields(collection)

            # 获取初始约束值
            constraints = self._get_initial_constraints(collection)

            schema = DatasetSchema(
                collection_id=collection_id,
                title=title,
                description=description,
                fields=fields,
                constraints=constraints,
            )

            logger.info(f"成功获取数据集 Schema: {collection_id}, 字段数: {len(fields)}")
            return schema

        except Exception as e:
            logger.error(f"获取数据集 Schema 失败: {str(e)}")
            raise DatastoresServiceError(f"获取数据集 Schema 失败: {str(e)}")

    def apply_constraints(
        self,
        collection_id: str,
        current_selection: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """应用约束，获取更新后的可选值

        根据当前选择的值，计算其他字段的可选值范围。

        示例：
        >>> apply_constraints("era5", {"year": "2000", "month": "02"})
        {"day": ["01", ..., "29"], "variable": [...], ...}

        Args:
            collection_id: 数据集 ID
            current_selection: 当前选择的字段和值

        Returns:
            Dict[str, List[str]]: 更新后的约束值字典

        Raises:
            DatastoresServiceError: 约束计算失败
        """
        try:
            client = self._get_client()

            # 转换选择值为字符串格式
            formatted_selection = self._format_selection(current_selection)

            # 调用 API 获取约束
            result = client.apply_constraints(collection_id, formatted_selection)

            # 解析结果
            constraints = self._parse_constraints_result(result)

            logger.debug(
                f"约束计算完成: collection={collection_id}, "
                f"selection={current_selection}, "
                f"updated_fields={list(constraints.keys())}"
            )
            return constraints

        except Exception as e:
            logger.error(f"约束计算失败: {str(e)}")
            raise DatastoresServiceError(f"约束计算失败: {str(e)}")

    def _parse_collection_fields(self, collection) -> List[FormFieldDefinition]:
        """解析集合的字段定义

        从 collection 对象中提取字段信息。

        Args:
            collection: 集合对象

        Returns:
            List[FormFieldDefinition]: 字段定义列表
        """
        fields = []

        # 尝试从 collection.form 获取字段
        if hasattr(collection, "form"):
            form = collection.form
            if isinstance(form, list):
                for field_data in form:
                    if isinstance(field_data, dict):
                        field_name = field_data.get("name", "")
                        if field_name:
                            field_def = FormFieldDefinition.from_api_field(
                                field_name, field_data
                            )
                            fields.append(field_def)
            elif isinstance(form, dict):
                # form 可能是一个字典
                for field_name, field_data in form.items():
                    if isinstance(field_data, dict):
                        field_def = FormFieldDefinition.from_api_field(
                            field_name, field_data
                        )
                        fields.append(field_def)

        # 尝试从 collection.json 获取字段
        if not fields and hasattr(collection, "json"):
            json_data = collection.json
            if isinstance(json_data, dict):
                # 查找 form 或 request 字段
                form_data = json_data.get("form", json_data.get("request", {}))
                if isinstance(form_data, dict):
                    # 可能是 properties 或 fields
                    properties = form_data.get("properties", form_data.get("fields", {}))
                    for field_name, field_data in properties.items():
                        if isinstance(field_data, dict):
                            field_def = FormFieldDefinition.from_api_field(
                                field_name, field_data
                            )
                            fields.append(field_def)

        # 如果无法解析，创建默认字段
        if not fields:
            logger.warning(f"无法从 collection 解析字段，使用默认字段")
            fields = self._get_default_fields()

        return fields

    def _get_initial_constraints(self, collection) -> Dict[str, List[str]]:
        """获取初始约束值

        从 collection 对象中提取初始可选值。
        优先从 constraints 获取，然后从 form.details.values 补充。

        Args:
            collection: 集合对象

        Returns:
            Dict[str, List[str]]: 初始约束值字典
        """
        constraints = {}

        # 1. 尝试从 collection.constraints 获取
        if hasattr(collection, "constraints"):
            collection_constraints = collection.constraints
            # constraints 可能是列表格式（每个元素是一个包含多个字段约束的字典）
            # 需要合并所有约束组合中的值，而不是覆盖
            if isinstance(collection_constraints, list):
                for constraint_item in collection_constraints:
                    if isinstance(constraint_item, dict):
                        for field_name, values in constraint_item.items():
                            if isinstance(values, list):
                                # 合并值而不是覆盖，去重并保持顺序
                                str_values = [str(v) for v in values]
                                if field_name not in constraints:
                                    constraints[field_name] = str_values
                                else:
                                    # 合并并去重，保持原始顺序
                                    existing = set(constraints[field_name])
                                    for v in str_values:
                                        if v not in existing:
                                            constraints[field_name].append(v)
                                            existing.add(v)
            elif isinstance(collection_constraints, dict):
                constraints.update(collection_constraints)

        # 2. 从 form.details.values 补充（获取 constraints 中没有的字段值）
        # 某些字段（如 data_format, download_format）的值在 form 中，不在 constraints 中
        if hasattr(collection, "form"):
            form = collection.form
            if isinstance(form, list):
                for field_data in form:
                    if isinstance(field_data, dict):
                        field_name = field_data.get("name", "")
                        if field_name and field_name not in constraints:
                            details = field_data.get("details", {})
                            values = self._extract_widget_values(field_data)
                            if values:
                                constraints[field_name] = [str(v) for v in values]

        # 3. 尝试从 collection.json 获取（作为后备）
        if not constraints and hasattr(collection, "json"):
            json_data = collection.json
            if isinstance(json_data, dict):
                # 查找 constraints
                json_constraints = json_data.get("constraints", {})
                if isinstance(json_constraints, dict):
                    constraints.update(json_constraints)

        return constraints

    @staticmethod
    def _extract_widget_values(field_data: Dict[str, Any]) -> List[str]:
        """从 form 字段定义中提取可选值列表（作为 constraints 的补充来源）。

        目标：
        - 兼容部分控件不提供 details.values 的情况（如 LicenceWidget/ExclusiveGroupWidget）
        - 在缺失时尽量从 schema.enum / schema.oneOf 中提取

        约定：
        - 返回字符串列表；调用方负责进一步 str() 归一化
        """
        if not isinstance(field_data, dict):
            return []

        widget_type = str(field_data.get("type", "")).lower()
        details = field_data.get("details", {}) if isinstance(field_data.get("details", {}), dict) else {}
        schema = field_data.get("schema", {}) if isinstance(field_data.get("schema", {}), dict) else {}

        # 1) 最常见：details.values
        values = details.get("values")
        if isinstance(values, list) and values:
            return [str(v) for v in values if v is not None]

        # 2) LicenceWidget：details.licences[*].id
        if "licence" in widget_type or "license" in widget_type:
            licences = details.get("licences", [])
            if isinstance(licences, list):
                ids: List[str] = []
                for lic in licences:
                    if isinstance(lic, dict) and lic.get("id"):
                        ids.append(str(lic["id"]))
                return ids

        # 3) ExclusiveGroupWidget：尽量从 details/options/choices 或 schema 提取
        if "exclusivegroup" in widget_type:
            for key in ("options", "choices", "items"):
                raw = details.get(key)
                if isinstance(raw, list) and raw:
                    # 既支持 ["global","area"] 也支持 [{"id":"global","label":"..."}]
                    if all(isinstance(x, dict) for x in raw):
                        ids = [str(x.get("id")) for x in raw if isinstance(x, dict) and x.get("id")]
                        if ids:
                            return ids
                    return [str(x) for x in raw if x is not None]
                if isinstance(raw, dict) and raw:
                    return [str(k) for k in raw.keys()]

        # 4) schema.enum
        enum_vals = schema.get("enum")
        if isinstance(enum_vals, list) and enum_vals:
            return [str(v) for v in enum_vals if v is not None]

        # 5) schema.oneOf / anyOf：提取 const/enum
        for key in ("oneOf", "anyOf"):
            variants = schema.get(key)
            if isinstance(variants, list) and variants:
                extracted: List[str] = []
                for item in variants:
                    if not isinstance(item, dict):
                        continue
                    if "const" in item and item["const"] is not None:
                        extracted.append(str(item["const"]))
                    enum2 = item.get("enum")
                    if isinstance(enum2, list):
                        extracted.extend(str(v) for v in enum2 if v is not None)
                # 去重保持顺序
                if extracted:
                    seen = set()
                    result: List[str] = []
                    for v in extracted:
                        if v not in seen:
                            seen.add(v)
                            result.append(v)
                    return result

        return []

    def _format_selection(self, selection: Dict[str, Any]) -> Dict[str, Any]:
        """格式化选择值为 API 预期格式

        Args:
            selection: 原始选择值

        Returns:
            Dict[str, Any]: 格式化后的选择值
        """
        formatted = {}
        for key, value in selection.items():
            if isinstance(value, list):
                formatted[key] = [str(v) for v in value]
            else:
                formatted[key] = str(value)
        return formatted

    def _parse_constraints_result(self, result: Any) -> Dict[str, List[str]]:
        """解析约束计算结果

        Args:
            result: API 返回的约束结果

        Returns:
            Dict[str, List[str]]: 解析后的约束字典
        """
        constraints = {}

        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, list):
                    constraints[key] = [str(v) for v in value]
                elif isinstance(value, dict) and "values" in value:
                    constraints[key] = [str(v) for v in value["values"]]
                else:
                    constraints[key] = [str(value)]

        return constraints

    def _get_default_fields(self) -> List[FormFieldDefinition]:
        """获取默认字段定义

        当无法从 API 解析时使用。

        Returns:
            List[FormFieldDefinition]: 默认字段列表
        """
        default_fields = [
            {"name": "product_type", "label": "产品类型", "required": True},
            {"name": "variable", "label": "变量列表", "required": True},
            {"name": "year", "label": "年份", "required": True},
            {"name": "month", "label": "月份", "required": True},
            {"name": "day", "label": "日期", "required": False},
            {"name": "time", "label": "时间点", "required": False},
            {"name": "pressure_level", "label": "气压层", "required": False},
            {"name": "area", "label": "区域范围", "required": False},
            {"name": "data_format", "label": "数据格式", "required": False},
            {"name": "download_format", "label": "下载格式", "required": False},
        ]

        from src.core.dataset_schema import FieldType

        return [
            FormFieldDefinition(
                name=f["name"],
                label=f["label"],
                field_type=FieldType.STRING_ARRAY,
                required=f["required"],
            )
            for f in default_fields
        ]
