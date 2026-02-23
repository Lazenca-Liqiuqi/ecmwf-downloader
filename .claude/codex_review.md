# Codex 第五轮修复验证审查报告（时间：2026-02-23 13:23）

## 审查范围

- 修复项：P1-风险1、P1-风险2（依据 `.claude/request.md`）
- 核心文件：`src/core/progress.py`

## 总体结论

- **P1-风险1（can_transition 断言检查）**：`retry_task()` 已在锁内、修改 `task.status` 之前增加两段 `can_transition()` 校验（`current_status→PENDING`、`PENDING→QUEUED`），校验失败会抛 `ValueError`，从而把“状态机规则变更导致 retry_task 漂移”的风险显式化（`src/core/progress.py:635`、`src/core/progress.py:639`）。
- **P1-风险2（文档边界）**：`reset_task_for_retry()` docstring 已新增 `Warning`，明确“仅重置字段不改变状态”，并推荐常规重试使用 `retry_task()`，同时列出适用场景与 `retry_task()` 的关键特性（原子化/避免中间态落盘/单次通知）（`src/core/progress.py:546`、`src/core/progress.py:554`）。

综合判断：两项修复均按预期落地；P1-风险2 的边界说明已明显更清晰，但仍有 1 个可进一步澄清的点（见“风险与建议”）。

## 逐项验证

### 1) P1-风险1：can_transition() 断言检查是否正确

**代码证据**
- `retry_task()` 在写入 `task.status` 前做两次校验（`src/core/progress.py:634` 到 `src/core/progress.py:642`）。
- 校验逻辑与当前状态机一致：该方法只允许 `FAILED/CANCELLED` 进入（`src/core/progress.py:628`），且现有规则允许 `FAILED/CANCELLED → PENDING`、`PENDING → QUEUED`。

**最小脚本验证证据**
- 我通过临时覆盖 `pm.can_transition = lambda *_: False` 模拟“状态机规则变更导致不再允许转换”的情形，验证 `retry_task()` 会在转换前抛出 `ValueError(非法状态转换...)`，脚本输出 `OK`。

### 2) P1-风险2：文档边界是否清晰

**代码证据**
- `reset_task_for_retry()` 的 `Warning` 已明确：
  - 不改变任务状态；
  - 常规重试推荐使用 `retry_task()`；
  - 给出“适用于哪些特定场景”的列表；
  - 解释 `retry_task()` 的原子化与避免中间态落盘等特性（`src/core/progress.py:554` 到 `src/core/progress.py:564`）。

**清晰度评价**
- 该边界足以指导 UI/业务方做选择（常规重试用 `retry_task()`；特殊场景才用 `reset_task_for_retry()`），整体清晰。

## 风险与建议（P1）

- **建议补充一个关键副作用说明**：当前 `reset_task_for_retry()` 实际会“持久化 + 触发观察者通知”（`src/core/progress.py:586`、`src/core/progress.py:597`），但 `Warning` 只强调“不改变状态”，容易让调用方误以为它是“纯内存重置”。建议在 `Warning` 中补充一句“会落盘并通知观察者”，以进一步减少误用成本。

## 评分（0-100）

**93/100**
- 加分：P1-风险1 把状态机规则变更风险转为显式失败；P1-风险2 文档边界更明确并直接引导使用 `retry_task()`。
- 扣分：`reset_task_for_retry()` 的文档仍可更明确其“持久化/通知”副作用；此外 `retry_task()` 仍未复用 `transition()`（已有 can_transition 校验缓解，但仍存在维护分叉）。

---

以下为历史记录（第四轮修复验证审查）：

# Codex 第四轮修复验证审查报告（时间：2026-02-23 13:18）

## 审查范围

- 修复项：P1-1、P1-2（依据 `.claude/request.md`）
- 核心文件：`src/core/progress.py`、`src/ui/screens/tasks_screen.py`

## 总体结论

