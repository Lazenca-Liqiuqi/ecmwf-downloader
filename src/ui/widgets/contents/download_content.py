"""
ECMWF Downloader TUI 下载管理内容组件

显示下载任务的整体进度和活动任务列表，提供下载控制功能。
这是从DownloadScreen迁移而来的Widget版本。
"""

from typing import TYPE_CHECKING, Iterable

from textual.containers import Container, Horizontal, Vertical
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

    CSS = """
    #download-title {
        text-align: left;
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 2;
    }

    #progress-section {
        height: 8;
        padding: 1 1;
    }

    #progress-label {
        text-align: left;
        text-style: bold;
        margin-bottom: 1;
        color: $text 80%;
    }

    #overall-progress {
        width: 1fr;
        margin: 0 0;
    }

    #progress-stats {
        height: 2;
        margin-top: 1;
    }

    #progress-stats Label {
        width: 1fr;
        text-align: center;
    }

    #active-tasks-section {
        height: 16;
        padding: 0 1;
    }

    #active-label {
        text-align: left;
        text-style: bold;
        margin-bottom: 1;
        color: $text 80%;
    }

    #active-table {
        height: 1fr;
        border: solid $panel;
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

    def compose(self) -> Iterable:
        """构建下载管理 UI"""
        # 主容器
        with Container(id="download-container", classes="content-container"):
            # 标题
            yield Label("下载管理", id="download-title", classes="page-title")

            # 整体进度区域
            with Vertical(id="progress-section", classes="section-standard"):
                yield Label("整体进度", id="progress-label")
                yield ProgressBar(
                    total=100,
                    show_percentage=True,
                    show_eta=False,
                    id="overall-progress",
                )
                with Horizontal(id="progress-stats"):
                    yield Label("总任务: 0", id="stat-total")
                    yield Label("下载中: 0", id="stat-downloading")
                    yield Label("已完成: 0", id="stat-completed")
                    yield Label("失败: 0", id="stat-failed")

            # 活动任务列表
            with Vertical(id="active-tasks-section", classes="section-standard"):
                yield Label("活动任务", id="active-label")
                yield TaskTable(id="active-table")

            # 控制按钮区域
            with Horizontal(id="control-section", classes="button-section"):
                yield Button("开始所有", id="btn-start-all", variant="default")
                yield Button("暂停所有", id="btn-pause-all", variant="default")
                yield Button("停止所有", id="btn-stop-all", variant="default")
                yield Button("刷新", id="btn-refresh", variant="default")

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        # 加载活动任务
        self._load_active_tasks()
        # 更新整体进度
        self._update_overall_progress()
        # 注册进度观察者
        self._register_progress_observer()

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

        # 更新统计标签
        self.query_one("#stat-total", Label).update(
            f"总任务: {summary['total_tasks']}"
        )
        self.query_one("#stat-downloading", Label).update(
            f"下载中: {summary['downloading']}"
        )
        self.query_one("#stat-completed", Label).update(
            f"已完成: {summary['completed']}"
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

        elif button_id == "btn-refresh":
            self._handle_refresh()

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

    def _handle_refresh(self) -> None:
        """处理刷新操作"""
        self._load_active_tasks()
        self._update_overall_progress()
        self.notify("已刷新", severity="information")

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
        # 使用 call_from_thread 确保在主线程中更新 UI
        self._app_ref.call_from_thread(
            self._on_progress_update,
            task_id,
            task_info,
        )

    def _on_progress_update(self, task_id: str, task_info: "TaskInfo") -> None:
        """进度更新时刷新界面

        Args:
            task_id: 任务ID
            task_info: 任务信息
        """
        # 如果是活动任务（下载中或重试中），增量更新表格
        if task_info.status in (TaskStatus.DOWNLOADING, TaskStatus.RETRYING):
            table = self.query_one("#active-table", TaskTable)
            table.update_row(task_info)

        # 始终更新整体进度
        self._update_overall_progress()
