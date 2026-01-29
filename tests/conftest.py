"""
pytest全局配置文件

提供项目级别的共享配置和fixtures。
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


def pytest_configure(config):
    """pytest配置钩子

    在测试会话开始时执行，用于配置全局测试参数。
    """
    # 可以在这里添加自定义的pytest标记
    config.addinivalue_line(
        "markers", "slow: 标记运行较慢的测试"
    )
    config.addinivalue_line(
        "markers", "integration: 标记集成测试"
    )
    config.addinivalue_line(
        "markers", "unit: 标记单元测试"
    )
