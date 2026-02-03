"""
ECMWF Downloader TUI 导航侧边栏组件

提供左侧导航菜单，支持页面切换和当前页面高亮显示。
"""

from typing import Iterable

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Button


class NavigationSidebar(Vertical):
    """导航侧边栏组件

    功能：
    - 显示5个导航按钮（首页/任务/下载/账号/配置）
    - 高亮当前选中页面（-active样式类）
    - 响应点击事件，通知App切换页面
    - 支持键盘快捷键（通过App.action）

    样式：
    - 固定宽度25字符
    - 左侧停靠
    - 深色背景
    - 右侧边框
    """

    DEFAULT_CSS = """
    NavigationSidebar {
        width: 25;
        dock: left;
        background: $panel;
        border-right: solid $accent;
        padding: 1 0;
    }

    NavigationSidebar Button {
        width: 1fr;
        margin: 0 0 1 0;
        padding: 1 2;
        text-align: left;
        border: none;
        background: transparent;
    }

    NavigationSidebar Button:hover {
        background: $primary 20%;
    }

    NavigationSidebar Button.-active {
        background: $primary;
        text-style: bold;
    }
    """

    # 导航项配置
    NAV_ITEMS = [
        {"id": "home", "label": "[H] 首页", "key": "h"},
        {"id": "tasks", "label": "[T] 任务", "key": "t"},
        {"id": "download", "label": "[D] 下载", "key": "d"},
        {"id": "accounts", "label": "[A] 账号", "key": "a"},
        {"id": "config", "label": "[C] 配置", "key": "c"},
    ]

    # 当前页面（reactive变量，会自动触发界面更新）
    current_page = reactive("home")

    def compose(self) -> Iterable:
        """构建侧边栏UI"""
        for nav_item in self.NAV_ITEMS:
            # 使用nav-前缀作为按钮ID，便于识别
            yield Button(
                nav_item["label"],
                id=f"nav-{nav_item['id']}",
                classes="" if nav_item["id"] != "home" else "-active",
            )

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        # 设置初始激活状态
        self._update_active_button()

    def watch_current_page(self, old_page: str, new_page: str) -> None:
        """监听current_page变化，更新按钮激活状态

        Args:
            old_page: 旧页面ID
            new_page: 新页面ID
        """
        self._update_active_button()

    def _update_active_button(self) -> None:
        """更新按钮激活状态（-active样式类）"""
        # 移除所有按钮的激活状态
        for nav_item in self.NAV_ITEMS:
            button = self.query_one(f"#nav-{nav_item['id']}", Button)
            button.remove_class("-active")

        # 为当前页面的按钮添加激活状态
        try:
            current_button = self.query_one(f"#nav-{self.current_page}", Button)
            current_button.add_class("-active")
        except Exception:
            # 如果查询失败（页面ID无效），忽略错误
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件处理

        Args:
            event: 按钮按下事件
        """
        button_id = event.button.id

        # 从按钮ID中提取页面ID（移除nav-前缀）
        if button_id and button_id.startswith("nav-"):
            page_id = button_id.replace("nav-", "")

            # 更新当前页面（会触发watch_current_page）
            self.current_page = page_id

            # 通知App切换页面
            # 注意：App需要实现action_switch_page方法
            if hasattr(self.app, "action_switch_page"):
                self.app.action_switch_page(page_id)
            else:
                # 如果App还没有实现switch_page，记录警告
                self.log.warning(
                    f"App.action_switch_page() 方法未实现，无法切换到页面: {page_id}"
                )
