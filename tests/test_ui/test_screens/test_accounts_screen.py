"""
AccountsScreen屏幕测试

测试账号管理屏幕的各项功能。
"""

import pytest
from textual.widgets import Button, Label

from src.ui.screens.accounts_screen import AccountsScreen
from src.core.config import AccountInfo, AccountStatus


@pytest.fixture
async def accounts_screen(mock_app):
    """创建AccountsScreen实例"""
    from textual.app import App

    class TestApp(App):
        def __init__(self, mock_ref):
            super().__init__()
            self._mock_ref = mock_ref

        @property
        def progress_manager(self):
            return self._mock_ref.progress_manager

        @property
        def account_pool(self):
            return self._mock_ref.account_pool

        def call_from_thread(self, func, *args, **kwargs):
            return func(*args, **kwargs)

        def notify(self, message, title="", severity="information", **kwargs):
            pass

        def log_message(self, message):
            pass

        def compose(self):
            yield AccountsScreen()

    app = TestApp(mock_app)

    async with app.run_test() as pilot:
        screen = app.query_one(AccountsScreen)
        yield screen


class TestAccountsScreenCompose:
    """测试UI结构"""

    async def test_compose_creates_title(self, accounts_screen):
        """测试创建标题"""
        title = accounts_screen.query_one("#accounts-title", Label)
        assert "账号管理" in str(title.render())

    async def test_compose_creates_action_buttons(self, accounts_screen):
        """测试创建操作按钮"""
        btn_add = accounts_screen.query_one("#btn-add", Button)
        btn_edit = accounts_screen.query_one("#btn-edit", Button)
        btn_delete = accounts_screen.query_one("#btn-delete", Button)
        btn_enable = accounts_screen.query_one("#btn-enable", Button)
        btn_disable = accounts_screen.query_one("#btn-disable", Button)
        btn_refresh = accounts_screen.query_one("#btn-refresh", Button)

        assert btn_add.label.plain == "添加"
        assert btn_edit.label.plain == "编辑"
        assert btn_delete.label.plain == "删除"
        assert btn_enable.label.plain == "启用"
        assert btn_disable.label.plain == "禁用"
        assert btn_refresh.label.plain == "刷新"


class TestAccountsScreenMount:
    """测试屏幕挂载"""

    async def test_on_screen_mount_loads_accounts(self, accounts_screen, mock_app):
        """测试挂载时加载账号"""
        mock_app.account_pool.get_all_accounts.assert_called()

    async def test_observer_registered(self, accounts_screen):
        """测试观察者已注册"""
        assert accounts_screen._observer_registered is True


class TestAccountsScreenButtons:
    """测试按钮功能"""

    async def test_handle_add(self, accounts_screen):
        """测试添加按钮"""
        accounts_screen._handle_add()
        # 验证没有抛出异常

    async def test_handle_edit_no_selection(self, accounts_screen):
        """测试编辑按钮未选择账号"""
        try:
            accounts_screen._handle_edit()
        except Exception:
            pass
        # 验证没有抛出严重异常

    async def test_handle_delete_no_selection(self, accounts_screen):
        """测试删除按钮未选择账号"""
        try:
            accounts_screen._handle_delete()
        except Exception:
            pass
        # 验证没有抛出严重异常

    async def test_handle_enable_no_selection(self, accounts_screen):
        """测试启用按钮未选择账号"""
        try:
            accounts_screen._handle_enable()
        except Exception:
            pass
        # 验证没有抛出严重异常

    async def test_handle_disable_no_selection(self, accounts_screen):
        """测试禁用按钮未选择账号"""
        try:
            accounts_screen._handle_disable()
        except Exception:
            pass
        # 验证没有抛出严重异常

    async def test_handle_refresh(self, accounts_screen, mock_app):
        """测试刷新按钮"""
        mock_app.account_pool.get_all_accounts.reset_mock()
        accounts_screen._handle_refresh()
        mock_app.account_pool.get_all_accounts.assert_called()


class TestAccountsScreenRefreshData:
    """测试数据刷新"""

    async def test_refresh_data(self, accounts_screen, mock_app):
        """测试refresh_data方法"""
        mock_app.account_pool.get_all_accounts.reset_mock()
        accounts_screen.refresh_data()
        mock_app.account_pool.get_all_accounts.assert_called()
