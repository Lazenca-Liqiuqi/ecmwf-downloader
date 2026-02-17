"""
ECMWF Downloader TUI 内容区域组件

提供主内容显示区域，支持动态切换内容Widget。
支持Tab键将焦点返回到侧边栏。
"""

from typing import Iterable, Optional

import asyncio

from textual.containers import Container, Vertical
from textual.events import Key
from textual.widget import Widget
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
        width: 1fr;
        height: 1fr;
        overflow: hidden;
    }

    #content-container {
        width: 1fr;
        height: 1fr;
        overflow: hidden;
    }
    """

    def __init__(self, **kwargs):
        """初始化内容区域

        Args:
            **kwargs: 传递给父类的参数
        """
        super().__init__(**kwargs)
        self._current_content_widget: Optional[Widget] = None
        self._switch_serial = 0
        self._switch_task: Optional[asyncio.Task] = None

    def compose(self) -> Iterable:
        """构建内容区域UI"""
        yield Header()
        with Container(id="content-container"):
            # 主内容容器，初始为空
            pass

    def switch_content(self, content_widget: Widget) -> None:
        """切换内容区域显示的 Widget（同步入口）

        为兼容测试与同步调用方，此方法不返回 coroutine；实际的 mount/remove
        在后台异步执行（Textual 7+ 需要 await）。
        """
        self._current_content_widget = content_widget
        self._switch_serial += 1
        serial = self._switch_serial

        def _schedule() -> None:
            if self._switch_task is not None and not self._switch_task.done():
                self._switch_task.cancel()
            self._switch_task = asyncio.create_task(self._apply_content(serial))

        self.call_after_refresh(_schedule)

    def clear_content(self) -> None:
        """清空内容区域（同步入口）"""
        if self._current_content_widget is None:
            return

        self._current_content_widget = None
        self._switch_serial += 1
        serial = self._switch_serial

        def _schedule() -> None:
            if self._switch_task is not None and not self._switch_task.done():
                self._switch_task.cancel()
            self._switch_task = asyncio.create_task(self._apply_content(serial))

        self.call_after_refresh(_schedule)

    async def _apply_content(self, serial: int) -> None:
        """根据当前状态应用内容（Textual 7+ 需要 await mount/remove）"""
        if serial != self._switch_serial:
            return

        try:
            content_container = self.query_one("#content-container", Container)
        except Exception:
            return

        try:
            await content_container.remove_children()

            if serial != self._switch_serial:
                return

            if self._current_content_widget is not None:
                await content_container.mount(self._current_content_widget)
                self.log.info(
                    f"内容区域已切换到: {self._current_content_widget.__class__.__name__}"
                )
            else:
                self.log.info("内容区域已清空")
        except Exception as e:
            self.log.warning(f"应用内容区域变更失败: {e}")
            return

        # 将焦点设置回侧边栏（NavigationSidebar）
        try:
            sidebar = self.app.query_one("NavigationSidebar")
            sidebar.focus()
            self.log.debug("焦点已返回到侧边栏")
        except Exception as e:
            self.log.warning(f"设置焦点到侧边栏失败: {e}")

    def get_current_content(self) -> Optional[Widget]:
        """获取当前显示的内容Widget

        Returns:
            Optional[Widget]: 当前内容Widget，如果没有则返回None
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
