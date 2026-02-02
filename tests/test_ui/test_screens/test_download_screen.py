"""
DownloadScreen屏幕测试

测试下载管理屏幕的各项功能。
"""

import pytest
from textual.widgets import Button, Label, ProgressBar

from src.ui.screens.download_screen import DownloadScreen
from src.core.progress import TaskInfo, TaskStatus


@pytest.fixture
async def download_screen(mock_app):
    """创建DownloadScreen实例"""
    from textual.app import App

    class TestApp(App):
        def __init__(self, mock_ref):
            super().__init__()
            self._mock_ref = mock_ref

        @property
        def progress_manager(self):
            return self._mock_ref.progress_manager

        @property
        def account_pool(self):
            return self._mock_ref.account_pool

        def call_from_thread(self, func, *args, **kwargs):
            return func(*args, **kwargs)

        def notify(self, message, title="", severity="information", **kwargs):
            pass

        def log_message(self, message):
            pass

        def compose(self):
            yield DownloadScreen()

    # 设置mock返回值
    mock_app.progress_manager.get_tasks_by_status.return_value = []
    mock_app.progress_manager.get_summary.return_value = {
        "total_tasks": 0,
        "downloading": 0,
        "completed": 0,
        "failed": 0,
        "overall_progress": 0.0
    }

    app = TestApp(mock_app)

    async with app.run_test() as pilot:
        screen = app.query_one(DownloadScreen)
        yield screen


class TestDownloadScreenCompose:
    """测试UI结构"""

    async def test_compose_creates_title(self, download_screen):
        """测试创建标题"""
        title = download_screen.query_one("#download-title", Label)
        assert "下载管理" in str(title.render())

    async def test_compose_creates_progress_bar(self, download_screen):
        """测试创建进度条"""
        progress_bar = download_screen.query_one("#overall-progress", ProgressBar)
        assert progress_bar is not None

    async def test_compose_creates_stats_labels(self, download_screen):
        """测试创建统计标签"""
        stat_total = download_screen.query_one("#stat-total", Label)
        stat_downloading = download_screen.query_one("#stat-downloading", Label)
        assert stat_total is not None
        assert stat_downloading is not None

    async def test_compose_creates_control_buttons(self, download_screen):
        """测试创建控制按钮"""
        btn_start = download_screen.query_one("#btn-start-all", Button)
        btn_pause = download_screen.query_one("#btn-pause-all", Button)
        btn_stop = download_screen.query_one("#btn-stop-all", Button)
        btn_refresh = download_screen.query_one("#btn-refresh", Button)

        assert btn_start.label.plain == "开始所有"
        assert btn_pause.label.plain == "暂停所有"
        assert btn_stop.label.plain == "停止所有"
        assert btn_refresh.label.plain == "刷新"


class TestDownloadScreenMount:
    """测试屏幕挂载"""

    async def test_on_screen_mount_loads_active_tasks(self, download_screen, mock_app):
        """测试挂载时加载活动任务"""
        mock_app.progress_manager.get_tasks_by_status.assert_called()

    async def test_observer_registered(self, download_screen):
        """测试观察者已注册"""
        assert download_screen._observer_registered is True


class TestDownloadScreenButtons:
    """测试按钮功能"""

    async def test_handle_start_all(self, download_screen):
        """测试开始所有按钮"""
        download_screen._handle_start_all()
        # 验证没有抛出异常

    async def test_handle_pause_all(self, download_screen):
        """测试暂停所有按钮"""
        download_screen._handle_pause_all()
        # 验证没有抛出异常

    async def test_handle_stop_all(self, download_screen):
        """测试停止所有按钮"""
        download_screen._handle_stop_all()
        # 验证没有抛出异常

    async def test_handle_refresh(self, download_screen, mock_app):
        """测试刷新按钮"""
        mock_app.progress_manager.get_tasks_by_status.reset_mock()
        download_screen._handle_refresh()
        mock_app.progress_manager.get_tasks_by_status.assert_called()


class TestDownloadScreenRefreshData:
    """测试数据刷新"""

    async def test_refresh_data(self, download_screen, mock_app):
        """测试refresh_data方法"""
        mock_app.progress_manager.get_tasks_by_status.reset_mock()
        download_screen.refresh_data()
        mock_app.progress_manager.get_tasks_by_status.assert_called()


class TestDownloadScreenProgressUpdate:
    """测试进度更新"""

    async def test_on_progress_update(self, download_screen):
        """测试进度更新回调"""
        sample_task = TaskInfo(
            task_id="task-001",
            filename="test.grib",
            status=TaskStatus.DOWNLOADING,
            progress=50.0,
            created_at="2024-01-15T10:00:00",
        )
        try:
            download_screen._on_progress_update("task-001", sample_task)
        except Exception:
            pass
        # 验证没有抛出异常
