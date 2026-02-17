"""
ECMWF Downloader TUI 请求预览对话框模块

展示任务拆分结果，支持用户在创建任务前进行确认。
"""

import json
from typing import Any, Dict, Iterable, List, Optional

from textual.containers import Container, Horizontal, Vertical
from textual.scroll_view import ScrollView
from textual.widgets import Button, Label, Static

from src.ui.dialogs.base_dialog import BaseDialog


class RequestPreviewDialog(BaseDialog):
    """请求预览对话框

    展示下载请求的详细参数和任务列表，支持用户确认或取消。
    """

    DEFAULT_CSS = """
    RequestPreviewDialog {
        align: center middle;
    }

    RequestPreviewDialog > Container {
        width: 110;
        max-width: 95;
        min-width: 70;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    RequestPreviewDialog .dialog-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    RequestPreviewDialog .dialog-content {
        margin: 1 0;
    }

    RequestPreviewDialog #summary-area {
        margin-bottom: 1;
    }

    RequestPreviewDialog #preview-scroll {
        height: 24;
        border: round $panel;
        padding: 0 1;
    }

    RequestPreviewDialog .task-item {
        margin: 0 0 1 0;
        padding: 0 0 1 0;
        border-bottom: solid $panel-lighten-1;
    }

    RequestPreviewDialog .task-index {
        color: $accent;
        text-style: bold;
    }

    RequestPreviewDialog .task-key {
        color: $text-muted;
    }

    RequestPreviewDialog .task-api {
        color: $text-muted;
        margin: 0 0 1 0;
    }

    RequestPreviewDialog .dialog-actions {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        preview_items: List[Dict[str, Any]],
        split_strategy: str = "month",
        **kwargs: Any,
    ) -> None:
        """初始化对话框。

        Args:
            preview_items: TaskService.preview_tasks() 返回的预览列表。
            split_strategy: 拆分策略名称（month/year/none）。
            **kwargs: 传递给父类的参数。
        """
        super().__init__(title="请求预览", **kwargs)
        self._preview_items: List[Dict[str, Any]] = preview_items
        self._split_strategy: str = split_strategy

    def compose(self) -> Iterable:
        """构建对话框 UI。

        Returns:
            Iterable: Textual 组件迭代器。
        """
        with Container(classes="dialog-container"):
            yield Label(self._title, classes="dialog-title")

            with Vertical(id="summary-area", classes="dialog-content"):
                yield Label(f"拆分策略: {self._format_split_strategy(self._split_strategy)}")
                yield Label(f"任务数量: {len(self._preview_items)}")

            with ScrollView(id="preview-scroll", classes="dialog-content"):
                with Vertical(id="preview-list"):
                    if not self._preview_items:
                        yield Static("无可创建任务，请检查请求参数。")
                    else:
                        for index, item in enumerate(self._preview_items, start=1):
                            time_range = self._format_time_range(item.get("time_range", {}))
                            filename = str(item.get("filename", "-"))
                            variables = self._format_variables(item.get("api_params", {}))
                            api_params_json = self._format_api_params_json(
                                item.get("api_params", {})
                            )

                            with Vertical(classes="task-item"):
                                yield Label(f"任务 {index}", classes="task-index")
                                yield Static(f"[b]时间范围:[/b] {time_range}", classes="task-key")
                                yield Static(f"[b]文件名:[/b] {filename}", classes="task-key")
                                yield Static(f"[b]变量:[/b] {variables}", classes="task-key")
                                yield Static("API 参数(JSON):", classes="task-api")
                                yield Static(api_params_json, classes="task-api")

            with Horizontal(classes="dialog-actions"):
                yield Button("确认创建", id="confirm", variant="primary", classes="-first")
                yield Button("取消", id="cancel", variant="default", classes="-last")

    def on_mount(self) -> None:
        """挂载后设置默认焦点。"""
        self.query_one("#confirm", Button).focus()

    def get_form_data(self) -> Optional[Dict[str, Any]]:
        """收集表单数据。

        Returns:
            Optional[Dict[str, Any]]: 确认时返回 ``{"confirmed": True}``。
        """
        return {"confirmed": True}

    @staticmethod
    def _format_split_strategy(split_strategy: str) -> str:
        """格式化拆分策略显示文本。"""
        mapping = {
            "month": "按月",
            "year": "按年",
            "none": "不拆分",
        }
        return mapping.get(split_strategy, split_strategy)

    @staticmethod
    def _format_time_range(time_range: Dict[str, Any]) -> str:
        """格式化时间范围展示文本。"""
        years = [str(year) for year in time_range.get("years", [])]
        months = [f"{int(month):02d}" for month in time_range.get("months", [])]
        days_raw = time_range.get("days", [])
        days = [f"{int(day):02d}" for day in days_raw] if days_raw else []

        year_text = ",".join(years) if years else "-"
        month_text = ",".join(months) if months else "-"
        day_text = ",".join(days) if days else "全月"
        return f"年[{year_text}] 月[{month_text}] 日[{day_text}]"

    @staticmethod
    def _format_variables(api_params: Dict[str, Any]) -> str:
        """格式化变量列表。"""
        variables_raw = api_params.get("variable", [])
        if not isinstance(variables_raw, list) or not variables_raw:
            return "-"
        return ", ".join(str(variable) for variable in variables_raw)

    @staticmethod
    def _format_api_params_json(api_params: Dict[str, Any]) -> str:
        """格式化 API 参数为 JSON 文本。"""
        return json.dumps(api_params, ensure_ascii=False, indent=2, default=str)
