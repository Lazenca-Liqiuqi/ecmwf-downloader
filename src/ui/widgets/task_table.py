"""
ECMWF Downloader TUI 任务表格组件

提供专业的任务列表显示，支持实时更新、状态颜色标记和多选操作。
"""

from typing import List, Optional, Set

from textual.message import Message
from textual.widgets import DataTable
from textual.widgets._data_table import RowDoesNotExist
from textual import events
from textual.coordinate import Coordinate

from src.core.progress import TaskInfo, TaskStatus


class TaskTable(DataTable):
    """任务列表表格组件

    功能：
    - 显示任务列表（选中标志、任务ID、文件名、状态、进度、创建时间）
    - 状态颜色标记
    - 实时更新单行数据
    - 斑马纹显示
    - 点击行切换选中状态
    - 多选支持
    """

    # 选中/未选中标志
    SELECTED_FLAG = "✓"
    UNSELECTED_FLAG = "○"

    class RowToggled(Message):
        """行选中状态切换事件"""

        def __init__(self, task_id: str, selected: bool) -> None:
            super().__init__()
            self.task_id = task_id
            self.selected = selected

    def __init__(self, **kwargs):
        """初始化任务表格"""
        super().__init__(**kwargs)
        self._task_row_map: dict[str, int] = {}  # 任务ID -> 行号映射
        self._selected_task_ids: Set[str] = set()  # 选中的任务ID集合

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        # 设置表格样式
        self.cursor_type = "row"
        self.zebra_stripes = True

        # 添加列（第一列为选中标志）
        self.add_column("选", width=4)
        self.add_column("任务ID", width=20)
        self.add_column("文件名", width=30)
        self.add_column("状态", width=10)
        self.add_column("进度", width=8)
        self.add_column("创建时间", width=20)

    def _row_key_to_task_id(self, row_key) -> str:
        """将 DataTable 的 RowKey 统一转换为 task_id 字符串。"""
        try:
            # Textual 7.x 的 RowKey / StringKey 具有 .value
            value = getattr(row_key, "value")
            return str(value)
        except Exception:
            return str(row_key) if row_key is not None else ""

    def on_mouse_down(self, event: events.MouseDown) -> None:
        """在鼠标按下时切换选中状态（只响应鼠标点击）。"""
        meta = event.style.meta

        if "row" not in meta or "column" not in meta:
            return
        if meta.get("out_of_bounds", False):
            return

        row_index = meta["row"]
        column_index = meta["column"]

        # 忽略表头和行标签点击
        if self.show_header and row_index == -1:
            return
        if self.show_row_labels and column_index == -1:
            return
        if row_index < 0:
            return

        try:
            row_key = self.ordered_rows[row_index].key
        except Exception:
            return

        task_id = self._row_key_to_task_id(row_key)
        if not task_id:
            return

        # 直接在这里切换选中状态并更新单元格
        if task_id in self._selected_task_ids:
            # 取消选中
            self._selected_task_ids.discard(task_id)
            flag = self.UNSELECTED_FLAG
        else:
            # 选中
            self._selected_task_ids.add(task_id)
            flag = self.SELECTED_FLAG

        # 直接用视觉行索引更新第一列
        try:
            coord = Coordinate(row_index, 0)
            self.update_cell_at(coord, flag)
        except Exception as e:
            self.log.warning(f"[TaskTable] 更新单元格失败: {e}")

        event.stop()


    def _toggle_selection(self, task_id: str) -> None:
        """切换任务的选中状态（内部方法）

        Args:
            task_id: 任务ID
        """
        if task_id in self._selected_task_ids:
            self._selected_task_ids.discard(task_id)
            self._update_selection_flag(task_id, selected=False)
            self.log.info(f"[TaskTable] 取消选中: {task_id}")
            self.post_message(self.RowToggled(task_id, False))
        else:
            self._selected_task_ids.add(task_id)
            self._update_selection_flag(task_id, selected=True)
            self.log.info(f"[TaskTable] 选中: {task_id}")
            self.post_message(self.RowToggled(task_id, True))

    def toggle_selection(self, task_id: str) -> None:
        """切换任务的选中状态（公开方法）

        Args:
            task_id: 任务ID
        """
        self._toggle_selection(task_id)

    def _update_selection_flag(self, task_id: str, selected: bool) -> None:
        """更新行的选中标志

        Args:
            task_id: 任务ID
            selected: 是否选中
        """
        flag = self.SELECTED_FLAG if selected else self.UNSELECTED_FLAG

        if task_id not in self._task_row_map:
            self.log.warning(f"[TaskTable] task_id 不在行映射中: {task_id}")
            return

        try:
            row_index = self._task_row_map[task_id]
            # 使用 Coordinate 对象更新单元格
            coord = Coordinate(row_index, 0)
            self.update_cell_at(coord, flag)
            self.log.info(f"[TaskTable] 已更新单元格: row={row_index} col=0 value={flag}")
        except Exception as e:
            self.log.warning(f"[TaskTable] 更新选中标志失败: {task_id} - {e}")

    def load_tasks(self, tasks: List[TaskInfo]) -> None:
        """加载任务列表到表格

        Args:
            tasks: 任务信息列表
        """
        # 清空现有数据
        self.clear()
        self._task_row_map.clear()
        # 清空选中状态
        self._selected_task_ids.clear()

        # 填充表格
        for task in tasks:
            self._add_task_row(task)

    def _add_task_row(self, task: TaskInfo) -> None:
        """添加单行任务数据

        Args:
            task: 任务信息
        """
        # 格式化数据
        select_flag = self.UNSELECTED_FLAG
        status_text = self._format_status_text(task.status)
        progress_text = f"{task.progress:.1f}%"
        created_time = self._format_datetime(task.created_at)

        # 添加行（使用任务ID作为行键，便于后续更新）
        row_key = self.add_row(
            select_flag,
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
        # 保持选中状态
        is_selected = task.task_id in self._selected_task_ids
        select_flag = self.SELECTED_FLAG if is_selected else self.UNSELECTED_FLAG
        status_text = self._format_status_text(task.status)
        progress_text = f"{task.progress:.1f}%"

        # 获取列键（按顺序：选、任务ID、文件名、状态、进度、创建时间）
        columns = list(self.ordered_columns)
        if len(columns) >= 6:
            self.update_cell(row_key=task.task_id, column_key=columns[0].key, value=select_flag)
            self.update_cell(row_key=task.task_id, column_key=columns[3].key, value=status_text)
            self.update_cell(row_key=task.task_id, column_key=columns[4].key, value=progress_text)

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
            # 从选中集合中移除
            self._selected_task_ids.discard(task_id)
            return True
        return False

    def get_selected_task_id(self) -> Optional[str]:
        """获取当前光标所在行的任务ID（单个）

        Returns:
            Optional[str]: 任务ID，如果没有选中则返回None
        """
        if self.cursor_row is None:
            return None

        # 获取整行数据，取第二列（任务ID）
        try:
            row_values = self.get_row_at(self.cursor_row)
            if row_values and len(row_values) > 1:
                return str(row_values[1])
        except (IndexError, KeyError, RowDoesNotExist):
            pass
        return None

    def get_selected_task_ids(self) -> Set[str]:
        """获取所有选中行的任务ID（多选）

        Returns:
            Set[str]: 选中的任务ID集合
        """
        return self._selected_task_ids.copy()

    def select_all(self) -> None:
        """全选所有行"""
        for task_id in self._task_row_map.keys():
            self._selected_task_ids.add(task_id)
            self._update_selection_flag(task_id, selected=True)

    def deselect_all(self) -> None:
        """取消所有选择"""
        for task_id in list(self._selected_task_ids):
            self._update_selection_flag(task_id, selected=False)
        self._selected_task_ids.clear()

    def is_selected(self, task_id: str) -> bool:
        """检查任务是否被选中

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否被选中
        """
        return task_id in self._selected_task_ids

    def get_task_count(self) -> int:
        """获取表格中的任务总数

        Returns:
            int: 任务数量
        """
        return len(self._task_row_map)

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