- **P1-1（告警位置）**：`update_status()` 的 `logger.warning()` 已移动到确认任务存在之后，避免对不存在任务产生无效告警噪声（`src/core/progress.py:410`、`src/core/progress.py:431`、`src/core/progress.py:437`）。
- **P1-2（retry_task 原子化）**：新增 `retry_task()` 在同一把锁内一次性完成“重置字段 + 置为 QUEUED + 单次持久化 + 单次通知”，UI 已切换使用该方法（`src/core/progress.py:588`、`src/core/progress.py:606`、`src/core/progress.py:640`；`src/ui/screens/tasks_screen.py:281`、`src/ui/screens/tasks_screen.py:316`）。
- **中间态落盘**：`retry_task()` 只对最终快照（`status=QUEUED`）执行一次 `save_task()`，不会将 PENDING 等中间态写入存储（证据见“最小回归脚本”）。

综合判断：本轮 P1-1/P1-2 修复目标均实现，且确实降低了告警噪声并避免了 UI 重试的中间态落盘。

## 逐项验证

### 1) P1-1 告警位置是否正确

**代码证据**
- `update_status()` 在锁内获取 `task`，`task is None` 直接 `return`（`src/core/progress.py:431`、`src/core/progress.py:433`）。
- `logger.warning(...)` 位于 `task` 存在之后（`src/core/progress.py:436`、`src/core/progress.py:437`）。

**最小回归脚本证据**
- 我用日志捕获验证：对不存在任务调用 `update_status('missing', ...)` 不产生 warning；对存在任务调用会产生 warning。脚本输出 `OK`。

### 2) P1-2 `retry_task()` 原子化是否正确

**实现证据（单锁 + 单次持久化 + 单次通知）**
- 全流程在 `with self._lock:` 内完成字段重置与状态设置（`src/core/progress.py:606`、`src/core/progress.py:619`、`src/core/progress.py:631`、`src/core/progress.py:634`）。
- 仅构造一次最终快照并持久化一次（`src/core/progress.py:636`、`src/core/progress.py:639`、`src/core/progress.py:642`）。
- 仅在锁外通知一次观察者（`src/core/progress.py:649`、`src/core/progress.py:651`）。
- UI 重试入口已改为调用 `retry_task()`（`src/ui/screens/tasks_screen.py:313`、`src/ui/screens/tasks_screen.py:316`）。

**状态机语义一致性（重要说明）**
- `retry_task()` 通过“仅允许 FAILED/CANCELLED 调用”的前置校验（`src/core/progress.py:613`、`src/core/progress.py:614`）保证语义正确；但它**直接赋值** `task.status = PENDING/QUEUED`（`src/core/progress.py:631`、`src/core/progress.py:634`），而非复用 `transition()` 的合法性检查与副作用逻辑。
  - 这在当前规则下是可证明安全的（FAILED/CANCELLED→PENDING、PENDING→QUEUED 都属于已定义的合法路径），并且实现了“避免中间态落盘”的目标；
  - 但如果未来状态机规则在 `transition()` 中新增副作用或更改合法转换集合，`retry_task()` 需要同步维护（建议见“风险与建议”）。

### 3) 是否避免了中间态落盘

**最小回归脚本证据（计数存储 + 观察者计数）**
- 我注入了一个 `CountingStore` 统计 `save_task` 调用次数，并注册观察者统计通知次数：
  - `retry_task()` 触发的 `save_task_calls == [(task_id, 'queued')]`（仅一次，且为最终状态 QUEUED）。
  - 观察者通知也仅一次，且携带最终状态 QUEUED。
  - 脚本输出 `OK`。

## 风险与建议（P1）

1) **可维护性风险**：`retry_task()` 直接写 `task.status`，未复用 `can_transition()/transition()`。
   - 建议：在 `retry_task()` 内部加入 `can_transition(current_status, PENDING)`、`can_transition(PENDING, QUEUED)` 的断言/检查，或抽取一个“仅内存转换、不落盘不通知”的私有方法复用状态机规则。

