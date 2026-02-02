"""
ECMWF Downloader TUI 账号表格组件

提供专业的账号列表显示，支持状态颜色标记和实时更新。
"""

from typing import List

from textual.widgets import DataTable
from textual.widgets._data_table import RowDoesNotExist

from src.core.config import AccountInfo, AccountStatus


class AccountTable(DataTable):
    """账号列表表格组件

    功能：
    - 显示账号列表（ID、UID、状态、使用次数、失败次数、最后使用时间）
    - 状态颜色标记
    - 实时更新单行数据
    - 斑马纹显示
    - 行光标选择
    """

    def __init__(self, **kwargs):
        """初始化账号表格"""
        super().__init__(**kwargs)
        self._account_row_map: dict[str, int] = {}  # 账号ID -> 行号映射

    def on_mount(self) -> None:
        """组件挂载时初始化"""
        # 设置表格样式
        self.cursor_type = "row"
        self.zebra_stripes = True

        # 添加列
        self.add_column("账号ID", width=15)
        self.add_column("UID", width=25)
        self.add_column("状态", width=10)
        self.add_column("使用次数", width=10)
        self.add_column("失败次数", width=10)
        self.add_column("最后使用", width=20)

    def load_accounts(self, accounts: List[AccountInfo]) -> None:
        """加载账号列表到表格

        Args:
            accounts: 账号信息列表
        """
        # 清空现有数据
        self.clear()
        self._account_row_map.clear()

        # 按使用次数和ID排序
        accounts = sorted(accounts, key=lambda a: (-a.used_count, a.id))

        # 填充表格
        for account in accounts:
            self._add_account_row(account)

    def _add_account_row(self, account: AccountInfo) -> None:
        """添加单行账号数据

        Args:
            account: 账号信息
        """
        # 格式化数据
        status_text = self._format_status_text(account.status)
        last_used = self._format_datetime(account.last_used)

        # 添加行（使用账号ID作为行键，便于后续更新）
        row_key = self.add_row(
            account.id,
            account.uid,
            status_text,
            str(account.used_count),
            str(account.fail_count),
            last_used,
            key=account.id,
        )

        # 记录行号映射
        if row_key:
            self._account_row_map[account.id] = self.get_row_index(row_key)

    def update_row(self, account: AccountInfo) -> None:
        """更新单行账号数据

        用于实时更新账号状态和使用统计。

        Args:
            account: 账号信息
        """
        if account.id not in self._account_row_map:
            # 如果账号不在表格中，添加新行
            self._add_account_row(account)
            return

        # 更新现有行数据
        status_text = self._format_status_text(account.status)
        last_used = self._format_datetime(account.last_used)

        self.update_cell(
            row_key=account.id,
            column_key="状态",
            value=status_text,
        )
        self.update_cell(
            row_key=account.id,
            column_key="使用次数",
            value=str(account.used_count),
        )
        self.update_cell(
            row_key=account.id,
            column_key="失败次数",
            value=str(account.fail_count),
        )
        self.update_cell(
            row_key=account.id,
            column_key="最后使用",
            value=last_used,
        )

    def remove_account(self, account_id: str) -> bool:
        """从表格中移除账号

        Args:
            account_id: 账号ID

        Returns:
            bool: 是否成功移除
        """
        if account_id in self._account_row_map:
            self.remove_row(account_id)
            del self._account_row_map[account_id]
            return True
        return False

    def get_selected_account_id(self) -> str | None:
        """获取当前选中行的账号ID

        Returns:
            Optional[str]: 账号ID，如果没有选中则返回None
        """
        if self.cursor_row is None:
            return None

        # 获取整行数据，取第一列（账号ID）
        try:
            row_values = self.get_row_at(self.cursor_row)
            if row_values and len(row_values) > 0:
                # get_row_at 返回的是值列表，不是 Cell 对象
                return str(row_values[0])
        except (IndexError, KeyError, RowDoesNotExist):
            # 行索引无效（表格为空或行不存在）
            pass
        return None

    def _format_status_text(self, status: AccountStatus) -> str:
        """格式化状态文本

        Args:
            status: 账号状态

        Returns:
            str: 格式化后的状态文本
        """
        status_map = {
            AccountStatus.ACTIVE: "可用",
            AccountStatus.FAILED: "失败",
            AccountStatus.DISABLED: "禁用",
        }
        return status_map.get(status, "未知")

    def _format_datetime(self, dt_str: str | None) -> str:
        """格式化日期时间

        Args:
            dt_str: ISO格式日期时间字符串

        Returns:
            str: 格式化后的日期时间（YYYY-MM-DD HH:MM:SS）
        """
        if not dt_str:
            return "未使用"

        # 截取到秒级（去除毫秒和时区）
        return dt_str[:19] if len(dt_str) >= 19 else dt_str
