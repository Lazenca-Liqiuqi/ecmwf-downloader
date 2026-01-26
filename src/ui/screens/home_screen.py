"""
ECMWF Downloader TUI 首页屏幕模块

显示应用概览、统计信息和快捷操作入口。
"""

from typing import Iterable

from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Header, Footer, Label

from src.ui.screens.base_screen import BaseScreen


class HomeScreen(BaseScreen):
    """首页屏幕

    显示：
    - 应用标题和欢迎信息
    - 统计卡片（总任务、下载中、已完成、失败）
    - 快捷操作按钮
    - 最近任务列表（最多5条）
    """

    # 屏幕名称（用于导航）
    NAME = "home"

    def compose(self) -> Iterable:
        """构建首页 UI"""
        yield Header()
        yield Footer()

        # 主容器
        with Container(id="home-container"):
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
                yield Button("任务列表", id="btn-tasks", variant="primary")
                yield Button("下载管理", id="btn-download", variant="success")
                yield Button("账号管理", id="btn-accounts", variant="warning")
                yield Button("配置管理", id="btn-config", variant="default")

            # 最近任务区域
            yield Label("最近任务", id="recent-title")
            yield DataTable(id="recent-table")

    def on_screen_mount(self) -> None:
        """屏幕挂载时初始化"""
        # 设置最近任务表格
        self._setup_recent_table()
        # 刷新统计数据
        self.refresh_data()

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

        if button_id == "btn-tasks":
            # 导航到任务列表屏幕（待实现）
            self.notify("任务列表屏幕开发中...", severity="information")
            # self.app.push_screen("tasks")

        elif button_id == "btn-download":
            # 导航到下载管理屏幕（待实现）
            self.notify("下载管理屏幕开发中...", severity="information")
            # self.app.push_screen("download")

        elif button_id == "btn-accounts":
            # 导航到账号管理屏幕（待实现）
            self.notify("账号管理屏幕开发中...", severity="information")
            # self.app.push_screen("accounts")

        elif button_id == "btn-config":
            # 导航到配置管理屏幕（待实现）
            self.notify("配置管理屏幕开发中...", severity="information")
            # self.app.push_screen("config")

    def refresh_data(self) -> None:
        """刷新统计数据和最近任务"""
        # 获取统计摘要
        summary = self.app.progress_manager.get_summary()

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
        all_tasks = self.app.progress_manager.get_all_tasks()

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

    def _on_progress_update(self, task_id: str, task_info) -> None:
        """进度更新时刷新数据"""
        # 刷新统计数据和最近任务
        self.refresh_data()
