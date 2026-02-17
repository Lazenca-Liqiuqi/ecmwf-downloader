"""
ECMWF Downloader TUI 配置管理内容组件

提供下载参数配置表单，支持创建新的下载任务。
这是从ConfigScreen迁移而来的Widget版本。
支持方向键操作：输入框用方向键移动光标，Enter键触发按钮。
"""

from typing import Iterable, Literal

from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RadioButton, RadioSet

from src.core.config import DownloadConfig
from src.core.task_service import TaskService
from src.ui.dialogs import RequestPreviewDialog


class ConfigContent(Widget):
    """配置管理内容组件

    功能：
    - 显示下载参数配置表单
    - 创建新的下载任务
    - 使用 Pydantic 进行参数验证
    """

    DEFAULT_CSS = """
    ConfigContent {
        width: 1fr;
        height: 1fr;
        overflow: hidden;
    }

    #config-container {
        width: 1fr;
        height: 1fr;
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
    }

    ConfigContent Input {
        width: 1fr;
        min-height: 3;
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

    #dataset-label,
    #variables-label,
    #years-label,
    #months-label,
    #area-label,
    #levels-label,
    #output-label,
    #strategy-label {
        text-style: bold;
        margin-bottom: 0;
        color: $text 80%;
    }

    #task-count-label {
        text-style: bold;
        color: $accent;
    }

    #dataset-section,
    #variables-section,
    #output-section,
    #strategy-section,
    #preview-info-section,
    #time-section,
    #spatial-section,
    #actions-section {
        height: auto;
    }

    #actions-section {
        min-height: 3;
        margin: 0 3 0 3;
        padding: 0 1;
    }

    #years-container,
    #months-container,
    #area-container,
    #levels-container {
        width: 1fr;
        height: auto;
    }

    #split-strategy-set {
        height: auto;
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

    def compose(self) -> Iterable:
        """构建配置管理 UI"""
        # 主容器（可滚动）
        with ScrollableContainer(id="config-container", classes="content-container"):
            # 标题
            yield Label("创建下载任务", id="config-title", classes="page-title")

            # 数据集配置
            with Vertical(id="dataset-section", classes="form-section"):
                yield Label("数据集类型", id="dataset-label")
                yield Input(
                    placeholder="reanalysis-era5-pressure-levels",
                    id="input-dataset",
                    value="reanalysis-era5-pressure-levels",
                )

            # 变量配置
            with Vertical(id="variables-section", classes="form-section"):
                yield Label("变量列表（逗号分隔）", id="variables-label")
                yield Input(
                    placeholder="temperature,geopotential",
                    id="input-variables",
                )

            # 时间配置
            with Horizontal(id="time-section", classes="section-compact"):
                with Vertical(id="years-container"):
                    yield Label("年份（逗号分隔）", id="years-label")
                    yield Input(placeholder="2020,2021", id="input-years")

                with Vertical(id="months-container"):
                    yield Label("月份（逗号分隔）", id="months-label")
                    yield Input(placeholder="1,2,3", id="input-months")

            # 空间配置
            with Horizontal(id="spatial-section", classes="section-compact"):
                with Vertical(id="area-container"):
                    yield Label("区域范围（N,W,S,E）", id="area-label")
                    yield Input(placeholder="90,-180,-90,180", id="input-area")

                with Vertical(id="levels-container"):
                    yield Label("气压层（逗号分隔）", id="levels-label")
                    yield Input(
                        placeholder="500,850,1000",
                        id="input-levels",
                    )

            # 输出配置
            with Vertical(id="output-section", classes="form-section"):
                yield Label("输出目录", id="output-label")
                yield Input(
                    placeholder="./data/downloads",
                    id="input-output",
                    value="./data/downloads",
                )

            # 拆分策略配置
            with Vertical(id="strategy-section", classes="form-section"):
                yield Label("拆分策略", id="strategy-label")
                with RadioSet(id="split-strategy-set"):
                    yield RadioButton("按月", id="strategy-month", value=True)
                    yield RadioButton("按年", id="strategy-year")
                    yield RadioButton("不拆分", id="strategy-none")

            # 任务数量预览
            with Horizontal(id="preview-info-section", classes="section-compact"):
                yield Label("将创建 0 个任务", id="task-count-label")

            # 操作按钮（不使用全局 button-section 类，避免固定高度冲突）
            with Horizontal(id="actions-section"):
                yield Button("预览", id="btn-preview", variant="primary")
                yield Button("创建任务", id="btn-create", variant="default")
                yield Button("清空", id="btn-clear", variant="default")
                yield Button("重置", id="btn-reset", variant="default")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件处理"""
        button_id = event.button.id

        if button_id == "btn-preview":
            await self._handle_preview()

        elif button_id == "btn-create":
            self._handle_create()

        elif button_id == "btn-clear":
            self._handle_clear()

        elif button_id == "btn-reset":
            self._handle_reset()

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
        """从表单读取输入并构建下载配置。"""
        dataset = self.query_one("#input-dataset", Input).value.strip()
        variables_str = self.query_one("#input-variables", Input).value.strip()
        years_str = self.query_one("#input-years", Input).value.strip()
        months_str = self.query_one("#input-months", Input).value.strip()
        area_str = self.query_one("#input-area", Input).value.strip()
        levels_str = self.query_one("#input-levels", Input).value.strip()
        output_dir = self.query_one("#input-output", Input).value.strip()

        if not dataset:
            raise ValueError("请输入数据集类型")
        if not variables_str:
            raise ValueError("请输入变量列表")
        if not years_str:
            raise ValueError("请输入年份")
        if not months_str:
            raise ValueError("请输入月份")

        variables = [item.strip() for item in variables_str.split(",") if item.strip()]
        years = [int(item.strip()) for item in years_str.split(",") if item.strip()]
        months = [int(item.strip()) for item in months_str.split(",") if item.strip()]

        area = None
        if area_str:
            area = [float(item.strip()) for item in area_str.split(",") if item.strip()]

        pressure_levels = None
        if levels_str:
            pressure_levels = [
                int(item.strip()) for item in levels_str.split(",") if item.strip()
            ]

        return DownloadConfig(
            dataset=dataset,
            variables=variables,
            years=years,
            months=months,
            days=None,
            times=None,
            pressure_levels=pressure_levels,
            area=area,
            output_dir=output_dir,
        )

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
        self.query_one("#input-dataset", Input).value = ""
        self.query_one("#input-variables", Input).value = ""
        self.query_one("#input-years", Input).value = ""
        self.query_one("#input-months", Input).value = ""
        self.query_one("#input-area", Input).value = ""
        self.query_one("#input-levels", Input).value = ""
        self.query_one("#input-output", Input).value = ""
        self._update_task_count(0)

    def _handle_reset(self) -> None:
        """重置表单为默认值"""
        self.query_one("#input-dataset", Input).value = "reanalysis-era5-pressure-levels"
        self.query_one("#input-variables", Input).value = ""
        self.query_one("#input-years", Input).value = ""
        self.query_one("#input-months", Input).value = ""
        self.query_one("#input-area", Input).value = ""
        self.query_one("#input-levels", Input).value = ""
        self.query_one("#input-output", Input).value = "./data/downloads"
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
