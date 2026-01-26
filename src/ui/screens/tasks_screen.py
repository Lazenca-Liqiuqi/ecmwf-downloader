"""
ECMWF Downloader TUI 任务列表屏幕模块

显示所有下载任务，支持筛选、搜索和操作。
"""

from typing import Iterable

from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Header, Footer, Input, Label

from src.core.progress import TaskStatus
from src.ui.widgets.task_table import TaskTable
from src.ui.screens.base_screen import BaseScreen
from src.ui.styles.theme import get_tasks_styles


class TasksScreen(BaseScreen):
    """任务列表屏幕

    显示：
    - 所有任务的表格列表
    - 状态筛选按钮
    - 搜索框
    - 操作按钮（重试、取消、删除）
    """

    # 屏幕名称（用于导航）
    NAME = "tasks"

    # 任务列表专用样式
    CSS = get_tasks_styles()

    def compose(self) -> Iterable:
        """构建任务列表 UI"""
        yield Header()
        yield Footer()

        # 主容器
        with Container(id="tasks-container"):
            # 标题和搜索区域
            with Horizontal(id="tasks-header"):
                yield Label("任务列表", id="tasks-title")
                yield Input(placeholder="搜索任务ID或文件名...", id="search-input")

            # 状态筛选区域
            with Horizontal(id="filter-container"):
                yield Button("全部", id="filter-all", variant="default")
                yield Button("待下载", id="filter-pending", variant="default")
                yield Button("下载中", id="filter-downloading", variant="default")
                yield Button("已完成", id="filter-completed", variant="default")
                yield Button("失败", id="filter-failed", variant="default")

            # 任务表格
            yield DataTable(id="tasks-table")

            # 操作按钮区域
            with Horizontal(id="actions-container"):
                yield Button("重试", id="btn-retry", variant="default")
                yield Button("取消", id="btn-cancel", variant="default")
                yield Button("删除", id="btn-delete", variant="default")
                yield Button("刷新", id="btn-refresh", variant="default")

    def on_screen_mount(self) -> None:
        """屏幕挂载时初始化"""
        # 设置任务表格
        self._setup_table()
        # 加载任务数据
        self._load_tasks()

        # 当前筛选状态
        self._current_filter = "all"

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
            tasks = self.app.progress_manager.get_all_tasks()
        else:
            status_map = {
                "pending": TaskStatus.PENDING,
                "downloading": TaskStatus.DOWNLOADING,
                "completed": TaskStatus.COMPLETED,
                "failed": TaskStatus.FAILED,
            }
            tasks = self.app.progress_manager.get_tasks_by_status(
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
        tasks = self.app.progress_manager.get_all_tasks()
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
        success = self.app.progress_manager.delete_task(task_id)
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

    def _on_progress_update(self, task_id: str, task_info) -> None:
        """进度更新时刷新任务列表

        使用增量更新提高性能，只更新变化的行。

        Args:
            task_id: 任务ID
            task_info: 任务信息
        """
        table = self.query_one("#tasks-table", TaskTable)
        # 使用 TaskTable 的增量更新方法
        table.update_row(task_info)
