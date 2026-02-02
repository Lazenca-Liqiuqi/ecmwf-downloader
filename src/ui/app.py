"""
ECMWF Downloader TUI 应用主入口

基于 Textual 框架的终端用户界面应用。
"""

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from textual.app import App
from textual.widgets import Header, Footer

from src.ui.screens.home_screen import HomeScreen
from src.ui.screens.tasks_screen import TasksScreen
from src.ui.screens.download_screen import DownloadScreen
from src.ui.screens.accounts_screen import AccountsScreen
from src.ui.screens.config_screen import ConfigScreen
from src.ui.styles.theme import get_global_styles

if TYPE_CHECKING:
    from src.core.account_pool import AccountPool
    from src.core.progress import ProgressManager


class ECMWFDownloaderApp(App):
    """ECMWF下载器TUI应用主类

    提供基于Textual框架的终端用户界面，管理所有屏幕和导航。
    采用延迟加载模式初始化核心模块，提高启动性能。
    """

    # 应用标题
    TITLE = "ECMWF Downloader"

    # 全局 CSS 样式
    CSS = get_global_styles()

    # 屏幕注册（将在后续任务中逐步实现）
    SCREENS = {
        "home": HomeScreen,  # ✅ 首页屏幕已实现
        "tasks": TasksScreen,  # ✅ 任务列表屏幕已实现
        "download": DownloadScreen,  # ✅ 下载管理屏幕已实现
        "accounts": AccountsScreen,  # ✅ 账号管理屏幕已实现
        "config": ConfigScreen,  # ✅ 配置管理屏幕已实现
    }

    # 全局快捷键绑定
    # 使用 switch_screen 替代 push_screen 避免stack无限增长导致RecursionError
    BINDINGS = [
        ("q", "quit", "退出"),
        ("ctrl+c", "quit", "退出"),
        ("h", "switch_screen('home')", "首页"),
        ("t", "switch_screen('tasks')", "任务"),
        ("d", "switch_screen('download')", "下载"),
        ("a", "switch_screen('accounts')", "账号"),
        ("c", "switch_screen('config')", "配置"),
    ]

    # 默认使用 Header 和 Footer
    # Header: 显示应用标题和当前时间
    # Footer: 显示快捷键提示

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

        # 确保数据目录存在
        self._ensure_data_dir()

    def _ensure_data_dir(self) -> None:
        """确保数据目录存在"""
        data_dir = self._progress_path.parent
        if not data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)

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

    def on_mount(self) -> None:
        """应用挂载时的生命周期钩子

        在应用启动后、显示第一个屏幕前调用。
        用于初始化应用状态、加载数据等。
        """
        self.log.info("ECMWF Downloader TUI 启动")
        self.log.info(f"配置文件: {self._config_path}")
        self.log.info(f"账号配置: {self._accounts_path}")
        self.log.info(f"进度文件: {self._progress_path}")

        # 显示欢迎消息
        self.notify(
            "欢迎使用 ECMWF Downloader！按 'q' 或 Ctrl+C 退出",
            title="欢迎",
            severity="information",
            timeout=5,
        )

        # 显示首页屏幕
        self.push_screen("home")

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
