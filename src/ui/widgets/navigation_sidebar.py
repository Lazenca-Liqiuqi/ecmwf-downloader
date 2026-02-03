"""
ECMWF Downloader TUI 导航侧边栏组件

提供左侧导航菜单，支持页面切换和当前页面高亮显示。
"""

from typing import Iterable

from textual.containers import Vertical, Container
from textual.reactive import reactive
from textual.widgets import Button, Label


class NavigationSidebar(Vertical):
    """导航侧边栏组件

    功能：
    - 显示应用标题和Logo区域
    - 显示5个导航按钮（首页/任务/下载/账号/配置）
    - 高亮当前选中页面（-active样式类 + 左侧指示条）
    - 响应点击事件，通知App切换页面
    - 支持键盘快捷键（通过App.action）
    - 显示底部提示信息

    样式特点：
    - 固定宽度28字符
    - 左侧停靠，深色背景
    - 右侧thick边框（$accent颜色）
    - 标题区域：30%主色背景 + 底部分隔线
    - 激活按钮：40%主色背景 + 左侧thick指示条
    - 悬停效果：15%主色背景柔和高亮
    """

    DEFAULT_CSS = """
    /* ═══════════════════════════════════════════════════════════════
       导航侧边栏容器 - 深色背景 + 右侧边框
       ═══════════════════════════════════════════════════════════════ */
    NavigationSidebar {
        width: 28;
        dock: left;
        background: $panel;
        border-right: thick $accent;
        padding: 0;
    }

    /* ═══════════════════════════════════════════════════════════════
       标题区域 - Logo和应用名称
       ═══════════════════════════════════════════════════════════════ */
    #sidebar-header {
        height: 5;
        background: $primary 30%;
        border-bottom: solid $accent;
        padding: 1 1;
        margin-bottom: 1;
    }

    #sidebar-logo {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 0;
    }

    #sidebar-title {
        text-align: center;
        text-style: bold;
        margin-top: 0;
        color: $text;
    }

    /* ═══════════════════════════════════════════════════════════════
       导航按钮容器 - 分组按钮
       ═══════════════════════════════════════════════════════════════ */
    #nav-buttons-container {
        padding: 0 1;
        margin: 1 0;
    }

    /* ═══════════════════════════════════════════════════════════════
       导航按钮 - 基础样式
       ═══════════════════════════════════════════════════════════════ */
    NavigationSidebar Button {
        width: 1fr;
        height: 3;
        margin: 0 0 1 0;
        padding: 0 2;
        text-align: left;
        border: none;
        background: transparent;
        text-style: none;
        color: $text 80%;
    }

    /* 悬停效果 - 柔和高亮 */
    NavigationSidebar Button:hover {
        background: $primary 15%;
        text-style: bold;
        color: $text;
    }

    /* 激活状态 - 左侧指示条 + 渐变背景 */
    NavigationSidebar Button.-active {
        background: $primary 40%;
        text-style: bold;
        color: $accent;
        border-left: thick $accent;
        padding-left: 1;
    }

    /* 激活状态悬停 - 增强效果 */
    NavigationSidebar Button.-active:hover {
        background: $primary 50%;
    }

    /* ═══════════════════════════════════════════════════════════════
       分隔线
       ═══════════════════════════════════════════════════════════════ */
    #nav-separator {
        height: 1;
        margin: 1 1;
        border-top: solid $panel 80%;
    }

    /* ═══════════════════════════════════════════════════════════════
       底部提示区域
       ═══════════════════════════════════════════════════════════════ */
    #sidebar-footer {
        height: 3;
        padding: 0 1;
        margin-top: 1;
    }

    #sidebar-footer Label {
        text-align: center;
        color: $text 50%;
        text-style: italic;
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
        """构建侧边栏UI

        结构：
        - 侧边栏标题区域（Logo + 应用名称）
        - 导航按钮容器
        - 分隔线
        - 底部提示区域
        """
        # 标题区域
        yield Container(
            Label("🌤️", id="sidebar-logo"),
            Label("ECMWF", id="sidebar-title"),
            id="sidebar-header",
        )

        # 导航按钮容器
        with Container(id="nav-buttons-container"):
            for nav_item in self.NAV_ITEMS:
                # 使用nav-前缀作为按钮ID，便于识别
                yield Button(
                    nav_item["label"],
                    id=f"nav-{nav_item['id']}",
                    classes="" if nav_item["id"] != "home" else "-active",
                )

        # 分隔线
        yield Container(id="nav-separator")

        # 底部提示区域
        yield Container(
            Label("按 [q] 退出", id="footer-label"),
            id="sidebar-footer",
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
