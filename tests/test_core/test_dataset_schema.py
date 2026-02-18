"""
数据集 Schema 数据模型单元测试

测试动态表单所需的数据结构。
"""

import pytest

from src.core.dataset_schema import (
    FieldType,
    FormFieldDefinition,
    DatasetSchema,
    DynamicFormField,
    DynamicFormState,
)


class TestFieldType:
    """测试 FieldType 枚举"""

    def test_field_types_exist(self):
        """测试所有字段类型存在"""
        assert FieldType.STRING_SINGLE == "string_single"
        assert FieldType.STRING_ARRAY == "string_array"
        assert FieldType.INTEGER_SINGLE == "integer_single"
        assert FieldType.INTEGER_ARRAY == "integer_array"
        assert FieldType.FLOAT_ARRAY == "float_array"
        assert FieldType.BOOLEAN == "boolean"
        assert FieldType.EXCLUSIVE_GROUP == "exclusive_group"
        assert FieldType.GEO_EXTENT == "geo_extent"
        assert FieldType.LICENCE == "licence"
        assert FieldType.STRING == "string"
        assert FieldType.UNKNOWN == "unknown"


class TestFormFieldDefinition:
    """测试 FormFieldDefinition 数据类"""

    def test_create_basic_field(self):
        """测试创建基本字段定义"""
        field = FormFieldDefinition(
            name="variable",
            label="变量列表",
            field_type=FieldType.STRING_ARRAY,
        )
        assert field.name == "variable"
        assert field.label == "变量列表"
        assert field.field_type == FieldType.STRING_ARRAY
        assert field.required is False
        assert field.details == {}

    def test_create_required_field(self):
        """测试创建必填字段"""
        field = FormFieldDefinition(
            name="year",
            label="年份",
            field_type=FieldType.INTEGER_ARRAY,
            required=True,
        )
        assert field.required is True

    def test_from_api_field_string_array(self):
        """测试从 API 字段数据创建（字符串数组类型）"""
        field_data = {
            "type": "StringArrayWidget",
            "required": True,
            "schema": {"type": "array"},
        }
        field = FormFieldDefinition.from_api_field("variable", field_data)
        assert field.name == "variable"
        assert field.label == "变量列表"
        assert field.required is True

    def test_from_api_field_integer_array(self):
        """测试从 API 字段数据创建（整数数组类型）"""
        field_data = {
            "type": "IntegerArrayWidget",
            "schema": {"type": "array", "items": {"type": "integer"}},
        }
        field = FormFieldDefinition.from_api_field("pressure_level", field_data)
        assert field.name == "pressure_level"
        assert field.label == "气压层"

    def test_from_api_field_exclusive_group_widget(self):
        """测试从 API 字段数据创建（排他分组类型）"""
        field_data = {
            "type": "ExclusiveGroupWidget",
            "required": False,
            "details": {"default": "global"},
            "schema": {"type": "string"},
        }
        field = FormFieldDefinition.from_api_field("area_group", field_data)
        assert field.field_type == FieldType.EXCLUSIVE_GROUP

    def test_from_api_field_free_edition_widget(self):
        """测试从 API 字段数据创建（布尔开关类型）"""
        field_data = {
            "type": "FreeEditionWidget",
            "required": False,
            "details": {"text": "With this option selected..."},
            "schema": {"type": "boolean"},
        }
        field = FormFieldDefinition.from_api_field("global", field_data)
        assert field.field_type == FieldType.BOOLEAN

    def test_from_api_field_geographic_extent_widget(self):
        """测试从 API 字段数据创建（地理范围类型）"""
        field_data = {
            "type": "GeographicExtentWidget",
            "required": False,
            "details": {"default": {"n": 90, "w": -180, "s": -90, "e": 180}},
            "schema": {"type": "object", "properties": {"n": {}, "w": {}, "s": {}, "e": {}}},
        }
        field = FormFieldDefinition.from_api_field("area", field_data)
        assert field.field_type == FieldType.GEO_EXTENT

    def test_from_api_field_licence_widget(self):
        """测试从 API 字段数据创建（许可证类型）"""
        field_data = {
            "type": "LicenceWidget",
            "required": False,
            "details": {"licences": [{"id": "cc-by", "label": "CC-BY licence"}]},
            "schema": {"type": "array", "items": {"type": "string"}},
        }
        field = FormFieldDefinition.from_api_field("licences", field_data)
        assert field.field_type == FieldType.LICENCE

    def test_generate_label_known_fields(self):
        """测试生成已知字段的中文标签"""
        assert FormFieldDefinition._generate_label("variable") == "变量列表"
        assert FormFieldDefinition._generate_label("year") == "年份"
        assert FormFieldDefinition._generate_label("month") == "月份"
        assert FormFieldDefinition._generate_label("day") == "日期"
        assert FormFieldDefinition._generate_label("time") == "时间点"
        assert FormFieldDefinition._generate_label("pressure_level") == "气压层"
        assert FormFieldDefinition._generate_label("product_type") == "产品类型"

    def test_generate_label_unknown_field(self):
        """测试生成未知字段的标签（使用原名）"""
        assert FormFieldDefinition._generate_label("unknown_field") == "unknown_field"


