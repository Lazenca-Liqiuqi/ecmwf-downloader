"""
ECMWF Downloader TUI 任务表格组件

提供专业的任务列表显示，支持实时更新和状态颜色标记。
"""

from typing import List, Optional

from textual.widgets import DataTable
from textual.widgets._data_table import RowDoesNotExist

from src.core.progress import TaskInfo, TaskStatus


class TaskTable(DataTable):
    """任务列表表格组件

    功能：
    - 显示任务列表（任务ID、文件名、状态、进度、创建时间）
    - 状态颜色标记
    - 实时更新单行数据
    - 斑马纹显示
    - 行光标选择
    """

    def __init__(self, **kwargs):
        """初始化任务表格"""
        super().__init__(**kwargs)
        self._task_row_map: dict[str, int] = {}  # 任务ID -> 行号映射

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        # 设置表格样式
        self.cursor_type = "row"
        self.zebra_stripes = True

        # 添加列
        self.add_column("任务ID", width=20)
        self.add_column("文件名", width=30)
        self.add_column("状态", width=10)
        self.add_column("进度", width=8)
        self.add_column("创建时间", width=20)

    def load_tasks(self, tasks: List[TaskInfo]) -> None:
        """加载任务列表到表格

        Args:
            tasks: 任务信息列表
        """
        # 清空现有数据
        self.clear()
        self._task_row_map.clear()

        # 填充表格
        for task in tasks:
            self._add_task_row(task)

    def _add_task_row(self, task: TaskInfo) -> None:
        """添加单行任务数据

        Args:
            task: 任务信息
        """
        # 格式化数据
        status_text = self._format_status_text(task.status)
        progress_text = f"{task.progress:.1f}%"
        created_time = self._format_datetime(task.created_at)

        # 添加行（使用任务ID作为行键，便于后续更新）
        row_key = self.add_row(
            task.task_id,
            task.filename,
            status_text,
            progress_text,
            created_time,
            key=task.task_id,
        )

        # 记录行号映射
        if row_key:
            self._task_row_map[task.task_id] = self.get_row_index(row_key)

    def update_row(self, task: TaskInfo) -> None:
        """更新单行任务数据

        用于实时更新任务状态和进度。

        Args:
            task: 任务信息
        """
        if task.task_id not in self._task_row_map:
            # 如果任务不在表格中，添加新行
            self._add_task_row(task)
            return

        # 更新现有行数据
        status_text = self._format_status_text(task.status)
        progress_text = f"{task.progress:.1f}%"

        self.update_cell(
            row_key=task.task_id,
            column_key="状态",
            value=status_text,
        )
        self.update_cell(
            row_key=task.task_id,
            column_key="进度",
            value=progress_text,
        )

    def remove_task(self, task_id: str) -> bool:
        """从表格中移除任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功移除
        """
        if task_id in self._task_row_map:
            self.remove_row(task_id)
            del self._task_row_map[task_id]
            return True
        return False

    def get_selected_task_id(self) -> Optional[str]:
        """获取当前选中行的任务ID

        Returns:
            Optional[str]: 任务ID，如果没有选中则返回None
        """
        if self.cursor_row is None:
            return None

        # 获取整行数据，取第一列（任务ID）
        try:
            row_values = self.get_row_at(self.cursor_row)
            if row_values and len(row_values) > 0:
                # get_row_at 返回的是值列表，不是 Cell 对象
                return str(row_values[0])
        except (IndexError, KeyError, RowDoesNotExist):
            # 行索引无效（表格为空或行不存在）
            pass
        return None

    def _format_status_text(self, status: TaskStatus) -> str:
        """格式化状态文本

        Args:
            status: 任务状态

        Returns:
            str: 格式化后的状态文本
        """
        status_map = {
            TaskStatus.PENDING: "待下载",
            TaskStatus.QUEUED: "已入队",
            TaskStatus.DOWNLOADING: "下载中",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.FAILED: "失败",
            TaskStatus.CANCELLED: "已取消",
            TaskStatus.RETRYING: "重试中",
        }
        return status_map.get(status, "未知")

    def _format_datetime(self, dt_str: Optional[str]) -> str:
        """格式化日期时间

        Args:
            dt_str: ISO格式日期时间字符串

        Returns:
            str: 格式化后的日期时间（YYYY-MM-DD HH:MM:SS）
        """
        if not dt_str:
            return ""

        # 截取到秒级（去除毫秒和时区）
        return dt_str[:19] if len(dt_str) >= 19 else dt_str
