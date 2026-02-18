# Codex 编码请求：修复 Path 对象 JSON 序列化问题

## 项目基本信息

- **项目名称**：ECMWF Downloader
- **项目类型**：Python TUI 应用（Textual 框架）
- **当前阶段**：第五阶段（下载功能集成）进行中

## 问题描述

**错误1**：保存进度时失败
```
ProgressSaveError: 保存进度文件失败: Object of type WindowsPath is not JSON serializable
```

**错误2**：加载进度时失败（文件已损坏）
```
ProgressLoadError: 进度文件JSON格式错误: Expecting value: line 44 column 26 (char 1016)
```

## 根因分析

`src/core/task_service.py` 第 192 行：
```python
return {
    ...
    "output_path": Path(request.output_path),  # ❌ Path 对象无法 JSON 序列化
    ...
}
```

`download_params` 字典中的 `output_path` 是 `Path` 对象，被存储到 `TaskInfo.metadata` 中，
然后 `ProgressManager.save()` 使用 `json.dump()` 保存时失败。

## 修复方案

### 方案1：在存储时转为字符串（推荐）

修改 `task_service.py` 第 192 行：
```python
# 修改前
"output_path": Path(request.output_path),

# 修改后
"output_path": str(request.output_path),
```

### 方案2：确保使用方能正确处理

检查 `src/ui/workers/download_worker.py` 和 `src/api/cds_client.py`，
确保它们能接受字符串类型的路径（通常会自动转换，无需修改）。

## 上下文信息

### task_service.py 关键代码

```python
@staticmethod
def _build_download_params(request: DownloadRequest) -> Dict[str, Any]:
    """构建可直接用于CDSClient.download的参数字典。"""
    ...
    return {
        "dataset": request.dataset,
        ...
        "output_path": Path(request.output_path),  # ⭐ 需要修改这里
        ...
    }
```

### CDSClient.download() 签名

需要检查 `cds_client.py` 中 `download()` 方法是否接受字符串路径。

## 交付物

1. 修改 `src/core/task_service.py` 第 192 行，将 `Path(...)` 改为 `str(...)`
2. 验证语法正确
3. 如果 cds_client.py 或 download_worker.py 需要适配，一并修改

## 验收标准

1. ✅ 创建任务后能正常保存到 JSON 文件
2. ✅ 重新打开应用能正常加载进度文件
3. ✅ 下载功能仍然正常工作（路径能被正确解析）
