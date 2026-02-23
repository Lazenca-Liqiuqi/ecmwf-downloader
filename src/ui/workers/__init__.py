"""
TUI 后台任务模块

包含所有下载执行函数的定义。
注意：实际的 @work 装饰方法在 ECMWFDownloaderApp 中，
因为 Textual 要求 @work 装饰的方法必须属于 DOMNode 子类。
"""

from src.ui.workers.download_worker import (
    execute_download_task,
    execute_download_with_account,
)

__all__ = [
    "execute_download_task",
    "execute_download_with_account",
]