2) **API 兼容性**：当前 UI 已迁移到 `retry_task()`，但 `reset_task_for_retry()` 仍保留且包含持久化与通知（`src/core/progress.py:545`）。
   - 建议：在文档/注释中明确 `reset_task_for_retry()` 的适用边界（仅用于特定流程或内部调用），避免外部误用导致非预期落盘/通知。

## 评分（0-100）

**94/100**
- 加分：P1-1 位置调整精准；P1-2 用单锁实现“单次落盘/单次通知”，并可用脚本证明“无中间态落盘”。
- 扣分：`retry_task()` 绕过 `transition()`，未来规则变更时需要额外维护成本；持久化失败仍采用“记录日志但不回滚内存”的策略（与既有设计一致，但会留下磁盘/内存不一致的可能）。

---

以下为历史记录（第三轮修复验证审查）：

## 审查范围

- 修复项：#5、#6、#7（依据 `.claude/request.md`）
- 核心文件：`src/core/progress.py`

## 总体结论

- **#5 日志告警**：已正确添加 `logger.warning()`，可以显式暴露 `update_status()` 的“绕过状态机”使用（`src/core/progress.py:410`、`src/core/progress.py:430`）。
- **#6 观察者通知 + 持久化**：已实现“锁内构造快照 + 锁内落盘 + 锁外通知观察者”的完整链路（`src/core/progress.py:545`、`src/core/progress.py:572`、`src/core/progress.py:583`）。
- **#7 持久化失败日志覆盖**：对本次列出的 4 个“原先吞异常”的持久化点均已补充 `logger.error()`（`src/core/progress.py:142`、`src/core/progress.py:283`、`src/core/progress.py:545`、`src/core/progress.py:628`）。

综合判断：#5/#6/#7 **实现符合修复目标**，但仍有 2 个非阻塞风险点（见“风险与建议”）。

## 逐项验证

### #5：`update_status()` 日志告警是否正确添加

**实现证据**
- `update_status()` 入口处新增告警日志（`logger.warning`），并在 docstring 中明确“绕过校验/不持久化/仅降级使用”的约束（`src/core/progress.py:410`、`src/core/progress.py:416`、`src/core/progress.py:426`、`src/core/progress.py:430`）。

**有效性判断**
- 该告警会在每次调用 `update_status()` 时触发，能达到“强提示迁移到 transition()”的目的。

**可能的副作用（非阻塞）**
- 当前实现 **在检查 task 是否存在之前**就记录 warning（`src/core/progress.py:430` 在 `task is None` 判断之前）。如果上层在竞态下对不存在任务调用 `update_status()`，会产生“无效告警噪声”。

### #6：`reset_task_for_retry()` 观察者通知与持久化是否正确

**实现证据**
- 锁内重置字段后构造快照（`src/core/progress.py:555`、`src/core/progress.py:569`）。
- 锁内调用 `self._store.save_task(...)` 落盘，并在异常时记录 error 日志（`src/core/progress.py:572`、`src/core/progress.py:578`）。
- 锁外调用 `_notify_observers(..., TaskEventType.UPDATED)`（`src/core/progress.py:583`、`src/core/progress.py:585`）。

**最小回归证据（脚本验证）**
- 我在本机沙盒中运行了一个最小脚本，验证“通知触发 + 落盘字段被重置”，输出 `OK`；数据目录：`manual_verify_round3_20260223_131045`。
  - 观察者最后一次通知为 `('r3_task', 'failed', 'updated')`（意味着 reset 后仍处于 FAILED 状态，但 UI 能刷新）。
  - `finished_tasks.json` 中该任务字段已被重置（`retry_count=0/progress=0/downloaded_size=0/...`）。