class TestDatasetSchema:
    """测试 DatasetSchema 数据类"""

    def test_create_schema(self):
        """测试创建数据集 Schema"""
        fields = [
            FormFieldDefinition(name="variable", label="变量", field_type=FieldType.STRING_ARRAY),
            FormFieldDefinition(name="year", label="年份", field_type=FieldType.INTEGER_ARRAY),
        ]
        constraints = {"variable": ["u", "v", "t"], "year": ["2020", "2021"]}

        schema = DatasetSchema(
            collection_id="test-dataset",
            title="Test Dataset",
            description="A test dataset",
            fields=fields,
            constraints=constraints,
        )

        assert schema.collection_id == "test-dataset"
        assert schema.title == "Test Dataset"
        assert len(schema.fields) == 2
        assert schema.constraints == constraints

    def test_get_field_existing(self):
        """测试获取已存在的字段"""
        schema = DatasetSchema(
            collection_id="test",
            title="Test",
            fields=[
                FormFieldDefinition(name="year", label="年份", field_type=FieldType.INTEGER_ARRAY),
            ],
        )
        field = schema.get_field("year")
        assert field is not None
        assert field.name == "year"

    def test_get_field_not_existing(self):
        """测试获取不存在的字段"""
        schema = DatasetSchema(collection_id="test", title="Test")
        field = schema.get_field("nonexistent")
        assert field is None

    def test_get_required_fields(self):
        """测试获取必填字段"""
        schema = DatasetSchema(
            collection_id="test",
            title="Test",
            fields=[
                FormFieldDefinition(name="variable", label="变量", field_type=FieldType.STRING_ARRAY, required=True),
                FormFieldDefinition(name="year", label="年份", field_type=FieldType.INTEGER_ARRAY, required=True),
                FormFieldDefinition(name="day", label="日期", field_type=FieldType.INTEGER_ARRAY, required=False),
            ],
        )
        required = schema.get_required_fields()
        assert len(required) == 2
        assert all(f.required for f in required)

    def test_get_field_names(self):
        """测试获取所有字段名"""
        schema = DatasetSchema(
            collection_id="test",
            title="Test",
            fields=[
                FormFieldDefinition(name="a", label="A", field_type=FieldType.STRING),
                FormFieldDefinition(name="b", label="B", field_type=FieldType.STRING),
            ],
        )
        names = schema.get_field_names()
        assert names == ["a", "b"]


class TestDynamicFormField:
    """测试 DynamicFormField 数据类"""

    @pytest.fixture
    def definition(self):
        """创建字段定义"""
        return FormFieldDefinition(
            name="variable",
            label="变量列表",
            field_type=FieldType.STRING_ARRAY,
            required=True,
        )

    def test_create_field(self, definition):
        """测试创建动态字段"""
        field = DynamicFormField(definition=definition)
        assert field.name == "variable"
        assert field.label == "变量列表"
        assert field.required is True
        assert field.values == []
        assert field.selected == []
        assert field.is_loading is False

    def test_set_values(self, definition):
        """测试设置可选值"""
        field = DynamicFormField(definition=definition)
        field.set_values(["u", "v", "t"])
        assert field.values == ["u", "v", "t"]

    def test_set_values_clears_invalid_selection(self, definition):
        """测试设置可选值时清理无效的已选值"""
        field = DynamicFormField(definition=definition)
        field.selected = ["u", "x", "v"]  # x 不在新值列表中
        field.set_values(["u", "v", "t"])
        assert field.selected == ["u", "v"]  # x 被清理

    def test_set_selected(self, definition):
        """测试设置选中值"""
        field = DynamicFormField(definition=definition)
        field.set_selected(["u", "v"])
        assert field.selected == ["u", "v"]

    def test_clear(self, definition):
        """测试清空选中值"""
        field = DynamicFormField(definition=definition)
        field.selected = ["u", "v"]
        field.clear()
        assert field.selected == []


