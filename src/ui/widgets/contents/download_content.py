"""
ECMWF Downloader TUI 下载管理内容组件

显示下载任务的整体进度和活动任务列表，提供下载控制功能。
这是从DownloadScreen迁移而来的Widget版本。
支持方向键操作：表格用方向键移动，Enter键触发按钮。
"""

from typing import TYPE_CHECKING, Iterable, Optional

from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.events import Key, Resize
from textual.widget import Widget
from textual.widgets import Button, Label, ProgressBar

from src.core.progress import TaskStatus
from src.ui.widgets.task_table import TaskTable

if TYPE_CHECKING:
    from src.core.progress import TaskInfo


class DownloadContent(Widget):
    """下载管理内容组件

    显示：
    - 整体下载进度条
    - 活动任务列表（下载中的任务）
    - 下载控制按钮（开始、暂停、停止）
    """

    DEFAULT_CSS = """
    DownloadContent {
        width: 1fr;
        height: 1fr;
    }

    /* ═══════════════════════════════════════════════════════════════
       主容器 - 自适应布局
       ═══════════════════════════════════════════════════════════════ */
    #download-container {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
    }

    #download-container #download-title {
        text-align: left;
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
    }

    /* ═══════════════════════════════════════════════════════════════
       进度信息卡片 - 单卡片布局
       ═══════════════════════════════════════════════════════════════ */
    #download-container #progress-card {
        width: 1fr;
        height: auto;
        border: solid $panel;
        padding: 1 0;
        margin: 1 0;
        background: $panel 30%;
    }

    /* 第一行：标签 + 进度条 */
    #download-container #progress-row {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }

    #download-container #progress-label {
        width: auto;
        text-style: bold;
        color: $accent;
        margin-right: 1;
    }

    /* 进度条占满剩余宽度 */
    #download-container #overall-progress {
        width: 1fr;
        margin: 0;
    }

    /* 第二行：统计信息并排显示 */
    #download-container #stats-row {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }

    #download-container .stat-item {
        width: 1fr;
        text-align: center;
        margin: 0;
    }

    /* Textual CSS 不支持复杂 :not() 选择器，改为显式 ID 选择器 */
    #download-container #stat-downloading,
    #download-container #stat-completed,
    #download-container #stat-pending,
    #download-container #stat-failed {
        margin-left: 1;
    }

    #download-container .stat-value {
        color: $accent;
        text-style: bold;
    }

    /* ═══════════════════════════════════════════════════════════════
       活动任务列表区域 - 加高表格
       ═══════════════════════════════════════════════════════════════ */
    #download-container #active-tasks-section {
        width: 1fr;
        height: 1fr;
        margin: 1 0;
    }

    #download-container #active-label {
        text-align: left;
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }

    #download-container #active-table {
        width: 1fr;
        height: 1fr;
        border: solid $panel;
        margin: 1 0 0 0;
    }

    /* ═══════════════════════════════════════════════════════════════
       控制按钮区域 - 紧凑布局
       ═══════════════════════════════════════════════════════════════ */
    #download-container #control-section {
        width: 1fr;
        height: auto;
        margin: 1 0 0 0;
    }

    #download-container #control-section Button {
        width: 1fr;
        margin: 0;
    }

    #download-container #control-section Button.-middle,
    #download-container #control-section Button.-last {
        margin-left: 1;
    }
    """

    def __init__(self, app, **kwargs):
        """初始化下载管理内容组件

        Args:
            app: 应用实例引用
            **kwargs: 传递给父类的参数
        """
        super().__init__(**kwargs)
        self._app_ref = app  # 使用_app_ref避免与Widget.app属性冲突
        self._observer_registered = False
        self._last_column_widths: Optional[tuple[int, int, int, int, int]] = None

    def compose(self) -> Iterable:
        """构建下载管理 UI"""
        # 主容器 - 使用 Vertical 以支持宽度自适应
        with Vertical(id="download-container", classes="content-container"):
            # 标题
            yield Label("下载管理", id="download-title", classes="page-title")

            # 进度信息卡片（合并）
            with Vertical(id="progress-card"):
                # 第一行：整体进度标签 + 进度条（进度条占满剩余宽度）
                with Horizontal(id="progress-row"):
                    yield Label("整体进度", id="progress-label")
                    yield ProgressBar(
                        total=100,
                        show_percentage=True,
                        show_eta=False,
                        id="overall-progress",
                    )

                # 第二行：统计信息并排（5项）
                with Horizontal(id="stats-row"):
                    yield Label("总文件: 0", id="stat-total", classes="stat-item")
                    yield Label("下载中: 0", id="stat-downloading", classes="stat-item")
                    yield Label("已完成: 0", id="stat-completed", classes="stat-item")
                    yield Label("排队中: 0", id="stat-pending", classes="stat-item")
                    yield Label("失败: 0", id="stat-failed", classes="stat-item")

            # 活动任务列表
            with Vertical(id="active-tasks-section"):
                yield Label("活动任务列表", id="active-label")
                yield TaskTable(id="active-table")

            # 控制按钮区域
            with Horizontal(id="control-section"):
                yield Button("开始所有", id="btn-start-all", variant="default")
                yield Button("暂停所有", id="btn-pause-all", variant="default", classes="-middle")
                yield Button("停止所有", id="btn-stop-all", variant="default", classes="-last")

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        # 等首帧渲染完成后再初始化，确保DOM可查询（Textual 7+ 不支持 interval=0 的 timer）
        self.call_after_refresh(self._initialize_after_mount)

    def on_resize(self, event: Resize) -> None:
        """窗口尺寸变化时，保持表格列宽占满可用空间"""
        self._resize_table_columns()

    def _initialize_after_mount(self) -> None:
        """DOM完全挂载后初始化"""
        # 检查Widget是否仍然挂载
        if not self.is_mounted:
            return

        try:
            # 加载活动任务
            self._load_active_tasks()
            # 调整表格列宽以占满可用空间
            self._resize_table_columns()
            # 更新整体进度
            self._update_overall_progress()
            # 注册进度观察者
            self._register_progress_observer()
        except Exception as e:
            import traceback
            self.log.error(f"[DownloadContent] 初始化失败: {e}")
            self.log.error(traceback.format_exc())
            # 显示错误通知
            try:
                self.notify(f"下载页面初始化失败: {e}", severity="error")
            except:
                pass

    def _resize_table_columns(self) -> None:
        """按当前表格宽度动态调整列宽，尽量占满可用空间"""
        try:
            table = self.query_one("#active-table", TaskTable)
        except NoMatches:
            return

        columns = list(table.ordered_columns)
        if len(columns) < 5:
            return

        table_width = table.size.width
        if table_width <= 0:
            return

        # 计算可用宽度（减去边框和列分隔符）
        interior_width = max(0, table_width - 2 - (len(columns) - 1))

        # 按比例分配列宽
        status_width = max(6, min(10, int(interior_width * 0.08)))
        progress_width = max(8, min(10, int(interior_width * 0.08)))
        time_width = max(16, min(20, int(interior_width * 0.15)))
        task_id_width = max(20, min(35, int(interior_width * 0.25)))
        filename_width = max(25, interior_width - task_id_width - status_width - progress_width - time_width)

        # 设置列宽（按添加顺序：任务ID、文件名、状态、进度、时间）
        new_widths = (
            task_id_width,
            filename_width,
            status_width,
            progress_width,
            time_width,
        )
        if self._last_column_widths == new_widths:
            return

        self._last_column_widths = new_widths
        columns[0].auto_width = False
        columns[0].width = task_id_width
        columns[1].auto_width = False
        columns[1].width = filename_width
        columns[2].auto_width = False
        columns[2].width = status_width
        columns[3].auto_width = False
        columns[3].width = progress_width
        columns[4].auto_width = False
        columns[4].width = time_width

        table.refresh()

    def on_unmount(self) -> None:
        """组件卸载时清理"""
        # 注销进度观察者
        self._unregister_progress_observer()

    def _load_active_tasks(self) -> None:
        """加载活动任务列表（下载中和重试中的任务）"""
        table = self.query_one("#active-table", TaskTable)

        # 获取下载中和重试中的任务
        downloading_tasks = self._app_ref.progress_manager.get_tasks_by_status(
            TaskStatus.DOWNLOADING
        )
        retrying_tasks = self._app_ref.progress_manager.get_tasks_by_status(
            TaskStatus.RETRYING
        )

        # 合并任务列表
        active_tasks = list(downloading_tasks) + list(retrying_tasks)

        # 按开始时间排序（最近的在前）
        active_tasks.sort(
            key=lambda t: t.started_at or t.created_at, reverse=True
        )

        # 加载到表格
        table.load_tasks(active_tasks)

    def _update_overall_progress(self) -> None:
        """更新整体进度和统计信息"""
        # 获取统计摘要
        summary = self._app_ref.progress_manager.get_summary()

        # 更新进度条
        progress_bar = self.query_one("#overall-progress", ProgressBar)
        progress_bar.progress = summary["overall_progress"]

        # 更新统计信息（5项并排）
        self.query_one("#stat-total", Label).update(
            f"总文件: {summary['total_tasks']}"
        )
        self.query_one("#stat-downloading", Label).update(
            f"下载中: {summary['downloading']}"
        )
        self.query_one("#stat-completed", Label).update(
            f"已完成: {summary['completed']}"
        )
        # 获取排队中任务数
        pending_count = len(list(self._app_ref.progress_manager.get_tasks_by_status(TaskStatus.PENDING)))
        self.query_one("#stat-pending", Label).update(
            f"排队中: {pending_count}"
        )
        self.query_one("#stat-failed", Label).update(
            f"失败: {summary['failed']}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件处理"""
        button_id = event.button.id

        if button_id == "btn-start-all":
            self._handle_start_all()

        elif button_id == "btn-pause-all":
            self._handle_pause_all()

        elif button_id == "btn-stop-all":
            self._handle_stop_all()

    def _handle_start_all(self) -> None:
        """处理开始所有下载"""
        # TODO: 实现开始所有待下载任务的逻辑（需要下载Worker）
        self.notify("开始所有下载功能待实现", severity="information")

    def _handle_pause_all(self) -> None:
        """处理暂停所有下载"""
        # TODO: 实现暂停所有下载中任务的逻辑（需要下载Worker）
        self.notify("暂停所有下载功能待实现", severity="information")

    def _handle_stop_all(self) -> None:
        """处理停止所有下载"""
        # TODO: 实现停止所有下载中任务的逻辑（需要下载Worker）
        self.notify("停止所有下载功能待实现", severity="information")

    def refresh_data(self) -> None:
        """刷新下载管理数据"""
        self._load_active_tasks()
        self._update_overall_progress()

    def _register_progress_observer(self) -> None:
        """注册进度管理器观察者"""
        if not self._observer_registered:
            self._app_ref.progress_manager.register_observer(
                self._progress_observer_callback
            )
            self._observer_registered = True
            self.log.info("[DownloadContent] 进度观察者已注册")

    def _unregister_progress_observer(self) -> None:
        """注销进度管理器观察者"""
        if self._observer_registered:
            self._app_ref.progress_manager.unregister_observer(
                self._progress_observer_callback
            )
            self._observer_registered = False
            self.log.info("[DownloadContent] 进度观察者已注销")

    def _progress_observer_callback(
        self, task_id: str, task_info: "TaskInfo"
    ) -> None:
        """进度管理器观察者回调（可能在后台线程调用）"""
        # 组件卸载后或应用退出阶段，忽略后续更新，避免 call_from_thread 阻塞/异常
        if (not self._observer_registered) or (not self.is_mounted):
            return

        try:
            # 使用 call_from_thread 确保在主线程中更新 UI
            self._app_ref.call_from_thread(
                self._on_progress_update,
                task_id,
                task_info,
            )
        except Exception:
            # 应用退出期间可能无法再调度回主线程，静默忽略即可
            return

    def _on_progress_update(self, task_id: str, task_info: "TaskInfo") -> None:
        """进度更新时刷新界面

        Args:
            task_id: 任务ID
            task_info: 任务信息
        """
        if not self.is_mounted:
            return

        # 如果是活动任务（下载中或重试中），增量更新表格
        if task_info.status in (TaskStatus.DOWNLOADING, TaskStatus.RETRYING):
            try:
                table = self.query_one("#active-table", TaskTable)
                table.update_row(task_info)
            except NoMatches:
                return

        # 始终更新整体进度
        self._update_overall_progress()

    def on_key(self, event: Key) -> None:
        """处理键盘事件

        Enter键：如果焦点在按钮上，触发按钮操作
        方向键：由各个控件自行处理（表格、按钮等）
        Tab键：返回侧边栏（由ContentArea处理）

        Args:
            event: 键盘事件
        """
        # Enter键处理
        if event.key == "enter":
            # 检查焦点是否在按钮上
            focused = self.app.focused
            if focused and isinstance(focused, Button):
                # 触发按钮
                focused.action_press()
                event.stop()

        # Tab键交给ContentArea处理（返回侧边栏）
        # 方向键由各个控件自行处理
