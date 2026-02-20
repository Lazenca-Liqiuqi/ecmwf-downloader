"""
ECMWF Downloader TUI 配置管理内容组件（动态表单版）

!! 弃用警告 !!
本模块已弃用，请使用新模块：
    from src.ui.pages.create_task import CreateTaskView

新模块位置：src/ui/pages/create_task/

提供基于数据集 Schema 的动态配置表单，支持：
- 从 ecmwf-datastores-client 获取数据集字段定义
- 约束驱动的字段更新（如选择年份后自动更新可选日期）
- 创建新的下载任务

支持方向键操作：输入框用方向键移动光标，Enter键触发按钮。
"""

import warnings

# 发出弃用警告
warnings.warn(
    "config_content.ConfigContent 已弃用，请使用 src.ui.pages.create_task.CreateTaskView",
    DeprecationWarning,
    stacklevel=2,
)

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Select, Static

from src.core.config import DownloadConfig
from src.core.dataset_schema import DynamicFormState, DynamicFormField
from src.core.task_service import TaskService
from src.core.ai_generator import AIGenerator, AIGeneratorError
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

    .form-section {
        height: auto;
        margin-bottom: 1;
    }

    #actions-section {
        height: auto;
        margin: 1 3 0 3;
        padding: 0 1;
    }

    #actions-section Button {
        width: 1fr;
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

    #btn-load-schema, #btn-save-config, #btn-load-config, #btn-ai-generate {
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

        # 约束更新序号（用于丢弃过期结果）
        self._constraints_seq = 0

        # AI 生成器（延迟初始化）
        self._ai_generator: Optional[AIGenerator] = None

    def _get_datastores_service(self) -> DatastoresService:
        """获取或创建 Datastores 服务实例

        从账号池获取活跃账号的凭据来初始化服务。
        """
        if self._datastores_service is None:
            # 从应用账号池获取凭据
            key, url = None, None

            try:
                if hasattr(self._app_ref, 'account_pool') and self._app_ref.account_pool:
                    # 使用 get_next_account 获取可用账号
                    account = self._app_ref.account_pool.get_next_account()
                    if account:
                        key = account.key
                        url = account.url
                        self.log.info(f"使用账号 {account.id} 的凭据")
            except Exception as e:
                self.log.warning(f"获取账号凭据失败: {e}")

            self._datastores_service = DatastoresService(
                url=url or "https://cds.climate.copernicus.eu/api",
                key=key,
            )
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
                        placeholder="输入数据集 ID",
                        id="input-dataset",
                        value="",
                    )
                    yield Button("在线加载", id="btn-load-schema", variant="primary")
                    yield Button("保存", id="btn-save-config", variant="default")
                    yield Button("读取", id="btn-load-config", variant="default")
                    yield Button("AI生成", id="btn-ai-generate", variant="default")
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

            # 操作按钮
            with Horizontal(id="actions-section"):
                yield Button("预览", id="btn-preview", variant="primary")
                yield Button("创建任务", id="btn-create", variant="default")
                yield Button("清空参数", id="btn-clear", variant="default")
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

        elif button_id == "btn-ai-generate":
            self._handle_ai_generate()

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
        load_button = self.query_one("#btn-load-schema", Button)
        load_button.disabled = True

        try:
            service = self._get_datastores_service()
            # 网络请求放到后台线程，避免阻塞 TUI 主线程
            schema = await asyncio.to_thread(
                service.get_dataset_schema,
                dataset_id,
            )

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
            load_button.disabled = False

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

            # 定义挂载完成后的回调
            def on_fields_mounted():
                """字段挂载完成后的回调"""
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

            # 渲染字段，使用回调处理异步挂载
            container.render_fields(self._form_state.fields, on_complete=on_fields_mounted)

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

        # 触发约束更新（异步，避免阻塞 UI）
        self._schedule_constraints_update(event.field_name)

    def _schedule_constraints_update(self, changed_field: str) -> None:
        """调度约束更新（异步）

        根据当前选择更新其他字段的可选值，并在后台线程执行网络调用。
        使用序号丢弃过期结果，避免快速操作时旧结果覆盖新状态。

        Args:
            changed_field: 变化的字段名称
        """
        if not self._form_state.is_schema_loaded:
            return
        self._constraints_seq += 1
        seq = self._constraints_seq
        self.run_worker(
            self._apply_constraints_update(changed_field, seq),
            name="constraints-update",
            group="constraints-update",
            exclusive=True,
            exit_on_error=False,
        )

    async def _apply_constraints_update(
        self,
        changed_field: str,
        seq: int,
    ) -> None:
        """执行约束更新（后台线程 + 主线程回写）"""
        if not self._form_state.is_schema_loaded:
            return

        try:
            service = self._get_datastores_service()
            current_selection = self._form_state.get_current_selection()

            # 调用 API 获取更新后的约束（放后台线程）
            constraints = await asyncio.to_thread(
                service.apply_constraints,
                self._form_state.collection_id,
                current_selection,
            )

            # 丢弃过期结果，防止旧请求覆盖新状态
            if seq != self._constraints_seq or not self.is_mounted:
                return

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

            def do_create():
                self._handle_create()

            self.app.push_screen(
                RequestPreviewDialog(preview_items, split_strategy, callback=do_create)
            )

        except ValueError as e:
            # 转义方括号避免 Textual markup 解析错误
            error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
            self.notify(f"参数验证失败: {error_msg}", severity="error")
        except Exception as e:
            error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
            self.notify(f"预览失败: {error_msg}", severity="error")

    def _handle_create(self) -> None:
        """处理创建任务按钮，直接创建任务。"""
        try:
            config = self._build_config_from_form()
            split_strategy = self._get_split_strategy()
            task_ids = self._task_service.create_batch_tasks(config, split_strategy)
            self.notify(f"已创建 {len(task_ids)} 个任务", severity="success")
            self._handle_clear()

        except ValueError as e:
            error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
            self.notify(f"参数验证失败: {error_msg}", severity="error")
        except Exception as e:
            error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
            self.notify(f"创建任务失败: {error_msg}", severity="error")

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

    def _handle_reset(self) -> None:
        """重置表单（清空所有内容）"""
        # 清空数据集
        self.query_one("#input-dataset", Input).value = ""
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
                config_data["fields"][field_name] = self._serialize_field_config(field)

        # 保存到文件
        config_dir = Path("./data/configs")
        config_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        config_file = config_dir / f"{safe_name}.json"
        temp_file = config_dir / f"{safe_name}.json.tmp"

        try:
            config_json = json.dumps(
                self._to_json_safe(config_data),
                indent=2,
                ensure_ascii=False,
            )
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(config_json)
            temp_file.replace(config_file)
            self.notify(f"配置已保存: {name}", severity="success")
        except Exception as e:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
            self.notify(f"保存失败: {str(e)}", severity="error")

    def _handle_load_config_file(self) -> None:
        """从文件加载配置（弹出选择框让用户选择）"""
        from textual.screen import ModalScreen
        from textual.widgets import Select as SelectWidget
        from textual.containers import Vertical, Horizontal

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
                self._form_state.fields = {}
                self._form_state.collection_id = config_data.get("dataset", "")
                self._form_state.is_schema_loaded = True

                for field_name, field_info in fields_data.items():
                    if not isinstance(field_info, dict):
                        continue
                    if "definition" not in field_info:
                        raise ValueError("配置格式过旧，请重新在线加载后保存")
                    self._form_state.fields[field_name] = self._deserialize_field_config(
                        field_name,
                        field_info,
                    )

                # 渲染动态字段
                self._render_dynamic_fields()

                self._update_schema_status(
                    f"已从配置文件加载（{len(fields_data)} 个字段）",
                    "success"
                )

            self.notify("配置已加载", severity="success")

        except Exception as e:
            self.notify(f"加载失败: {str(e)}", severity="error")

    @staticmethod
    def _to_json_safe(value: Any) -> Any:
        """将任意值转换为可 JSON 序列化的数据结构。"""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): ConfigContent._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [ConfigContent._to_json_safe(v) for v in value]
        if isinstance(value, set):
            return [ConfigContent._to_json_safe(v) for v in sorted(value, key=lambda x: str(x))]
        return str(value)

    @classmethod
    def _serialize_field_config(cls, field: DynamicFormField) -> Dict[str, Any]:
        """序列化单个字段配置（仅保留新格式必要信息）。"""
        raw_definition = cls._to_json_safe(field.definition.details or {})
        return {
            "field_type": field.field_type.value,
            "selected": cls._to_json_safe(field.selected),
            "definition": raw_definition,
        }

    @classmethod
    def _deserialize_field_config(
        cls,
        field_name: str,
        field_info: Dict[str, Any],
    ) -> DynamicFormField:
        """反序列化单个字段配置（仅支持新格式）。"""
        from src.core.dataset_schema import DynamicFormField, FieldType, FormFieldDefinition

        definition = field_info.get("definition", {})
        if not isinstance(definition, dict):
            definition = {}

        field_data = dict(definition)
        field_data.setdefault("name", field_name)

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
        definition_values = cls._extract_all_values_from_definition(field_data)
        values = definition_values if isinstance(definition_values, list) else []

        field_state = DynamicFormField(
            definition=field_def,
            values=[str(v) for v in values],
        )

        selected = field_info.get("selected", [])
        if isinstance(selected, list):
            normalized_selected = selected
        elif selected in (None, ""):
            normalized_selected = []
        else:
            normalized_selected = [selected]

        # 单值字段只取第一个
        if field_type in (FieldType.STRING_SINGLE, FieldType.INTEGER_SINGLE, FieldType.BOOLEAN, FieldType.EXCLUSIVE_GROUP):
            normalized_selected = normalized_selected[:1] if normalized_selected else []

        field_state.set_selected(normalized_selected)
        return field_state

    @staticmethod
    def _extract_all_values_from_definition(raw_definition: Any) -> List[Any]:
        """从原始定义中提取完整可选值列表。"""
        if not isinstance(raw_definition, dict):
            return []

        details = raw_definition.get("details", {})
        if not isinstance(details, dict):
            details = {}

        for key in ("values", "options", "choices", "items"):
            value = details.get(key)
            if isinstance(value, list) and value:
                # 支持 [{"id": "..."}] 与 ["..."] 两种格式
                result: List[Any] = []
                for item in value:
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

        # 特殊控件：LicenceWidget
        licences = details.get("licences")
        if isinstance(licences, list) and licences:
            result = []
            for item in licences:
                if isinstance(item, dict) and "id" in item:
                    result.append(item["id"])
                else:
                    result.append(item)
            return result

        return []

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

    def _get_ai_generator(self) -> AIGenerator:
        """获取或创建 AI 生成器实例"""
        if self._ai_generator is None:
            self._ai_generator = AIGenerator()
        return self._ai_generator

    def _handle_ai_generate(self) -> None:
        """处理 AI 生成按钮：弹出对话框让用户输入需求"""
        # 检查表单是否已加载
        if not self._form_state.is_schema_loaded:
            self.notify("请先加载数据集 Schema", severity="warning")
            return

        # 检查 AI 是否配置
        generator = self._get_ai_generator()
        if not generator.is_configured:
            self.notify(
                "AI 功能未配置，请在 config/ai_config.yaml 中设置 api_key",
                severity="warning",
            )
            return

        # 弹出对话框让用户输入需求
        from textual.screen import ModalScreen
        from textual.widgets import TextArea

        class AIGenerateDialog(ModalScreen):
            """AI 生成对话框"""

            DEFAULT_CSS = """
            AIGenerateDialog {
                align: center middle;
            }

            AIGenerateDialog > Vertical {
                width: 60;
                height: auto;
                max-height: 80%;
                background: $surface;
                border: thick $primary;
                padding: 1 2;
            }

            AIGenerateDialog Label {
                margin-bottom: 1;
            }

            AIGenerateDialog TextArea {
                width: 1fr;
                height: 8;
                margin-bottom: 1;
                border: round $panel;
            }

            AIGenerateDialog Horizontal {
                height: auto;
                align: center middle;
            }

            AIGenerateDialog Button {
                min-width: 10;
                margin: 0 1;
            }
            """

            def __init__(self, callback):
                super().__init__()
                self._callback = callback

            def compose(self):
                with Vertical():
                    yield Label("AI 生成参数", classes="dialog-title")
                    yield Label("请描述您需要的数据（如：下载2024年1月的温度数据）")
                    yield TextArea(
                        id="ai-request-input",
                        placeholder="下载2024年1月的温度数据...",
                    )
                    with Horizontal():
                        yield Button("生成", id="btn-confirm-ai", variant="primary")
                        yield Button("取消", id="btn-cancel-ai", variant="default")

            def on_button_pressed(self, event):
                if event.button.id == "btn-confirm-ai":
                    textarea = self.query_one("#ai-request-input", TextArea)
                    request_text = textarea.text.strip()
                    if request_text:
                        self._callback(request_text)
                    else:
                        self.app.notify("请输入您的需求", severity="warning")
                        return
                    self.dismiss()
                elif event.button.id == "btn-cancel-ai":
                    self.dismiss()

            def on_key(self, event):
                if event.key == "escape":
                    self.dismiss()

        def do_generate(request_text: str):
            self._execute_ai_generate(request_text)

        self.app.push_screen(AIGenerateDialog(do_generate))

    def _execute_ai_generate(self, user_request: str) -> None:
        """执行 AI 生成（异步 Worker）

        Args:
            user_request: 用户的自然语言需求
        """
        self.run_worker(
            self._do_ai_generate(user_request),
            name="ai-generate",
            group="ai-generate",
            exclusive=True,
            exit_on_error=False,
        )

    async def _do_ai_generate(self, user_request: str) -> None:
        """实际执行 AI 生成

        Args:
            user_request: 用户的自然语言需求
        """
        # 禁用按钮，显示加载状态
        ai_button = self.query_one("#btn-ai-generate", Button)
        ai_button.disabled = True
        self._update_schema_status("AI 正在生成参数...", "loading")

        try:
            generator = self._get_ai_generator()

            # 准备字段 schema
            field_schema = {}
            for field_name, field in self._form_state.fields.items():
                field_schema[field_name] = {
                    "field_type": field.field_type.value,
                    "values": list(field.values),
                    "selected": [],  # 清空已选项
                }

            # 调用 AI 生成（网络请求放后台线程）
            import asyncio
            result = await asyncio.to_thread(
                generator.generate,
                field_schema,
                user_request,
            )

            # 将 AI 生成的 selected 应用到表单
            self._apply_ai_result(result)

            self._update_schema_status(
                f"AI 生成完成（已填充 {len(result)} 个字段）",
                "success",
            )
            self.notify("AI 参数生成成功", severity="success")

        except AIGeneratorError as e:
            self._update_schema_status("AI 生成失败", "error")
            self.notify(f"AI 生成失败: {str(e)}", severity="error", timeout=8)
        except Exception as e:
            self._update_schema_status("AI 生成异常", "error")
            self.notify(f"AI 生成异常: {str(e)}", severity="error", timeout=8)
        finally:
            ai_button.disabled = False

    def _apply_ai_result(self, result: Dict[str, Any]) -> None:
        """将 AI 生成结果应用到表单

        Args:
            result: AI 生成的字段配置（包含 selected）
        """
        container = self.query_one("#dynamic-fields", DynamicFormFieldsContainer)

        for field_name, field_info in result.items():
            if field_name not in self._form_state.fields:
                continue

            selected = field_info.get("selected", [])
            if not selected:
                continue

            # 更新表单状态
            self._form_state.set_field_selection(field_name, selected)

            # 更新 UI
            widget = container.get_field_widget(field_name)
            if widget:
                widget.set_selected_values(selected)
