"""
ECMWF Downloader TUI 配置管理内容组件（动态表单版）

提供基于数据集 Schema 的动态配置表单，支持：
- 从 ecmwf-datastores-client 获取数据集字段定义
- 约束驱动的字段更新（如选择年份后自动更新可选日期）
- 创建新的下载任务

支持方向键操作：输入框用方向键移动光标，Enter键触发按钮。
"""

from typing import Any, Dict, Iterable, List, Literal, Optional

from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Select, Static

from src.core.config import DownloadConfig
from src.core.dataset_schema import DynamicFormState, DynamicFormField
from src.core.task_service import TaskService
from src.api.ecmwf_datastores_client import DatastoresService, DatastoresServiceError
from src.ui.dialogs import RequestPreviewDialog
from src.ui.widgets.dynamic_form_field import (
    DynamicFieldWidget,
    DynamicFormFieldsContainer,
)


class ConfigContent(Widget):
    """配置管理内容组件（动态表单版）

    功能：
    - 输入数据集 ID 后加载 Schema
    - 根据数据集 Schema 动态渲染表单字段
    - 字段值变化时自动更新约束
    - 创建新的下载任务
    """

    DEFAULT_CSS = """
    ConfigContent {
        width: 1fr;
        height: 1fr;
        overflow: hidden;
    }

    #config-container {
        width: 1fr;
        height: auto;
        max-height: 100%;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
        padding: 1 2;
    }

    ConfigContent Input {
        width: 1fr;
        height: auto;
        min-height: 1;
        border: round $panel;
        background: transparent;
        color: $text;
    }

    ConfigContent Input:focus {
        border: round $accent;
    }

    #config-title {
        text-align: left;
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 2;
    }

    .form-label {
        text-style: bold;
        margin-bottom: 0;
        color: $text 80%;
    }

    #task-count-label {
        text-style: bold;
        color: $accent;
    }

    .form-section {
        height: auto;
        margin-bottom: 1;
    }

    #actions-section {
        height: auto;
        margin: 1 3 0 3;
        padding: 0 1;
    }

    #split-strategy-set {
        height: auto;
    }

    #dataset-section {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: round $panel;
    }

    .dataset-input-row {
        height: auto;
        align: center middle;
    }

    #schema-status {
        margin-top: 0;
        color: $text-muted;
    }

    #schema-status.loading {
        color: $warning;
    }

    #schema-status.success {
        color: $success;
    }

    #schema-status.error {
        color: $error;
    }

    #dynamic-form-section {
        height: auto;
        margin-top: 1;
        padding-top: 1;
        border-top: solid $panel;
    }

    #dynamic-fields {
        height: auto;
    }

    #static-options-section {
        margin-top: 1;
        padding-top: 1;
        border-top: solid $panel;
    }

    #btn-load-schema, #btn-save-config, #btn-load-config {
        width: auto;
        min-width: 0;
        padding: 0 1;
    }
    """

    def __init__(self, app, **kwargs):
        """初始化配置管理内容组件

        Args:
            app: 应用实例引用
            **kwargs: 传递给父类的参数
        """
        super().__init__(**kwargs)
        self._app_ref = app  # 使用_app_ref避免与Widget.app属性冲突
        self._task_service = TaskService(app.progress_manager)

        # 动态表单状态
        self._form_state = DynamicFormState()

        # Datastores 服务（延迟初始化）
        self._datastores_service: Optional[DatastoresService] = None

        # 是否正在加载
        self._is_loading = False

        # 待恢复的字段值（从配置文件加载后使用）
        self._pending_field_values: Dict[str, List[Any]] = {}

    def _get_datastores_service(self) -> DatastoresService:
        """获取或创建 Datastores 服务实例"""
        if self._datastores_service is None:
            # 尝试从应用获取账号信息
            # TODO: 从账号池获取凭据
            self._datastores_service = DatastoresService()
        return self._datastores_service

    def compose(self) -> Iterable:
        """构建配置管理 UI"""
        # 主容器（可滚动）
        with ScrollableContainer(id="config-container", classes="content-container"):
            # 标题
            yield Label("创建下载任务", id="config-title", classes="page-title")

            # 数据集 ID 输入区域
            with Vertical(id="dataset-section", classes="form-section"):
                yield Label("数据集 ID", classes="form-label")
                with Horizontal(classes="dataset-input-row"):
                    yield Input(
                        placeholder="reanalysis-era5-pressure-levels",
                        id="input-dataset",
                        value="reanalysis-era5-pressure-levels",
                    )
                    yield Button("加载配置", id="btn-load-schema", variant="primary")
                    yield Button("保存", id="btn-save-config", variant="default")
                    yield Button("读取", id="btn-load-config", variant="default")
                yield Label("输入数据集 ID 后点击加载", id="schema-status")

            # 动态表单区域（初始为空）
            with Vertical(id="dynamic-form-section", classes="form-section"):
                yield Label("数据集参数", classes="form-label")
                # 动态字段容器
                yield DynamicFormFieldsContainer(id="dynamic-fields")

            # 静态配置选项
            with Vertical(id="static-options-section", classes="form-section"):
                # 输出目录
                with Vertical(classes="form-section"):
                    yield Label("输出目录", classes="form-label")
                    yield Input(
                        placeholder="./data/downloads",
                        id="input-output",
                        value="./data/downloads",
                    )

                # 拆分策略配置
                with Vertical(classes="form-section"):
                    yield Label("拆分策略", classes="form-label")
                    with RadioSet(id="split-strategy-set"):
                        yield RadioButton("按月", id="strategy-month", value=True)
                        yield RadioButton("按年", id="strategy-year")
                        yield RadioButton("不拆分", id="strategy-none")

            # 任务数量预览
            with Horizontal(id="preview-info-section", classes="section-compact"):
                yield Label("将创建 0 个任务", id="task-count-label")

            # 操作按钮
            with Horizontal(id="actions-section"):
                yield Button("预览", id="btn-preview", variant="primary")
                yield Button("创建任务", id="btn-create", variant="default")
                yield Button("清空", id="btn-clear", variant="default")
                yield Button("重置", id="btn-reset", variant="default")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件处理"""
        button_id = event.button.id

        if button_id == "btn-load-schema":
            await self._handle_load_schema()

        elif button_id == "btn-save-config":
            self._handle_save_config()

        elif button_id == "btn-load-config":
            self._handle_load_config_file()

        elif button_id == "btn-preview":
            await self._handle_preview()

        elif button_id == "btn-create":
            self._handle_create()

        elif button_id == "btn-clear":
            self._handle_clear()

        elif button_id == "btn-reset":
            self._handle_reset()

    async def _handle_load_schema(self) -> None:
        """处理加载 Schema 按钮"""
        if self._is_loading:
            return

        dataset_id = self.query_one("#input-dataset", Input).value.strip()
        if not dataset_id:
            self._update_schema_status("请输入数据集 ID", "error")
            return

        self._is_loading = True
        self._update_schema_status("正在加载 Schema...", "loading")

        try:
            service = self._get_datastores_service()
            schema = service.get_dataset_schema(dataset_id)

            # 初始化表单状态
            self._form_state.init_from_schema(schema)

            # 渲染动态字段
            self._render_dynamic_fields()

            self._update_schema_status(
                f"已加载: {schema.title}（{len(schema.fields)} 个字段）",
                "success"
            )

        except DatastoresServiceError as e:
            error_msg = str(e)
            self._update_schema_status("加载失败", "error")
            # 使用 notify 显示完整错误信息
            self.notify(error_msg, severity="error", timeout=10)
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            self._update_schema_status("加载失败", "error")
            self.notify(error_msg, severity="error", timeout=10)
        finally:
            self._is_loading = False

    def _render_dynamic_fields(self) -> None:
        """渲染动态表单字段"""
        try:
            container = self.query_one("#dynamic-fields", DynamicFormFieldsContainer)
            if container is None:
                raise RuntimeError("找不到 dynamic-fields 容器")

            # 检查是否有字段
            if not self._form_state.fields:
                self.notify("警告：数据集没有可用的字段", severity="warning")
                return

            container.render_fields(self._form_state.fields)

            # 恢复从配置文件加载的字段值
            if self._pending_field_values:
                for field_name, values in self._pending_field_values.items():
                    if field_name in self._form_state.fields:
                        self._form_state.set_field_selection(field_name, values)
                        widget = container.get_field_widget(field_name)
                        if widget:
                            widget.set_selected_values(values)
                # 清空待恢复的值
                self._pending_field_values = {}

            # 初始化 area_group 相关字段的显示状态
            # 默认 area_group = global，所以隐藏 global 开关和 area 输入框
            area_group = self._form_state.fields.get("area_group")
            if area_group and area_group.selected:
                mode = str(area_group.selected[0]).strip().lower()
                global_widget = container.get_field_widget("global")
                area_widget = container.get_field_widget("area")

                if mode == "global":
                    # 默认 global 模式：隐藏 global 开关和 area 输入框
                    if global_widget:
                        global_widget.display = False
                    if area_widget:
                        area_widget.display = False
                elif mode == "area":
                    # area 模式：隐藏 global 开关
                    if global_widget:
                        global_widget.display = False

            # 刷新布局
            container.refresh(layout=True)
            self.refresh(layout=True)

        except Exception as e:
            self.notify(f"渲染字段失败: {str(e)}", severity="error")
            raise

    def _update_schema_status(self, message: str, status_type: str = "") -> None:
        """更新 Schema 加载状态显示

        Args:
            message: 状态消息
            status_type: 状态类型（loading, success, error）
        """
        status_label = self.query_one("#schema-status", Label)
        status_label.update(message)

        # 更新样式类
        status_label.remove_class("loading", "success", "error")
        if status_type:
            status_label.add_class(status_type)

    def on_dynamic_field_widget_field_changed(
        self,
        event: DynamicFieldWidget.FieldChanged,
    ) -> None:
        """处理动态字段值变化事件

        当字段值变化时，触发约束更新。
        """
        # 更新表单状态
        self._form_state.set_field_selection(event.field_name, event.selected_values)

        # 特殊互斥逻辑：area_group 用于在 global/area 两种模式间切换
        # 规则（仅在相关字段存在时生效）：
        # - 选择 global：隐藏 global 开关和 area 输入框（选了就是全球范围）
        # - 选择 area：隐藏 global 开关，显示 area 输入框
        if event.field_name == "area_group" and event.selected_values:
            mode = str(event.selected_values[0]).strip().lower()
            try:
                container = self.query_one("#dynamic-fields", DynamicFormFieldsContainer)
                global_widget = container.get_field_widget("global")
                area_widget = container.get_field_widget("area")

                if mode == "global":
                    # 选了 global 模式：隐藏 global 开关和 area 输入框
                    if global_widget:
                        global_widget.set_selected_values(["true"])
                        self._form_state.set_field_selection("global", ["true"])
                        global_widget.display = False
                    if area_widget:
                        area_widget.set_selected_values([])
                        self._form_state.set_field_selection("area", [])
                        area_widget.display = False
                elif mode == "area":
                    # 选了 area 模式：隐藏 global 开关，显示 area 输入框
                    if global_widget:
                        global_widget.set_selected_values([])
                        self._form_state.set_field_selection("global", [])
                        global_widget.display = False
                    if area_widget:
                        area_widget.display = True
                        area_widget.disabled = False
            except Exception:
                # 互斥增强逻辑不应影响主流程
                pass

        # 触发约束更新
        self._trigger_constraints_update(event.field_name)

    def _trigger_constraints_update(self, changed_field: str) -> None:
        """触发约束更新

        根据当前选择更新其他字段的可选值。

        Args:
            changed_field: 变化的字段名称
        """
        if not self._form_state.is_schema_loaded:
            return

        try:
            service = self._get_datastores_service()
            current_selection = self._form_state.get_current_selection()

            # 调用 API 获取更新后的约束
            constraints = service.apply_constraints(
                self._form_state.collection_id,
                current_selection,
            )

            # 更新表单状态
            self._form_state.update_constraints(constraints)

            # 更新 UI
            container = self.query_one("#dynamic-fields", DynamicFormFieldsContainer)
            for field_name, values in constraints.items():
                if field_name != changed_field:
                    container.update_field_values(field_name, values)

        except DatastoresServiceError as e:
            # 约束更新失败不阻塞用户操作，只记录日志
            self.log.warning(f"约束更新失败: {str(e)}")
        except Exception as e:
            self.log.warning(f"约束更新异常: {str(e)}")

    async def _handle_preview(self) -> None:
        """处理预览按钮：展示请求参数并可确认创建任务。"""
        try:
            config = self._build_config_from_form()
            split_strategy = self._get_split_strategy()
            preview_items = self._task_service.preview_tasks(config, split_strategy)

            self._update_task_count(len(preview_items))

            result = await self.app.push_screen(
                RequestPreviewDialog(preview_items, split_strategy)
            )
            if result and result.get("confirmed"):
                task_ids = self._task_service.create_batch_tasks(config, split_strategy)
                self.notify(f"已创建 {len(task_ids)} 个任务", severity="success")
                self._handle_clear()

        except ValueError as e:
            self.notify(f"参数验证失败: {str(e)}", severity="error")
        except Exception as e:
            self.notify(f"预览失败: {str(e)}", severity="error")

    def _handle_create(self) -> None:
        """处理创建任务按钮，直接创建任务。"""
        try:
            config = self._build_config_from_form()
            split_strategy = self._get_split_strategy()
            task_ids = self._task_service.create_batch_tasks(config, split_strategy)
            self._update_task_count(len(task_ids))
            self.notify(f"已创建 {len(task_ids)} 个任务", severity="success")
            self._handle_clear()

        except ValueError as e:
            self.notify(f"参数验证失败: {str(e)}", severity="error")
        except Exception as e:
            self.notify(f"创建任务失败: {str(e)}", severity="error")

    def _build_config_from_form(self) -> DownloadConfig:
        """从表单读取输入并构建下载配置。

        优先从动态表单获取值，如果动态表单未加载则使用静态字段。
        """
        dataset = self.query_one("#input-dataset", Input).value.strip()
        if not dataset:
            raise ValueError("请输入数据集 ID")

        output_dir = self.query_one("#input-output", Input).value.strip()

        # 从动态表单获取参数
        if self._form_state.is_schema_loaded:
            config_dict = self._form_state.to_download_config_dict()
            config_dict["dataset"] = dataset
            config_dict["output_dir"] = output_dir

            # 验证必填字段
            errors = self._form_state.validate()
            if errors:
                raise ValueError("; ".join(errors))

            return DownloadConfig(**config_dict)

        # 回退：如果动态表单未加载，显示提示
        raise ValueError("请先加载数据集 Schema")

    def _get_split_strategy(self) -> Literal["month", "year", "none"]:
        """获取当前选中的拆分策略。"""
        radio_set = self.query_one("#split-strategy-set", RadioSet)
        pressed = radio_set.pressed_button
        if pressed is None:
            return "month"

        if pressed.id == "strategy-year":
            return "year"
        if pressed.id == "strategy-none":
            return "none"
        return "month"

    def _update_task_count(self, count: int) -> None:
        """更新任务数量提示标签。"""
        self.query_one("#task-count-label", Label).update(f"将创建 {count} 个任务")

    def _handle_clear(self) -> None:
        """清空表单"""
        # 清空数据集输入
        self.query_one("#input-dataset", Input).value = ""
        self._update_schema_status("输入数据集 ID 后点击加载", "")

        # 清空动态字段
        if self._form_state.is_schema_loaded:
            container = self.query_one("#dynamic-fields", DynamicFormFieldsContainer)
            container.clear_all()

        # 清空静态字段
        self.query_one("#input-output", Input).value = ""

        self._update_task_count(0)

    def _handle_reset(self) -> None:
        """重置表单为默认值"""
        # 重置数据集
        self.query_one("#input-dataset", Input).value = "reanalysis-era5-pressure-levels"
        self._update_schema_status("输入数据集 ID 后点击加载", "")

        # 重置表单状态
        self._form_state = DynamicFormState()

        # 清空动态字段容器
        container = self.query_one("#dynamic-fields", DynamicFormFieldsContainer)
        for child in list(container.children):
            child.remove()

        # 重置静态字段
        self.query_one("#input-output", Input).value = "./data/downloads"

        # 重置拆分策略
        strategy_set = self.query_one("#split-strategy-set", RadioSet)
        buttons = list(strategy_set.query(RadioButton))
        for i, btn in enumerate(buttons):
            btn.value = (i == 0)

        self._update_task_count(0)

    def _handle_save_config(self) -> None:
        """保存当前配置到文件（弹出输入框让用户输入名称）"""
        from textual.screen import ModalScreen
        from textual.containers import Vertical, Horizontal
        textual_widgets_Input = Input

        class SaveConfigDialog(ModalScreen):
            """保存配置对话框"""

            DEFAULT_CSS = """
            SaveConfigDialog {
                align: center middle;
            }

            SaveConfigDialog > Vertical {
                width: 50;
                height: auto;
                background: $surface;
                border: thick $primary;
                padding: 1 2;
            }

            SaveConfigDialog Label {
                margin-bottom: 1;
            }

            SaveConfigDialog Input {
                width: 1fr;
                margin-bottom: 1;
            }

            SaveConfigDialog Horizontal {
                height: auto;
                align: center middle;
            }

            SaveConfigDialog Button {
                min-width: 10;
                margin: 0 1;
            }
            """

            def __init__(self, default_name: str, callback):
                super().__init__()
                self._default_name = default_name
                self._callback = callback

            def compose(self):
                with Vertical():
                    yield Label("保存配置")
                    yield Input(value=self._default_name, placeholder="输入配置名称", id="config-name-input")
                    with Horizontal():
                        yield Button("保存", id="btn-confirm-save", variant="primary")
                        yield Button("取消", id="btn-cancel-save", variant="default")

            def on_button_pressed(self, event):
                if event.button.id == "btn-confirm-save":
                    name = self.query_one("#config-name-input", Input).value.strip()
                    if name:
                        self._callback(name)
                    self.dismiss()
                elif event.button.id == "btn-cancel-save":
                    self.dismiss()

            def on_key(self, event):
                if event.key == "escape":
                    self.dismiss()

        # 生成默认名称
        dataset_id = self.query_one("#input-dataset", Input).value.strip() or "config"
        default_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in dataset_id)

        def do_save(name: str):
            self._do_save_config(name)

        self.app.push_screen(SaveConfigDialog(default_name, do_save))

    def _do_save_config(self, name: str) -> None:
        """实际保存配置到文件（保存完整的字段定义）"""
        from pathlib import Path

        # 收集当前配置
        config_data = {
            "dataset": self.query_one("#input-dataset", Input).value.strip(),
            "output_dir": self.query_one("#input-output", Input).value.strip(),
            "split_strategy": self._get_split_strategy(),
            "fields": {},
        }

        # 收集完整的字段定义（包括可选值和已选中的值）
        if self._form_state.is_schema_loaded:
            for field_name, field in self._form_state.fields.items():
                field_info = {
                    "label": field.label,
                    "field_type": field.field_type.value,
                    "required": field.required,
                    "values": field.values,  # 可选值列表
                    "selected": field.selected,  # 已选中的值
                    "details": field.definition.details,  # 字段定义详情
                }
                config_data["fields"][field_name] = field_info

        # 保存到文件
        config_dir = Path("./data/configs")
        config_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        config_file = config_dir / f"{safe_name}.json"

        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            self.notify(f"配置已保存: {name}", severity="success")
        except Exception as e:
            self.notify(f"保存失败: {str(e)}", severity="error")

    def _handle_load_config_file(self) -> None:
        """从文件加载配置（弹出选择框让用户选择）"""
        from pathlib import Path
        from textual.screen import ModalScreen
        from textual.widgets import Select as SelectWidget
        from textual.containers import Vertical, Horizontal
        import os

        config_dir = Path("./data/configs")
        config_dir.mkdir(parents=True, exist_ok=True)

        # 查找所有配置文件
        config_files = list(config_dir.glob("*.json"))
        if not config_files:
            self.notify("没有找到保存的配置文件", severity="warning")
            return

        # 按修改时间排序
        config_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        options = [(f.stem, str(f)) for f in config_files]

        class LoadConfigDialog(ModalScreen):
            """加载配置对话框"""

            DEFAULT_CSS = """
            LoadConfigDialog {
                align: center middle;
            }

            LoadConfigDialog > Vertical {
                width: 50;
                height: auto;
                background: $surface;
                border: thick $primary;
                padding: 1 2;
            }

            LoadConfigDialog Label {
                margin-bottom: 1;
            }

            LoadConfigDialog Select {
                width: 1fr;
                margin-bottom: 1;
            }

            LoadConfigDialog Horizontal {
                height: auto;
                align: center middle;
            }

            LoadConfigDialog Button {
                min-width: 10;
                margin: 0 1;
            }
            """

            def __init__(self, options, callback):
                super().__init__()
                self._options = options
                self._callback = callback

            def compose(self):
                with Vertical():
                    yield Label("选择配置文件")
                    yield SelectWidget(
                        options=[(name, path) for name, path in self._options],
                        id="config-select",
                        allow_blank=False,
                    )
                    with Horizontal():
                        yield Button("加载", id="btn-confirm-load", variant="primary")
                        yield Button("取消", id="btn-cancel-load", variant="default")

            def on_button_pressed(self, event):
                if event.button.id == "btn-confirm-load":
                    select = self.query_one("#config-select", SelectWidget)
                    if select.value:
                        self._callback(select.value)
                    self.dismiss()
                elif event.button.id == "btn-cancel-load":
                    self.dismiss()

            def on_key(self, event):
                if event.key == "escape":
                    self.dismiss()

        def do_load(path: str):
            self._load_config_from_file(path)

        self.app.push_screen(LoadConfigDialog(options, do_load))

    def _load_config_from_file(self, config_path: str) -> None:
        """从指定文件加载配置（直接恢复完整表单，不需要 API）"""
        from src.core.dataset_schema import FormFieldDefinition, FieldType

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # 恢复数据集 ID
            if config_data.get("dataset"):
                self.query_one("#input-dataset", Input).value = config_data["dataset"]

            # 恢复输出目录
            if config_data.get("output_dir"):
                self.query_one("#input-output", Input).value = config_data["output_dir"]

            # 恢复拆分策略
            strategy = config_data.get("split_strategy", "month")
            strategy_set = self.query_one("#split-strategy-set", RadioSet)
            buttons = list(strategy_set.query(RadioButton))
            strategy_map = {"month": 0, "year": 1, "none": 2}
            target_index = strategy_map.get(strategy, 0)
            for i, btn in enumerate(buttons):
                btn.value = (i == target_index)

            # 从配置文件恢复完整的字段定义
            fields_data = config_data.get("fields", {})
            if fields_data:
                # 创建 FormFieldDefinition 和 DynamicFormField 对象
                from src.core.dataset_schema import DynamicFormField

                self._form_state.fields = {}
                self._form_state.collection_id = config_data.get("dataset", "")
                self._form_state.is_schema_loaded = True

                for field_name, field_info in fields_data.items():
                    # 创建字段定义
                    field_def = FormFieldDefinition(
                        name=field_name,
                        label=field_info.get("label", field_name),
                        field_type=FieldType(field_info.get("field_type", "string_array")),
                        required=field_info.get("required", False),
                        details=field_info.get("details", {}),
                    )

                    # 创建字段状态
                    field_state = DynamicFormField(
                        definition=field_def,
                        values=field_info.get("values", []),
                    )
                    if field_info.get("selected"):
                        field_state.set_selected(field_info["selected"])

                    self._form_state.fields[field_name] = field_state

                # 渲染动态字段
                self._render_dynamic_fields()

                self._update_schema_status(
                    f"已从配置文件加载（{len(fields_data)} 个字段）",
                    "success"
                )

            self.notify("配置已加载", severity="success")

        except Exception as e:
            self.notify(f"加载失败: {str(e)}", severity="error")

    def refresh_data(self) -> None:
        """刷新配置数据（无需实现）"""
        pass

    def on_unmount(self) -> None:
        """组件卸载时清理"""
        # 配置管理不需要观察者模式
        pass

    def on_key(self, event: Key) -> None:
        """处理键盘事件

        Enter键：如果焦点在按钮上，触发按钮操作；如果在输入框，默认提交表单
        方向键：由各个控件自行处理（输入框、按钮等）
        Tab键：返回侧边栏（由ContentArea处理）

        Args:
            event: 键盘事件
        """
        # Enter键处理
        if event.key == "enter":
            # 检查焦点所在控件
            focused = self.app.focused
            if focused and isinstance(focused, Button):
                # 焦点在按钮上，触发按钮
                focused.action_press()
                event.stop()
            elif focused and isinstance(focused, Input):
                # 焦点在输入框上，可以按Tab切换到下一个输入框，或按Enter提交
                # 这里不阻止Enter，让输入框的默认行为处理（换行等）
                pass

        # Tab键交给ContentArea处理（返回侧边栏）
        # 方向键由各个控件自行处理
