"""
ConfigScreen屏幕测试

测试配置管理屏幕的各项功能。
"""

import pytest
from textual.widgets import Button, Input, Label

from src.ui.screens.config_screen import ConfigScreen


@pytest.fixture
async def config_screen(mock_app):
    """创建ConfigScreen实例"""
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
            yield ConfigScreen()

    app = TestApp(mock_app)

    async with app.run_test() as pilot:
        screen = app.query_one(ConfigScreen)
        yield screen


class TestConfigScreenCompose:
    """测试UI结构"""

    async def test_compose_creates_title(self, config_screen):
        """测试创建标题"""
        title = config_screen.query_one("#config-title", Label)
        assert "创建下载任务" in str(title.render())

    async def test_compose_creates_input_fields(self, config_screen):
        """测试创建输入字段"""
        input_dataset = config_screen.query_one("#input-dataset", Input)
        input_variables = config_screen.query_one("#input-variables", Input)
        input_years = config_screen.query_one("#input-years", Input)
        input_months = config_screen.query_one("#input-months", Input)

        assert input_dataset is not None
        assert input_variables is not None
        assert input_years is not None
        assert input_months is not None

    async def test_compose_creates_action_buttons(self, config_screen):
        """测试创建操作按钮"""
        btn_create = config_screen.query_one("#btn-create", Button)
        btn_clear = config_screen.query_one("#btn-clear", Button)
        btn_reset = config_screen.query_one("#btn-reset", Button)

        assert btn_create.label.plain == "创建任务"
        assert btn_clear.label.plain == "清空"
        assert btn_reset.label.plain == "重置"


class TestConfigScreenDefaultValues:
    """测试默认值"""

    async def test_default_dataset_value(self, config_screen):
        """测试默认数据集值"""
        input_dataset = config_screen.query_one("#input-dataset", Input)
        assert input_dataset.value == "reanalysis-era5-pressure-levels"

    async def test_default_output_dir(self, config_screen):
        """测试默认输出目录"""
        input_output = config_screen.query_one("#input-output", Input)
        assert input_output.value == "./data/downloads"


class TestConfigScreenButtons:
    """测试按钮功能"""

    async def test_handle_create_with_empty_fields(self, config_screen):
        """测试创建任务时字段为空"""
        # 清空必填字段
        config_screen.query_one("#input-dataset", Input).value = ""
        config_screen._handle_create()
        # 验证没有抛出异常

    async def test_handle_clear(self, config_screen):
        """测试清空表单"""
        config_screen._handle_clear()
        # 验证没有抛出异常
        input_dataset = config_screen.query_one("#input-dataset", Input)
        assert input_dataset.value == ""

    async def test_handle_reset(self, config_screen):
        """测试重置表单"""
        # 先修改值
        config_screen.query_one("#input-dataset", Input).value = "test"
        # 重置
        config_screen._handle_reset()
        # 验证恢复默认值
        input_dataset = config_screen.query_one("#input-dataset", Input)
        assert input_dataset.value == "reanalysis-era5-pressure-levels"


class TestConfigScreenRefreshData:
    """测试数据刷新"""

    async def test_refresh_data(self, config_screen):
        """测试refresh_data方法（无需实现）"""
        config_screen.refresh_data()
        # ConfigScreen的refresh_data是空实现
