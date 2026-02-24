"""
ECMWF Downloader TUI 任务管理内容组件

显示所有下载任务，支持状态筛选、多选操作和批量任务操作。
这是从TasksScreen迁移而来的Widget版本。
只支持鼠标点击操作。
"""

from typing import TYPE_CHECKING, Iterable, List, Set, Tuple

from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.events import Resize
from textual.widget import Widget
from textual.widgets import Button, Label

from src.core.progress import TaskStatus
from src.ui.widgets.task_table import TaskTable

if TYPE_CHECKING:
    from src.core.progress import TaskInfo, TaskEventType


class TasksContent(Widget):
    """任务管理内容组件

    显示：
    - 所有任务的表格列表
    - 状态筛选按钮（全部/待下载/下载中/已完成/失败）
    - 操作按钮（全选、入队、重试、取消、删除）
    - 支持多选操作（Ctrl+点击 或 Shift+点击）
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
    }

    /* ═══════════════════════════════════════════════════════════════
       任务表格 - 占满剩余空间
       ═══════════════════════════════════════════════════════════════ */
    #tasks-container #tasks-table {
        width: 1fr;
        height: 1fr;
        margin: 1 0 2 0;
    }

    /* ═══════════════════════════════════════════════════════════════
       操作按钮区域 - 五等分布局
       ═══════════════════════════════════════════════════════════════ */
    #tasks-container #actions-container {
        width: 1fr;
        height: auto;
        margin: 1 0;
    }

    #tasks-container #actions-container Button {
        width: 1fr;
    }
    """

    def __init__(self, app, **kwargs):
        """初始化任务管理内容组件

        Args:
            app: 应用实例引用
            **kwargs: 传递给父类的参数
        """
        super().__init__(**kwargs)
        self._app_ref = app  # 使用_app_ref避免与Widget.app属性冲突
        self._observer_registered = False
        self._current_filter = "all"

    def compose(self) -> Iterable:
        """构建任务管理 UI"""
        # 主容器
        with Vertical(id="tasks-container", classes="content-container"):
            # 标题
            yield Label("任务管理", id="tasks-title")

            # 状态筛选区域（五等分）
            with Horizontal(id="filter-container"):
                yield Button("全部", id="filter-all", variant="default")
                yield Button("待下载", id="filter-pending", variant="default", classes="-middle")
                yield Button("下载中", id="filter-downloading", variant="default", classes="-middle")
                yield Button("已完成", id="filter-completed", variant="default", classes="-middle")
                yield Button("失败", id="filter-failed", variant="default", classes="-last")

            # 任务表格
            yield TaskTable(id="tasks-table")

            # 操作按钮区域（五等分）
            with Horizontal(id="actions-container"):
                yield Button("全选", id="btn-select-all", variant="default")
                yield Button("入队", id="btn-enqueue", variant="default", classes="-middle")
                yield Button("重试", id="btn-retry", variant="default", classes="-middle")
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
        """设置任务表格

        注意：列设置由 TaskTable.on_mount() 处理，这里只需要确保表格样式正确。
        """
        table = self.query_one("#tasks-table", TaskTable)
        # 列由 TaskTable.on_mount() 添加，不要调用 clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True

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
                "queued": TaskStatus.QUEUED,
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
        elif button_id == "btn-select-all":
            self._handle_select_all()

        elif button_id == "btn-enqueue":
            self._handle_enqueue()

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
        if len(columns) < 6:
            return

        table_width = table.size.width
        if table_width <= 0:
            return

        # 估算可用宽度：减去左右边框与列分隔符（近似值，避免溢出）
        interior_width = max(0, table_width - 2 - (len(columns) - 1))

        # 列宽分配（6列：选、任务ID、文件名、状态、进度、创建时间）
        # - 选：固定4字符
        # - 状态：尽量窄（6~8）
        # - 进度：较窄（7~9）
        # - 创建时间：保持可读（17~19）
        # - 任务ID：适中偏宽（20~40）
        # - 文件名：吃掉剩余
        select_width = 4
        status_width = max(6, min(8, int(interior_width * 0.06)))
        progress_width = max(7, min(9, int(interior_width * 0.07)))
        time_width = max(17, min(19, int(interior_width * 0.16)))
        task_id_width = max(18, min(40, int(interior_width * 0.25)))
        filename_width = max(
            20,
            interior_width
            - select_width
            - task_id_width
            - status_width
            - progress_width
            - time_width,
        )

        # 如果空间太窄，优先压缩任务ID列给文件名列
        min_filename = 20
        if filename_width < min_filename:
            shortage = min_filename - filename_width
            task_id_width = max(16, task_id_width - shortage)
            filename_width = max(min_filename, interior_width - select_width - task_id_width - status_width - progress_width - time_width)

        # 设置列宽（按添加顺序：选、任务ID、文件名、状态、进度、创建时间）
        columns[0].auto_width = False
        columns[0].width = select_width
        columns[1].auto_width = False
        columns[1].width = task_id_width
        columns[2].auto_width = False
        columns[2].width = filename_width
        columns[3].auto_width = False
        columns[3].width = status_width
        columns[4].auto_width = False
        columns[4].width = progress_width
        columns[5].auto_width = False
        columns[5].width = time_width

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

    def _handle_select_all(self) -> None:
        """处理全选/取消全选操作"""
        table = self.query_one("#tasks-table", TaskTable)

        # 检查当前是否已有选择
        selected_count = len(table.get_selected_task_ids())
        total_count = table.get_task_count()

        if selected_count > 0 and selected_count == total_count:
            # 已全选，取消全选
            table.deselect_all()
            self.notify("已取消全选", severity="information")
        else:
            # 全选
            table.select_all()
            self.notify(f"已选中 {total_count} 个任务", severity="information")

    def _get_selected_tasks(self) -> Tuple[Set[str], List["TaskInfo"]]:
        """获取选中的任务ID和任务信息

        Returns:
            Tuple[Set[str], List[TaskInfo]]: (任务ID集合, 任务信息列表)
        """
        table = self.query_one("#tasks-table", TaskTable)
        task_ids = table.get_selected_task_ids()

        if not task_ids:
            return set(), []

        tasks = []
        for task_id in task_ids:
            task = self._app_ref.progress_manager.get_task(task_id)
            if task:
                tasks.append(task)

        return task_ids, tasks

    def _handle_enqueue(self) -> None:
        """处理批量入队操作

        将任务入队到等待调度状态，由队列调度器负责分配账号和启动下载。
        只允许 PENDING 状态的任务入队。
        """
        task_ids, tasks = self._get_selected_tasks()

        if not task_ids:
            self.notify("请先选择任务", severity="warning")
            return

        # 筛选出可以入队的任务（仅 PENDING 状态）
        pending_tasks = [t for t in tasks if t.status == TaskStatus.PENDING]

        if not pending_tasks:
            self.notify("没有可以入队的任务（仅支持待下载状态）", severity="warning")
            return

        # 执行批量入队
        success_count = 0
        fail_count = 0

        for task in pending_tasks:
            try:
                self._app_ref.progress_manager.enqueue(task.task_id)
                success_count += 1
            except ValueError as e:
                self.log.warning(f"[TasksContent] 入队失败: {task.task_id} - {e}")
                fail_count += 1

        # 显示结果
        if fail_count == 0:
            self.notify(f"已入队 {success_count} 个任务", severity="success")
        else:
            self.notify(f"入队完成：成功 {success_count} 个，失败 {fail_count} 个", severity="warning")

    def _handle_retry(self) -> None:
        """处理批量重试操作"""
        task_ids, tasks = self._get_selected_tasks()

        if not task_ids:
            self.notify("请先选择任务", severity="warning")
            return

        # 筛选出可以重试的任务（失败或已取消状态）
        retryable_tasks = [t for t in tasks if t.status in [TaskStatus.FAILED, TaskStatus.CANCELLED]]

        if not retryable_tasks:
            self.notify("没有可以重试的任务（仅支持失败或已取消状态）", severity="warning")
            return

        # TODO: 实现批量重试逻辑
        self.notify(f"批量重试 {len(retryable_tasks)} 个任务 - 功能待实现", severity="information")

    def _handle_cancel(self) -> None:
        """处理批量取消操作"""
        task_ids, tasks = self._get_selected_tasks()

        if not task_ids:
            self.notify("请先选择任务", severity="warning")
            return

        # TODO: 实现批量取消逻辑
        self.notify(f"批量取消 {len(task_ids)} 个任务 - 功能待实现", severity="information")

    def _handle_delete(self) -> None:
        """处理批量删除操作"""
        task_ids, tasks = self._get_selected_tasks()

        if not task_ids:
            self.notify("请先选择任务", severity="warning")
            return

        # 执行批量删除
        success_count = 0
        fail_count = 0

        for task_id in task_ids:
            success = self._app_ref.progress_manager.delete_task(task_id)
            if success:
                success_count += 1
            else:
                fail_count += 1

        # 显示结果
        if fail_count == 0:
            self.notify(f"已删除 {success_count} 个任务", severity="success")
        else:
            self.notify(f"删除完成：成功 {success_count} 个，失败 {fail_count} 个", severity="warning")

        # 重新加载任务列表（如果删除了任务）
        if success_count > 0:
            self._load_tasks(status_filter=self._current_filter)

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
        self, task_id: str, task_info: "TaskInfo", event_type: "TaskEventType"
    ) -> None:
        """进度管理器观察者回调（可能在后台线程调用）

        Args:
            task_id: 任务ID
            task_info: 任务信息快照
            event_type: 事件类型（CREATED/UPDATED/DELETED）
        """
        # 使用 call_from_thread 确保在主线程中更新 UI
        self._app_ref.call_from_thread(
            self._on_progress_update,
            task_id,
            task_info,
            event_type,
        )

    def _on_progress_update(
        self, task_id: str, task_info: "TaskInfo", event_type: "TaskEventType"
    ) -> None:
        """进度更新时刷新任务列表

        根据事件类型处理不同的更新操作。

        Args:
            task_id: 任务ID
            task_info: 任务信息快照
            event_type: 事件类型（CREATED/UPDATED/DELETED）
        """
        from src.core.progress import TaskEventType

        table = self.query_one("#tasks-table", TaskTable)

        if event_type == TaskEventType.DELETED:
            # 任务已删除，从表格中移除
            table.remove_task(task_id)
        else:
            # CREATED 或 UPDATED：使用增量更新方法
            table.update_row(task_info)
