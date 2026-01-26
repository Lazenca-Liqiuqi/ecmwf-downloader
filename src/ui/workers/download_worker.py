"""
ECMWF Downloader TUI 下载执行Worker

提供后台下载任务的执行和管理，支持多账号轮换和失败重试。
"""

from pathlib import Path
from typing import TYPE_CHECKING

from textual import work

from src.api.cds_client import CDSClient
from src.core.exceptions import APIError, AccountPoolError
from src.core.progress import TaskStatus

if TYPE_CHECKING:
    from src.ui.app import ECMWFDownloaderApp


class DownloadWorker:
    """下载执行Worker管理类

    使用Textual的@work装饰器在后台线程中执行下载任务。
    因为cdsapi是同步阻塞库，必须使用thread=True。

    功能：
    - 自动获取可用账号
    - 执行CDS API下载
    - 更新任务进度和状态
    - 失败自动重试
    - 使用call_from_thread安全更新UI
    """

    def __init__(self, app: "ECMWFDownloaderApp"):
        """初始化下载Worker管理器

        Args:
            app: TUI应用实例
        """
        self.app = app

    @work(exclusive=False, thread=True)
    def download_task(self, task_id: str) -> None:
        """执行下载任务（在后台线程中运行）

        下载流程：
        1. 获取任务信息
        2. 检查任务状态
        3. 获取可用账号
        4. 更新状态为DOWNLOADING
        5. 创建CDS客户端
        6. 执行下载
        7. 更新状态为COMPLETED

        错误处理：
        - 账号失败：重试或获取新账号
        - 下载失败：根据重试次数决定是否重试

        Args:
            task_id: 任务ID
        """
        try:
            # 获取任务信息
            task = self.app.progress_manager.get_task(task_id)
            if task is None:
                self._safe_notify(f"任务 {task_id} 不存在", severity="error")
                return

            # 检查任务状态
            if task.status not in (TaskStatus.PENDING, TaskStatus.RETRYING):
                self._safe_notify(
                    f"任务 {task_id} 状态不正确: {task.status}",
                    severity="warning",
                )
                return

            # 获取下载参数
            download_params = task.metadata.get("download_params", {})
            if not download_params:
                self._safe_notify(
                    f"任务 {task_id} 缺少下载参数",
                    severity="error",
                )
                self.app.progress_manager.update_status(
                    task_id, TaskStatus.FAILED, "缺少下载参数"
                )
                return

            # 获取可用账号
            account = self._get_account()
            if account is None:
                self.app.progress_manager.update_status(
                    task_id, TaskStatus.FAILED, "无可用账号"
                )
                return

            # 更新状态为下载中
            self.app.progress_manager.update_status(
                task_id, TaskStatus.DOWNLOADING
            )
            self.app.progress_manager.set_account(
                task_id, account.account_id
            )

            # 创建CDS客户端
            client = CDSClient(
                account_info={
                    "uid": account.uid,
                    "key": account.api_key,
                    "url": account.url,
                }
            )

            # 执行下载
            self._safe_notify(
                f"开始下载: {task.filename}",
                severity="information",
            )

            output_path = client.download(**download_params)

            # 下载成功
            self.app.progress_manager.update_status(
                task_id, TaskStatus.COMPLETED
            )

            # 更新文件大小
            if output_path.exists():
                file_size = output_path.stat().st_size
                self.app.progress_manager.update_progress(
                    task_id, 100.0, file_size
                )

            self._safe_notify(
                f"下载完成: {task.filename}",
                severity="success",
            )

        except AccountPoolError as e:
            # 账号池错误（无可用账号等）
            self.app.progress_manager.update_status(
                task_id, TaskStatus.FAILED, str(e)
            )
            self._safe_notify(
                f"账号池错误: {str(e)}",
                severity="error",
            )

        except APIError as e:
            # API错误
            self._handle_download_error(task_id, str(e))

        except Exception as e:
            # 其他错误
            self._handle_download_error(task_id, f"未知错误: {str(e)}")

    def _get_account(self):
        """获取可用账号

        Returns:
            AccountInfo: 可用账号，失败返回None
        """
        try:
            account = self.app.account_pool.get_next_account()
            return account
        except AccountPoolError as e:
            self._safe_notify(f"无可用账号: {str(e)}", severity="error")
            return None
        except Exception as e:
            self._safe_notify(f"获取账号失败: {str(e)}", severity="error")
            return None

    def _handle_download_error(self, task_id: str, error_message: str) -> None:
        """处理下载错误

        根据重试次数决定是重试还是标记为失败。

        Args:
            task_id: 任务ID
            error_message: 错误信息
        """
        task = self.app.progress_manager.get_task(task_id)
        if task is None:
            return

        max_retries = task.metadata.get("max_retries", 3)
        current_retries = task.retry_count

        if current_retries < max_retries:
            # 可以重试
            self.app.progress_manager.increment_retry(task_id)
            self.app.progress_manager.update_status(
                task_id, TaskStatus.RETRYING
            )
            self._safe_notify(
                f"下载失败，稍后重试 ({current_retries + 1}/{max_retries}): {error_message}",
                severity="warning",
            )
        else:
            # 达到最大重试次数
            self.app.progress_manager.update_status(
                task_id, TaskStatus.FAILED, error_message
            )
            self._safe_notify(
                f"下载失败（已达最大重试次数）: {error_message}",
                severity="error",
            )

    def _safe_notify(self, message: str, severity: str = "information") -> None:
        """安全地通知UI（线程安全）

        使用call_from_thread确保在主线程中更新UI。

        Args:
            message: 通知消息
            severity: 严重程度（information/warning/error/success）
        """
        self.app.call_from_thread(
            self.app.notify,
            message,
            severity=severity,
        )


def start_download_task(app: "ECMWFDownloaderApp", task_id: str) -> None:
    """启动下载任务的便捷函数

    Args:
        app: TUI应用实例
        task_id: 任务ID
    """
    worker = DownloadWorker(app)
    worker.download_task(task_id)
