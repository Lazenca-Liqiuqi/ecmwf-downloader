## 项目概况
ECMWF Downloader是一个用于下载ECMWF（欧洲中期天气预报中心）气象数据的Python工具。项目正在进行GUI改造，将现有的命令行脚本改造为功能完整的桌面应用程序。

## 工作任务
本次对话主要完成GUI改造项目的前期规划和第一阶段核心模块重构的初步工作，包括：
1. 分析现有ERA5_download.py脚本
2. 制定完整的GUI改造架构方案
3. 创建项目分层目录结构
4. 实现自定义异常类系统

## 工作内容

### 第一部分：项目规划

**技术决策确认**：
- GUI框架：CustomTkinter
- API密钥策略：多密钥轮换 + 账号池功能
- 实施方式：分5个阶段渐进式实施
- 首期数据集：ERA5 Pressure Levels
- 部署方式：可执行文件 + 源码

**架构设计**：
- 核心层（core/）：配置模型、进度管理、下载引擎、账号池
- API层（api/）：CDS API客户端抽象
- UI层（ui/）：CustomTkinter界面组件
- 工具层（utils/）：日志、验证器等

**分阶段计划**：
1. Week 1-2：核心模块重构
2. Week 3：基础GUI框架
3. Week 4-5：核心下载功能
4. Week 6：完善与优化
5. Week 7：打包部署

### 第二部分：第一阶段实施

**任务1：创建项目目录结构** ✅
```
src/
├── core/       # 核心业务逻辑层
├── api/        # API抽象层
├── ui/
│   ├── pages/      # 页面组件
│   └── components/ # 可复用组件
└── utils/      # 工具模块
config/         # 配置文件目录
tests/
├── test_core/
└── test_api/
```

**任务2：实现自定义异常类** ✅
创建 `src/core/exceptions.py`（222行），定义异常类：
- `DownloadError`：下载异常基类
- `APIError`：API调用异常（含状态码、响应体）
- `AccountPoolError`：账号池异常（含账号ID、可用数量）
- `ProgressLoadError`：进度加载异常
- `ProgressSaveError`：进度保存异常
- `ConfigurationError`：配置验证异常
- `TaskValidationError`：任务参数验证异常

## 交付物
- `.claude/plans/elegant-squishing-marshmallow.md` - 完整的GUI改造计划
- `src/` - 分层源代码目录结构（9个子目录，含__init__.py）
- `src/core/exceptions.py` - 自定义异常类系统
- `TASKS.json` - 9个待办任务（2个已完成，7个待完成）

## 状态变动
- **版本**：v0.0.1（初始化阶段）
- **项目阶段**：第一阶段（核心模块重构）进行中
- **Git状态**：有未提交更改
- **任务进度**：2/9 已完成（22%）

## 待办任务
- #3: 实现Pydantic配置模型
- #4: 创建账号池管理模块
- #5: 实现线程安全进度管理器
- #6: 创建API抽象基类
- #7: 实现CDS API客户端
- #8: 创建配置文件模板
- #9: 编写核心模块单元测试

## 工具
- **工具**：Task、Bash、Write、Read
- **规范参考**：项目记忆skill、CustomTkinter官方文档、ECMWF CDS API文档
