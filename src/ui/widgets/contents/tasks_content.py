"""
ECMWF Downloader TUI 任务列表内容组件

显示所有下载任务，支持状态筛选和任务操作。
这是从TasksScreen迁移而来的Widget版本。
支持方向键操作：表格用方向键移动，Enter键选中行/触发按钮。
"""

from typing import TYPE_CHECKING, Iterable

from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.events import Key, Resize
from textual.widget import Widget
from textual.widgets import Button, Label

from src.core.progress import TaskStatus
from src.ui.widgets.task_table import TaskTable

if TYPE_CHECKING:
    from src.core.progress import TaskInfo


class TasksContent(Widget):
    """任务列表内容组件

    显示：
    - 所有任务的表格列表
    - 状态筛选按钮（全部/待下载/下载中/已完成/失败）
    - 操作按钮（重试、取消、删除）
    """

    DEFAULT_CSS = """
    TasksContent {
        width: 1fr;
        height: 1fr;
    }

    #tasks-container {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
    }

    /* 标题样式 */
    #tasks-title {
        text-align: left;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    /* ═══════════════════════════════════════════════════════════════
       筛选按钮区域 - 五等分布局
       ═══════════════════════════════════════════════════════════════ */
    #filter-container {
        width: 1fr;
        height: auto;
        margin: 1 0;
    }

    #filter-container Button {
        width: 1fr;
        margin: 0 0 0 0;
    }

    #filter-container Button.-middle,
    #filter-container Button.-last {
        margin-left: 1;
    }

    #filter-container Button.-active {
        border: solid $accent;
        text-style: bold;
        color: $accent;
    }

    /* ═══════════════════════════════════════════════════════════════
       任务表格 - 占满剩余空间
       ═══════════════════════════════════════════════════════════════ */
    #tasks-container #tasks-table {
        width: 1fr;
        height: 1fr;
        border: solid $panel;
        margin: 1 0 3 0;
    }

    /* ═══════════════════════════════════════════════════════════════
       操作按钮区域 - 三等分布局
       ═══════════════════════════════════════════════════════════════ */
    #tasks-container #actions-container {
        width: 1fr;
        height: auto;
        margin: 1 0;
    }

    #tasks-container #actions-container Button {
        width: 1fr;
        margin: 0 0 0 0;
    }

    #tasks-container #actions-container Button.-middle,
    #tasks-container #actions-container Button.-last {
        margin-left: 1;
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
        with Vertical(id="tasks-container", classes="content-container"):
            # 标题
            yield Label("任务列表", id="tasks-title")

            # 状态筛选区域（五等分）
            with Horizontal(id="filter-container"):
                yield Button("全部", id="filter-all", variant="default")
                yield Button("待下载", id="filter-pending", variant="default", classes="-middle")
                yield Button("下载中", id="filter-downloading", variant="default", classes="-middle")
                yield Button("已完成", id="filter-completed", variant="default", classes="-middle")
                yield Button("失败", id="filter-failed", variant="default", classes="-last")

            # 任务表格
            yield TaskTable(id="tasks-table")

            # 操作按钮区域（三个按钮）
            with Horizontal(id="actions-container"):
                yield Button("重试", id="btn-retry", variant="default")
                yield Button("取消", id="btn-cancel", variant="default", classes="-middle")
                yield Button("删除", id="btn-delete", variant="default", classes="-last")

    def on_mount(self) -> None:
        """组件挂载后初始化（延后到首帧渲染完成，确保可获得正确尺寸）"""
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
            # 设置任务表格
            self._setup_table()
            # 等布局完成后再按窗口宽度调整列宽
            self.call_after_refresh(self._resize_table_columns)
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
        table = self.query_one("#tasks-table", TaskTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.clear(columns=True)
        # 显式给出 width，避免 DataTable 进入 auto_width 模式（否则后续动态宽度会被忽略）
        # TaskTable有5列：任务ID、文件名、状态、进度、创建时间
        # 注意：TaskTable.update_row 当前使用列名（如“状态”“进度”）作为 column_key。
        # 这里不要传 key=，避免列 key 与列名不一致导致 update_cell 失败。
        table.add_column("任务ID", width=20)
        table.add_column("文件名", width=30)
        table.add_column("状态", width=8)
        table.add_column("进度", width=8)
        table.add_column("创建时间", width=19)

    def _load_tasks(self, status_filter: str = "all") -> None:
        """加载任务数据到表格

        Args:
            status_filter: 状态筛选（all/pending/downloading/completed/failed）
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

    def _resize_table_columns(self) -> None:
        """按当前表格宽度动态调整列宽，尽量占满可用空间"""
        try:
            table = self.query_one("#tasks-table", TaskTable)
        except NoMatches:
            return

        columns = list(table.ordered_columns)
        if len(columns) < 5:
            return

        table_width = table.size.width
        if table_width <= 0:
            return

        # 估算可用宽度：减去左右边框与列分隔符（近似值，避免溢出）
        interior_width = max(0, table_width - 2 - (len(columns) - 1))

        # 更偏向“前两列更宽、状态更窄”的分配：
        # - 状态列尽量窄（6~8）
        # - 进度列较窄（7~9）
        # - 创建时间尽量保持可读（17~19）
        # - 任务ID适中偏宽（20~44）
        # - 文件名吃掉剩余
        status_width = max(6, min(8, int(interior_width * 0.06)))
        progress_width = max(7, min(9, int(interior_width * 0.07)))
        time_width = max(17, min(19, int(interior_width * 0.16)))
        task_id_width = max(20, min(44, int(interior_width * 0.30)))
        filename_width = max(
            22,
            interior_width
            - task_id_width
            - status_width
            - progress_width
            - time_width,
        )

        # 如果空间太窄，优先压缩任务ID列给文件名列
        min_filename = 22
        if filename_width < min_filename:
            shortage = min_filename - filename_width
            task_id_width = max(18, task_id_width - shortage)
            filename_width = max(min_filename, interior_width - task_id_width - status_width - progress_width - time_width)

        # 设置列宽（按添加顺序：任务ID、文件名、状态、进度、创建时间）
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

        table.refresh(layout=True)

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
        self._load_tasks(status_filter=filter_type)

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
            self._load_tasks(status_filter=self._current_filter)
        else:
            self.notify(f"删除任务 {task_id} 失败", severity="error")

    def refresh_data(self) -> None:
        """刷新任务列表数据"""
        self._load_tasks(status_filter=self._current_filter)

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
