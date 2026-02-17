"""
ECMWF Downloader TUI 账号对话框模块

提供账号添加和编辑的模态对话框。
"""

from typing import Any, Dict, Iterable, Optional

from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Input, Label

from src.core.config import AccountInfo
from src.ui.dialogs.base_dialog import BaseDialog


class AccountDialog(BaseDialog):
    """账号添加/编辑对话框

    功能：
    - 支持添加（add）和编辑（edit）两种模式
    - 表单字段：账号ID、UID、API Key（密码掩码）、API URL（可选）
    - 表单验证：必填字段检查、ID格式校验
    - 编辑模式下预填充现有数据
    - 编辑模式下禁用ID输入

    Usage:
        # 添加账号
        result = await app.push_screen(AccountDialog(mode="add"))

        # 编辑账号
        result = await app.push_screen(
            AccountDialog(mode="edit", account_data=existing_account)
        )
    """

    DEFAULT_CSS = """
    AccountDialog {
        align: center middle;
    }

    AccountDialog > Container {
        width: 65;
        max-width: 80;
        min-width: 50;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        overflow-y: auto;
    }

    AccountDialog .dialog-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    AccountDialog .dialog-content {
        margin: 1 0;
        height: auto;
    }

    AccountDialog .form-row {
        height: auto;
        margin: 1 0;
    }

    AccountDialog .form-label {
        color: $text;
        margin-bottom: 0;
        padding: 0;
    }

    AccountDialog Input {
        width: 100%;
        margin-top: 0;
    }

    AccountDialog Input:focus {
        border: tall $accent;
    }

    AccountDialog Input.-invalid {
        border: tall $error;
    }

    AccountDialog Input:disabled {
        opacity: 0.6;
        background: $panel;
    }

    AccountDialog .hint {
        color: $text-muted;
        text-style: italic;
        margin-top: 0;
        padding: 0;
    }

    AccountDialog .error-message {
        color: $error;
        text-style: bold;
        margin-top: 1;
        text-align: center;
    }

    AccountDialog .dialog-actions {
        align: center middle;
        height: auto;
        margin-top: 1;
    }

    AccountDialog .dialog-actions Button {
        width: 1fr;
        margin: 0 1;
    }

    AccountDialog .dialog-actions Button.-first {
        margin-left: 0;
    }

    AccountDialog .dialog-actions Button.-last {
        margin-right: 0;
    }
    """

    def __init__(
        self,
        mode: str = "add",
        account_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """初始化账号对话框

        Args:
            mode: 对话框模式，"add" 或 "edit"
            account_data: 编辑模式下的现有账号数据
            **kwargs: 传递给父类的参数
        """
        title = "添加账号" if mode == "add" else "编辑账号"
        super().__init__(title=title, **kwargs)
        self._mode = mode
        self._account_data = account_data or {}

    def compose(self) -> Iterable:
        """构建对话框UI"""
        with Container(classes="dialog-container"):
            # 标题
            yield Label(self._title, classes="dialog-title")

            # 表单内容
            with Vertical(classes="dialog-content"):
                # 账号ID
                with Vertical(classes="form-row"):
                    yield Label("账号ID *", classes="form-label")
                    yield Input(
                        placeholder="例如: account_1",
                        id="input-id",
                        value=self._account_data.get("id", ""),
                        disabled=(self._mode == "edit"),  # 编辑模式下禁用
                    )

                # UID
                with Vertical(classes="form-row"):
                    yield Label("ECMWF UID *", classes="form-label")
                    yield Input(
                        placeholder="例如: 123456",
                        id="input-uid",
                        value=self._account_data.get("uid", ""),
                    )

                # API Key
                with Vertical(classes="form-row"):
                    yield Label("API Key *", classes="form-label")
                    yield Input(
                        placeholder="例如: abc123def456...",
                        id="input-key",
                        value=self._account_data.get("key", ""),
                        password=True,  # 密码掩码显示
                    )

                # API URL（可选）
                with Vertical(classes="form-row"):
                    yield Label("API URL（可选）", classes="form-label")
                    yield Input(
                        placeholder="默认: https://cds.climate.copernicus.eu/api",
                        id="input-url",
                        value=self._account_data.get("url", ""),
                    )
                    yield Label("留空使用默认URL", classes="hint")

            # 错误消息
            yield Label("", id="error-message", classes="error-message")

            # 操作按钮
            with Horizontal(classes="dialog-actions"):
                yield Button("确定", id="confirm", variant="primary", classes="-first")
                yield Button("取消", id="cancel", variant="default", classes="-last")

    def on_mount(self) -> None:
        """对话框挂载时初始化"""
        # 隐藏错误消息
        error_label = self.query_one("#error-message", Label)
        error_label.display = False

        # 添加模式下，聚焦到第一个输入框
        if self._mode == "add":
            self.query_one("#input-id", Input).focus()
        else:
            # 编辑模式下，聚焦到UID输入框
            self.query_one("#input-uid", Input).focus()

    def get_form_data(self) -> Optional[Dict[str, Any]]:
        """收集并验证表单数据

        Returns:
            Optional[Dict[str, Any]]: 验证通过返回表单数据，否则返回 None
        """
        # 获取输入值
        input_id = self.query_one("#input-id", Input)
        input_uid = self.query_one("#input-uid", Input)
        input_key = self.query_one("#input-key", Input)
        input_url = self.query_one("#input-url", Input)

        account_id = input_id.value.strip()
        uid = input_uid.value.strip()
        key = input_key.value.strip()
        url = input_url.value.strip()

        # 验证必填字段
        errors = []

        if not account_id:
            errors.append("账号ID不能为空")
            input_id.add_class("-invalid")
        else:
            input_id.remove_class("-invalid")

        if not uid:
            errors.append("UID不能为空")
            input_uid.add_class("-invalid")
        else:
            input_uid.remove_class("-invalid")

        if not key:
            errors.append("API Key不能为空")
            input_key.add_class("-invalid")
        else:
            input_key.remove_class("-invalid")

        # ID格式验证（只允许字母、数字、下划线、连字符）
        if account_id and not all(c.isalnum() or c in "_-" for c in account_id):
            errors.append("账号ID只能包含字母、数字、下划线和连字符")
            input_id.add_class("-invalid")

        # 显示错误
        if errors:
            self.set_error("; ".join(errors))
            return None

        # 清除错误
        self.clear_error()

        # 构建返回数据
        result = {
            "id": account_id,
            "uid": uid,
            "key": key,
        }

        # URL可选，如果有值则添加
        if url:
            result["url"] = url

        return result

    def set_error(self, message: str) -> None:
        """设置错误消息

        Args:
            message: 错误消息内容
        """
        self._error_message = message
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
