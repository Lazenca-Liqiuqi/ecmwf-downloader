"""
DynamicFieldWidget 组件测试

覆盖动态表单字段（尤其是 Select 下拉框）在 Textual 7.5+ 下的挂载行为，
防止因 value=None 导致 InvalidSelectValueError 从而使动态字段区域空白。
"""

from contextlib import asynccontextmanager
from textual.widgets import Select

from src.core.dataset_schema import DynamicFormField, FieldType, FormFieldDefinition
from src.ui.widgets.dynamic_form_field import DynamicFieldWidget


@asynccontextmanager
async def _run_widget(field: DynamicFormField):
    """将 DynamicFieldWidget 挂载到一个最小 App，并在上下文内执行断言。"""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield DynamicFieldWidget(field, id="dyn-field")

    app = TestApp()
    async with app.run_test() as _pilot:
        yield app.query_one("#dyn-field", DynamicFieldWidget)


class TestDynamicFieldWidgetSelectInitialValue:
    """测试 Select 初始值逻辑（关键回归点）"""

    async def test_required_select_defaults_to_first_option(self):
        """必填下拉框：未选中时默认选择第一项，避免 value=None 挂载报错。"""
        field = DynamicFormField(
            definition=FormFieldDefinition(
                name="variable",
                label="Variable",
                field_type=FieldType.STRING_SINGLE,
                required=True,
            ),
            values=["t", "u"],
            selected=[],
        )

        async with _run_widget(field) as widget:
            select = widget.query_one("#select-variable", Select)
            assert select.value == "t"

    async def test_optional_select_uses_blank(self):
        """非必填下拉框：未选中时允许空值并使用 Select.BLANK。"""
        field = DynamicFormField(
            definition=FormFieldDefinition(
                name="product_type",
                label="Product Type",
                field_type=FieldType.STRING_SINGLE,
                required=False,
            ),
            values=["reanalysis", "ensemble_members"],
            selected=[],
        )

        async with _run_widget(field) as widget:
            select = widget.query_one("#select-product_type", Select)
            assert select.value == Select.BLANK

    async def test_required_select_with_no_options_does_not_crash(self):
        """必填下拉框但无可选项：仍应可挂载（允许空值作为防御）。"""
        field = DynamicFormField(
            definition=FormFieldDefinition(
                name="data_format",
                label="Data Format",
                field_type=FieldType.STRING_SINGLE,
                required=True,
            ),
            values=[],
            selected=[],
        )

        async with _run_widget(field) as widget:
            select = widget.query_one("#select-data_format", Select)
            assert select.value == Select.BLANK