class TestDynamicFormState:
    """测试 DynamicFormState 数据类"""

    @pytest.fixture
    def schema(self):
        """创建测试用 Schema"""
        return DatasetSchema(
            collection_id="test-dataset",
            title="Test Dataset",
            fields=[
                FormFieldDefinition(name="variable", label="变量", field_type=FieldType.STRING_ARRAY, required=True),
                FormFieldDefinition(name="year", label="年份", field_type=FieldType.INTEGER_ARRAY, required=True),
                FormFieldDefinition(name="month", label="月份", field_type=FieldType.INTEGER_ARRAY, required=False),
            ],
            constraints={
                "variable": ["u", "v", "t"],
                "year": ["2020", "2021", "2022"],
                "month": ["01", "02", "03"],
            },
        )

    def test_create_state(self):
        """测试创建表单状态"""
        state = DynamicFormState()
        assert state.collection_id == ""
        assert state.schema is None
        assert state.fields == {}
        assert state.is_schema_loaded is False

    def test_init_from_schema(self, schema):
        """测试从 Schema 初始化"""
        state = DynamicFormState()
        state.init_from_schema(schema)

        assert state.collection_id == "test-dataset"
        assert state.is_schema_loaded is True
        assert "variable" in state.fields
        assert "year" in state.fields
        assert "month" in state.fields

        # 验证初始约束值被设置
        assert state.fields["variable"].values == ["u", "v", "t"]
        assert state.fields["year"].values == ["2020", "2021", "2022"]

    def test_set_field_selection(self, schema):
        """测试设置字段选中值"""
        state = DynamicFormState()
        state.init_from_schema(schema)
        state.set_field_selection("variable", ["u", "v"])

        assert state.fields["variable"].selected == ["u", "v"]

    def test_get_current_selection(self, schema):
        """测试获取当前选择"""
        state = DynamicFormState()
        state.init_from_schema(schema)
        state.set_field_selection("variable", ["u", "v"])
        state.set_field_selection("year", [2020])

        selection = state.get_current_selection()
        assert "variable" in selection
        assert "year" in selection

    def test_to_download_config_dict(self, schema):
        """测试转换为 DownloadConfig 参数"""
        state = DynamicFormState()
        state.init_from_schema(schema)
        state.set_field_selection("variable", ["u", "v"])
        state.set_field_selection("year", [2020, 2021])
        state.set_field_selection("month", [1, 2])

        config_dict = state.to_download_config_dict()

        # 验证字段名映射
        assert "variables" in config_dict  # variable -> variables
        assert "years" in config_dict       # year -> years
        assert "months" in config_dict      # month -> months

        # 验证值转换
        assert config_dict["variables"] == ["u", "v"]
        assert config_dict["years"] == [2020, 2021]
        assert config_dict["months"] == [1, 2]

    def test_update_constraints(self, schema):
        """测试更新约束值"""
        state = DynamicFormState()
        state.init_from_schema(schema)

        # 模拟约束更新（如选择年份后月份变化）
        new_constraints = {
            "month": ["01", "02"],  # 只有前两个月可选
        }
        state.update_constraints(new_constraints)

        assert state.fields["month"].values == ["01", "02"]

    def test_validate_success(self, schema):
        """测试验证成功"""
        state = DynamicFormState()
        state.init_from_schema(schema)
        state.set_field_selection("variable", ["u"])
        state.set_field_selection("year", [2020])

        errors = state.validate()
        assert len(errors) == 0

    def test_validate_missing_required(self, schema):
        """测试验证失败（缺少必填字段）"""
        state = DynamicFormState()
        state.init_from_schema(schema)
        # 不设置任何值

        errors = state.validate()
        assert len(errors) == 2  # variable 和 year 是必填的

    def test_reset(self, schema):
        """测试重置表单"""
        state = DynamicFormState()
        state.init_from_schema(schema)
        state.set_field_selection("variable", ["u", "v"])

        state.reset()

        assert state.fields["variable"].selected == []
