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
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

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
        background: $surface;
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

    #btn-load-schema {
        min-width: 15;
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
                    yield Button("加载 Schema", id="btn-load-schema", variant="primary")
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

        # 特殊互斥逻辑：area_group 通常用于在 global/area 两种模式间切换
        # 规则（仅在相关字段存在时生效）：
        # - 选择 global：自动开启 global 开关并禁用/清空 area
        # - 选择 area：关闭 global 并启用 area
        if event.field_name == "area_group" and event.selected_values:
            mode = str(event.selected_values[0]).strip().lower()
            try:
                container = self.query_one("#dynamic-fields", DynamicFormFieldsContainer)
                global_widget = container.get_field_widget("global")
                area_widget = container.get_field_widget("area")

                if mode == "global":
                    if global_widget:
                        global_widget.disabled = False
                        global_widget.set_selected_values(["true"])
                        self._form_state.set_field_selection("global", ["true"])
                    if area_widget:
                        area_widget.set_selected_values([])
                        self._form_state.set_field_selection("area", [])
                        area_widget.disabled = True
                elif mode == "area":
                    if global_widget:
                        global_widget.set_selected_values([])
                        self._form_state.set_field_selection("global", [])
                        global_widget.disabled = True
                    if area_widget:
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
        strategy_set.pressed_index = 0

        self._update_task_count(0)

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
