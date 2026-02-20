"""
创建任务页面 - 服务模块

提供外部依赖的封装服务：
- SchemaService: 数据集 Schema 加载与约束更新
- ConfigStore: 配置文件保存与读取
- AIFillService: AI 参数生成
"""

from .schema_service import SchemaService, SchemaLoadResult
from .config_store import ConfigStore, ConfigMeta
from .ai_fill_service import AIFillService, AIFillResult

__all__ = [
    "SchemaService",
    "SchemaLoadResult",
    "ConfigStore",
    "ConfigMeta",
    "AIFillService",
    "AIFillResult",
]
