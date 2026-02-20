# ECMWF Downloader

一个用于自动化下载ECMWF（欧洲中期天气预报中心）气象数据的Python工具。

## 项目背景信息

ECMWF（European Centre for Medium-Range Weather Forecasts）提供全球领先的气象数据和预报服务。本项目旨在开发一个便捷的工具，帮助研究人员和开发者高效获取ECMWF Climate Data Store (CDS)中的气象数据，支持气象研究、气候分析和业务应用。

## 当前状态

**版本**：0.2.2

**开发阶段**：第五阶段（下载功能集成）**进行中**

项目已完成核心模块、TUI 界面和请求构建模块的实现，包括：
- ✅ 自定义异常类体系
- ✅ Pydantic配置模型
- ✅ 账号池管理（支持多API密钥轮换）
- ✅ 线程安全进度管理器
- ✅ API抽象层和CDS客户端
- ✅ 请求构建器（支持按月/年/不拆分策略）
- ✅ 任务服务（统一任务创建入口）
- ✅ TUI 终端界面（Textual 框架）
  - ✅ 首页（统计卡片 + 快捷操作）
  - ✅ 任务列表（筛选、搜索、操作）
  - ✅ 下载管理（进度条 + 活动任务）
  - ✅ 账号管理（添加/编辑/启用/禁用/删除）
  - ✅ 配置管理（创建任务 + 预览功能）
- ✅ 对话框模块（添加/编辑账号 + 请求预览）
- ✅ 自定义组件（TaskTable、AccountTable）
- ✅ 后台下载Worker（线程安全）
- ✅ AI 参数生成（支持自然语言转配置）
- ✅ 完整的单元测试（421个测试）

## 目录结构

```
ECMWF downloader/
├── .claude/                      # 项目记忆组件
│   ├── rules/                    # 项目规则目录
│   ├── CLAUDE.md                 # 项目提示词
│   ├── LAST_CLAUDE_PROGRESS.md   # 工作进度记录
│   └── TASKS.json                # 任务清单
├── src/                          # 源代码目录
│   ├── core/                     # 核心业务逻辑层 ✅
│   │   ├── exceptions.py         # 自定义异常类
│   │   ├── config.py             # Pydantic配置模型
│   │   ├── account_pool.py       # 账号池管理
│   │   └── progress.py           # 进度管理器
│   ├── api/                      # API抽象层 ✅
│   │   ├── base.py               # API客户端基类
│   │   └── cds_client.py         # CDS API客户端
│   ├── ui/                       # 用户界面层 ✅ TUI框架完成
│   │   ├── app.py                # TUI应用主入口
│   │   ├── screens/              # 屏幕模块
│   │   ├── dialogs/              # 对话框模块 ✅
│   │   ├── widgets/              # 自定义组件
│   │   ├── workers/              # 后台任务
│   │   └── styles/               # 样式文件
│   └── utils/                    # 工具模块（待开发）
├── config/                       # 配置文件目录 ✅
│   ├── default_config.yaml       # 默认配置模板
│   └── accounts.yaml             # 账号池配置模板
├── tests/                        # 测试目录 ✅
│   ├── test_core/                # 核心模块测试
│   └── test_api/                 # API模块测试
├── README.md                     # 项目说明（本文件）
└── CHANGELOG.md                  # 版本更新日志
```

## 技术栈与技术路线

### 核心技术
- **语言**：Python 3.8+
- **主要依赖**：
  - `cdsapi` - ECMWF CDS数据下载API客户端
  - `pydantic` - 配置验证和数据模型
  - `PyYAML` - YAML配置文件解析
  - `pytest` - 单元测试框架

### 技术架构
```
配置层 → API抽象层 → 数据下载层 → 进度管理层
  ↓         ↓           ↓            ↓
YAML    BaseAPIClient  CDSClient  ProgressManager
```

### 技术路线
1. 使用ECMWF Climate Data Store (CDS) API进行数据请求
2. 支持多种气象数据集（ERA5、ERA5-Land等）
3. 提供YAML配置文件管理下载参数
4. 实现多账号轮换和并发下载
5. 支持断点续传和进度持久化

## 第一阶段交付成果

### 核心模块
| 模块 | 文件 | 代码行数 | 说明 |
|------|------|---------|------|
| 异常类 | exceptions.py | 223行 | 7种自定义异常 |
| 配置模型 | config.py | 241行 | 9个Pydantic模型 |
| 账号池 | account_pool.py | 355行 | 多账号管理 |
| 进度管理 | progress.py | 483行 | 任务进度跟踪 |
| API基类 | base.py | 172行 | API抽象接口 |
| CDS客户端 | cds_client.py | 408行 | CDS API实现 |

### 测试覆盖
| 类型 | 测试数 | 文件 |
|------|-------|------|
| 异常类测试 | 27 | test_exceptions.py |
| 配置模型测试 | 37 | test_config.py |
| 账号池测试 | 38 | test_account_pool.py |
| 进度管理测试 | 47 | test_progress.py |
| CDS客户端测试 | 26 | test_cds_client.py |
| API基类测试 | 13 | test_base.py |
| **总计** | **188** | **全部通过** ✅ |

### 配置模板
- `config/default_config.yaml`（142行）- 主配置文件模板
- `config/accounts.yaml`（73行）- 账号池配置模板

## TODO

### 近期任务
**第三阶段：TUI测试与完善**（已完成 ✅）
- [x] 样式优化：统一设计风格和用户体验
- [x] 布局调整：账号页、下载页布局优化
- [x] Bug 修复：下载页空白、终端卡住等问题

**第四阶段：功能完善与优化**（已完成 ✅）
- [x] 实现添加/编辑账号对话框
- [x] 操作回滚机制
- [ ] 实现日志查看器组件
- [ ] 添加快捷键支持
- [ ] 优化样式和颜色主题
- [ ] 实现导出功能

**第五阶段：核心下载功能集成**（进行中 🔄）
- [x] 请求构建器模块（RequestBuilder）
- [x] 任务服务模块（TaskService）
- [x] 请求预览对话框
- [x] 配置页面预览功能
- [x] 配置页面滚动修复
- [ ] 集成下载Worker与控制按钮
- [ ] 实现批量下载功能
- [ ] 添加下载进度实时更新
- [ ] 实现断点续传功能

### 中期目标
- [ ] 支持更多ECMWF数据集类型
- [ ] 添加数据预处理功能（重采样、插值等）
- [ ] 开发命令行界面（CLI）
- [ ] 实现下载进度可视化
- [ ] 添加数据验证功能

### 长期规划
- [ ] 完善图形用户界面（GUI）
- [ ] 实现智能数据缓存机制
- [ ] 支持分布式下载
- [ ] 提供Docker容器化部署
- [ ] 编写完整文档和示例

## 资源

### 官方资源
- [ECMWF Climate Data Store](https://cds.climate.copernicus.eu/) - 数据下载平台
- [CDS API使用指南](https://cds.climate.copernicus.eu/api-how-to) - API配置教程
- [ECMWF数据集目录](https://cds.climate.copernicus.eu/datasets) - 可用数据集列表

### 开发资源
- [cdsapi Python库文档](https://pypi.org/project/cdsapi/)
- [ECMWF API文档](https://confluence.ecmwf.int/display/CKB/Climate+Data+Store+%28CDS%29+API)
- [ERA5数据文档](https://confluence.ecmwf.int/display/CKB/ERA5+data+documentation)

## 许可证

待定

## 联系方式

待定
