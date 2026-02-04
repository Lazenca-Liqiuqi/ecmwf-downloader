"""
ECMWF Downloader TUI 账号管理内容组件

显示和管理所有API账号，支持添加、编辑、删除和启用/禁用账号。
这是从AccountsScreen迁移而来的Widget版本。
"""

from typing import Iterable

from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Label

from src.core.config import AccountInfo
from src.core.exceptions import AccountPoolError
from src.ui.widgets.account_table import AccountTable


class AccountsContent(Widget):
    """账号管理内容组件

    显示：
    - 所有账号的表格列表
    - 账号状态（可用/失败/禁用）
    - 操作按钮（添加、编辑、删除、启用/禁用、刷新）
    """

    CSS = """
    #accounts-title {
        text-align: left;
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 2;
    }

    #table-section {
        height: 20;
    }

    #accounts-table {
        height: 1fr;
        border: solid $panel;
    }
    """

    def __init__(self, app, **kwargs):
        """初始化账号管理内容组件

        Args:
            app: 应用实例引用
            **kwargs: 传递给父类的参数
        """
        super().__init__(**kwargs)
        self._app_ref = app  # 使用_app_ref避免与Widget.app属性冲突
        self._observer_registered = False

    def compose(self) -> Iterable:
        """构建账号管理 UI"""
        # 主容器
        with Container(id="accounts-container", classes="content-container"):
            # 标题
            yield Label("账号管理", id="accounts-title", classes="page-title")

            # 账号表格
            with Vertical(id="table-section", classes="table-section"):
                yield AccountTable(id="accounts-table")

            # 操作按钮区域
            with Horizontal(id="actions-section", classes="button-section"):
                yield Button("添加", id="btn-add", variant="default")
                yield Button("编辑", id="btn-edit", variant="default")
                yield Button("删除", id="btn-delete", variant="default")
                yield Button("启用", id="btn-enable", variant="default")
                yield Button("禁用", id="btn-disable", variant="default")
                yield Button("刷新", id="btn-refresh", variant="default")

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        # AccountTable 组件会在 on_mount 时自动初始化列
        # 加载账号数据
        self._load_accounts()

    def _load_accounts(self) -> None:
        """加载账号数据到表格"""
        table = self.query_one("#accounts-table", AccountTable)

        # 获取所有账号
        accounts = self._app_ref.account_pool.get_all_accounts()

        # 使用 AccountTable 的 load_accounts 方法加载
        table.load_accounts(accounts)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件处理"""
        button_id = event.button.id

        if button_id == "btn-add":
            self._handle_add()

        elif button_id == "btn-edit":
            self._handle_edit()

        elif button_id == "btn-delete":
            self._handle_delete()

        elif button_id == "btn-enable":
            self._handle_enable()

        elif button_id == "btn-disable":
            self._handle_disable()

        elif button_id == "btn-refresh":
            self._handle_refresh()

    def _handle_add(self) -> None:
        """处理添加账号"""
        # TODO: 实现添加账号对话框（需要弹出输入框）
        self.notify("添加账号功能待实现", severity="information")

    def _handle_edit(self) -> None:
        """处理编辑账号"""
        table = self.query_one("#accounts-table", AccountTable)
        account_id = table.get_selected_account_id()

        if account_id is None:
            self.notify("请先选择一个账号", severity="warning")
            return

        # TODO: 实现编辑账号对话框
        self.notify(f"编辑账号 {account_id} 功能待实现", severity="information")

    def _handle_delete(self) -> None:
        """处理删除账号"""
        table = self.query_one("#accounts-table", AccountTable)
        account_id = table.get_selected_account_id()

        if account_id is None:
            self.notify("请先选择一个账号", severity="warning")
            return

        # 删除账号
        try:
            self._app_ref.account_pool.remove_account(account_id)
            self.notify(f"账号 {account_id} 已删除", severity="success")
            # 重新加载账号列表
            self._load_accounts()
        except AccountPoolError as e:
            self.notify(f"删除账号失败: {str(e)}", severity="error")

    def _handle_enable(self) -> None:
        """处理启用账号"""
        table = self.query_one("#accounts-table", AccountTable)
        account_id = table.get_selected_account_id()

        if account_id is None:
            self.notify("请先选择一个账号", severity="warning")
            return

        # 启用账号
        try:
            self._app_ref.account_pool.enable_account(account_id)
            self.notify(f"账号 {account_id} 已启用", severity="success")
            # 重新加载账号列表
            self._load_accounts()
        except AccountPoolError as e:
            self.notify(f"启用账号失败: {str(e)}", severity="error")

    def _handle_disable(self) -> None:
        """处理禁用账号"""
        table = self.query_one("#accounts-table", AccountTable)
        account_id = table.get_selected_account_id()

        if account_id is None:
            self.notify("请先选择一个账号", severity="warning")
            return

        # 禁用账号
        try:
            self._app_ref.account_pool.disable_account(account_id)
            self.notify(f"账号 {account_id} 已禁用", severity="success")
            # 重新加载账号列表
            self._load_accounts()
        except AccountPoolError as e:
            self.notify(f"禁用账号失败: {str(e)}", severity="error")

    def _handle_refresh(self) -> None:
        """处理刷新操作"""
        self._load_accounts()
        self.notify("账号列表已刷新", severity="information")

    def refresh_data(self) -> None:
        """刷新账号列表数据"""
        self._load_accounts()

    def on_unmount(self) -> None:
        """组件卸载时清理"""
        # 账号管理不需要观察者模式
        pass
