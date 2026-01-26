# ECMWF Downloader

## 项目背景信息
ECMWF（European Centre for Medium-Range Weather Forecasts，欧洲中期天气预报中心）提供全球领先的气象数据和预报服务。本项目旨在开发一个Python工具，用于自动化下载和管理ECMWF的气象数据，支持气象研究、气候分析和业务应用。

## 项目阶段
**当前阶段**：第二阶段（TUI 基础框架）**已完成** 🎉
**版本**：v0.0.1

## 目录结构
```
/home/pc/project/ECMWF downloader/
├── .claude/                      # 项目记忆组件
│   ├── rules/                    # 项目规则目录
│   ├── CLAUDE.md                 # 项目提示词（本文件）
│   ├── LAST_CLAUDE_PROGRESS.md   # 工作进度
│   └── TASKS.json                # 任务清单
├── src/                          # 源代码目录
│   ├── __init__.py
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
│   │   │   ├── base_screen.py    # 基础屏幕类
│   │   │   ├── home_screen.py    # 首页屏幕
│   │   │   ├── tasks_screen.py   # 任务列表屏幕
│   │   │   ├── download_screen.py# 下载管理屏幕
│   │   │   ├── accounts_screen.py# 账号管理屏幕
│   │   │   └── config_screen.py  # 配置管理屏幕
│   │   ├── widgets/              # 自定义组件
│   │   │   ├── task_table.py     # 任务表格组件
│   │   │   └── account_table.py  # 账号表格组件
│   │   ├── workers/              # 后台任务
│   │   │   └── download_worker.py# 下载执行Worker
│   │   └── styles/               # 样式文件
│   │       └── theme.py          # 主题配置
│   └── utils/                    # 工具模块（待开发）
├── config/                       # 配置文件目录 ✅
│   ├── default_config.yaml       # 默认配置模板
│   └── accounts.yaml             # 账号池配置模板
├── tests/                        # 测试目录 ✅
│   ├── test_core/                # 核心模块测试
│   └── test_api/                 # API模块测试
├── README.md                     # 项目说明
└── CHANGELOG.md                  # 更新日志
```

## 技术栈与技术路线
- **语言**：Python 3.8+
- **核心依赖**：
  - `cdsapi` - ECMWF CDS API客户端
  - `pydantic` - 配置验证
  - `PyYAML` - YAML配置解析
  - `pytest` - 单元测试框架
- **技术路线**：
  1. 使用ECMWF CDS API下载数据
  2. 支持多账号轮换提高下载效率
  3. 支持断点续传和批量下载
  4. 提供配置化的请求参数管理

## 第一阶段完成情况
✅ **核心模块重构（100%完成）**

| 模块 | 文件 | 状态 |
|------|------|------|
| 异常类 | exceptions.py | ✅ 223行 |
| 配置模型 | config.py | ✅ 241行 |
| 账号池 | account_pool.py | ✅ 355行 |
| 进度管理 | progress.py | ✅ 483行 |
| API基类 | base.py | ✅ 172行 |
| CDS客户端 | cds_client.py | ✅ 408行 |

**单元测试**：188个测试全部通过 ✅

## 下一步规划
根据TUI改造计划，已完成第一、二阶段，下一阶段可选择：

**第三阶段：功能完善与优化**
- 实现添加/编辑账号对话框
- 实现日志查看器组件
- 添加快捷键支持
- 优化样式和颜色主题
- 实现导出功能

**第四阶段：核心下载功能集成**
- 集成下载Worker与控制按钮
- 实现批量下载功能
- 添加下载进度实时更新
- 实现断点续传功能

## 资源
- [ECMWF Climate Data Store (CDS)](https://cds.climate.copernicus.eu/)
- [CDS API文档](https://cds.climate.copernicus.eu/api-how-to)
- [cdsapi Python库](https://pypi.org/project/cdsapi/)
