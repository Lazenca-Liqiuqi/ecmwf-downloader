# Codex 第二轮修复验证审查请求

## 项目信息

**项目名称**：ECMWF Downloader
**版本**：v0.3.0

## 审查背景

根据上一轮审查（评分 79/100），已修复以下 4 个新发现的问题：

| # | 问题 | 修复方案 | 修改文件 |
|---|------|----------|----------|
| 1 | transition 落盘并发乱序风险 | 将落盘移到锁内，避免并发乱序覆盖 | progress.py |
| 2 | 调度器回退绕过状态机 | 在 VALID_TRANSITIONS 中添加 DOWNLOADING -> QUEUED 路径 | progress.py |
| 3 | UI 重试未重置 retry_count | 添加 reset_task_for_retry() 方法并在重试时调用 | progress.py, tasks_screen.py |
| 4 | delete_task 未持久化 | 在 delete_task() 中调用存储层 delete_task | progress.py |

## 需要审查的核心文件

| 文件 | 功能 | 变更说明 |
|------|------|----------|
| `src/core/progress.py` | 状态机、持久化 | 锁内落盘、新增转换路径、reset_task_for_retry、delete_task 持久化 |
| `src/ui/screens/tasks_screen.py` | 任务列表 UI | 重试时调用 reset_task_for_retry |

## 审查关注点

### 1. 修复验证
- [ ] #1：落盘是否在锁内？是否避免了并发乱序风险？
- [ ] #2：DOWNLOADING -> QUEUED 转换是否合法？调度器回退是否正确？
- [ ] #3：reset_task_for_retry() 是否正确重置所有字段？UI 重试是否调用？
- [ ] #4：delete_task() 是否正确调用存储层？

### 2. 回归检查
- [ ] 是否有修复引入的新问题？
- [ ] 端到端链路是否仍然正常？

### 3. 测试验证
- [ ] 57 个测试是否全部通过？

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
