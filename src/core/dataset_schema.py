"""
数据集 Schema 数据模型

定义动态表单所需的数据结构，包括字段定义、约束值和表单状态管理。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FieldType(str, Enum):
    """表单字段类型枚举"""

    STRING_SINGLE = "string_single"      # 单选字符串（下拉框）
    STRING_ARRAY = "string_array"        # 多选字符串（复选框/输入框）
    INTEGER_SINGLE = "integer_single"    # 单选整数
    INTEGER_ARRAY = "integer_array"      # 多选整数
    FLOAT_ARRAY = "float_array"          # 浮点数数组（如区域范围）
    BOOLEAN = "boolean"                  # 布尔开关（如 global）
    EXCLUSIVE_GROUP = "exclusive_group"  # 排他分组（如 area_group）
    GEO_EXTENT = "geo_extent"            # 地理范围（N, W, S, E）
    LICENCE = "licence"                  # 许可证确认/选择
    STRING = "string"                    # 普通字符串输入
    UNKNOWN = "unknown"                  # 未知类型


@dataclass
class FormFieldDefinition:
    """从 collection API 获取的字段定义

    存储数据集字段的元信息，包括名称、类型、是否必填等。
    """

    name: str                    # API 字段名（如 "variable", "year"）
    label: str                   # 显示标签（中文描述）
    field_type: FieldType        # 字段类型
    required: bool = False       # 是否必填
    details: Dict[str, Any] = field(default_factory=dict)  # 原始详细信息

    @classmethod
    def from_api_field(cls, field_name: str, field_data: Dict[str, Any]) -> "FormFieldDefinition":
        """从 API 返回的字段数据创建定义对象

        Args:
            field_name: 字段名称
            field_data: API 返回的字段详情

        Returns:
            FormFieldDefinition: 解析后的字段定义
        """
        # 解析字段类型
        field_type = cls._parse_field_type(field_data)

        # 生成中文标签
        label = cls._generate_label(field_name)

        # 解析是否必填
        required = field_data.get("required", False)

        return cls(
            name=field_name,
            label=label,
            field_type=field_type,
            required=required,
            details=field_data,
        )

    @staticmethod
    def _parse_field_type(field_data: Dict[str, Any]) -> FieldType:
        """解析字段类型

        根据 API 返回的字段结构判断字段类型。
        """
        # 获取字段的 schema 或 type 信息
        schema = field_data.get("schema", {})
        widget_type = field_data.get("type", "")
        value_type = schema.get("type", "")

        # 根据 widget 类型判断（支持多种命名格式）
        widget_type_lower = widget_type.lower()

        # 优先识别特殊控件（避免被 single/list 等通用规则误判）
        if "geographicextent" in widget_type_lower:
            return FieldType.GEO_EXTENT
        if "freeedition" in widget_type_lower:
            return FieldType.BOOLEAN
        if "exclusivegroup" in widget_type_lower:
            return FieldType.EXCLUSIVE_GROUP
        if "licence" in widget_type_lower or "license" in widget_type_lower:
            return FieldType.LICENCE

        # StringListWidget / StringArrayWidget -> STRING_ARRAY
        if "stringlist" in widget_type_lower or "stringarray" in widget_type_lower:
            return FieldType.STRING_ARRAY
        # StringSelectionWidget / StringSingleWidget -> STRING_SINGLE
        if "stringselection" in widget_type_lower or "stringsingle" in widget_type_lower:
            return FieldType.STRING_SINGLE
        # IntegerListWidget / IntegerArrayWidget -> INTEGER_ARRAY
        if "integerlist" in widget_type_lower or "integerarray" in widget_type_lower:
            return FieldType.INTEGER_ARRAY
        # IntegerSelectionWidget / IntegerSingleWidget -> INTEGER_SINGLE
        if "integerselection" in widget_type_lower or "integersingle" in widget_type_lower:
            return FieldType.INTEGER_SINGLE
        # 包含 "multi" 或 "list" 的通常是数组类型
        if "multi" in widget_type_lower or "list" in widget_type_lower:
            return FieldType.STRING_ARRAY
        if "single" in widget_type_lower or "selection" in widget_type_lower:
            return FieldType.STRING_SINGLE

        # 根据 value type 判断
        if value_type == "array":
            items_type = schema.get("items", {}).get("type", "")
            if items_type == "integer":
                return FieldType.INTEGER_ARRAY
            return FieldType.STRING_ARRAY
        if value_type == "boolean":
            return FieldType.BOOLEAN
        if value_type == "object":
            # GeographicExtentWidget 往往是对象结构（n/e/s/w）
            properties = schema.get("properties", {})
            if isinstance(properties, dict) and {"n", "s", "e", "w"}.issubset(set(properties.keys())):
                return FieldType.GEO_EXTENT
        if value_type == "string":
            return FieldType.STRING_SINGLE
        if value_type == "integer":
            return FieldType.INTEGER_SINGLE
        if value_type == "number":
            return FieldType.FLOAT_ARRAY

        # 根据 details.values 判断（如果有值列表，默认为字符串数组）
        details = field_data.get("details", {})
        if details.get("values"):
            return FieldType.STRING_ARRAY
        if details.get("licences"):
            return FieldType.LICENCE

        return FieldType.STRING_ARRAY  # 默认为字符串数组

    @staticmethod
    def _generate_label(field_name: str) -> str:
        """生成字段的中文标签

        Args:
            field_name: 字段名称

        Returns:
            str: 中文标签
        """
        label_mapping = {
            "variable": "变量列表",
            "year": "年份",
            "month": "月份",
            "day": "日期",
            "time": "时间点",
            "pressure_level": "气压层",
            "product_type": "产品类型",
            "data_format": "数据格式",
            "download_format": "下载格式",
            "area": "区域范围",
            "area_group": "区域模式",
            "global": "全球范围",
            "licences": "许可证",
            "grid": "网格分辨率",
            "levtype": "层级类型",
            "step": "时间步长",
            "type": "数据类型",
            "stream": "数据流",
            "class": "数据类别",
            "expver": "版本号",
            "param": "参数",
            "frequency": "频率",
            "origin": "来源",
            "system": "系统",
            "method": "方法",
        }
        return label_mapping.get(field_name, field_name)


@dataclass
class DatasetSchema:
    """完整的数据集 Schema

    包含数据集的基本信息和所有字段的定义。
    """

    collection_id: str                             # 数据集 ID
    title: str                                     # 数据集标题
    description: str = ""                          # 数据集描述
    fields: List[FormFieldDefinition] = field(default_factory=list)  # 字段定义列表
    constraints: Dict[str, List[str]] = field(default_factory=dict)  # 初始约束值

    def get_field(self, field_name: str) -> Optional[FormFieldDefinition]:
        """获取指定字段的定义

        Args:
            field_name: 字段名称

        Returns:
            Optional[FormFieldDefinition]: 字段定义，不存在则返回 None
        """
        for f in self.fields:
            if f.name == field_name:
                return f
        return None

    def get_required_fields(self) -> List[FormFieldDefinition]:
        """获取所有必填字段

        Returns:
            List[FormFieldDefinition]: 必填字段列表
        """
        return [f for f in self.fields if f.required]

    def get_field_names(self) -> List[str]:
        """获取所有字段名

        Returns:
            List[str]: 字段名列表
        """
        return [f.name for f in self.fields]


@dataclass
class DynamicFormField:
    """动态表单字段（UI 渲染用）

    存储字段的当前状态，包括可选值、已选值和加载状态。
    """

    definition: FormFieldDefinition        # 字段定义
    values: List[str] = field(default_factory=list)       # 当前可选值
    selected: List[Any] = field(default_factory=list)     # 当前选中值
    is_loading: bool = False              # 是否正在加载

    @property
    def name(self) -> str:
        """字段名称"""
        return self.definition.name

    @property
    def label(self) -> str:
        """字段标签"""
        return self.definition.label

    @property
    def field_type(self) -> FieldType:
        """字段类型"""
        return self.definition.field_type

    @property
    def required(self) -> bool:
        """是否必填"""
        return self.definition.required

    def set_values(self, values: List[str]) -> None:
        """设置可选值

        同时清理已选值中不在新可选值列表中的项。

        Args:
            values: 新的可选值列表
        """
        self.values = values
        # 清理已选值
        # 当 API 没有提供可选值列表时，不应误删用户输入（如自由输入/地理范围/布尔开关等）。
        if self.selected and self.values:
            self.selected = [v for v in self.selected if str(v) in values]

    def set_selected(self, selected: List[Any]) -> None:
        """设置选中值

        Args:
            selected: 新的选中值列表
        """
        self.selected = selected

    def clear(self) -> None:
        """清空选中值"""
        self.selected = []


@dataclass
class DynamicFormState:
    """动态表单状态管理

    管理整个动态表单的状态，包括数据集信息和所有字段状态。
    """

    collection_id: str = ""                                        # 数据集 ID
    schema: Optional[DatasetSchema] = None                         # 数据集 Schema
    fields: Dict[str, DynamicFormField] = field(default_factory=dict)  # 字段状态字典
    is_schema_loaded: bool = False                                 # Schema 是否已加载
    output_dir: str = "./data/downloads"                           # 输出目录
    split_strategy: str = "month"                                  # 拆分策略

    def get_field(self, field_name: str) -> Optional[DynamicFormField]:
        """获取指定字段的状态

        Args:
            field_name: 字段名称

        Returns:
            Optional[DynamicFormField]: 字段状态，不存在则返回 None
        """
        return self.fields.get(field_name)

    def set_field_selection(self, field_name: str, selected: List[Any]) -> None:
        """设置字段的选中值

        Args:
            field_name: 字段名称
            selected: 选中值列表
        """
        if field_name in self.fields:
            self.fields[field_name].set_selected(selected)

    def get_current_selection(self) -> Dict[str, Any]:
        """获取当前选择，用于 apply_constraints

        只包含有选中值的字段。

        Returns:
            Dict[str, Any]: 当前选择的字典
        """
        selection = {}
        for name, field in self.fields.items():
            if field.selected:
                # 单值字段取第一个，多值字段保持列表
                if field.field_type in (
                    FieldType.STRING_SINGLE,
                    FieldType.INTEGER_SINGLE,
                    FieldType.BOOLEAN,
                    FieldType.EXCLUSIVE_GROUP,
                ):
                    selection[name] = str(field.selected[0])
                else:
                    selection[name] = [str(v) for v in field.selected]
        return selection

    def to_download_config_dict(self) -> Dict[str, Any]:
        """转换为 DownloadConfig 参数

        字段名映射：
        - variable -> variables
        - year -> years
        - month -> months
        - day -> days
        - time -> times
        - pressure_level -> pressure_levels

        Returns:
            Dict[str, Any]: DownloadConfig 构造参数
        """
        # 字段名映射（API 字段名 -> DownloadConfig 字段名）
        field_mapping = {
            "variable": "variables",
            "year": "years",
            "month": "months",
            "day": "days",
            "time": "times",
            "pressure_level": "pressure_levels",
            "product_type": "product_type",
            "area": "area",
            "data_format": "data_format",
            "download_format": "download_format",
        }

        config_dict: Dict[str, Any] = {
            "dataset": self.collection_id,
            "output_dir": self.output_dir,
        }

        for api_name, config_name in field_mapping.items():
            field = self.get_field(api_name)
            if field and field.selected:
                # 类型转换
                value = self._convert_value(field)
                if value is not None:
                    config_dict[config_name] = value

        return config_dict

    @staticmethod
    def _convert_value(field: DynamicFormField) -> Optional[Any]:
        """转换字段值为适当的类型

        Args:
            field: 字段状态

        Returns:
            Optional[Any]: 转换后的值
        """
        if not field.selected:
            return None

        selected = field.selected

        # 整数类型转换
        if field.field_type in (FieldType.INTEGER_SINGLE, FieldType.INTEGER_ARRAY):
            try:
                if field.field_type == FieldType.INTEGER_SINGLE:
                    return int(selected[0])
                return [int(v) for v in selected]
            except (ValueError, TypeError):
                return selected

        # 浮点数类型转换
        if field.field_type in (FieldType.FLOAT_ARRAY, FieldType.GEO_EXTENT):
            try:
                return [float(v) for v in selected]
            except (ValueError, TypeError):
                return selected

        # 布尔类型转换
        if field.field_type == FieldType.BOOLEAN:
            if not selected:
                return None
            raw = str(selected[0]).strip().lower()
            return raw in ("1", "true", "yes", "y", "on")

        # 字符串类型
        if field.field_type == FieldType.STRING_SINGLE:
            return str(selected[0]) if selected else None

        return selected

    def init_from_schema(self, schema: DatasetSchema) -> None:
        """从 Schema 初始化表单状态

        Args:
            schema: 数据集 Schema
        """
        self.schema = schema
        self.collection_id = schema.collection_id
        self.is_schema_loaded = True

        # 创建字段状态
        self.fields = {}
        for field_def in schema.fields:
            # 获取初始约束值
            initial_values = schema.constraints.get(field_def.name, [])
            field_state = DynamicFormField(
                definition=field_def,
                values=initial_values,
            )
            # 应用默认值（主要用于无预定义 values 列表的特殊控件）
            default_selected = self._get_default_selected(field_def)
            if default_selected and not field_state.selected:
                field_state.set_selected(default_selected)

            self.fields[field_def.name] = field_state

    @staticmethod
    def _get_default_selected(field_def: FormFieldDefinition) -> List[Any]:
        """从字段定义中提取默认选中值。

        说明：
        - Datastores form 字段的默认值通常位于 field_data["details"]["default"]
        - 本方法只负责将 default 归一化为 DynamicFormField.selected 的内部表示
        """
        raw_details = field_def.details.get("details", {})
        default_value = raw_details.get("default")
        if default_value is None:
            return []

        field_type = field_def.field_type

        if field_type in (FieldType.STRING_SINGLE, FieldType.EXCLUSIVE_GROUP):
            return [str(default_value)]

        if field_type == FieldType.BOOLEAN:
            if isinstance(default_value, bool):
                return ["true"] if default_value else []
            default_str = str(default_value).strip().lower()
            return ["true"] if default_str in ("1", "true", "yes", "y", "on") else []

        if field_type in (FieldType.FLOAT_ARRAY, FieldType.GEO_EXTENT):
            # 支持 dict（n/e/s/w）或 list/tuple（长度 4）
            if isinstance(default_value, dict):
                keys = set(default_value.keys())
                if {"n", "w", "s", "e"}.issubset(keys):
                    return [
                        default_value.get("n"),
                        default_value.get("w"),
                        default_value.get("s"),
                        default_value.get("e"),
                    ]
                if {"n", "e", "s", "w"}.issubset(keys):
                    return [
                        default_value.get("n"),
                        default_value.get("w"),
                        default_value.get("s"),
                        default_value.get("e"),
                    ]
            if isinstance(default_value, (list, tuple)) and len(default_value) == 4:
                return list(default_value)

        if field_type == FieldType.LICENCE:
            if isinstance(default_value, list):
                return [str(v) for v in default_value]
            if isinstance(default_value, str):
                return [default_value]

        return []

    def update_constraints(self, constraints: Dict[str, List[str]]) -> None:
        """更新字段约束值

        Args:
            constraints: 新的约束值字典
        """
        for field_name, values in constraints.items():
            if field_name in self.fields:
                self.fields[field_name].set_values(values)

    def validate(self) -> List[str]:
        """验证表单数据

        检查必填字段是否有值。

        Returns:
            List[str]: 错误信息列表
        """
        errors = []

        for field_name, field in self.fields.items():
            if field.required and not field.selected:
                errors.append(f"{field.label} 是必填字段")

        return errors

    def reset(self) -> None:
        """重置表单状态"""
        for field in self.fields.values():
            field.clear()
        if self.schema:
            # 重新应用初始约束
            self.update_constraints(self.schema.constraints)