**一致性风险（非阻塞，但需要明确语义）**
- `reset_task_for_retry()` 会在 **不改变 status** 的前提下清空 `completed_at/error_message`（`src/core/progress.py:563`、`src/core/progress.py:564`），因此可能形成“FAILED 但 completed_at=None”的持久化记录。这在当前数据模型（字段 Optional）下不一定是错误，但会让“终态字段语义”变得不再单调一致。
  - 若该方法仅被 UI 的“重试”按钮按固定流程调用（随后立即 `transition(..., PENDING)`），风险较低；
  - 若未来出现“单独调用 reset_task_for_retry() 但未后续 transition”的路径，建议在接口层面禁止或提供更原子化的 `retry_task()`。

### #7：日志告警是否覆盖所有“持久化失败被吞掉”的场景

**本轮声明需覆盖的 4 个点（与 `.claude/request.md` 一致）**
1. `transition()` 中 `save_task()` 异常：已记录 error（`src/core/progress.py:354`、`src/core/progress.py:359`）。
2. `delete_task()` 中 `store.delete_task()` 异常：已记录 error（`src/core/progress.py:648`、`src/core/progress.py:654`）。
3. `load()` reconcile 后 `save()` 异常：已记录 error（捕获 `ProgressSaveError`）（`src/core/progress.py:159`、`src/core/progress.py:162`、`src/core/progress.py:164`）。
4. `reset_task_for_retry()` 中 `save_task()` 异常：已记录 error（`src/core/progress.py:572`、`src/core/progress.py:578`）。

**最小回归证据（脚本验证）**
- 我用一个 `FailingStore`（`save/save_task/delete_task` 主动抛异常）注入 `ProgressManager(store=...)`：
  - 断言日志中包含上述 4 条错误信息关键字，脚本输出 `OK`。
  - 这证明 #7 的日志分支可被触发且文本与预期一致。

**覆盖性结论**
- 对“本轮明确列出的吞异常点”，覆盖完整。
- 仍有改进空间：目前使用 `logger.error(... error={e})`，不包含堆栈；如排障需要更完整上下文，可考虑改为 `logger.exception(...)`（不影响本轮验收结论）。

## 回归与测试说明

- `.claude/request.md` 声称 `pytest tests/test_core/test_progress.py` 全通过；但在我当前沙盒账号权限下，pytest 的 tmpdir/cleanup 相关操作会触发 `PermissionError: [WinError 5]`，因此 **无法以 pytest 结果作为本轮审查证据来源**。
- 本轮验证主要依赖：代码证据（精确到行）+ 两个可重复的最小脚本（一个验证 #6 行为，一个验证 #7 日志触发）。

## 风险与建议（帮助快速决策）

1) **P1（建议改进）：降低 #5 告警噪声**
   - 现状：warning 发生在 `task is None` 之前（`src/core/progress.py:430`）。
   - 建议：将 warning 挪到确认任务存在之后，或在日志中补充“task 不存在”的分支信息，避免误导排障。

2) **P1（建议明确语义）：`reset_task_for_retry()` 与状态字段一致性**
   - 现状：方法会清空 `completed_at/error_message` 但不改 status（`src/core/progress.py:557`、`src/core/progress.py:563`）。落盘后可能出现“FAILED 但 completed_at=None”。
   - 建议（二选一）：
     - 将“重置字段 + 转 PENDING + 入队”封装为 `retry_task()`（单锁内一次持久化），避免中间态落盘；或
     - 保持当前流程，但只重置与“下一次下载”强相关的运行时字段，不提前清空 `completed_at`（直到 status 真正变更为 PENDING）。

## 评分（0-100）

**91/100**
- 加分：#5/#6/#7 目标均落地；#6 用“锁内持久化 + 锁外通知”保证线程安全与 UI 刷新；#7 对吞异常点补齐日志，能显著提升可观测性。
- 扣分：#5 可能产生一定无效告警噪声；#6 新增持久化后，中间态语义更需严格约束；#7 日志缺少堆栈对排障仍有提升空间。

---

以下为历史记录（第二轮修复验证审查）：

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
