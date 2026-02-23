# Codex 第五轮修复验证审查请求

## 项目信息

**项目名称**：ECMWF Downloader
**版本**：v0.3.0
**阶段**：第五阶段（下载功能集成）进行中

## 审查背景

上一轮审查（评分 94/100）发现 2 个 P1 风险点，现已修复：

| # | 问题 | 修复方案 | 修改文件 |
|---|------|----------|----------|
| P1-风险1 | `retry_task()` 绕过 `transition()` | 添加 `can_transition()` 断言检查 | progress.py |
| P1-风险2 | `reset_task_for_retry()` 适用边界不清 | 在文档中明确适用边界，推荐使用 `retry_task()` | progress.py |

## 修复详情

### P1-风险1：添加 `can_transition()` 断言检查

**问题**：`retry_task()` 直接写 `task.status`，未复用状态机规则，未来规则变更时需要额外维护成本。

**修复**：在状态转换前添加 `can_transition()` 断言检查。

```python
def retry_task(self, task_id: str) -> bool:
    """原子化重试任务：重置字段 + 转 PENDING + 入队

    P1-风险1 修复：添加 can_transition() 断言检查，确保状态机规则变更时自动校验。
    """
    # ... 获取任务 ...

    # P1-风险1 修复：断言状态转换合法性
    if not self.can_transition(current_status, TaskStatus.PENDING):
        raise ValueError(
            f"非法状态转换: {current_status.value} → {TaskStatus.PENDING.value}"
        )
    if not self.can_transition(TaskStatus.PENDING, TaskStatus.QUEUED):
        raise ValueError(
            f"非法状态转换: {TaskStatus.PENDING.value} → {TaskStatus.QUEUED.value}"
        )

    # ... 后续操作 ...
```

### P1-风险2：明确 `reset_task_for_retry()` 适用边界

**问题**：`reset_task_for_retry()` 仍保留且包含持久化与通知，可能被外部误用。

**修复**：在文档中明确适用边界，推荐使用 `retry_task()`。

```python
def reset_task_for_retry(self, task_id: str) -> None:
    """重置任务的运行时字段，准备重新下载

    P1-风险2 修复：明确适用边界。

    Warning:
        此方法仅重置字段，不改变任务状态。推荐使用 retry_task() 进行原子化重试操作。
        此方法适用于以下特定场景：
        - 需要单独重置运行时字段但不立即入队的场景
        - 内部流程中需要分步操作的场景

        对于常规的"重试失败任务"场景，请使用 retry_task() 方法。
    """
```

## 需要审查的核心文件

| 文件 | 功能 | 变更说明 |
|------|------|----------|
| `src/core/progress.py` | 状态机、持久化 | 添加断言检查、明确文档边界 |

## 审查关注点

### 1. 修复验证
- [ ] P1-风险1：`can_transition()` 断言检查是否正确？
- [ ] P1-风险2：文档是否清晰明确了适用边界？

### 2. 回归检查
- [ ] 57 个测试是否全部通过？
- [ ] 是否有修复引入的新问题？

### 3. 代码质量
- [ ] 断言检查的位置是否合适？
- [ ] 文档是否足够清晰？

## 测试验证

- `python -m compileall -q src`：通过
- `pytest tests/test_core/test_progress.py`：57 个测试全部通过

## 评分标准

| 维度 | 权重 | 说明 |
|------|------|------|
| 功能完整性 | 30% | 工作流是否完整 |
| 状态机正确性 | 25% | 状态转换是否合法 |
| 线程安全性 | 20% | 并发控制是否正确 |
| 错误处理 | 15% | 异常处理是否完善 |
| 代码质量 | 10% | 可读性、注释 |

## 交付物

- 审查报告（更新 codex_review.md）
- 评分（0-100）
- 问题分级（如有）

## Codex Thread ID（继续对话）

Thread ID：`019c8b8e-5585-7c01-b478-e85130f3ff80`
