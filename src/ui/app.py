"""
ECMWF Downloader TUI 应用主入口

基于 Textual 框架的终端用户界面应用。
采用侧边栏布局架构，包含导航侧边栏和内容区域。
"""

from pathlib import Path
from typing import Dict, Iterable, Optional, TYPE_CHECKING

from textual.app import App
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from src.ui.styles.theme import get_global_styles
from src.ui.widgets.content_area import ContentArea
from src.ui.widgets.contents.accounts_content import AccountsContent
from src.ui.widgets.contents.config_content import ConfigContent
from src.ui.widgets.contents.download_content import DownloadContent
from src.ui.widgets.contents.home_content import HomeContent
from src.ui.widgets.contents.tasks_content import TasksContent
from src.ui.widgets.navigation_sidebar import NavigationSidebar

if TYPE_CHECKING:
    from src.core.account_pool import AccountPool
    from src.core.progress import ProgressManager
    from src.ui.widgets.contents.home_content import HomeContent
    from src.ui.widgets.contents.tasks_content import TasksContent
    from src.ui.widgets.contents.download_content import DownloadContent
    from src.ui.widgets.contents.accounts_content import AccountsContent
    from src.ui.widgets.contents.config_content import ConfigContent


class ECMWFDownloaderApp(App):
    """ECMWF下载器TUI应用主类

    提供基于Textual框架的终端用户界面，采用侧边栏布局架构。

    布局结构：
    - 左侧：NavigationSidebar（导航菜单）
    - 右侧：ContentArea（内容区域）
    - 底部：Footer（状态栏）

    采用延迟加载模式初始化核心模块，提高启动性能。
    """

    # 应用标题
    TITLE = "ECMWF Downloader"

    # 全局 CSS 样式
    CSS = get_global_styles()

    # 全局快捷键绑定
    # Textual的BINDINGS要求action必须是方法名，不能带参数
    # 因此为每个页面创建专门的action方法
    BINDINGS = [
        ("q", "quit", "退出"),
        ("ctrl+c", "quit", "退出"),
        ("h", "go_home", "首页"),
        ("t", "go_tasks", "任务"),
        ("d", "go_download", "下载"),
        ("a", "go_accounts", "账号"),
        ("c", "go_config", "配置"),
    ]

    def __init__(
        self,
        config_path: Optional[Path] = None,
        accounts_path: Optional[Path] = None,
        progress_path: Optional[Path] = None,
    ):
        """初始化应用

        Args:
            config_path: 配置文件路径（可选，默认使用 config/default_config.yaml）
            accounts_path: 账号配置文件路径（可选，默认使用 config/accounts.yaml）
            progress_path: 进度文件路径（可选，默认使用 data/download_progress.json）
        """
        super().__init__()

        # 配置文件路径
        self._config_path = config_path or Path("config/default_config.yaml")
        self._accounts_path = accounts_path or Path("config/accounts.yaml")
        self._progress_path = progress_path or Path("data/download_progress.json")

        # 核心模块实例（延迟加载）
        self._account_pool: Optional["AccountPool"] = None
        self._progress_manager: Optional["ProgressManager"] = None

        # 内容Widget实例（在on_mount中初始化）
        self._content_widgets: Dict[str, "HomeContent | TasksContent | DownloadContent | AccountsContent | ConfigContent"] = {}

        # 确保数据目录存在
        self._ensure_data_dir()

    def _ensure_data_dir(self) -> None:
        """确保数据目录存在"""
        data_dir = self._progress_path.parent
        if not data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)

    def compose(self) -> Iterable:
        """构建应用UI

        采用侧边栏布局：
        - 左侧：NavigationSidebar（导航菜单）
        - 右侧：ContentArea（内容区域，已包含Header和Footer）
        """
        with Horizontal():
            yield NavigationSidebar()
            yield ContentArea(id="main-content")

    def on_mount(self) -> None:
        """应用挂载时的生命周期钩子

        在应用启动后、显示第一个屏幕前调用。
        用于初始化应用状态、加载数据等。
        """
        self.log.info("ECMWF Downloader TUI 启动")
        self.log.info(f"配置文件: {self._config_path}")
        self.log.info(f"账号配置: {self._accounts_path}")
        self.log.info(f"进度文件: {self._progress_path}")

        # 初始化所有内容Widget
        self._content_widgets = {
            "home": HomeContent(app=self),
            "tasks": TasksContent(app=self),
            "download": DownloadContent(app=self),
            "accounts": AccountsContent(app=self),
            "config": ConfigContent(app=self),
        }
        self.log.info(f"内容Widget已初始化: {list(self._content_widgets.keys())}")

        # 检查Widget是否可访问
        for page_id, widget in self._content_widgets.items():
            self.log.info(f"Widget {page_id}: {widget.__class__.__name__}, app={widget.app}")

        # 显示首页
        self.action_switch_page("home")

        # 设置初始焦点在侧边栏
        try:
            sidebar = self.query_one(NavigationSidebar)
            sidebar.focus()
            self.log.info("初始焦点已设置到侧边栏")
        except Exception as e:
            self.log.warning(f"设置初始焦点失败: {e}")

        # 显示欢迎消息
        self.notify(
            "欢迎使用 ECMWF Downloader！按 Tab 键在侧边栏和内容区域间切换，按 'q' 或 Ctrl+C 退出",
            title="欢迎",
            severity="information",
            timeout=5,
        )

    def action_switch_page(self, page_id: str) -> None:
        """切换当前显示的页面（同步入口）

        兼容测试与同步调用方；实际的 mount/remove 在 ContentArea 内部异步执行。
        """
        # 验证page_id
        if page_id not in self._content_widgets:
            self.log.error(f"无效的页面ID: {page_id}")
            return

        # 更新侧边栏的激活状态
        try:
            sidebar = self.query_one(NavigationSidebar)
            sidebar.current_page = page_id
        except Exception as e:
            self.log.warning(f"更新侧边栏状态失败: {e}")

        # 切换内容区域
        try:
            content_area = self.query_one("#main-content", ContentArea)
            content_widget = self._content_widgets[page_id]
            content_area.switch_content(content_widget)
            self.log.info(f"页面已切换到: {page_id}")
        except Exception as e:
            self.log.error(f"切换页面失败: {e}")

    # 专门的action方法供快捷键调用（Textual要求BINDINGS中的action必须是方法名）
    def action_go_home(self) -> None:
        """快捷键h：切换到首页"""
        self.action_switch_page("home")

    def action_go_tasks(self) -> None:
        """快捷键t：切换到任务页"""
        self.action_switch_page("tasks")

    def action_go_download(self) -> None:
        """快捷键d：切换到下载页"""
        self.action_switch_page("download")

    def action_go_accounts(self) -> None:
        """快捷键a：切换到账号页"""
        self.action_switch_page("accounts")

    def action_go_config(self) -> None:
        """快捷键c：切换到配置页"""
        self.action_switch_page("config")

    @property
    def account_pool(self) -> "AccountPool":
        """获取账号池实例（延迟加载）

        Returns:
            AccountPool: 账号池管理器实例

        Raises:
            Exception: 账号配置文件加载失败
        """
        if self._account_pool is None:
            from src.core.account_pool import AccountPool

            self._account_pool = AccountPool(
                config_file=self._accounts_path,
                auto_disable_threshold=5,
            )
            self.log.info("账号池初始化完成")
        return self._account_pool

    @property
    def progress_manager(self) -> "ProgressManager":
        """获取进度管理器实例（延迟加载）

        Returns:
            ProgressManager: 进度管理器实例
        """
        if self._progress_manager is None:
            from src.core.progress import ProgressManager

            self._progress_manager = ProgressManager(
                progress_file=self._progress_path
            )
            self.log.info("进度管理器初始化完成")
        return self._progress_manager

    def on_unmount(self) -> None:
        """应用卸载时的生命周期钩子

        在应用退出前调用。
        用于保存状态、清理资源等。
        """
        self.log.info("ECMWF Downloader TUI 退出")

        # 保存进度
        if self._progress_manager is not None:
            self._progress_manager.save()
            self.log.info("进度已保存")


# 创建应用的便捷函数（供 __main__.py 使用）
def create_app(
    config_path: Optional[Path] = None,
    accounts_path: Optional[Path] = None,
    progress_path: Optional[Path] = None,
) -> ECMWFDownloaderApp:
    """创建应用实例的便捷函数

    Args:
        config_path: 配置文件路径
        accounts_path: 账号配置文件路径
        progress_path: 进度文件路径

    Returns:
        ECMWFDownloaderApp: 应用实例
    """
    return ECMWFDownloaderApp(
        config_path=config_path,
        accounts_path=accounts_path,
        progress_path=progress_path,
    )
