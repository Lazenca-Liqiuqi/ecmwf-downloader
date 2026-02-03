"""
ECMWF Downloader TUI 配置管理内容组件

提供下载参数配置表单，支持创建新的下载任务。
这是从ConfigScreen迁移而来的Widget版本。
"""

from typing import Iterable

from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Input, Label

from src.core.config import DownloadConfig


class ConfigContent(Widget):
    """配置管理内容组件

    功能：
    - 显示下载参数配置表单
    - 创建新的下载任务
    - 使用 Pydantic 进行参数验证
    """

    CSS = """
    #config-container {
        padding: 1 1 1 1;
    }

    #config-title {
        text-align: left;
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 2;
    }

    #dataset-section,
    #variables-section,
    #output-section {
        margin: 1 3 1 3;
    }

    #dataset-label,
    #variables-label,
    #years-label,
    #months-label,
    #area-label,
    #levels-label,
    #output-label {
        text-style: bold;
        margin-bottom: 0;
        color: $text 80%;
    }

    #time-section,
    #spatial-section {
        height: 4;
        margin: 0 3 1 3;
    }

    #years-container,
    #months-container,
    #area-container,
    #levels-container {
        width: 1fr;
    }

    #actions-section {
        height: 3;
        margin: 2 3 0 3;
    }

    #actions-section Button {
        width: 1fr;
        margin: 0 1;
        padding: 0 2;
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

    def compose(self) -> Iterable:
        """构建配置管理 UI"""
        # 主容器
        with Container(id="config-container"):
            # 标题
            yield Label("创建下载任务", id="config-title")

            # 数据集配置
            with Vertical(id="dataset-section"):
                yield Label("数据集类型", id="dataset-label")
                yield Input(
                    placeholder="reanalysis-era5-pressure-levels",
                    id="input-dataset",
                    value="reanalysis-era5-pressure-levels",
                )

            # 变量配置
            with Vertical(id="variables-section"):
                yield Label("变量列表（逗号分隔）", id="variables-label")
                yield Input(
                    placeholder="temperature,geopotential",
                    id="input-variables",
                )

            # 时间配置
            with Horizontal(id="time-section"):
                with Vertical(id="years-container"):
                    yield Label("年份（逗号分隔）", id="years-label")
                    yield Input(placeholder="2020,2021", id="input-years")

                with Vertical(id="months-container"):
                    yield Label("月份（逗号分隔）", id="months-label")
                    yield Input(placeholder="1,2,3", id="input-months")

            # 空间配置
            with Horizontal(id="spatial-section"):
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
            with Vertical(id="output-section"):
                yield Label("输出目录", id="output-label")
                yield Input(
                    placeholder="./data/downloads",
                    id="input-output",
                    value="./data/downloads",
                )

            # 操作按钮
            with Horizontal(id="actions-section"):
                yield Button("创建任务", id="btn-create", variant="default")
                yield Button("清空", id="btn-clear", variant="default")
                yield Button("重置", id="btn-reset", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件处理"""
        button_id = event.button.id

        if button_id == "btn-create":
            self._handle_create()

        elif button_id == "btn-clear":
            self._handle_clear()

        elif button_id == "btn-reset":
            self._handle_reset()

    def _handle_create(self) -> None:
        """处理创建任务"""
        try:
            # 获取表单数据
            dataset = self.query_one("#input-dataset", Input).value.strip()
            variables_str = self.query_one("#input-variables", Input).value.strip()
            years_str = self.query_one("#input-years", Input).value.strip()
            months_str = self.query_one("#input-months", Input).value.strip()
            area_str = self.query_one("#input-area", Input).value.strip()
            levels_str = self.query_one("#input-levels", Input).value.strip()
            output_dir = self.query_one("#input-output", Input).value.strip()

            # 验证必填字段
            if not dataset:
                self.notify("请输入数据集类型", severity="warning")
                return

            if not variables_str:
                self.notify("请输入变量列表", severity="warning")
                return

            if not years_str:
                self.notify("请输入年份", severity="warning")
                return

            if not months_str:
                self.notify("请输入月份", severity="warning")
                return

            # 解析字段
            variables = [v.strip() for v in variables_str.split(",")]
            years = [int(y.strip()) for y in years_str.split(",")]
            months = [int(m.strip()) for m in months_str.split(",")]

            # 可选字段
            area = None
            if area_str:
                area = [float(x.strip()) for x in area_str.split(",")]

            pressure_levels = None
            if levels_str:
                pressure_levels = [int(l.strip()) for l in levels_str.split(",")]

            # 使用 Pydantic 验证配置
            config = DownloadConfig(
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

            # 创建任务
            self._create_task(config)

        except ValueError as e:
            self.notify(f"参数验证失败: {str(e)}", severity="error")
        except Exception as e:
            self.notify(f"创建任务失败: {str(e)}", severity="error")

    def _create_task(self, config: DownloadConfig) -> None:
        """创建下载任务

        Args:
            config: 下载配置
        """
        from pathlib import Path

        # 生成任务ID
        import uuid
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        # 生成文件名
        filename = self._generate_filename(config)

        # 准备下载参数
        download_params = {
            "dataset": config.dataset,
            "variables": config.variables,
            "years": config.years,
            "months": config.months,
        }

        # 添加可选参数
        if config.days:
            download_params["days"] = config.days
        if config.times:
            download_params["times"] = config.times
        if config.pressure_levels:
            download_params["pressure_levels"] = config.pressure_levels
        if config.area:
            download_params["area"] = config.area

        # 设置输出路径
        output_path = Path(config.output_dir) / filename
        download_params["output_path"] = output_path

        # 创建任务
        self._app_ref.progress_manager.create_task(
            task_id=task_id,
            filename=filename,
            metadata={
                "download_params": download_params,
                "max_retries": 3,
            },
        )

        self.notify(f"任务创建成功: {task_id}", severity="success")

        # 清空表单
        self._handle_clear()

    def _generate_filename(self, config: DownloadConfig) -> str:
        """生成输出文件名

        Args:
            config: 下载配置

        Returns:
            str: 文件名
        """
        # 简单的文件名生成逻辑
        var_name = config.variables[0] if config.variables else "data"
        year_str = f"{config.years[0]}-{config.years[-1]}" if config.years else "all"
        month_str = f"{config.months[0]:02d}-{config.months[-1]:02d}" if config.months else "all"

        return f"{config.dataset}_{var_name}_{year_str}_{month_str}.nc"

    def _handle_clear(self) -> None:
        """清空表单"""
        self.query_one("#input-dataset", Input).value = ""
        self.query_one("#input-variables", Input).value = ""
        self.query_one("#input-years", Input).value = ""
        self.query_one("#input-months", Input).value = ""
        self.query_one("#input-area", Input).value = ""
        self.query_one("#input-levels", Input).value = ""
        self.query_one("#input-output", Input).value = ""

    def _handle_reset(self) -> None:
        """重置表单为默认值"""
        self.query_one("#input-dataset", Input).value = "reanalysis-era5-pressure-levels"
        self.query_one("#input-variables", Input).value = ""
        self.query_one("#input-years", Input).value = ""
        self.query_one("#input-months", Input).value = ""
        self.query_one("#input-area", Input).value = ""
        self.query_one("#input-levels", Input).value = ""
        self.query_one("#input-output", Input).value = "./data/downloads"

    def refresh_data(self) -> None:
        """刷新配置数据（无需实现）"""
        pass

    def on_unmount(self) -> None:
        """组件卸载时清理"""
        # 配置管理不需要观察者模式
        pass
