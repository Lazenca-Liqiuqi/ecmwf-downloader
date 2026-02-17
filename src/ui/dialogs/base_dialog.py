"""
ECMWF Downloader TUI 基础对话框模块

提供可复用的模态对话框基类，实现统一的视觉效果和交互模式。
"""

from abc import abstractmethod
from typing import Any, Dict, Iterable, Optional

from textual.screen import ModalScreen
from textual.widgets import Button, Label


class BaseDialog(ModalScreen[Optional[Dict[str, Any]]]):
    """基础模态对话框

    功能：
    - 居中显示 + 半透明遮罩背景
    - ESC 键关闭支持
    - 统一的视觉样式
    - 可扩展的表单布局

    子类需要实现：
    - compose()：构建对话框内容
    - get_form_data()：收集表单数据

    Usage:
        class MyDialog(BaseDialog):
            def compose(self):
                yield Label("对话框标题")
                yield Input(placeholder="输入内容")
                yield Button("确定", id="confirm")
                yield Button("取消", id="cancel")

            def get_form_data(self):
                return {"value": self.query_one(Input).value}

        # 调用方式
        result = await app.push_screen(MyDialog())
    """

    DEFAULT_CSS = """
    BaseDialog {
        align: center middle;
    }

    BaseDialog > Container {
        width: 60;
        max-width: 80;
        min-width: 40;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    BaseDialog .dialog-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        padding: 0 1;
    }

    BaseDialog .dialog-content {
        margin: 1 0;
        padding: 0 1;
    }

    BaseDialog .dialog-actions {
        align: center middle;
        height: auto;
        margin-top: 1;
        padding: 0 1;
    }

    BaseDialog .dialog-actions Button {
        width: 1fr;
        margin: 0 1;
    }

    BaseDialog .dialog-actions Button.-first {
        margin-left: 0;
    }

    BaseDialog .dialog-actions Button.-last {
        margin-right: 0;
    }

    BaseDialog .error-message {
        color: $error;
        text-style: bold;
        margin-top: 1;
        padding: 0 1;
    }

    BaseDialog .form-row {
        height: auto;
        margin: 1 0;
        padding: 0 1;
    }

    BaseDialog .form-label {
        color: $text-muted;
        margin-bottom: 0;
    }

    BaseDialog Input {
        width: 100%;
        margin-top: 0;
    }

    BaseDialog Input:focus {
        border: tall $accent;
    }

    BaseDialog Input.-invalid {
        border: tall $error;
    }
    """

    def __init__(self, title: str = "对话框", **kwargs):
        """初始化基础对话框

        Args:
            title: 对话框标题
            **kwargs: 传递给父类的参数
        """
        super().__init__(**kwargs)
        self._title = title
        self._error_message: Optional[str] = None

    @abstractmethod
    def get_form_data(self) -> Optional[Dict[str, Any]]:
        """收集表单数据

        子类必须实现此方法，返回表单数据字典。
        如果验证失败，返回 None 并设置错误消息。

        Returns:
            Optional[Dict[str, Any]]: 表单数据字典，验证失败返回 None
        """
        pass

    def set_error(self, message: str) -> None:
        """设置错误消息

        Args:
            message: 错误消息内容
        """
        self._error_message = message
        # 尝试更新错误标签
        try:
            error_label = self.query_one("#error-message", Label)
            error_label.update(message)
            error_label.display = True
        except Exception:
            pass

    def clear_error(self) -> None:
        """清除错误消息"""
        self._error_message = None
        try:
            error_label = self.query_one("#error-message", Label)
            error_label.display = False
        except Exception:
            pass

    def on_key(self, event) -> None:
        """处理键盘事件

        ESC 键关闭对话框并返回 None。

        Args:
            event: 键盘事件
        """
        if event.key == "escape":
            self.dismiss(None)
            event.stop()

    def _handle_confirm(self) -> None:
        """处理确认操作

        收集表单数据并关闭对话框。
        """
        form_data = self.get_form_data()
        if form_data is not None:
            self.dismiss(form_data)

    def _handle_cancel(self) -> None:
        """处理取消操作

        关闭对话框并返回 None。
        """
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件处理

        Args:
            event: 按钮点击事件
        """
        button_id = event.button.id
        if button_id == "confirm":
            self._handle_confirm()
        elif button_id == "cancel":
            self._handle_cancel()
