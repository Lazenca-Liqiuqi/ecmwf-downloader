# ECMWF Downloader

## 项目背景信息
ECMWF（European Centre for Medium-Range Weather Forecasts，欧洲中期天气预报中心）提供全球领先的气象数据和预报服务。本项目旨在开发一个Python工具，用于自动化下载和管理ECMWF的气象数据，支持气象研究、气候分析和业务应用。

## 目录结构
```
/home/pc/project/ECMWF downloader/
├── .claude/
│   ├── rules/              # 项目规则目录
│   ├── CLAUDE.md           # 项目提示词（本文件）
│   ├── LAST_CLAUDE_PROGRESS.md  # 工作进度
│   └── TASKS.json          # 任务清单
├── README.md               # 项目说明
└── CHANGELOG.md            # 更新日志
```

## 技术栈与技术路线
- **语言**：Python 3.x
- **主要依赖**：
  - `cdsapi`：ECMWF CDS数据下载API客户端
  - `requests`：HTTP请求处理
  - `xarray` / `netCDF4`：气象数据处理
  - `pandas`：数据表格处理
- **技术路线**：
  1. 使用ECMWF Climate Data Store (CDS) API下载数据
  2. 支持多种气象数据集（ERA5、ERA5-Land等）
  3. 提供配置化的请求参数管理
  4. 支持断点续传和批量下载

## 当前状态
项目初始化已完成，版本0.0.1。基础项目结构搭建完成，准备进入开发阶段。

## TODO
### 近期任务
1. 配置开发环境（Python虚拟环境、依赖安装）
2. 实现基础API连接功能
3. 实现单次数据下载功能
4. 实现批量下载功能
5. 实现配置文件管理
6. 添加日志记录功能
7. 编写单元测试

### 长期规划
1. 支持更多ECMWF数据集
2. 添加数据预处理功能
3. 开发命令行界面（CLI）
4. 添加图形用户界面（GUI）
5. 实现数据缓存机制
6. 添加下载进度可视化

## 资源
- [ECMWF Climate Data Store (CDS)](https://cds.climate.copernicus.eu/)
- [CDS API文档](https://cds.climate.copernicus.eu/api-how-to)
- [cdsapi Python库](https://pypi.org/project/cdsapi/)
