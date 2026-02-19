"""
DynamicFieldWidget 组件测试

覆盖动态表单字段（尤其是 Select 下拉框）在 Textual 7.5+ 下的挂载行为，
防止因 value=None 导致 InvalidSelectValueError 从而使动态字段区域空白。
"""

from contextlib import asynccontextmanager
from textual.widgets import Input
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


@asynccontextmanager
async def _run_widget_with_pilot(field: DynamicFormField):
    """将 DynamicFieldWidget 挂载到一个最小 App，并返回 pilot 以便等待事件循环。"""
    from textual.app import App

    class TestApp(App):
        def compose(self):
            yield DynamicFieldWidget(field, id="dyn-field")

    app = TestApp()
    async with app.run_test() as pilot:
        yield app.query_one("#dyn-field", DynamicFieldWidget), pilot


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


class TestDynamicFieldWidgetSelectBehavior:
    """测试 Select 在不同形态下的行为差异（崩溃回归点 + 组合控件功能点）"""

    async def test_string_single_select_does_not_reset_to_blank(self):
        """纯下拉框：选择后应保持选中值（required 时不允许 BLANK）。"""
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

        async with _run_widget_with_pilot(field) as (widget, pilot):
            select = widget.query_one("#select-variable", Select)
            select.value = "u"
            await pilot.pause()
            assert select.value == "u"

    async def test_quick_select_appends_to_input_and_resets_select(self):
        """组合控件：Select 选择后写入 Input，并将 Select 重置为空以允许重复选择同一项。"""
        field = DynamicFormField(
            definition=FormFieldDefinition(
                name="variable",
                label="Variable",
                field_type=FieldType.STRING_ARRAY,
                required=False,
            ),
            values=["t", "u"],
            selected=[],
        )

        async with _run_widget_with_pilot(field) as (widget, pilot):
            select = widget.query_one("#select-variable", Select)
            inp = widget.query_one("#input-variable", Input)

            assert inp.value == ""
            assert select.value == Select.BLANK

            select.value = "t"
            await pilot.pause()
            assert inp.value == "t"
            assert select.value == Select.BLANK

            select.value = "u"
            await pilot.pause()
            assert inp.value == "t, u"
            assert select.value == Select.BLANK

    async def test_quick_select_update_values_keeps_blank_default(self):
        """组合控件刷新可选值后，Select 仍应保持空值，不应自动跳到第一项。"""
        field = DynamicFormField(
            definition=FormFieldDefinition(
                name="variable",
                label="Variable",
                field_type=FieldType.STRING_ARRAY,
                required=True,
            ),
            values=["t", "u"],
            selected=[],
        )

        async with _run_widget_with_pilot(field) as (widget, pilot):
            select = widget.query_one("#select-variable", Select)
            inp = widget.query_one("#input-variable", Input)

            assert select.value == Select.BLANK
            assert inp.value == ""

            widget.update_values(["a", "b", "c"])
            await pilot.pause()
            await pilot.pause()

            assert select.value == Select.BLANK
            assert inp.value == ""

    async def test_programmatic_update_values_does_not_emit_field_changed(self):
        """程序化刷新选项：不应被当作用户点击，不应触发 FieldChanged。"""
        from textual.app import App

        changed_events = []
        field = DynamicFormField(
            definition=FormFieldDefinition(
                name="variable",
                label="Variable",
                field_type=FieldType.STRING_SINGLE,
                required=True,
            ),
            values=["b", "c"],
            selected=[],
        )

        class TestApp(App):
            def compose(self):
                yield DynamicFieldWidget(field, id="dyn-field")

            def on_dynamic_field_widget_field_changed(self, event: DynamicFieldWidget.FieldChanged) -> None:
                changed_events.append((event.field_name, list(event.selected_values)))

        app = TestApp()
        async with app.run_test() as pilot:
            widget = app.query_one("#dyn-field", DynamicFieldWidget)
            select = widget.query_one("#select-variable", Select)

            # required=True 初始会选中首项 "b"
            assert select.value == "b"
            changed_events.clear()

            # 触发一次程序化选项刷新（原选项 "b" 被移除）
            widget.update_values(["a", "c"])
            await pilot.pause()
            await pilot.pause()

            # 应自动回退到首项且同步内部状态，但不应触发用户变更事件
            assert select.value == "a"
            assert field.selected == ["a"]
            assert changed_events == []
