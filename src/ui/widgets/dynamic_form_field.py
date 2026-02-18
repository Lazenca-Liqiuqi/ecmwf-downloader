"""
动态表单字段组件

提供可复用的动态表单字段，支持多种输入类型和约束更新。
"""

from typing import Any, Dict, List, Optional

from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Checkbox, Input, Label, RadioButton, RadioSet, Select, Static, Switch

from src.core.dataset_schema import DynamicFormField, FieldType


class DynamicFieldWidget(Vertical):
    """动态表单字段组件

    根据字段类型渲染不同的输入控件：
    - STRING_ARRAY: Input（逗号分隔多选）
    - STRING_SINGLE: Select 下拉框
    - INTEGER_ARRAY: Input（数字列表）
    - INTEGER_SINGLE: Input（单数字）
    - FLOAT_ARRAY: Input（浮点数列表）

    特性：
    - 支持加载状态显示
    - 发送 FieldChanged 消息通知父组件
    - 支持外部更新可选值
    """

    DEFAULT_CSS = """
    DynamicFieldWidget {
        height: auto;
        margin-bottom: 1;
    }

    .field-label {
        text-style: bold;
        margin-bottom: 0;
        color: $text 80%;
    }

    .field-required {
        color: $error;
    }

    .field-input {
        width: 1fr;
        min-height: 3;
        border: round $panel;
        background: $surface;
        color: $text;
    }

    .field-input:focus {
        border: round $accent;
    }

    .field-select {
        width: 1fr;
    }

    .field-hint {
        color: $text-muted;
        text-style: italic;
        margin-top: 0;
    }

    .field-loading {
        color: $warning;
        text-style: italic;
    }

    .field-count {
        color: $accent;
        margin-left: 1;
    }
    """

    class FieldChanged(Message):
        """字段值变化消息

        当用户修改字段值时发送，通知父组件更新约束。
        """

        def __init__(self, field_name: str, selected_values: List[Any]) -> None:
            """初始化消息

            Args:
                field_name: 字段名称
                selected_values: 选中的值列表
            """
            super().__init__()
            self.field_name = field_name
            self.selected_values = selected_values

    def __init__(
        self,
        field: DynamicFormField,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
        disabled: bool = False,
    ) -> None:
        """初始化动态字段组件

        Args:
            field: 动态字段状态对象
            name: 组件名称
            id: 组件 ID
            classes: CSS 类名
            disabled: 是否禁用
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._field = field
        self._suppress_events = False
        self._input_widget: Optional[Input] = None
        self._select_widget: Optional[Select] = None
        self._switch_widget: Optional[Switch] = None
        self._radio_set_widget: Optional[RadioSet] = None
        self._licence_checkboxes: Dict[str, Checkbox] = {}
        self._extent_inputs: Dict[str, Input] = {}

    def compose(self) -> None:
        """构建字段 UI"""
        # 标签行
        label_text = self._field.label
        if self._field.required:
            label_text += " *"

        # 显示可选值数量
        if self._field.values:
            count_text = f"({len(self._field.values)} 可选)"
            label_text += f"  {count_text}"

        yield Label(label_text, classes="field-label")

        # 根据字段类型渲染输入控件
        field_type = self._field.field_type

        if field_type == FieldType.STRING_SINGLE:
            # 单选下拉框
            yield from self._compose_select()
        elif field_type == FieldType.BOOLEAN:
            yield from self._compose_switch()
        elif field_type == FieldType.EXCLUSIVE_GROUP:
            yield from self._compose_exclusive_group()
        elif field_type == FieldType.GEO_EXTENT:
            yield from self._compose_geo_extent()
        elif field_type == FieldType.LICENCE:
            yield from self._compose_licences()
        else:
            # 默认使用输入框
            yield from self._compose_input()

        # 提示信息
        hint = self._get_field_hint()
        if hint:
            yield Label(hint, classes="field-hint")

    def _compose_input(self) -> None:
        """构建输入框控件"""
        placeholder = self._get_placeholder()
        initial_value = self._format_selected_for_input()

        self._input_widget = Input(
            placeholder=placeholder,
            value=initial_value,
            id=f"input-{self._field.name}",
            classes="field-input",
        )
        yield self._input_widget

    def _compose_select(self) -> None:
        """构建下拉选择框控件"""
        options = self._build_select_options()
        allow_blank = not self._field.required

        # Textual 7.5+：Select 的 value 不能为 None；未选择时应使用 Select.BLANK。
        # 对于必填字段，如果当前没有选中值且存在可选项，则默认选择第一项，避免组件挂载时报错。
        if self._field.selected:
            initial_value = str(self._field.selected[0])
        elif options and not allow_blank:
            initial_value = str(options[0][1])
            self._field.set_selected([initial_value])
        else:
            initial_value = Select.BLANK

        # 防御：如果没有任何可选项，允许空值以避免 Select 在挂载阶段访问 options[0]。
        if not options:
            allow_blank = True
            initial_value = Select.BLANK

        self._select_widget = Select(
            options=options,
            value=initial_value,
            id=f"select-{self._field.name}",
            classes="field-select",
            allow_blank=allow_blank,
        )
        yield self._select_widget

    def _compose_switch(self) -> None:
        """构建布尔开关控件（Switch）"""
        initial = bool(self._field.selected) and str(self._field.selected[0]).strip().lower() in (
            "1",
            "true",
            "yes",
            "y",
            "on",
        )
        self._switch_widget = Switch(
            value=initial,
            id=f"switch-{self._field.name}",
            classes="field-switch",
        )
        yield self._switch_widget

        # FreeEditionWidget 通常会携带解释文本，放在开关下方辅助理解
        details = self._field.definition.details.get("details", {})
        text = details.get("text")
        if isinstance(text, str) and text.strip():
            yield Static(text.strip(), classes="field-hint")

    def _compose_exclusive_group(self) -> None:
        """构建排他分组控件（RadioSet）"""
        options = self._get_exclusive_group_options()
        if not options:
            # 无法推断可选项时降级为自由输入，避免 UI 空白
            yield from self._compose_input()
            return

        selected_value = str(self._field.selected[0]) if self._field.selected else None
        buttons: List[RadioButton] = []
        for option in options:
            option_id = option.get("id", "")
            option_label = option.get("label", option_id)
            pressed = selected_value == option_id if selected_value is not None else False
            buttons.append(
                RadioButton(
                    label=option_label,
                    value=pressed,
                    name=option_id,
                    id=f"radio-{self._field.name}-{option_id}",
                    compact=True,
                )
            )

        self._radio_set_widget = RadioSet(
            *buttons,
            id=f"radio-set-{self._field.name}",
            classes="field-radio-set",
            compact=True,
        )
        yield self._radio_set_widget

    def _compose_geo_extent(self) -> None:
        """构建地理范围控件（4 个输入框：N, W, S, E）"""
        initial = self._get_geo_extent_initial_values()

        def _make_input(key: str, placeholder: str) -> Input:
            return Input(
                placeholder=placeholder,
                value=initial.get(key, ""),
                id=f"extent-{self._field.name}-{key}",
                classes="field-input field-extent",
            )

        self._extent_inputs = {
            "n": _make_input("n", "N"),
            "w": _make_input("w", "W"),
            "s": _make_input("s", "S"),
            "e": _make_input("e", "E"),
        }

        with Horizontal(classes="field-extent-row"):
            yield self._extent_inputs["n"]
            yield self._extent_inputs["w"]
            yield self._extent_inputs["s"]
            yield self._extent_inputs["e"]

    def _compose_licences(self) -> None:
        """构建许可证控件（Checkbox 列表）"""
        details = self._field.definition.details.get("details", {})
        licences = details.get("licences", [])
        if not isinstance(licences, list) or not licences:
            # 无法解析许可证列表时降级为自由输入
            yield from self._compose_input()
            return

        self._licence_checkboxes = {}
        selected_ids = {str(v) for v in self._field.selected}

        for lic in licences:
            if not isinstance(lic, dict):
                continue
            lic_id = lic.get("id")
            if not lic_id:
                continue
            lic_id = str(lic_id)
            lic_label = str(lic.get("label") or lic_id)
            checkbox = Checkbox(
                label=lic_label,
                value=lic_id in selected_ids,
                name=lic_id,
                id=f"licence-{self._field.name}-{lic_id}",
                compact=True,
            )
            self._licence_checkboxes[lic_id] = checkbox
            yield checkbox

    def _build_select_options(self) -> List[tuple]:
        """构建下拉框选项列表

        Returns:
            List[tuple]: (显示文本, 值) 元组列表
        """
        options = []
        for value in self._field.values:
            # 显示值和实际值相同
            options.append((str(value), str(value)))
        return options

    def _get_placeholder(self) -> str:
        """获取输入框占位符

        Returns:
            str: 占位符文本
        """
        field_type = self._field.field_type

        if field_type == FieldType.INTEGER_ARRAY:
            return "逗号分隔的数字，如 500,850,1000"
        if field_type == FieldType.INTEGER_SINGLE:
            return "输入数字"
        if field_type == FieldType.FLOAT_ARRAY:
            return "逗号分隔的数字，如 90,-180,-90,180"
        if field_type == FieldType.STRING_ARRAY:
            if self._field.values:
                return f"逗号分隔，共 {len(self._field.values)} 可选"
            return "逗号分隔的值"
        return "输入值"

    def _get_field_hint(self) -> str:
        """获取字段提示信息

        Returns:
            str: 提示文本
        """
        # 根据字段名返回提示
        hints = {
            "variable": "选择要下载的气象变量",
            "year": "输入年份，如 2020,2021",
            "month": "输入月份 1-12",
            "day": "输入日期 1-31，留空表示全月",
            "time": "时间点，格式 HH:MM",
            "pressure_level": "气压层高度（hPa）",
            "area": "区域范围：N, W, S, E",
            "product_type": "数据产品类型",
        }
        return hints.get(self._field.name, "")

    def _format_selected_for_input(self) -> str:
        """格式化选中值为输入框显示格式

        Returns:
            str: 逗号分隔的字符串
        """
        if not self._field.selected:
            return ""
        return ", ".join(str(v) for v in self._field.selected)

    def on_input_changed(self, event: Input.Changed) -> None:
        """输入框值变化事件处理

        Args:
            event: 输入变化事件
        """
        if self._suppress_events:
            return

        # 地理范围输入：由 4 个 Input 组成
        if self._extent_inputs and event.input in self._extent_inputs.values():
            values = self._parse_geo_extent_inputs()
            # 只有在 4 个值均有效时才触发更新，避免频繁清空导致约束抖动
            if values is not None:
                self.post_message(self.FieldChanged(self._field.name, values))
            return

        if event.input != self._input_widget:
            return

        # 解析输入值
        values = self._parse_input_value(event.value)

        # 发送消息
        self.post_message(self.FieldChanged(self._field.name, values))

    def on_select_changed(self, event: Select.Changed) -> None:
        """下拉框选择变化事件处理

        Args:
            event: 选择变化事件
        """
        if self._suppress_events:
            return

        if event.select != self._select_widget:
            return

        # 获取选中的值
        value = event.value
        if value is None or value == Select.BLANK:
            values = []
        else:
            values = [value]

        # 发送消息
        self.post_message(self.FieldChanged(self._field.name, values))

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Switch 变化事件处理（布尔字段）"""
        if self._suppress_events:
            return
        if event.switch != self._switch_widget:
            return

        values = ["true"] if event.value else []
        self.post_message(self.FieldChanged(self._field.name, values))

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """RadioSet 变化事件处理（排他分组）"""
        if self._suppress_events:
            return
        if event.radio_set != self._radio_set_widget:
            return

        option_id = getattr(event.pressed, "name", None)
        values = [option_id] if option_id else []
        self.post_message(self.FieldChanged(self._field.name, values))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Checkbox 变化事件处理（许可证列表等）"""
        if self._suppress_events:
            return

        # 仅处理本字段的 checkbox 集合
        if not self._licence_checkboxes:
            return
        checkbox = event.toggle_button
        if not isinstance(checkbox, Checkbox):
            return
        if checkbox not in self._licence_checkboxes.values():
            return

        selected = [lic_id for lic_id, cb in self._licence_checkboxes.items() if cb.value]
        self.post_message(self.FieldChanged(self._field.name, selected))

    def _parse_input_value(self, value: str) -> List[Any]:
        """解析输入框的值

        根据字段类型将字符串转换为适当类型的列表。

        Args:
            value: 输入框的字符串值

        Returns:
            List[Any]: 解析后的值列表
        """
        # 空值返回空列表
        if not value.strip():
            return []

        # 分割字符串
        parts = [p.strip() for p in value.split(",") if p.strip()]

        # 根据字段类型转换
        field_type = self._field.field_type

        if field_type in (FieldType.INTEGER_ARRAY, FieldType.INTEGER_SINGLE):
            try:
                return [int(p) for p in parts]
            except ValueError:
                return parts

        if field_type == FieldType.FLOAT_ARRAY:
            try:
                return [float(p) for p in parts]
            except ValueError:
                return parts

        # 字符串类型
        return parts

    def update_values(self, values: List[str]) -> None:
        """更新可选值

        外部调用此方法来更新字段的可选值列表。

        Args:
            values: 新的可选值列表
        """
        # 更新内部状态
        self._field.set_values(values)

        # 更新下拉框选项
        if self._select_widget:
            new_options = self._build_select_options()
            self._suppress_events = True
            try:
                self._select_widget.set_options(new_options)
                # 若当前值不在新选项中，回退到 BLANK（或必填时回退到第一项）
                current = self._select_widget.value
                valid_values = {opt[1] for opt in new_options}
                if current not in valid_values:
                    if new_options and self._field.required:
                        self._select_widget.value = str(new_options[0][1])
                        self._field.set_selected([self._select_widget.value])
                    else:
                        self._select_widget.value = Select.BLANK
                        self._field.clear()
            finally:
                self._suppress_events = False

        # 更新可选值数量显示
        self._update_count_label()

    def _update_count_label(self) -> None:
        """更新可选值数量标签"""
        try:
            count_label = self.query_one(".field-count", Label)
            if self._field.values:
                count_label.update(f"({len(self._field.values)} 可选)")
            else:
                count_label.update("")
        except Exception:
            pass

    def set_loading(self, loading: bool) -> None:
        """设置加载状态

        Args:
            loading: 是否正在加载
        """
        self._field.is_loading = loading

        if loading:
            self.add_class("loading")
            if self._input_widget:
                self._input_widget.disabled = True
            if self._select_widget:
                self._select_widget.disabled = True
            if self._switch_widget:
                self._switch_widget.disabled = True
            if self._radio_set_widget:
                self._radio_set_widget.disabled = True
            for cb in self._licence_checkboxes.values():
                cb.disabled = True
            for inp in self._extent_inputs.values():
                inp.disabled = True
        else:
            self.remove_class("loading")
            if self._input_widget:
                self._input_widget.disabled = False
            if self._select_widget:
                self._select_widget.disabled = False
            if self._switch_widget:
                self._switch_widget.disabled = False
            if self._radio_set_widget:
                self._radio_set_widget.disabled = False
            for cb in self._licence_checkboxes.values():
                cb.disabled = False
            for inp in self._extent_inputs.values():
                inp.disabled = False

    def get_selected_values(self) -> List[Any]:
        """获取当前选中的值

        Returns:
            List[Any]: 选中的值列表
        """
        if self._input_widget:
            return self._parse_input_value(self._input_widget.value)
        if self._select_widget:
            value = self._select_widget.value
            if value is None or value == Select.BLANK:
                return []
            return [value]
        if self._switch_widget:
            return ["true"] if self._switch_widget.value else []
        if self._radio_set_widget:
            pressed = self._radio_set_widget.pressed_button
            option_id = getattr(pressed, "name", None)
            return [option_id] if option_id else []
        if self._licence_checkboxes:
            return [lic_id for lic_id, cb in self._licence_checkboxes.items() if cb.value]
        if self._extent_inputs:
            return self._field.selected
        return []

    def set_selected_values(self, values: List[Any]) -> None:
        """设置选中的值

        Args:
            values: 要设置的值列表
        """
        self._suppress_events = True
        try:
            self._field.set_selected(values)

            if self._input_widget:
                self._input_widget.value = self._format_selected_for_input()
            if self._select_widget:
                if values:
                    self._select_widget.value = str(values[0])
                else:
                    self._select_widget.value = Select.BLANK
            if self._switch_widget:
                self._switch_widget.value = bool(values) and str(values[0]).strip().lower() in (
                    "1",
                    "true",
                    "yes",
                    "y",
                    "on",
                )
            if self._radio_set_widget:
                target = str(values[0]) if values else None
                for button in self._radio_set_widget.query(RadioButton):
                    button.value = bool(target) and getattr(button, "name", None) == target
            if self._licence_checkboxes:
                selected_ids = {str(v) for v in values}
                for lic_id, cb in self._licence_checkboxes.items():
                    cb.value = lic_id in selected_ids
            if self._extent_inputs:
                if len(values) == 4:
                    n, w, s, e = values
                    self._extent_inputs["n"].value = str(n)
                    self._extent_inputs["w"].value = str(w)
                    self._extent_inputs["s"].value = str(s)
                    self._extent_inputs["e"].value = str(e)
        finally:
            self._suppress_events = False

    def clear(self) -> None:
        """清空字段值"""
        self._suppress_events = True
        try:
            self._field.clear()
            if self._input_widget:
                self._input_widget.value = ""
            if self._select_widget:
                self._select_widget.value = Select.BLANK
            if self._switch_widget:
                self._switch_widget.value = False
            if self._radio_set_widget:
                for button in self._radio_set_widget.query(RadioButton):
                    button.value = False
            for cb in self._licence_checkboxes.values():
                cb.value = False
            for inp in self._extent_inputs.values():
                inp.value = ""
        finally:
            self._suppress_events = False

    @property
    def field_name(self) -> str:
        """字段名称"""
        return self._field.name

    @property
    def is_valid(self) -> bool:
        """字段值是否有效

        必填字段需要有值才有效。
        """
        if not self._field.required:
            return True
        values = self.get_selected_values()
        return len(values) > 0

    def _get_exclusive_group_options(self) -> List[Dict[str, str]]:
        """提取 ExclusiveGroupWidget 的选项列表。

        返回格式：
            [{"id": "...", "label": "..."}, ...]
        """
        # 优先使用约束/可选值列表（若已由 constraints 填充）
        if self._field.values:
            return [{"id": str(v), "label": str(v)} for v in self._field.values]

        details = self._field.definition.details.get("details", {})
        for key in ("options", "choices", "items", "values"):
            raw = details.get(key)
            if isinstance(raw, list) and raw:
                if all(isinstance(x, dict) for x in raw):
                    options: List[Dict[str, str]] = []
                    for item in raw:
                        if not isinstance(item, dict) or not item.get("id"):
                            continue
                        opt_id = str(item["id"])
                        opt_label = str(item.get("label") or opt_id)
                        options.append({"id": opt_id, "label": opt_label})
                    if options:
                        return options
                return [{"id": str(x), "label": str(x)} for x in raw if x is not None]
            if isinstance(raw, dict) and raw:
                return [{"id": str(k), "label": str(v)} for k, v in raw.items()]

        # 兜底：若只有 default，则至少提供一个可选项避免空白
        default_value = details.get("default")
        if default_value is not None:
            dv = str(default_value)
            return [{"id": dv, "label": dv}]

        return []

    def _get_geo_extent_initial_values(self) -> Dict[str, str]:
        """获取地理范围输入框的初始显示值（字符串）。"""
        if len(self._field.selected) == 4:
            n, w, s, e = self._field.selected
            return {"n": str(n), "w": str(w), "s": str(s), "e": str(e)}

        details = self._field.definition.details.get("details", {})
        default_value = details.get("default")
        if isinstance(default_value, dict):
            keys = set(default_value.keys())
            if {"n", "w", "s", "e"}.issubset(keys):
                return {
                    "n": str(default_value.get("n", "")),
                    "w": str(default_value.get("w", "")),
                    "s": str(default_value.get("s", "")),
                    "e": str(default_value.get("e", "")),
                }
            if {"n", "e", "s", "w"}.issubset(keys):
                return {
                    "n": str(default_value.get("n", "")),
                    "w": str(default_value.get("w", "")),
                    "s": str(default_value.get("s", "")),
                    "e": str(default_value.get("e", "")),
                }
        if isinstance(default_value, (list, tuple)) and len(default_value) == 4:
            n, w, s, e = default_value
            return {"n": str(n), "w": str(w), "s": str(s), "e": str(e)}

        return {"n": "", "w": "", "s": "", "e": ""}

    def _parse_geo_extent_inputs(self) -> Optional[List[float]]:
        """解析 4 个地理范围输入框。

        返回：
        - 4 个值都有效：返回 [N, W, S, E]
        - 仍在编辑/存在非法值：返回 None（不触发消息）
        """
        if not self._extent_inputs:
            return None

        raw = {k: self._extent_inputs[k].value.strip() for k in ("n", "w", "s", "e")}
        if any(v == "" for v in raw.values()):
            return None

        try:
            n = float(raw["n"])
            w = float(raw["w"])
            s = float(raw["s"])
            e = float(raw["e"])
        except ValueError:
            return None

        return [n, w, s, e]


class DynamicFormFieldsContainer(Vertical):
    """动态表单字段容器

    管理多个动态字段组件的容器，提供统一的字段访问接口。
    """

    DEFAULT_CSS = """
    DynamicFormFieldsContainer {
        height: auto;
        padding: 1 0;
    }
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """初始化容器"""
        super().__init__(name=name, id=id, classes=classes)
        self._field_widgets: Dict[str, DynamicFieldWidget] = {}

    def render_fields(
        self,
        fields: Dict[str, DynamicFormField],
    ) -> None:
        """渲染字段组件

        根据字段状态字典创建并渲染所有字段组件。

        Args:
            fields: 字段状态字典
        """
        # 清除现有字段
        self._field_widgets.clear()
        for child in list(self.children):
            child.remove()

        # 创建新字段组件
        widgets_to_mount = []
        for field_name, field in fields.items():
            widget = DynamicFieldWidget(field, id=f"field-{field_name}")
            self._field_widgets[field_name] = widget
            widgets_to_mount.append(widget)

        # 批量挂载所有字段
        if widgets_to_mount:
            self.mount_all(widgets_to_mount)

    def get_field_widget(self, field_name: str) -> Optional[DynamicFieldWidget]:
        """获取指定字段的组件

        Args:
            field_name: 字段名称

        Returns:
            Optional[DynamicFieldWidget]: 字段组件
        """
        return self._field_widgets.get(field_name)

    def update_field_values(
        self,
        field_name: str,
        values: List[str],
    ) -> None:
        """更新指定字段的可选值

        Args:
            field_name: 字段名称
            values: 新的可选值列表
        """
        widget = self.get_field_widget(field_name)
        if widget:
            widget.update_values(values)

    def set_field_loading(
        self,
        field_name: str,
        loading: bool,
    ) -> None:
        """设置指定字段的加载状态

        Args:
            field_name: 字段名称
            loading: 是否加载中
        """
        widget = self.get_field_widget(field_name)
        if widget:
            widget.set_loading(loading)

    def get_all_values(self) -> Dict[str, List[Any]]:
        """获取所有字段的值

        Returns:
            Dict[str, List[Any]]: 字段名到值的映射
        """
        result = {}
        for field_name, widget in self._field_widgets.items():
            values = widget.get_selected_values()
            if values:
                result[field_name] = values
        return result

    def validate(self) -> List[str]:
        """验证所有字段

        Returns:
            List[str]: 错误信息列表
        """
        errors = []
        for field_name, widget in self._field_widgets.items():
            if not widget.is_valid:
                errors.append(f"{widget._field.label} 是必填字段")
        return errors

    def clear_all(self) -> None:
        """清空所有字段"""
        for widget in self._field_widgets.values():
            widget.clear()
