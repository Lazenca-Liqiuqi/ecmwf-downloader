"""
ECMWF Downloader TUI 下载执行模块

提供后台下载任务的执行和管理，支持多账号轮换和失败重试。
与队列调度器集成，支持从调度器接收已分配的账号。

注意：实际的 @work 装饰器方法在 ECMWFDownloaderApp 中，
因为 Textual 要求 @work 装饰的方法必须属于 DOMNode 子类。
本模块提供纯粹的业务逻辑函数。
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from src.api.cds_client import CDSClient
from src.core.config import AccountInfo
from src.core.exceptions import APIError, AccountPoolError
from src.core.progress import TaskStatus

if TYPE_CHECKING:
    from src.ui.app import ECMWFDownloaderApp

logger = logging.getLogger(__name__)


def execute_download_with_account(
    app: "ECMWFDownloaderApp",
    task_id: str,
    account: AccountInfo,
    on_complete: Optional[Callable[[str], None]] = None,
) -> None:
    """执行下载任务（后台线程中运行）

    此函数由调度器调用，在 App 的 @work 方法中执行。
    不使用 @work 装饰器，因为调用者已经是 @work 方法。

    Args:
        app: TUI应用实例
        task_id: 任务ID
        account: 已分配的账号
        on_complete: 下载完成后的回调
    """
    try:
        # 获取任务信息
        task = app.progress_manager.get_task(task_id)
        if task is None:
            _safe_notify(app, f"任务 {task_id} 不存在", severity="error")
            return

        # 验证任务状态
        if task.status != TaskStatus.DOWNLOADING:
            _safe_notify(
                app,
                f"任务 {task_id} 状态不正确: {task.status}",
                severity="warning",
            )
            return

        # 获取下载参数
        download_params = task.metadata.get("download_params", {})
        if not download_params:
            _safe_notify(app, f"任务 {task_id} 缺少下载参数", severity="error")
            try:
                app.progress_manager.transition(task_id, TaskStatus.FAILED, "缺少下载参数")
            except ValueError:
                app.progress_manager.update_status(task_id, TaskStatus.FAILED, "缺少下载参数")
            return

        # 创建CDS客户端（使用调度器分配的账号）
        client = CDSClient(
            account_info={
                "email": account.email,
                "key": account.key,
                "url": account.url,
            }
        )

        # 执行下载
        _safe_notify(app, f"开始下载: {task.filename}", severity="information")
        logger.info(f"[DownloadWorker] 开始下载任务: {task_id}, 文件: {task.filename}")

        output_path = client.download(**download_params)

        # 下载成功
        try:
            app.progress_manager.transition(task_id, TaskStatus.COMPLETED)
        except ValueError:
            app.progress_manager.update_status(task_id, TaskStatus.COMPLETED)

        # 更新文件大小
        if output_path and output_path.exists():
            file_size = output_path.stat().st_size
            app.progress_manager.update_progress(task_id, 100.0, file_size)

        _safe_notify(app, f"下载完成: {task.filename}", severity="success")
        logger.info(f"[DownloadWorker] 任务下载完成: {task_id}")

    except APIError as e:
        logger.error(f"[DownloadWorker] API错误: {task_id} - {e}")
        _handle_download_error(app, task_id, str(e))

    except Exception as e:
        logger.exception(f"[DownloadWorker] 未知错误: {task_id} - {e}")
        _handle_download_error(app, task_id, f"未知错误: {str(e)}")

    finally:
        # 通知调度器任务完成（无论成功失败）
        if on_complete is not None:
            try:
                on_complete(task_id)
            except Exception as e:
                logger.warning(f"[DownloadWorker] 完成回调异常: {e}")


def execute_download_task(app: "ECMWFDownloaderApp", task_id: str) -> None:
    """执行下载任务（独立模式，后台线程中运行）

    此函数用于独立启动下载，不通过调度器。
    内部会自动获取账号并更新状态。

    Args:
        app: TUI应用实例
        task_id: 任务ID
    """
    try:
        # 获取任务信息
        task = app.progress_manager.get_task(task_id)
        if task is None:
            _safe_notify(app, f"任务 {task_id} 不存在", severity="error")
            return

        # 检查任务状态（支持 PENDING/RETRYING/QUEUED）
        if task.status not in (TaskStatus.PENDING, TaskStatus.RETRYING, TaskStatus.QUEUED):
            _safe_notify(
                app,
                f"任务 {task_id} 状态不正确: {task.status}",
                severity="warning",
            )
            return

        # 获取下载参数
        download_params = task.metadata.get("download_params", {})
        if not download_params:
            _safe_notify(app, f"任务 {task_id} 缺少下载参数", severity="error")
            try:
                app.progress_manager.transition(task_id, TaskStatus.FAILED, "缺少下载参数")
            except ValueError:
                app.progress_manager.update_status(task_id, TaskStatus.FAILED, "缺少下载参数")
            return

        # 获取可用账号
        account = _get_account(app)
        if account is None:
            try:
                app.progress_manager.transition(task_id, TaskStatus.FAILED, "无可用账号")
            except ValueError:
                app.progress_manager.update_status(task_id, TaskStatus.FAILED, "无可用账号")
            return

        # 状态转换到 DOWNLOADING
        try:
            app.progress_manager.transition(task_id, TaskStatus.DOWNLOADING)
        except ValueError:
            _safe_notify(app, f"任务 {task_id} 状态转换失败", severity="error")
            return

        app.progress_manager.set_account(task_id, account.id)

        # 创建CDS客户端
        client = CDSClient(
            account_info={
                "email": account.email,
                "key": account.key,
                "url": account.url,
            }
        )

        # 执行下载
        _safe_notify(app, f"开始下载: {task.filename}", severity="information")
        logger.info(f"[DownloadWorker] 开始下载任务: {task_id}, 文件: {task.filename}")

        output_path = client.download(**download_params)

        # 下载成功
        try:
            app.progress_manager.transition(task_id, TaskStatus.COMPLETED)
        except ValueError:
            app.progress_manager.update_status(task_id, TaskStatus.COMPLETED)

        # 更新文件大小
        if output_path and output_path.exists():
            file_size = output_path.stat().st_size
            app.progress_manager.update_progress(task_id, 100.0, file_size)

        _safe_notify(app, f"下载完成: {task.filename}", severity="success")
        logger.info(f"[DownloadWorker] 任务下载完成: {task_id}")

    except AccountPoolError as e:
        logger.error(f"[DownloadWorker] 账号池错误: {task_id} - {e}")
        try:
            app.progress_manager.transition(task_id, TaskStatus.FAILED, str(e))
        except ValueError:
            app.progress_manager.update_status(task_id, TaskStatus.FAILED, str(e))
        _safe_notify(app, f"账号池错误: {str(e)}", severity="error")

    except APIError as e:
        logger.error(f"[DownloadWorker] API错误: {task_id} - {e}")
        _handle_download_error(app, task_id, str(e))

    except Exception as e:
        logger.exception(f"[DownloadWorker] 未知错误: {task_id} - {e}")
        _handle_download_error(app, task_id, f"未知错误: {str(e)}")


def _get_account(app: "ECMWFDownloaderApp") -> Optional[AccountInfo]:
    """获取可用账号

    Args:
        app: TUI应用实例

    Returns:
        AccountInfo: 可用账号，失败返回None
    """
    try:
        account = app.account_pool.get_next_account()
        return account
    except AccountPoolError as e:
        _safe_notify(app, f"无可用账号: {str(e)}", severity="error")
        return None
    except Exception as e:
        _safe_notify(app, f"获取账号失败: {str(e)}", severity="error")
        return None


def _handle_download_error(app: "ECMWFDownloaderApp", task_id: str, error_message: str) -> None:
    """处理下载错误

    根据重试次数决定是重试还是标记为失败。
    重试时将任务状态转为 RETRYING，由调度器重新调度。

    P0-1 修复：increment_retry() 不再改变状态，
    由 transition() 统一处理状态转换。

    P1-1 修复：添加重试退避机制，避免频繁重试打爆 API。

    Args:
        app: TUI应用实例
        task_id: 任务ID
        error_message: 错误信息
    """
    from datetime import datetime, timedelta

    task = app.progress_manager.get_task(task_id)
    if task is None:
        return

    max_retries = task.metadata.get("max_retries", 3)
    current_retries = task.retry_count

    if current_retries < max_retries:
        # 可以重试：先递增计数，再统一转换状态
        new_retry_count = app.progress_manager.increment_retry(task_id)

        # P1-1 修复：设置重试退避时间
        # 退避策略：第1次 5秒，第2次 15秒，第3次 60秒
        backoff_seconds = {1: 5, 2: 15, 3: 60}.get(new_retry_count, 60)
        next_retry_at = (datetime.now() + timedelta(seconds=backoff_seconds)).isoformat()

        # 更新任务的 metadata 中的 next_retry_at
        app.progress_manager.update_task_metadata(task_id, {"next_retry_at": next_retry_at})

        # P0-1 修复：统一使用 transition() 处理状态转换
        # DOWNLOADING -> RETRYING 是合法转换
        try:
            app.progress_manager.transition(task_id, TaskStatus.RETRYING, error_message)
        except ValueError:
            # 如果转换失败，尝试降级方案
            logger.warning(f"[DownloadWorker] 状态转换失败，尝试降级: {task_id}")
            try:
                # DOWNLOADING -> QUEUED -> RETRYING 可能需要两步
                app.progress_manager.transition(task_id, TaskStatus.QUEUED)
            except ValueError:
                # 最后使用 update_status 强制更新
                app.progress_manager.update_status(task_id, TaskStatus.RETRYING, error_message)

        _safe_notify(
            app,
            f"下载失败，{backoff_seconds}秒后重试 ({new_retry_count}/{max_retries}): {error_message}",
            severity="warning",
        )
        logger.warning(f"[DownloadWorker] 任务将重试: {task_id}, 次数: {new_retry_count}/{max_retries}, 等待: {backoff_seconds}秒")
    else:
        # 达到最大重试次数
        try:
            app.progress_manager.transition(task_id, TaskStatus.FAILED, error_message)
        except ValueError:
            app.progress_manager.update_status(task_id, TaskStatus.FAILED, error_message)
        _safe_notify(
            app,
            f"下载失败（已达最大重试次数）: {error_message}",
            severity="error",
        )
        logger.error(f"[DownloadWorker] 任务失败（已达最大重试次数）: {task_id}")


def _safe_notify(app: "ECMWFDownloaderApp", message: str, severity: str = "information") -> None:
    """安全地通知UI（线程安全）

    使用call_from_thread确保在主线程中更新UI。

    Args:
        app: TUI应用实例
        message: 通知消息
        severity: 严重程度（information/warning/error/success）
    """
    try:
        app.call_from_thread(app.notify, message, severity=severity)
    except Exception as e:
        logger.warning(f"[DownloadWorker] 通知失败: {e}")
