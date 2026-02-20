"""
配置初始化模块

在应用启动时检查配置文件是否存在，如果不存在则从 example 文件复制。
"""

import shutil
from pathlib import Path
from typing import List, Tuple

# 配置文件定义：(目标文件名, example 文件名)
CONFIG_FILES: List[Tuple[str, str]] = [
    ("default_config.yaml", "default_config.yaml.example"),
    ("accounts.yaml", "accounts.yaml.example"),
    ("ai_config.yaml", "ai_config.yaml.example"),
]


def get_config_dir() -> Path:
    """获取配置文件目录路径

    Returns:
        Path: 配置目录的绝对路径
    """
    # 配置目录相对于项目根目录
    # src/utils/config_initializer.py -> ../../.. -> 项目根目录
    return Path(__file__).parent.parent.parent / "config"


def ensure_config_files() -> List[str]:
    """确保所有配置文件存在

    检查配置目录下的文件，如果不存在则从对应的 example 文件复制。

    Returns:
        List[str]: 创建的配置文件列表
    """
    config_dir = get_config_dir()
    created_files = []

    # 确保配置目录存在
    config_dir.mkdir(parents=True, exist_ok=True)

    for target_file, example_file in CONFIG_FILES:
        target_path = config_dir / target_file
        example_path = config_dir / example_file

        # 如果目标文件已存在，跳过
        if target_path.exists():
            continue

        # 如果 example 文件存在，复制它
        if example_path.exists():
            shutil.copy2(example_path, target_path)
            created_files.append(target_file)
        else:
            # example 文件不存在，记录警告
            print(f"警告: example 文件不存在: {example_path}")

    return created_files


def initialize_config() -> bool:
    """初始化配置

    在应用启动时调用，确保所有必要的配置文件都存在。

    Returns:
        bool: 是否创建了新的配置文件
    """
    created = ensure_config_files()

    if created:
        print(f"已创建配置文件: {', '.join(created)}")
        return True

    return False
