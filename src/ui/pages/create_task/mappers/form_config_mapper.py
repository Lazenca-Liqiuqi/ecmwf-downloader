"""
表单配置映射器

提供表单状态与配置数据之间的双向转换功能：
- 序列化：DynamicFormField -> 可 JSON 序列化的字典
- 反序列化：字典 -> DynamicFormField
- 配置构建：表单状态 -> DownloadConfig
"""

from typing import Any, Dict, List, Optional, Tuple

from src.core.config import DownloadConfig
from src.core.dataset_schema import (
    DynamicFormField,
    DynamicFormState,
    FieldType,
    FormFieldDefinition,
)


class FormConfigMapper:
    """表单配置映射器

    负责在表单状态对象与可持久化配置之间进行双向转换。
    所有方法均为静态方法或类方法，确保无状态性。
    """

    @staticmethod
    def to_json_safe(value: Any) -> Any:
        """将任意值转换为可 JSON 序列化的数据结构

        Args:
            value: 任意 Python 值

        Returns:
            可 JSON 序列化的数据结构
        """
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): FormConfigMapper.to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [FormConfigMapper.to_json_safe(v) for v in value]
        if isinstance(value, set):
            return [FormConfigMapper.to_json_safe(v) for v in sorted(value, key=lambda x: str(x))]
        return str(value)

    @classmethod
    def serialize_field(cls, field: DynamicFormField) -> Dict[str, Any]:
        """序列化单个字段配置

        仅保留新格式必要信息，包括字段类型、已选值和原始定义。

        Args:
            field: 动态表单字段对象

        Returns:
            可 JSON 序列化的字段配置字典
        """
        raw_definition = cls.to_json_safe(field.definition.details or {})
        return {
            "field_type": field.field_type.value,
            "selected": cls.to_json_safe(field.selected),
            "definition": raw_definition,
        }

    @classmethod
    def deserialize_field(
        cls,
        field_name: str,
        field_info: Dict[str, Any],
    ) -> DynamicFormField:
        """反序列化单个字段配置

        仅支持新格式，旧格式将抛出异常。

        Args:
            field_name: 字段名称
            field_info: 字段配置字典（来自 JSON 文件）

        Returns:
            重建的 DynamicFormField 对象

        Raises:
            ValueError: 配置格式过旧或不合法
        """
        definition = field_info.get("definition", {})
        if not isinstance(definition, dict):
            definition = {}

        field_data = dict(definition)
        field_data.setdefault("name", field_name)

        # 解析字段类型
        saved_type = field_info.get("field_type")
        if isinstance(saved_type, str):
            try:
                field_type = FieldType(saved_type)
            except ValueError:
                field_type = FormFieldDefinition._parse_field_type(field_data)
        else:
            field_type = FormFieldDefinition._parse_field_type(field_data)

        label = str(field_data.get("label") or FormFieldDefinition._generate_label(field_name))
        required = bool(field_data.get("required", False))

        field_def = FormFieldDefinition(
            name=field_name,
            label=label,
            field_type=field_type,
            required=required,
            details=field_data,
        )

        # 可选值始终以 definition 中的完整值为准，避免只恢复到约束后的子集
        definition_values = cls.extract_values_from_definition(field_data)
        values = definition_values if isinstance(definition_values, list) else []

        field_state = DynamicFormField(
            definition=field_def,
            values=[str(v) for v in values],
        )

        # 解析已选值
        selected = field_info.get("selected", [])
        if isinstance(selected, list):
            normalized_selected = selected
        elif selected in (None, ""):
            normalized_selected = []
        else:
            normalized_selected = [selected]

        # 单值字段只取第一个
        if field_type in (
            FieldType.STRING_SINGLE,
            FieldType.INTEGER_SINGLE,
            FieldType.BOOLEAN,
            FieldType.EXCLUSIVE_GROUP,
        ):
            normalized_selected = normalized_selected[:1] if normalized_selected else []

        field_state.set_selected(normalized_selected)
        return field_state

    @staticmethod
    def extract_values_from_definition(raw_definition: Any) -> List[Any]:
        """从原始定义中提取完整可选值列表

        支持多种格式：
        - values/options/choices/items 键
        - [{"id": "..."}] 与 ["..."] 两种值格式
        - LicenceWidget 的 licences 键

        Args:
            raw_definition: 原始字段定义（字典或任意值）

        Returns:
            可选值列表
        """
        if not isinstance(raw_definition, dict):
            return []

        details = raw_definition.get("details", {})
        if not isinstance(details, dict):
            details = {}

        # 查找标准键
        for key in ("values", "options", "choices", "items"):
            value = details.get(key)
            if isinstance(value, list) and value:
                return FormConfigMapper._extract_values_from_list(value)

        # 特殊控件：LicenceWidget
        licences = details.get("licences")
        if isinstance(licences, list) and licences:
            return FormConfigMapper._extract_values_from_list(licences)

        return []

    @staticmethod
    def _extract_values_from_list(items: List[Any]) -> List[Any]:
        """从列表中提取值

        支持 [{"id": "..."}] 与 ["..."] 两种格式。

        Args:
            items: 原始列表

        Returns:
            提取的值列表
        """
        result: List[Any] = []
        for item in items:
            if isinstance(item, dict):
                if "id" in item:
                    result.append(item["id"])
                elif "value" in item:
                    result.append(item["value"])
                else:
                    result.append(item)
            else:
                result.append(item)
        return result

    @classmethod
    def to_download_config(
        cls,
        form_state: DynamicFormState,
        dataset: str,
        output_dir: str,
    ) -> DownloadConfig:
        """从表单状态构建下载配置

        验证必填字段并构建 DownloadConfig 对象。

        Args:
            form_state: 动态表单状态对象
            dataset: 数据集 ID
            output_dir: 输出目录路径

        Returns:
            验证后的 DownloadConfig 对象

        Raises:
            ValueError: 必填字段未填写或其他验证错误
        """
        # 验证 dataset 非空
        if not dataset or not dataset.strip():
            raise ValueError("请输入数据集 ID")

        if not form_state.is_schema_loaded:
            raise ValueError("请先加载数据集 Schema")

        config_dict = form_state.to_download_config_dict()
        config_dict["dataset"] = dataset
        config_dict["output_dir"] = output_dir

        # 验证必填字段
        errors = form_state.validate()
        if errors:
            raise ValueError("; ".join(errors))

        return DownloadConfig(**config_dict)

    @classmethod
    def serialize_form_state(
        cls,
        form_state: DynamicFormState,
        dataset: str,
        output_dir: str,
        split_strategy: str,
    ) -> Dict[str, Any]:
        """序列化完整的表单状态到可保存的配置字典

        Args:
            form_state: 动态表单状态对象
            dataset: 数据集 ID
            output_dir: 输出目录路径
            split_strategy: 拆分策略

        Returns:
            可 JSON 序列化的配置字典
        """
        config_data = {
            "dataset": dataset,
            "output_dir": output_dir,
            "split_strategy": split_strategy,
            "fields": {},
        }

        # 收集完整的字段定义
        if form_state.is_schema_loaded:
            for field_name, field in form_state.fields.items():
                config_data["fields"][field_name] = cls.serialize_field(field)

        return config_data

    @classmethod
    def deserialize_to_form_state(
        cls,
        config_data: Dict[str, Any],
    ) -> Tuple[DynamicFormState, str, str, str]:
        """从配置字典反序列化到表单状态

        Args:
            config_data: 从 JSON 文件加载的配置字典

        Returns:
            元组：(form_state, dataset, output_dir, split_strategy)

        Raises:
            ValueError: 配置格式过旧或不合法
        """
        form_state = DynamicFormState()
        form_state.collection_id = config_data.get("dataset", "")
        form_state.is_schema_loaded = True
        form_state.fields = {}

        fields_data = config_data.get("fields", {})
        for field_name, field_info in fields_data.items():
            if not isinstance(field_info, dict):
                continue
            if "definition" not in field_info:
                raise ValueError("配置格式过旧，请重新在线加载后保存")
            form_state.fields[field_name] = cls.deserialize_field(field_name, field_info)

        return (
            form_state,
            config_data.get("dataset", ""),
            config_data.get("output_dir", "./data/downloads"),
            config_data.get("split_strategy", "month"),
        )
