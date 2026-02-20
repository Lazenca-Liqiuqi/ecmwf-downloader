"""
配置存储服务

封装配置文件的保存与读取操作。
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConfigMeta:
    """配置文件元信息

    Attributes:
        name: 配置名称（文件名不含扩展名）
        path: 完整文件路径
        modified_time: 最后修改时间戳
    """
    name: str
    path: Path
    modified_time: float


class ConfigStore:
    """配置存储服务

    负责配置文件的保存、读取和列表操作。

    使用示例:
        store = ConfigStore("./data/configs")
        store.save("my_config", config_data)
        configs = store.list_configs()
        data = store.load(configs[0].path)
    """

    def __init__(self, config_dir: str = "./data/configs"):
        """初始化配置存储服务

        Args:
            config_dir: 配置文件存储目录
        """
        self._config_dir = Path(config_dir)
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """确保配置目录存在"""
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, name: str) -> str:
        """将名称转换为安全的文件名

        只保留字母、数字、连字符和下划线。

        Args:
            name: 原始名称

        Returns:
            安全的文件名
        """
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    def list_configs(self) -> List[ConfigMeta]:
        """列出所有已保存的配置

        按修改时间降序排列（最新在前）。

        Returns:
            配置元信息列表
        """
        config_files = list(self._config_dir.glob("*.json"))

        configs = []
        for f in config_files:
            configs.append(ConfigMeta(
                name=f.stem,
                path=f,
                modified_time=f.stat().st_mtime,
            ))

        # 按修改时间降序排列
        configs.sort(key=lambda c: c.modified_time, reverse=True)
        return configs

    def save(self, name: str, data: Dict[str, Any]) -> Path:
        """保存配置到文件

        使用原子写入策略（先写临时文件，再替换）确保数据安全。

        Args:
            name: 配置名称
            data: 配置数据

        Returns:
            保存的文件路径

        Raises:
            IOError: 保存失败
        """
        safe_name = self._safe_name(name)
        config_file = self._config_dir / f"{safe_name}.json"
        temp_file = self._config_dir / f"{safe_name}.json.tmp"

        try:
            config_json = json.dumps(data, indent=2, ensure_ascii=False)
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(config_json)
            temp_file.replace(config_file)
            return config_file
        except Exception as e:
            # 清理临时文件
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as cleanup_error:
                logger.warning("清理临时配置文件失败: %s", cleanup_error)
            raise IOError(f"保存配置失败: {str(e)}") from e

    def load(self, path: Path) -> Dict[str, Any]:
        """从文件加载配置

        Args:
            path: 配置文件路径

        Returns:
            配置数据字典

        Raises:
            FileNotFoundError: 文件不存在
            json.JSONDecodeError: JSON 解析失败
        """
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def delete(self, name: str) -> bool:
        """删除配置文件

        Args:
            name: 配置名称

        Returns:
            是否删除成功
        """
        safe_name = self._safe_name(name)
        config_file = self._config_dir / f"{safe_name}.json"

        try:
            if config_file.exists():
                config_file.unlink()
                return True
            return False
        except Exception:
            logger.exception("删除配置文件失败: %s", config_file)
            return False

    def exists(self, name: str) -> bool:
        """检查配置是否存在

        Args:
            name: 配置名称

        Returns:
            是否存在
        """
        safe_name = self._safe_name(name)
        config_file = self._config_dir / f"{safe_name}.json"
        return config_file.exists()

    def get_path(self, name: str) -> Path:
        """获取配置文件路径

        Args:
            name: 配置名称

        Returns:
            配置文件路径
        """
        safe_name = self._safe_name(name)
        return self._config_dir / f"{safe_name}.json"
