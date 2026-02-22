时间：2026-02-22 17:25

**结论（核心问题）**
- 新增的“状态机（VALID_TRANSITIONS + transition）”目前与生产调用路径不一致：下载执行仍直接 `update_status` 跳过校验，导致规则形同虚设且未来容易“接上就炸”。见 `src/ui/workers/download_worker.py:69`、`src/ui/workers/download_worker.py:97`、`src/core/progress.py:18`、`src/core/progress.py:339`。
- “终态（terminal）”语义自相矛盾：`TaskStatus.get_terminal_statuses()` 宣称终态不可再转换，但 `VALID_TRANSITIONS` 允许 `FAILED/CANCELLED → PENDING`；同时 `transition()` 仍会把 `FAILED/CANCELLED` 当终态写入 `completed_at`，后续若回到 `PENDING` 会残留时间戳。见 `src/core/models.py:45`、`src/core/progress.py:18`、`src/core/progress.py:242`。

---

## 1) 状态转换规则是否合理完整
**发现**
- 规则要求 `PENDING → QUEUED → DOWNLOADING`（`PENDING` 不允许直达 `DOWNLOADING`）。见 `src/core/progress.py:18`。  
  但实际下载线程只接受 `PENDING/RETRYING`，并直接 `PENDING → DOWNLOADING`（调用 `update_status`）。见 `src/ui/workers/download_worker.py:69`、`src/ui/workers/download_worker.py:97`。  
  => 规则与真实流程冲突；一旦把生产代码改为走 `transition()`，现有下载流程会直接抛 `ValueError`（你们的测试也明确认为这是非法转换）。见 `tests/test_core/test_progress.py:275`、`src/core/progress.py:242`。
- `update_status()` / `increment_retry()` 仍可随意写状态，绕过 `VALID_TRANSITIONS`。见 `src/core/progress.py:339`、`src/core/progress.py:407`。  
  => 如果状态机是“约束”，目前不成立；如果状态机只是“工具”，需要明确接口契约（哪些入口必须走状态机，哪些是强制写入/迁移专用）。

**建议（P0）**
- 明确接口契约（二选一，必须落地到代码/测试）：
  1) **保留 QUEUED**：生产下载启动前必须 `enqueue()`，下载开始必须 `QUEUED→DOWNLOADING`；把 `download_worker`/UI 按此改造。  
  2) **移除/弱化 QUEUED**：允许 `PENDING→DOWNLOADING`，并同步调整测试与 `src/core/models.py:13` 中的状态流转说明。
- 统一入口：让 `update_status()`（以及 `increment_retry()`）内部走 `transition()`；若确实需要“无视规则的强制写入”，另设私有方法（如 `_force_set_status_for_migration`）并限制调用面。

---

## 2) reconcile 逻辑是否正确处理崩溃恢复
**现状**
- `_reconcile_tasks()` 将 `QUEUED/DOWNLOADING/RETRYING` 重置为 `PENDING`，并清空 `account_id`。见 `src/core/progress.py:139`、`src/core/models.py:33`。  
  这对“崩溃时正在下载/占用账号”是合理的（至少不会卡死在运行态）。
- 但它**不处理**尝试级字段的一致性策略：例如 `started_at` 保留会导致下次真正开始下载时不再更新时间（因为只在 `started_at is None` 时写入）。见 `src/core/progress.py:281`。这是否符合产品语义需要明确。
- reconcile **不回写存储**：重启后内存已变 `PENDING`，但磁盘上仍可能留着 transient 状态；多文件存储下还会短期出现“任务所在文件与其 status 不匹配”。见 `src/core/progress.py:124`、`src/core/progress_store.py:422`。

**建议（P1）**
- 定义并测试“崩溃恢复策略”：对 transient→pending 时，`started_at/completed_at/error_message/progress` 各自是“保留历史”还是“重置为新一轮尝试”。目前只对 `account_id` 有明确动作。见 `src/core/progress.py:139`。
- 可选：当 `reconciled_count>0` 时自动触发一次保存（或在应用启动后尽早保存），保证存储与内存一致；注意 I/O 时机与失败处理（避免启动时硬失败）。

---

## 3) 线程安全性
**优点**
- 使用 `RLock`，大多数读写均在锁内；观察者回调在锁外执行且使用快照，规避死锁。见 `src/core/progress.py:104`、`src/core/progress.py:595`、`src/core/progress.py:242`。

**风险**
- `tasks` 是公有可变 `dict`（`self.tasks: Dict[str, TaskInfo]`），外部可绕过锁直接改，破坏线程安全/状态不变量。见 `src/core/progress.py:100`。

**建议（P1）**
- 将 `tasks` 私有化（`_tasks`），对外只暴露拷贝读取与受控写入接口。

---

## 4) 异常处理
- `transition()` 对非法转换抛 `ValueError`，语义清晰；但 `enqueue_all_pending()` 静默吞掉 `ValueError`，缺少可观测性。见 `src/core/progress.py:242`、`src/core/progress.py:315`。
- 观察者异常被完全吞掉且无日志，排障困难。见 `src/core/progress.py:612`。

---

## 5) 测试覆盖度
**已有覆盖**
- Transition/Enqueue/Reconcile 的基本 happy path 与部分恢复（`DOWNLOADING/QUEUED→PENDING`、终态保持）覆盖到位。见 `tests/test_core/test_progress.py:275`、`tests/test_core/test_progress.py:404`。

**关键缺口**
- 未覆盖 `RETRYING` 的 reconcile；未覆盖“terminal 语义 vs VALID_TRANSITIONS”一致性；未覆盖“生产仍绕过 transition”这一架构风险（测试通过但线上不生效）。见 `src/core/models.py:45`、`src/core/progress.py:18`、`src/core/progress.py:339`。

**执行层面的阻塞（需要你们环境侧处理）**
- 我在此环境运行 `python -m pytest -p no:cacheprovider tests/test_core/test_progress.py` 触发 WinError 5（pytest 临时目录权限问题），因此无法用测试结果为实现背书（只能做静态审查）。

---

## 评分（严审）
- 技术维度（代码质量/测试覆盖/规范遵循）：72/100  
- 战略维度（需求匹配/架构一致/风险评估）：63/100  
- 综合评分：68/100 —— 建议：退回（需先解决“状态机语义与生产路径不一致 + terminal 定义矛盾”这两个 P0）

如果你希望我给出“最小改动”的落地方案，我可以按你选择的路线（保留 QUEUED 或允许 PENDING→DOWNLOADING）列出需要修改的具体函数与新增/调整的测试用例清单。