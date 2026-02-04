"""
ECMWF Downloader TUI 内容区域组件

提供主内容显示区域，支持动态切换内容Widget。
支持Tab键将焦点返回到侧边栏。
"""

from typing import Iterable, Optional

from textual.containers import Container, Vertical
from textual.events import Key
from textual.widgets import Header


class ContentArea(Vertical):
    """内容区域组件

    功能：
    - 动态加载和显示页面内容Widget
    - 保持Header和Footer固定
    - 支持页面切换

    样式：
    - 占据剩余空间
    - 垂直布局
    - 主内容区域可滚动
    """

    DEFAULT_CSS = """
    ContentArea {
        height: 100%;
    }

    ContentArea > Container {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs):
        """初始化内容区域

        Args:
            **kwargs: 传递给父类的参数
        """
        super().__init__(**kwargs)
        self._current_content_widget: Optional[Vertical] = None

    def compose(self) -> Iterable:
        """构建内容区域UI"""
        yield Header()
        with Container(id="main-content"):
            # 主内容容器，初始为空
            pass

    def switch_content(self, content_widget: Vertical) -> None:
        """切换内容区域显示的Widget

        切换后，焦点会保留在侧边栏，用户需要按Tab键才能聚焦到内容区域。

        Args:
            content_widget: 要显示的内容Widget
        """
        # 获取主内容容器
        content_container = self.query_one("#main-content", Container)

        # 移除所有现有的子Widget
        for child in content_container.children:
            child.remove()

        # 挂载新的内容Widget
        content_container.mount(content_widget)
        self._current_content_widget = content_widget

        # 记录日志
        self.log.info(f"内容区域已切换到: {content_widget.__class__.__name__}")

        # 将焦点设置回侧边栏（NavigationSidebar）
        # 这样用户必须按Tab键才能聚焦到内容区域
        try:
            sidebar = self.app.query_one("NavigationSidebar")
            sidebar.focus()
            self.log.debug("焦点已返回到侧边栏")
        except Exception as e:
            self.log.warning(f"设置焦点到侧边栏失败: {e}")

    def clear_content(self) -> None:
        """清空内容区域

        移除当前显示的内容Widget，将内容区域重置为空状态。
        """
        if self._current_content_widget is not None:
            content_container = self.query_one("#main-content", Container)
            try:
                content_container.remove_child(self._current_content_widget)
                self._current_content_widget = None
                self.log.info("内容区域已清空")
            except Exception as e:
                self.log.warning(f"清空内容区域失败: {e}")

    def get_current_content(self) -> Optional[Vertical]:
        """获取当前显示的内容Widget

        Returns:
            Optional[Vertical]: 当前内容Widget，如果没有则返回None
        """
        return self._current_content_widget

    def on_key(self, event: Key) -> None:
        """处理键盘事件，支持Tab键返回侧边栏

        当焦点在内容区域时，按Tab键将焦点返回到侧边栏，
        而不是在内容区域的控件间切换。

        Args:
            event: 键盘事件
        """
        # Tab键：返回焦点到侧边栏
        if event.key == "tab":
            event.stop()  # 阻止默认的Tab行为（在控件间切换）
            self._return_focus_to_sidebar()

    def _return_focus_to_sidebar(self) -> None:
        """将焦点返回到侧边栏"""
        try:
            from src.ui.widgets.navigation_sidebar import NavigationSidebar
            sidebar = self.app.query_one(NavigationSidebar)
            sidebar.focus()
            self.log.info("焦点已返回到侧边栏")
        except Exception as e:
            self.log.warning(f"返回焦点到侧边栏失败: {e}")
