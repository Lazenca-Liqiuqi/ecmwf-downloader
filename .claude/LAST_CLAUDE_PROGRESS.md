## 项目概况
ECMWF Downloader是一个用于下载ECMWF（欧洲中期天气预报中心）气象数据的Python工具。项目正在进行GUI改造，将现有的命令行脚本改造为功能完整的桌面应用程序。

## 工作任务
本次对话继续推进第一阶段（核心模块重构）的开发工作，完成了2个API模块的实现：
1. 创建API抽象基类
2. 实现CDS API客户端

## 工作内容

### 任务#6：创建API抽象基类 ✅
创建 `src/api/base.py`（185行），定义API客户端抽象接口：

**BaseAPIClient抽象基类**：
- `download()` - 下载数据的抽象方法
- `check_connection()` - 检查连接状态的抽象方法
- `get_available_datasets()` - 获取可用数据集列表的抽象方法
- `get_dataset_variables()` - 获取数据集变量的抽象方法
- `get_request_info()` - 获取请求元信息的抽象方法

**具体方法**（提供默认实现）：
- `validate_params()` - 验证请求参数有效性
- `get_client_info()` - 获取客户端信息
- `__repr__()` - 字符串表示

**设计理念**：
- 接口隔离：上层模块（下载引擎）只需依赖此抽象接口
- 可扩展性：新增数据源只需实现此接口，无需修改上层代码
- 可测试性：可以创建Mock客户端用于单元测试

### 任务#7：实现CDS API客户端 ✅
创建 `src/api/cds_client.py`（370行），实现CDS API客户端：

**CDSClient类**（继承BaseAPIClient）：
- 使用cdsapi.Client实现API调用
- 支持uid/key认证方式
- 延迟创建客户端（支持账号切换）
- 自动禁用系统代理（CDS API要求）

**核心方法实现**：
- `download()` - 实现下载数据方法，自动构建请求参数
- `check_connection()` - 检查API连接状态
- `get_available_datasets()` - 返回5个ERA5数据集列表
- `get_dataset_variables()` - 返回支持的数据变量
- `get_request_info()` - 获取下载请求的元信息

**辅助方法**：
- `_build_request()` - 构建CDS API请求参数（年/月/日/时间/气压层等）
- `_generate_output_path()` - 生成输出文件路径
- `_handle_error()` - 统一错误处理（解析401/403/404/timeout等）
- `_disable_proxy()` - 禁用系统代理环境变量

**支持的数据集**：
1. reanalysis-era5-pressure-levels（首期支持）
2. reanalysis-era5-single-levels
3. reanalysis-era5-land
4. reanalysis-era5-land-monthly-means
5. reanalysis-era5-monthly-means

**配置参数**：
- 支持自定义网格分辨率（默认 [2.5, 2]）
- 支持自定义数据格式（默认 netcdf）
- 支持自定义区域范围
- 支持自定义气压层
- 超时设置：30分钟

## 交付物
- `src/api/__init__.py` - API模块初始化文件（11行）
- `src/api/base.py` - API抽象基类（185行）
- `src/api/cds_client.py` - CDS API客户端实现（370行）
- 共566行API层代码

## 状态变动
- **版本**：v0.0.1（初始化阶段）
- **项目阶段**：第一阶段（核心模块重构）进行中
- **任务进度**：7/9 已完成（78%）
- **Git状态**：有未提交更改

## 待办任务
- #8: 创建配置文件模板
- #9: 编写核心模块单元测试

## 工具
- **工具**：Task、Write、Read、Edit
- **框架**：abc（抽象基类）、cdsapi（CDS客户端）
- **模式**：策略模式（抽象接口）、模板方法（基类定义流程）
- **规范参考**：项目记忆skill、GUI改造计划文档
