"""
ECMWF Downloader TUI 任务列表内容组件

显示所有下载任务，支持筛选、搜索和操作。
这是从TasksScreen迁移而来的Widget版本。
支持方向键操作：表格用方向键移动，Enter键选中行/触发按钮。
"""

from typing import TYPE_CHECKING, Iterable

from textual.containers import Container, Horizontal, Vertical
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Button, Input, Label

from src.core.progress import TaskStatus
from src.ui.widgets.task_table import TaskTable

if TYPE_CHECKING:
    from src.core.progress import TaskInfo


class TasksContent(Widget):
    """任务列表内容组件

    显示：
    - 所有任务的表格列表
    - 状态筛选按钮
    - 搜索框
    - 操作按钮（重试、取消、删除）
    """

    DEFAULT_CSS = """
    #tasks-header {
        height: 3;
        margin-bottom: 1;
    }

    #tasks-title {
        text-align: left;
        text-style: bold;
        color: $accent;
        padding: 0 1;
        min-width: 20;
    }

    #search-input {
        width: 1fr;
        margin: 0 1 0 0;
        border: wide;
    }

    #filter-container {
        height: 3;
    }

    #tasks-table {
        height: 18;
        border: solid $panel;
    }

    #filter-container Button.-active {
        border: solid $accent;
        text-style: bold;
        color: $accent;
    }

    #search-input:focus {
        border: solid $accent;
    }
    """

    def __init__(self, app, **kwargs):
        """初始化任务列表内容组件

        Args:
            app: 应用实例引用
            **kwargs: 传递给父类的参数
        """
        super().__init__(**kwargs)
        self._app_ref = app  # 使用_app_ref避免与Widget.app属性冲突
        self._observer_registered = False
        self._current_filter = "all"

    def compose(self) -> Iterable:
        """构建任务列表 UI"""
        # 主容器
        with Container(id="tasks-container", classes="content-container"):
            # 标题和搜索区域
            with Horizontal(id="tasks-header"):
                yield Label("任务列表", id="tasks-title")
                yield Input(placeholder="搜索任务ID或文件名...", id="search-input")

            # 状态筛选区域
            with Horizontal(id="filter-container", classes="section-compact"):
                yield Button("全部", id="filter-all", variant="default")
                yield Button("待下载", id="filter-pending", variant="default")
                yield Button("下载中", id="filter-downloading", variant="default")
                yield Button("已完成", id="filter-completed", variant="default")
                yield Button("失败", id="filter-failed", variant="default")

            # 任务表格
            with Container(id="tasks-table-wrapper", classes="table-section"):
                yield TaskTable(id="tasks-table")

            # 操作按钮区域
            with Horizontal(id="actions-container", classes="button-section"):
                yield Button("重试", id="btn-retry", variant="default")
                yield Button("取消", id="btn-cancel", variant="default")
                yield Button("删除", id="btn-delete", variant="default")
                yield Button("刷新", id="btn-refresh", variant="default")

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        # 等首帧渲染完成后再初始化，确保DOM可查询（Textual 7+ 不支持 interval=0 的 timer）
        self.call_after_refresh(self._initialize_after_mount)

    def _initialize_after_mount(self) -> None:
        """DOM完全挂载后初始化"""
        # 检查Widget是否仍然挂载
        if not self.is_mounted:
            return

        try:
            # 设置任务表格
            self._setup_table()
            # 加载任务数据
            self._load_tasks()
            # 注册进度观察者
            self._register_progress_observer()
        except Exception as e:
            self.log.warning(f"[TasksContent] 初始化失败: {e}")

    def on_unmount(self) -> None:
        """组件卸载时清理"""
        # 注销进度观察者
        self._unregister_progress_observer()

    def _setup_table(self) -> None:
        """设置任务表格列"""
        # TaskTable 组件会在 on_mount 时自动初始化列
        pass

    def _load_tasks(self, status_filter: str = "all", search_text: str = "") -> None:
        """加载任务数据到表格

        Args:
            status_filter: 状态筛选（all/pending/downloading/completed/failed）
            search_text: 搜索文本
        """
        table = self.query_one("#tasks-table", TaskTable)

        # 获取任务列表
        if status_filter == "all":
            tasks = self._app_ref.progress_manager.get_all_tasks()
        else:
            status_map = {
                "pending": TaskStatus.PENDING,
                "downloading": TaskStatus.DOWNLOADING,
                "completed": TaskStatus.COMPLETED,
                "failed": TaskStatus.FAILED,
            }
            tasks = self._app_ref.progress_manager.get_tasks_by_status(
                status_map.get(status_filter, TaskStatus.PENDING)
            )

        # 应用搜索过滤
        if search_text:
            search_lower = search_text.lower()
            tasks = [
                t
                for t in tasks
                if search_lower in t.task_id.lower()
                or search_lower in t.filename.lower()
            ]

        # 按创建时间降序排序
        tasks = sorted(tasks, key=lambda t: t.created_at, reverse=True)

        # 使用 TaskTable 的 load_tasks 方法加载
        table.load_tasks(tasks)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件处理"""
        button_id = event.button.id

        # 筛选按钮
        if button_id.startswith("filter-"):
            self._handle_filter(button_id.replace("filter-", ""))

        # 操作按钮
        elif button_id == "btn-retry":
            self._handle_retry()

        elif button_id == "btn-cancel":
            self._handle_cancel()

        elif button_id == "btn-delete":
            self._handle_delete()

        elif button_id == "btn-refresh":
            self._handle_refresh()

    def on_input_changed(self, event: Input.Changed) -> None:
        """搜索框变化事件"""
        if event.input.id == "search-input":
            search_text = event.value
            self._load_tasks(
                status_filter=self._current_filter, search_text=search_text
            )

    def _handle_filter(self, filter_type: str) -> None:
        """处理状态筛选

        Args:
            filter_type: 筛选类型（all/pending/downloading/completed/failed）
        """
        self._current_filter = filter_type

        # 更新按钮样式
        for button_id in [
            "filter-all",
            "filter-pending",
            "filter-downloading",
            "filter-completed",
            "filter-failed",
        ]:
            button = self.query_one(f"#{button_id}", Button)
            if button_id == f"filter-{filter_type}":
                button.variant = "primary"
            else:
                button.variant = "default"

        # 重新加载任务
        search_input = self.query_one("#search-input", Input)
        self._load_tasks(
            status_filter=filter_type, search_text=search_input.value
        )

    def _handle_retry(self) -> None:
        """处理重试操作"""
        table = self.query_one("#tasks-table", TaskTable)
        task_id = table.get_selected_task_id()

        if task_id is None:
            self.notify("请先选择一个任务", severity="warning")
            return

        # 检查任务状态
        tasks = self._app_ref.progress_manager.get_all_tasks()
        task = next((t for t in tasks if t.task_id == task_id), None)

        if task and task.status in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
            # TODO: 实现重试逻辑（需要下载Worker）
            self.notify(f"重试任务 {task_id} 功能待实现", severity="information")
        else:
            self.notify("只能重试失败或已取消的任务", severity="warning")

    def _handle_cancel(self) -> None:
        """处理取消操作"""
        table = self.query_one("#tasks-table", TaskTable)
        task_id = table.get_selected_task_id()

        if task_id is None:
            self.notify("请先选择一个任务", severity="warning")
            return

        # TODO: 实现取消逻辑
        self.notify(f"取消任务 {task_id} 功能待实现", severity="information")

    def _handle_delete(self) -> None:
        """处理删除操作"""
        table = self.query_one("#tasks-table", TaskTable)
        task_id = table.get_selected_task_id()

        if task_id is None:
            self.notify("请先选择一个任务", severity="warning")
            return

        # 删除任务
        success = self._app_ref.progress_manager.delete_task(task_id)
        if success:
            self.notify(f"任务 {task_id} 已删除", severity="success")
            # 重新加载任务列表
            self._load_tasks(
                status_filter=self._current_filter,
                search_text=self.query_one("#search-input", Input).value,
            )
        else:
            self.notify(f"删除任务 {task_id} 失败", severity="error")

    def _handle_refresh(self) -> None:
        """处理刷新操作"""
        search_input = self.query_one("#search-input", Input)
        self._load_tasks(
            status_filter=self._current_filter, search_text=search_input.value
        )
        self.notify("任务列表已刷新", severity="information")

    def refresh_data(self) -> None:
        """刷新任务列表数据"""
        search_input = self.query_one("#search-input", Input)
        self._load_tasks(
            status_filter=self._current_filter, search_text=search_input.value
        )

    def _register_progress_observer(self) -> None:
        """注册进度管理器观察者"""
        if not self._observer_registered:
            self._app_ref.progress_manager.register_observer(
                self._progress_observer_callback
            )
            self._observer_registered = True
            self.log.info("[TasksContent] 进度观察者已注册")

    def _unregister_progress_observer(self) -> None:
        """注销进度管理器观察者"""
        if self._observer_registered:
            self._app_ref.progress_manager.unregister_observer(
                self._progress_observer_callback
            )
            self._observer_registered = False
            self.log.info("[TasksContent] 进度观察者已注销")

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
        """进度更新时刷新任务列表

        使用增量更新提高性能，只更新变化的行。

        Args:
            task_id: 任务ID
            task_info: 任务信息
        """
        table = self.query_one("#tasks-table", TaskTable)
        # 使用 TaskTable 的增量更新方法
        table.update_row(task_info)

    def on_key(self, event: Key) -> None:
        """处理键盘事件

        Enter键：如果焦点在按钮上，触发按钮操作；如果在表格上，选中行
        方向键：由各个控件自行处理（表格、输入框、按钮等）
        Tab键：返回侧边栏（由ContentArea处理）

        Args:
            event: 键盘事件
        """
        # Enter键处理
        if event.key == "enter":
            # 检查焦点所在控件
            focused = self.app.focused
            if focused and isinstance(focused, Button):
                # 焦点在按钮上，触发按钮
                focused.action_press()
                event.stop()
            elif focused:
                # 焦点在其他控件上（如表格、输入框），由控件自行处理
                pass

        # Tab键交给ContentArea处理（返回侧边栏）
        # 方向键由各个控件自行处理
