"""
ECMWF Downloader TUI 首页内容组件

显示应用概览、统计信息和任务列表。
这是从HomeScreen迁移而来的Widget版本。
首页为只读概览页面，不包含任何操作控件。
"""

from typing import TYPE_CHECKING, Iterable

from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.events import Key, Resize
from textual.widget import Widget
from textual.widgets import DataTable, Label

if TYPE_CHECKING:
    from src.core.progress import TaskInfo, TaskStatus


class HomeContent(Widget):
    """首页内容组件

    显示：
    - 应用标题和欢迎信息
    - 任务信息概览（合并的总任务统计）
    - 账号池状态（总账号、空闲、失效）
    - 最近任务列表（最多5条）

    注意：
    - 这是Widget版本，不包含Header和Footer
    - Header和Footer由ContentArea提供
    - 需要在构造时传入app引用
    - 首页为只读概览，无操作控件
    """

    # 首页专用样式（与全局样式合并）
    DEFAULT_CSS = """
    HomeContent {
        width: 1fr;
        height: 1fr;
    }

    /* ═══════════════════════════════════════════════════════════════
       主容器 - 自适应布局
       ═══════════════════════════════════════════════════════════════ */
    #home-container {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
    }

    #app-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 0;
    }

    #app-subtitle {
        text-align: center;
        text-style: italic;
        margin-top: 0;
        margin-bottom: 1;
        color: $text 60%;
    }

    /* ═══════════════════════════════════════════════════════════════
       统计区域容器 - 占满窗口宽度
       ═══════════════════════════════════════════════════════════════ */
    #stats-section {
        width: 1fr;
        height: auto;
        margin: 1 0;
    }

    /* ═══════════════════════════════════════════════════════════════
       统计卡片样式 - 占满宽度
       ═══════════════════════════════════════════════════════════════ */
    #home-container .stat-card {
        width: 1fr;
        height: auto;
        border: round $border;
        padding: 1;
        margin: 0;
        background: $surface;
    }

    .card-title {
        text-align: left;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .stat-item {
        text-align: left;
        text-style: none;
        color: $text 90%;
        margin: 0;
    }

    /* ═══════════════════════════════════════════════════════════════
       最近任务区域 - 自适应
       ═══════════════════════════════════════════════════════════════ */
    #home-container #recent-title {
        text-align: left;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
        margin-left: 0;
        color: $accent;
    }

    #home-container #recent-table {
        width: 1fr;
        height: 1fr;
        min-height: 10;
        margin: 1 0 2 0;
    }
    """

    def __init__(self, app, **kwargs):
        """初始化首页内容组件

        Args:
            app: 应用实例引用
            **kwargs: 传递给父类的参数
        """
        super().__init__(**kwargs)
        self._app_ref = app  # 使用_app_ref避免与Widget.app属性冲突
        self._observer_registered = False

    def compose(self) -> Iterable:
        """构建首页 UI"""
        # 主容器
        with Vertical(id="home-container", classes="content-container"):
            # 标题区域
            yield Label("ECMWF Downloader", id="app-title")
            yield Label("欧洲中期天气预报中心数据下载工具", id="app-subtitle")

            # 统计区域：两个大卡片并排
            with Horizontal(id="stats-section"):
                # 任务信息卡片
                with Vertical(classes="stat-card"):
                    yield Label("任务信息", classes="card-title")
                    yield Label("总任务: 0", id="stat-total", classes="stat-item")
                    yield Label("下载中: 0", id="stat-downloading", classes="stat-item")
                    yield Label("已完成: 0", id="stat-completed", classes="stat-item")
                    yield Label("失败: 0", id="stat-failed", classes="stat-item")

                # 账号池状态卡片
                with Vertical(classes="stat-card"):
                    yield Label("账号池状态", classes="card-title")
                    yield Label("总账号: 0", id="account-total", classes="stat-item")
                    yield Label("正忙: 0", id="account-busy", classes="stat-item")
                    yield Label("空闲: 0", id="account-active", classes="stat-item")
                    yield Label("失效: 0", id="account-failed", classes="stat-item")

            # 最近任务区域
            yield Label("最近任务", id="recent-title")
            yield DataTable(id="recent-table")

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        try:
            # 设置最近任务表格
            self._setup_recent_table()
            # 等布局完成后再按窗口宽度调整列宽
            self.call_after_refresh(self._resize_recent_table_columns)
            # 刷新统计数据
            self.refresh_data()
            # 注册进度观察者
            self._register_progress_observer()
        except Exception as e:
            self.log.warning(f"首页初始化失败（已忽略）: {e}")

    def on_resize(self, event: Resize) -> None:
        """窗口尺寸变化时，保持表格列宽占满可用空间"""
        self._resize_recent_table_columns()

    def on_unmount(self) -> None:
        """组件卸载时清理"""
        # 注销进度观察者
        self._unregister_progress_observer()

    def _setup_recent_table(self) -> None:
        """设置最近任务表格"""
        table = self.query_one("#recent-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.clear(columns=True)
        # 显式给出 width，避免 DataTable 进入 auto_width 模式（否则后续动态宽度会被忽略）
        table.add_column("任务ID", key="task_id", width=20)
        table.add_column("文件名", key="filename", width=40)
        table.add_column("状态", key="status", width=8)

    def _resize_recent_table_columns(self) -> None:
        """按当前表格宽度动态调整列宽（状态更窄，前两列更宽，并尽量占满）"""
        try:
            table = self.query_one("#recent-table", DataTable)
        except NoMatches:
            return

        columns = list(table.ordered_columns)
        if len(columns) < 3:
            return

        table_width = table.size.width
        if table_width <= 0:
            return

        # 估算可用宽度：减去左右边框与列分隔符（近似值，避免溢出）
        interior_width = max(0, table_width - 2 - (len(columns) - 1))

        # 状态列：尽量窄，但保证中文状态可读
        status_width = max(6, min(10, int(interior_width * 0.10)))
        # 任务ID列：适中
        task_id_width = max(22, min(50, int(interior_width * 0.34)))
        # 文件名列：吃掉剩余
        filename_width = max(20, interior_width - task_id_width - status_width)

        # 如果空间太窄，优先压缩任务ID列给文件名列
        min_filename = 20
        if filename_width < min_filename:
            shortage = min_filename - filename_width
            task_id_width = max(18, task_id_width - shortage)
            filename_width = max(min_filename, interior_width - task_id_width - status_width)

        # 设置列宽（按添加顺序：任务ID、文件名、状态）
        columns[0].auto_width = False
        columns[0].width = task_id_width
        columns[1].auto_width = False
        columns[1].width = filename_width
        columns[2].auto_width = False
        columns[2].width = status_width

        table.refresh(layout=True)

    def on_key(self, event: Key) -> None:
        """处理键盘事件

        首页只有表格，不需要特殊处理：
        - 方向键：由表格自行处理（移动行/列）
        - Tab键：返回侧边栏（由ContentArea处理）

        Args:
            event: 键盘事件
        """
        # Tab键交给ContentArea处理（返回侧边栏）
        # 方向键由表格自行处理
        pass

    def refresh_data(self) -> None:
        """刷新统计数据和最近任务"""
        # 更新任务统计卡片
        self._update_task_stats()

        # 更新账号池统计卡片
        self._update_account_stats()

        # 更新最近任务列表
        self._update_recent_tasks()

    def _update_task_stats(self) -> None:
        """更新任务统计卡片"""
        try:
            # 获取统计摘要
            summary = self._app_ref.progress_manager.get_summary()

            # 更新每个任务统计标签（格式：总任务: 0）
            self._update_stat_card("stat-total", f"总任务: {summary['total_tasks']}")
            self._update_stat_card("stat-downloading", f"下载中: {summary['downloading']}")
            self._update_stat_card("stat-completed", f"已完成: {summary['completed']}")
            self._update_stat_card("stat-failed", f"失败: {summary['failed']}")
        except NoMatches:
            self.log.warning("任务统计卡片未找到")

    def _update_account_stats(self) -> None:
        """更新账号池统计卡片"""
        try:
            # 账号池采用延迟加载：首页默认不触发初始化，避免破坏 lazy-loading 语义与测试预期。
            if getattr(self._app_ref, "_account_pool", None) is None:
                self._update_stat_card("account-total", "总账号: -")
                self._update_stat_card("account-busy", "正忙: -")
                self._update_stat_card("account-active", "空闲: -")
                self._update_stat_card("account-failed", "失效: -")
                return

            # 获取账号池统计
            usage = self._app_ref.account_pool.get_usage_summary()

            # 计算失效账号（FAILED + DISABLED）
            total = usage["total_accounts"]
            active = usage["active_accounts"]
            failed = total - active

            # 获取下载中的任务数作为"正忙"账号数
            summary = self._app_ref.progress_manager.get_summary()
            busy = min(summary["downloading"], active)  # 正忙数不超过活跃账号数

            # 更新每个账号统计标签（格式：总账号: 0）
            self._update_stat_card("account-total", f"总账号: {total}")
            self._update_stat_card("account-busy", f"正忙: {busy}")
            self._update_stat_card("account-active", f"空闲: {active}")
            self._update_stat_card("account-failed", f"失效: {failed}")
        except NoMatches:
            self.log.warning("账号统计卡片未找到")

    def _update_stat_card(self, card_id: str, value: str) -> None:
        """更新统计卡片数值

        Args:
            card_id: 卡片组件ID
            value: 新数值
        """
        try:
            label = self.query_one(f"#{card_id}", Label)
            label.update(value)
        except NoMatches:
            self.log.warning(f"统计卡片未找到: {card_id}")

    def _update_recent_tasks(self) -> None:
        """更新最近任务列表"""
        table = self.query_one("#recent-table", DataTable)
        table.clear()

        # 获取所有任务（返回 List[TaskInfo]）
        all_tasks = self._app_ref.progress_manager.get_all_tasks()

        # 按创建时间降序排序，取前5个
        recent_tasks = sorted(
            all_tasks,
            key=lambda t: t.created_at,
            reverse=True,
        )[:5]

        # 填充表格
        for task in recent_tasks:
            status_text = self.get_status_text(task.status)
            table.add_row(
                task.task_id,
                task.filename,
                status_text,
            )

    def _register_progress_observer(self) -> None:
        """注册进度管理器观察者"""
        if not self._observer_registered:
            self._app_ref.progress_manager.register_observer(
                self._progress_observer_callback
            )
            self._observer_registered = True
            self.log.info("[HomeContent] 进度观察者已注册")

    def _unregister_progress_observer(self) -> None:
        """注销进度管理器观察者"""
        if self._observer_registered:
            self._app_ref.progress_manager.unregister_observer(
                self._progress_observer_callback
            )
            self._observer_registered = False
            self.log.info("[HomeContent] 进度观察者已注销")

    def _progress_observer_callback(
        self, task_id: str, task_info: "TaskInfo"
    ) -> None:
        """进度管理器观察者回调（可能在后台线程调用）"""
        # 使用 call_from_thread 确保在主线程中更新 UI
        self._app_ref.call_from_thread(
            self._on_progress_update,
            task_id,
            task_info,
        )

    def _on_progress_update(
        self, task_id: str, task_info: "TaskInfo"
    ) -> None:
        """进度更新时刷新数据"""
        # 刷新统计数据和最近任务
        self.refresh_data()

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
