# ECMWF Downloader

一个用于自动化下载ECMWF（欧洲中期天气预报中心）气象数据的Python工具。

## 项目背景信息

ECMWF（European Centre for Medium-Range Weather Forecasts）提供全球领先的气象数据和预报服务。本项目旨在开发一个便捷的工具，帮助研究人员和开发者高效获取ECMWF Climate Data Store (CDS)中的气象数据，支持气象研究、气候分析和业务应用。

## 目录结构

```
ECMWF downloader/
├── .claude/
│   ├── rules/              # 项目规则目录
│   ├── CLAUDE.md           # 项目提示词
│   ├── LAST_CLAUDE_PROGRESS.md  # 工作进度记录
│   └── TASKS.json          # 阶段性任务清单
├── README.md               # 项目说明（本文件）
└── CHANGELOG.md            # 版本更新日志
```

## 技术栈与技术路线

### 核心技术
- **语言**：Python 3.8+
- **主要依赖**：
  - `cdsapi` - ECMWF CDS数据下载API客户端
  - `requests` - HTTP请求处理
  - `xarray` / `netCDF4` - 气象数据处理
  - `pandas` - 数据表格处理

### 技术架构
```
用户配置层 → API请求层 → 数据下载层 → 数据处理层
    ↓           ↓            ↓            ↓
  配置文件   CDS API认证   批量下载    格式转换/存储
```

### 技术路线
1. 使用ECMWF Climate Data Store (CDS) API进行数据请求
2. 支持多种气象数据集（ERA5、ERA5-Land等）
3. 提供YAML/JSON配置文件管理下载参数
4. 实现断点续传和并发下载
5. 支持多种输出格式（NetCDF、GRIB、CSV等）

## 当前状态

**版本**：0.0.1

**开发阶段**：初始化完成

项目已完成基础结构搭建，包括：
- Git仓库初始化
- 项目记忆组件配置
- 开发规划制定

## TODO

### 近期任务
- [ ] 配置Python开发环境
- [ ] 安装项目依赖（cdsapi、xarray等）
- [ ] 实现CDS API认证功能
- [ ] 实现单次数据下载功能
- [ ] 实现批量下载功能
- [ ] 添加配置文件支持
- [ ] 实现日志记录系统
- [ ] 编写单元测试

### 中期目标
- [ ] 支持更多ECMWF数据集类型
- [ ] 添加数据预处理功能（重采样、插值等）
- [ ] 开发命令行界面（CLI）
- [ ] 实现下载进度可视化
- [ ] 添加数据验证功能

### 长期规划
- [ ] 开发图形用户界面（GUI）
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
