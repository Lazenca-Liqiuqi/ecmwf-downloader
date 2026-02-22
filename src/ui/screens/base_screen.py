"""
ECMWF Downloader TUI 基础屏幕模块

定义所有屏幕的抽象基类，提供通用功能和观察者模式集成。
"""

from abc import abstractmethod
from typing import TYPE_CHECKING

from textual.screen import Screen
from textual.widgets import Header, Footer

if TYPE_CHECKING:
    from src.core.progress import TaskInfo, TaskStatus
    from src.ui.app import ECMWFDownloaderApp


class BaseScreen(Screen):
    """基础屏幕抽象类

    所有自定义屏幕的基类，提供以下功能：
    - 自动注册 ProgressManager 观察者
    - 线程安全的 UI 更新机制（使用 call_from_thread）
    - 通用的生命周期钩子
    - 标准的 Header 和 Footer 布局

    子类应该：
    - 重写 compose() 方法构建 UI
    - 重写 _on_progress_update() 处理进度更新

    Note:
        self.app 是 Screen 基类提供的 property，指向父级 App 实例。
    """

    # 基础 CSS 变量定义（确保单独测试时也能访问）
    # 这些变量与 App 级别的 CSS 变量保持一致
    DEFAULT_CSS = """
    /* CSS 变量定义 - 深色主题 + 青绿强调 */
    $bg: #0d1117;
    $panel: #161b22;
    $surface: #1c2128;
    $border: #30363d;

    $text: #f0f6fc;
    $text-muted: #8b949e;

    $primary: #58a6ff;
    $accent: #3fb950;
    $success: #3fb950;
    $warning: #d29922;
    $error: #f85149;
    """

    def __init__(self, *args, **kwargs):
        """初始化基础屏幕"""
        super().__init__(*args, **kwargs)

        # 观察者注册标志
        self._observer_registered = False

    def on_mount(self) -> None:
        """屏幕挂载时的生命周期钩子

        在屏幕显示时调用。
        子类可以重写此方法添加自定义初始化逻辑。
        """
        # 注册进度观察者
        self._register_progress_observer()

        # 调用子类的初始化钩子
        self.on_screen_mount()

    def on_unmount(self) -> None:
        """屏幕卸载时的生命周期钩子

        在屏幕隐藏时调用。
        """
        # 注销进度观察者（防止递归和内存泄漏）
        self._unregister_progress_observer()

        # 调用子类的清理钩子
        self.on_screen_unmount()

    def on_screen_mount(self) -> None:
        """屏幕挂载钩子（子类可重写）

        在屏幕显示时调用，用于加载数据、更新 UI 等。
        """
        pass

    def on_screen_unmount(self) -> None:
        """屏幕卸载钩子（子类可重写）

        在屏幕隐藏时调用，用于清理资源、保存状态等。
        """
        pass

    def _register_progress_observer(self) -> None:
        """注册进度管理器观察者

        将此屏幕注册为 ProgressManager 的观察者，
        以便在任务状态变化时接收通知。
        """
        if not self._observer_registered:
            self.app.progress_manager.register_observer(
                self._progress_observer_callback
            )
            self._observer_registered = True
            self.log.info(f"[{self.__class__.__name__}] 进度观察者已注册")

    def _unregister_progress_observer(self) -> None:
        """注销进度管理器观察者

        在屏幕卸载时调用，防止递归和内存泄漏。
        """
        if self._observer_registered:
            self.app.progress_manager.unregister_observer(
                self._progress_observer_callback
            )
            self._observer_registered = False
            self.log.info(f"[{self.__class__.__name__}] 进度观察者已注销")

    def _progress_observer_callback(
        self, task_id: str, task_info: "TaskInfo", event_type: "TaskEventType"
    ) -> None:
        """进度管理器观察者回调（可能在后台线程调用）

        这是 ProgressManager 观察者模式的回调函数。
        由于下载在后台线程执行，此回调也可能在后台线程调用。

        重要：所有 UI 更新必须通过 call_from_thread() 在主线程执行！

        Args:
            task_id: 任务ID
            task_info: 任务信息快照
            event_type: 事件类型（CREATED/UPDATED/DELETED）
        """
        # 使用 call_from_thread 确保在主线程中更新 UI
        self.app.call_from_thread(
            self._on_progress_update,
            task_id,
            task_info,
            event_type,
        )

    def _on_progress_update(
        self, task_id: str, task_info: "TaskInfo", event_type: "TaskEventType"
    ) -> None:
        """进度更新处理（在主线程中调用）

        子类重写此方法以响应进度更新。
        此方法已通过 call_from_thread() 确保在主线程中执行。

        Args:
            task_id: 任务ID
            task_info: 任务信息快照
            event_type: 事件类型（CREATED/UPDATED/DELETED）
        """
        # 默认实现：子类重写
        pass

    def refresh_data(self) -> None:
        """刷新屏幕数据（子类可重写）

        主动刷新屏幕显示的数据。
        例如：重新加载任务列表、更新统计信息等。
        """
        pass

    def get_status_color(self, status: "TaskStatus") -> str:
        """获取任务状态对应的颜色

        Args:
            status: 任务状态

        Returns:
            str: Textual 颜色标识
        """
        from src.core.progress import TaskStatus

        color_map = {
            TaskStatus.PENDING: "grey",
            TaskStatus.DOWNLOADING: "blue",
            TaskStatus.COMPLETED: "green",
            TaskStatus.FAILED: "red",
            TaskStatus.CANCELLED: "yellow",
            TaskStatus.RETRYING: "orange",
        }
        return color_map.get(status, "white")

    def get_status_text(self, status: "TaskStatus") -> str:
        """获取任务状态的中文显示

        Args:
            status: 任务状态

        Returns:
            str: 中文状态文本
        """
        from src.core.progress import TaskStatus

        text_map = {
            TaskStatus.PENDING: "待下载",
            TaskStatus.DOWNLOADING: "下载中",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.FAILED: "失败",
            TaskStatus.CANCELLED: "已取消",
            TaskStatus.RETRYING: "重试中",
        }
        return text_map.get(status, str(status))

    @abstractmethod
    def compose(self):
        """构建屏幕 UI（子类必须实现）

        Returns:
            Iterable[Widget]: 屏幕包含的组件
        """
        # 默认提供 Header 和 Footer
        yield Header()
        yield Footer()
