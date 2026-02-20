"""
AI 生成对话框

让用户输入自然语言需求，由 AI 生成参数。
"""

from typing import Callable

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea


class AIGenerateDialog(ModalScreen):
    """AI 生成对话框

    提供文本输入区域让用户描述数据需求。

    使用示例:
        def on_generate(request: str):
            print(f"用户需求: {request}")

        app.push_screen(AIGenerateDialog(on_generate))
    """

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

    def __init__(self, callback: Callable[[str], None]):
        """初始化 AI 生成对话框

        Args:
            callback: 确认回调函数，接收用户输入的需求文本
        """
        super().__init__()
        self._callback = callback

    def compose(self):
        """构建对话框 UI"""
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理按钮点击事件"""
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

    def on_key(self, event) -> None:
        """处理键盘事件"""
        if event.key == "escape":
            self.dismiss()
