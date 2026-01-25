"""
ECMWF下载器API抽象层

定义API客户端的统一接口和具体实现。
"""

from src.api.base import BaseAPIClient
from src.api.cds_client import CDSClient

__all__ = ["BaseAPIClient", "CDSClient"]
