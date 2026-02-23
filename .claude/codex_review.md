审查时间：2026-02-23 12:44

## 结论（4/4 均已实现，端到端链路可跑通）
1) **#1 transition 落盘并发乱序风险**：已按要求把落盘移到锁内。`transition()` 在 `with self._lock:` 内部调用 `self._store.save_task(...)`（`src/core/progress.py:278`）。  
2) **#2 调度器回退绕过状态机**：已补齐 **DOWNLOADING → QUEUED** 合法转换（`VALID_TRANSITIONS`，`src/core/progress.py:1`），`DownloadQueueScheduler` 启动失败回退时优先走 `transition(..., QUEUED)`（`src/core/queue_scheduler.py:240`）。  
3) **#3 UI 重试未重置 retry_count**：已新增 `reset_task_for_retry()` 清零 `retry_count` 等运行时字段（`src/core/progress.py:525`），UI 重试流程已调用并串联 `FAILED/CANCELLED → PENDING → enqueue`（`src/ui/screens/tasks_screen.py:281`）。  
4) **#4 delete_task 未持久化**：已在 `delete_task()` 锁内调用存储层 `delete_task`（`src/core/progress.py:588`；存储实现见 `src/core/progress_store.py:347`）。

## 端到端链路核对（代码证据 + 最小回归）
- UI“开始/入队”→ `ProgressManager.enqueue()` → `transition(PENDING→QUEUED)`（`src/ui/screens/tasks_screen.py:243`，`src/core/progress.py:362`）  
- 调度器取任务→ `transition(QUEUED→DOWNLOADING)`；启动失败→ `transition(DOWNLOADING→QUEUED 或 RETRYING)`（`src/core/queue_scheduler.py:240`）  
- UI“重试”→ `reset_task_for_retry()` → `transition(...→PENDING)` → `enqueue()`（`src/ui/screens/tasks_screen.py:281`）

我做了一个不依赖 pytest 的最小回归脚本验证 #2/#3/#4（包含重载检查“删除后不复活”、以及 `retry_count` 落盘后仍为 0；注意 **QUEUED 会在 load() reconcile 时重置为 PENDING**，因此重载后状态应为 PENDING）。脚本运行输出 OK，数据目录：`manual_verify_20260223_124426`（在项目根目录下）。

## 新问题/风险点（基于现有代码）
- **仍存在“绕过状态机”的后门**：调度器/worker 在 `transition()` 抛 `ValueError` 时仍会降级 `update_status()` 强制改状态（`src/core/queue_scheduler.py:240`，`src/ui/workers/download_worker.py:240`）。这意味着“修复 #2”降低了触发概率，但并未从机制上消除绕过路径。  
- `reset_task_for_retry()` **不通知观察者、不直接落盘**（`src/core/progress.py:525`）：目前 UI 会紧接着 `transition()+enqueue()` 触发通知/持久化，因此链路没断；但如果未来别处单独调用该方法，UI 可能不刷新、数据也可能不落盘。  
- `transition()` 的持久化异常被吞掉（`src/core/progress.py:278`）：会导致“内存已变、磁盘未变”的隐性不一致（当前实现选择了“不中断业务流”）。

## 测试说明
- `pytest tests/test_core/test_progress.py` 在此环境下大量报错 `PermissionError: [WinError 5]`（tmpdir/cleanup 阶段对临时目录无权限），导致 **无法用 pytest 给出通过/失败的客观结论**；因此本轮验证以“代码证据 + 手工最小回归脚本”为主。

## 评分（0-100）
**85/100**  
扣分主要来自：pytest 无法跑通导致置信度下降；以及 `update_status()` 仍作为降级路径存在、`reset_task_for_retry()` 缺少通知/持久化约束带来的潜在误用风险。