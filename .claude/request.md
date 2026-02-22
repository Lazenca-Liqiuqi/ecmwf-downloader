# Codex 审查请求：load-time reconcile + transition/enqueue 方法

## 项目状态

**版本**：v0.3.0
**阶段**：第五阶段（下载功能集成）进行中
**当前任务**：任务 #6（load-time reconcile）+ 任务 #7（transition/enqueue 方法）

## 工作内容

### 任务 #6：load-time reconcile 修复逻辑

**目的**：应用启动加载任务时，修复"不一致状态"（崩溃后遗留的非持久状态）

**实现**：
1. `src/core/models.py` - 添加 `TaskStatus` 类方法
   - `get_transient_statuses()` - 返回非持久状态集合 {QUEUED, DOWNLOADING, RETRYING}
   - `get_terminal_statuses()` - 返回终态集合 {COMPLETED, FAILED, CANCELLED}

2. `src/core/progress.py` - 添加修复逻辑
   - `_reconcile_tasks()` - 将非持久状态重置为 PENDING，清空 account_id
   - 修改 `load()` - 加载后自动调用 `_reconcile_tasks()`

### 任务 #7：transition() 和 enqueue() 方法

**目的**：提供安全的状态转换方法，确保状态流转符合业务规则

**实现**：
1. `src/core/progress.py` - 添加状态转换机制
   - `VALID_TRANSITIONS` - 状态转换映射表
   - `can_transition(current, target)` - 验证状态转换是否合法
   - `transition(task_id, target_status, error_message)` - 执行状态转换（验证 + 执行 + 通知）
   - `enqueue(task_id)` - 将 PENDING 任务入队到 QUEUED
   - `enqueue_all_pending()` - 批量入队所有 PENDING 任务

**状态转换规则**：
```
PENDING → {QUEUED, CANCELLED}
QUEUED → {DOWNLOADING, PENDING, CANCELLED}
DOWNLOADING → {COMPLETED, FAILED, CANCELLED, RETRYING}
RETRYING → {DOWNLOADING, FAILED, CANCELLED, PENDING}
FAILED → {PENDING}  # 可重试
CANCELLED → {PENDING}  # 可重新入队
COMPLETED → {}  # 终态不可转换
```

## 审查范围

### 核心文件
1. `src/core/models.py` - 新增类方法
2. `src/core/progress.py` - 新增状态转换和修复逻辑

### 测试文件
3. `tests/test_core/test_progress.py` - 新增测试用例

## 审查关注点

### 1. 状态转换设计
- [ ] 状态转换规则是否合理完整
- [ ] 终态和非终态的划分是否正确
- [ ] 是否有遗漏的转换路径

### 2. Reconcile 逻辑
- [ ] 非持久状态的识别是否正确
- [ ] 修复后是否清除了必要的运行时数据（如 account_id）
- [ ] 进度等业务数据是否正确保留

### 3. 线程安全
- [ ] transition() 方法的锁使用是否正确
- [ ] 是否存在竞态条件

### 4. 异常处理
- [ ] 非法状态转换的异常是否清晰
- [ ] 任务不存在时的处理是否合理

### 5. 测试覆盖
- [ ] 正常转换路径是否覆盖
- [ ] 异常情况是否覆盖
- [ ] reconcile 行为是否正确验证

## 评分标准

| 维度 | 权重 | 说明 |
|------|------|------|
| 状态机设计 | 30% | 转换规则合理性、完整性 |
| 代码质量 | 25% | 线程安全、异常处理、可读性 |
| 测试覆盖 | 25% | 测试用例完整性和正确性 |
| 边界条件 | 20% | 特殊情况处理 |

## 期望输出

1. 质量评分（1-10）
2. 发现的问题列表（按优先级分类）
3. 改进建议
