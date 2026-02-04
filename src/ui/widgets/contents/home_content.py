"""
ECMWF Downloader TUI 首页内容组件

显示应用概览、统计信息和快捷操作入口。
这是从HomeScreen迁移而来的Widget版本。
"""

from typing import TYPE_CHECKING, Iterable

from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button, DataTable, Label

if TYPE_CHECKING:
    from src.core.progress import TaskInfo, TaskStatus


class HomeContent(Widget):
    """首页内容组件

    显示：
    - 应用标题和欢迎信息
    - 统计卡片（总任务、下载中、已完成、失败）
    - 快捷操作按钮
    - 最近任务列表（最多5条）

    注意：
    - 这是Widget版本，不包含Header和Footer
    - Header和Footer由ContentArea提供
    - 需要在构造时传入app引用
    """

    # 首页专用样式（与全局样式合并）
    CSS = """
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
        margin-bottom: 2;
        color: $text 60%;
    }

    #stats-container {
        height: 12;
        margin: 2 3 2 3;
        padding: 0 1;
    }

    .stat-card {
        width: 25%;
        height: 100%;
        border: solid $accent;
        padding: 1 1;
        margin: 0 0;
    }

    .stat-card:last-child {
        margin-right: 0;
    }

    .stat-card:hover {
        border: solid $primary;
    }

    .stat-label {
        text-align: center;
        text-style: bold;
        margin-bottom: 0;
        color: $text 80%;
    }

    .stat-value {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-top: 0;
    }

    #actions-container {
        height: 4;
        margin: 2 3 2 3;
        padding: 0 1;
    }

    #recent-title {
        text-align: left;
        text-style: bold;
        margin-top: 2;
        margin-bottom: 1;
        color: $accent;
    }

    #recent-table {
        height: 16;
        border: solid $panel;
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
        with Container(id="home-container", classes="content-container"):
            # 标题区域
            yield Label("ECMWF Downloader", id="app-title")
            yield Label("欧洲中期天气预报中心数据下载工具", id="app-subtitle")

            # 统计卡片区域
            with Horizontal(id="stats-container"):
                with Vertical(classes="stat-card"):
                    yield Label("总任务", classes="stat-label")
                    yield Label("0", id="stat-total", classes="stat-value")
                with Vertical(classes="stat-card"):
                    yield Label("下载中", classes="stat-label")
                    yield Label("0", id="stat-downloading", classes="stat-value")
                with Vertical(classes="stat-card"):
                    yield Label("已完成", classes="stat-label")
                    yield Label("0", id="stat-completed", classes="stat-value")
                with Vertical(classes="stat-card"):
                    yield Label("失败", classes="stat-label")
                    yield Label("0", id="stat-failed", classes="stat-value")

            # 快捷操作区域
            with Horizontal(id="actions-container"):
                yield Button("任务列表", id="btn-tasks", variant="default")
                yield Button("下载管理", id="btn-download", variant="default")
                yield Button("账号管理", id="btn-accounts", variant="default")
                yield Button("配置管理", id="btn-config", variant="default")

            # 最近任务区域
            yield Label("最近任务", id="recent-title")
            yield DataTable(id="recent-table")

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        # 设置最近任务表格
        self._setup_recent_table()
        # 刷新统计数据
        self.refresh_data()
        # 注册进度观察者
        self._register_progress_observer()

    def on_unmount(self) -> None:
        """组件卸载时清理"""
        # 注销进度观察者
        self._unregister_progress_observer()

    def _setup_recent_table(self) -> None:
        """设置最近任务表格"""
        table = self.query_one("#recent-table", DataTable)
        table.add_column("任务ID", width=20)
        table.add_column("文件名", width=30)
        table.add_column("状态", width=10)
        table.clear()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件处理"""
        button_id = event.button.id

        # 注意：这里使用App的action_switch_page方法
        # 该方法将在后续的任务中实现
        if button_id == "btn-tasks":
            if hasattr(self._app_ref, "action_switch_page"):
                self._app_ref.action_switch_page("tasks")
            else:
                self._app_ref.switch_screen("tasks")

        elif button_id == "btn-download":
            if hasattr(self._app_ref, "action_switch_page"):
                self._app_ref.action_switch_page("download")
            else:
                self._app_ref.switch_screen("download")

        elif button_id == "btn-accounts":
            if hasattr(self._app_ref, "action_switch_page"):
                self._app_ref.action_switch_page("accounts")
            else:
                self._app_ref.switch_screen("accounts")

        elif button_id == "btn-config":
            if hasattr(self._app_ref, "action_switch_page"):
                self._app_ref.action_switch_page("config")
            else:
                self._app_ref.switch_screen("config")

    def refresh_data(self) -> None:
        """刷新统计数据和最近任务"""
        # 获取统计摘要
        summary = self._app_ref.progress_manager.get_summary()

        # 更新统计卡片
        self._update_stat_card("stat-total", str(summary["total_tasks"]))
        self._update_stat_card("stat-downloading", str(summary["downloading"]))
        self._update_stat_card("stat-completed", str(summary["completed"]))
        self._update_stat_card("stat-failed", str(summary["failed"]))

        # 更新最近任务列表
        self._update_recent_tasks()

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
