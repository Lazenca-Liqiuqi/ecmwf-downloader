"""
TUI 样式模块

包含样式定义和主题配置。
"""

from src.ui.styles.theme import (
    get_global_styles,
    get_home_styles,
    get_tasks_styles,
    get_status_color,
    get_status_css_class,
    get_available_themes,
    get_theme_info,
    STATUS_COLORS,
    STATUS_CSS_CLASSES,
)

__all__ = [
    "get_global_styles",
    "get_home_styles",
    "get_tasks_styles",
    "get_status_color",
    "get_status_css_class",
    "get_available_themes",
    "get_theme_info",
    "STATUS_COLORS",
    "STATUS_CSS_CLASSES",
]
