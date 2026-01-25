## 项目概况
ECMWF Downloader是一个用于下载ECMWF（欧洲中期天气预报中心）气象数据的Python工具。项目正在进行GUI改造，将现有的命令行脚本改造为功能完整的桌面应用程序。

## 工作任务
本次对话继续推进第一阶段（核心模块重构）的开发工作，完成了3个核心模块的实现：
1. 实现Pydantic配置模型
2. 创建账号池管理模块（支持并行获取）
3. 实现线程安全进度管理器

## 工作内容

### 任务#3：实现Pydantic配置模型 ✅
创建 `src/core/config.py`（270行），定义9个配置模型：

**基础模型**：
- `DatasetType` - 数据集类型枚举（ERA5 Pressure Levels）
- `AccountStatus` - 账号状态枚举（ACTIVE/FAILED/DISABLED）
- `AccountInfo` - 单个账号信息（id/uid/key/status/used_count/fail_count等）

**配置模型**：
- `AccountPoolConfig` - 账号池配置（账号列表+自动禁用阈值）
- `ConcurrencyConfig` - 并发配置（批大小/线程数/重试等）
- `DownloadConfig` - 下载配置（变量/时间/空间/输出等，含完整验证器）
- `ProgressConfig` - 进度管理配置
- `LoggingConfig` - 日志配置
- `AppConfig` - 应用总配置（整合所有模块）

**验证特性**：
- 年份范围验证（1940-当前年份）
- 月份范围验证（1-12）
- 气压层有效性验证
- 区域范围格式验证
- 自动创建输出目录

### 任务#4：创建账号池管理模块 ✅
创建 `src/core/account_pool.py`（337行），实现线程安全的账号池管理器：

**核心功能**：
- `get_next_account()` - 获取下一个可用账号（轮换策略，支持多线程并行获取）
- `mark_account_failed()` - 标记账号失败，超阈值自动禁用
- `mark_account_success()` - 标记账号成功，重置失败计数
- `update_usage_stats()` - 更新账号使用统计
- `get_available_count()` - 获取可用账号数量
- `add_account()` / `remove_account()` - 添加/移除账号
- `enable_account()` / `disable_account()` - 手动启用/禁用账号
- `load_from_file()` / `save_to_file()` - YAML配置持久化
- `get_usage_summary()` - 获取使用摘要统计

**并行获取原理**：
- 使用RLock保护轮换索引
- 多线程同时调用返回不同账号
- 自动跳过失效账号
- 循环分配，负载均衡

**线程安全保证**：
- 所有操作使用RLock保护
- 账号列表返回副本防止外部修改
- 失败阈值可配置（默认5次）

### 任务#5：实现线程安全进度管理器 ✅
创建 `src/core/progress.py`（423行），实现进度管理器：

**任务状态枚举**（6种）：
- PENDING - 待下载
- DOWNLOADING - 下载中
- COMPLETED - 已完成
- FAILED - 失败
- CANCELLED - 已取消
- RETRYING - 重试中

**TaskInfo数据类**：
- 任务ID、文件名、状态、进度
- 错误信息、重试次数
- 创建/开始/完成时间戳
- 文件大小、已下载大小
- 使用的账号ID、元数据

**ProgressManager核心功能**：
- `create_task()` - 创建新任务
- `update_status()` - 更新任务状态（自动更新时间戳）
- `update_progress()` - 更新下载进度
- `increment_retry()` - 增加重试计数
- `get_task()` / `get_all_tasks()` - 查询任务（返回副本）
- `get_tasks_by_status()` - 按状态筛选任务
- `get_summary()` - 获取总体统计
- `save()` / `load()` - JSON持久化
- `clear_completed()` / `clear_all()` - 清理任务

**观察者模式**：
- `register_observer()` - 注册观察者回调
- 任何状态/进度变化自动通知观察者
- 支持GUI实时更新（通过after()调度）

**线程安全**：
- 所有操作使用RLock保护
- 返回任务副本避免外部修改
- 观察者在锁外调用避免死锁

## 交付物
- `src/core/config.py` - Pydantic配置模型（270行）
- `src/core/account_pool.py` - 账号池管理器（337行）
- `src/core/progress.py` - 进度管理器（423行）
- 共1030行核心业务代码

## 状态变动
- **版本**：v0.0.1（初始化阶段）
- **项目阶段**：第一阶段（核心模块重构）进行中
- **任务进度**：5/9 已完成（56%）
- **Git状态**：有未提交更改

## 待办任务
- #6: 创建API抽象基类
- #7: 实现CDS API客户端
- #8: 创建配置文件模板
- #9: 编写核心模块单元测试

## 工具
- **工具**：Task、Write、Read
- **框架**：Pydantic（配置验证）、threading（线程安全）
- **模式**：观察者模式（进度通知）、轮换策略（账号池）
- **规范参考**：项目记忆skill、GUI改造计划文档
