"""
保存配置对话框

让用户输入配置名称并保存。
"""

from typing import Callable

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class SaveConfigDialog(ModalScreen):
    """保存配置对话框

    提供输入框让用户输入配置名称，支持确认和取消操作。

    使用示例:
        def on_save(name: str):
            print(f"保存配置: {name}")

        app.push_screen(SaveConfigDialog("default_name", on_save))
    """

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

    def __init__(self, default_name: str, callback: Callable[[str], None]):
        """初始化保存配置对话框

        Args:
            default_name: 默认配置名称
            callback: 确认回调函数，接收配置名称参数
        """
        super().__init__()
        self._default_name = default_name
        self._callback = callback

    def compose(self):
        """构建对话框 UI"""
        with Vertical():
            yield Label("保存配置")
            yield Input(
                value=self._default_name,
                placeholder="输入配置名称",
                id="config-name-input",
            )
            with Horizontal():
                yield Button("保存", id="btn-confirm-save", variant="primary")
                yield Button("取消", id="btn-cancel-save", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理按钮点击事件"""
        if event.button.id == "btn-confirm-save":
            name = self.query_one("#config-name-input", Input).value.strip()
            if name:
                self._callback(name)
            self.dismiss()
        elif event.button.id == "btn-cancel-save":
            self.dismiss()

    def on_key(self, event) -> None:
        """处理键盘事件"""
        if event.key == "escape":
            self.dismiss()
