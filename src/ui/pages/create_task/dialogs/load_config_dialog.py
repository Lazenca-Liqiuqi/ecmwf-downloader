"""
加载配置对话框

让用户选择要加载的配置文件。
"""

from pathlib import Path
from typing import Callable, List, Tuple

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select


class LoadConfigDialog(ModalScreen):
    """加载配置对话框

    提供下拉选择框让用户选择已保存的配置文件。

    使用示例:
        def on_load(path: str):
            print(f"加载配置: {path}")

        options = [("config1", "/path/to/config1.json"), ...]
        app.push_screen(LoadConfigDialog(options, on_load))
    """

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

    def __init__(
        self,
        options: List[Tuple[str, str]],
        callback: Callable[[str], None],
    ):
        """初始化加载配置对话框

        Args:
            options: 选项列表，格式为 [(显示名称, 文件路径), ...]
            callback: 确认回调函数，接收文件路径参数
        """
        super().__init__()
        self._options = options
        self._callback = callback

    def compose(self):
        """构建对话框 UI"""
        with Vertical():
            yield Label("选择配置文件")
            yield Select(
                options=[(name, path) for name, path in self._options],
                id="config-select",
                allow_blank=False,
            )
            with Horizontal():
                yield Button("加载", id="btn-confirm-load", variant="primary")
                yield Button("取消", id="btn-cancel-load", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理按钮点击事件"""
        if event.button.id == "btn-confirm-load":
            select = self.query_one("#config-select", Select)
            if select.value:
                self._callback(str(select.value))
            self.dismiss()
        elif event.button.id == "btn-cancel-load":
            self.dismiss()

    def on_key(self, event) -> None:
        """处理键盘事件"""
        if event.key == "escape":
            self.dismiss()
