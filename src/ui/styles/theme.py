"""
ECMWF Downloader TUI 样式主题模块

专业数据仪表盘风格 - 深色主题 + 青色强调 + 精致细节
"""

# =============================================================================
# 全局 CSS 样式 - 专业数据仪表盘风格
# =============================================================================
GLOBAL_CSS = """
/* ═══════════════════════════════════════════════════════════════
   全局基础样式
   ═══════════════════════════════════════════════════════════════ */

Screen {
    background: $background 95%;
}

/* ═══════════════════════════════════════════════════════════════
   Header - 顶部导航栏（深色渐变效果）
   ═══════════════════════════════════════════════════════════════ */

Header {
    background: $primary;
    text-align: center;
    text-style: bold;
    padding: 0 2;
}

/* ═══════════════════════════════════════════════════════════════
   Footer - 底部状态栏
   ═══════════════════════════════════════════════════════════════ */

Footer {
    background: $panel;
    padding: 0 1;
}

/* ═══════════════════════════════════════════════════════════════
   首页容器 - 添加左边距
   ═══════════════════════════════════════════════════════════════ */

#home-container {
    padding: 1 1 1 4;
    margin-left: 2;
}

/* ═══════════════════════════════════════════════════════════════
   标题区域 - 层次化设计
   ═══════════════════════════════════════════════════════════════ */

#app-title {
    text-align: center;
    text-style: bold;
    color: $accent;
    margin-bottom: 0;
}

#app-subtitle {
    text-align: center;
    text-style: italic;
    margin-top: 0;
    margin-bottom: 2;
    color: $text 60%;
}

/* ═══════════════════════════════════════════════════════════════
   统计卡片区域 - 现代化卡片设计
   ═══════════════════════════════════════════════════════════════ */

#stats-container {
    height: 12;
    margin: 2 5 2 5;
    padding: 0 1;
}

.stat-card {
    width: 25%;
    height: 100%;
    border: solid $accent;
    padding: 1 1;
    margin: 0 0;
}

.stat-card:last-child {
    margin-right: 0;
}

.stat-card:hover {
    border: solid $primary;
}

.stat-label {
    text-align: center;
    text-style: bold;
    margin-bottom: 0;
    color: $text 80%;
}

.stat-value {
    text-align: center;
    text-style: bold;
    color: $accent;
    margin-top: 0;
}

/* ═══════════════════════════════════════════════════════════════
   快捷操作按钮区域 - 现代化按钮设计
   ═══════════════════════════════════════════════════════════════ */

#actions-container {
    height: 4;
    margin: 2 3 2 5;
    padding: 0 1;
}

Button {
    width: 1fr;
    margin: 0 1;
    padding: 0 2;
    border: wide;
}

/* ═══════════════════════════════════════════════════════════════
   最近任务区域
   ═══════════════════════════════════════════════════════════════ */

#recent-title {
    text-align: left;
    text-style: bold;
    margin-top: 2;
    margin-bottom: 1;
    margin-left: 2;
    color: $accent;
}

#recent-table {
    height: 16;
    border: solid $panel;
    margin: 0 3 0 5;
}

/* ═══════════════════════════════════════════════════════════════
   DataTable 通用样式 - 斑马纹和焦点
   ═══════════════════════════════════════════════════════════════ */

DataTable {
    border: solid $panel;
}

DataTable > DataTableCursor {
    background: $primary 40%;
    text-style: bold;
}

/* ═══════════════════════════════════════════════════════════════
   状态颜色 - 精心调配的语义化颜色
   ═══════════════════════════════════════════════════════════════ */

.status-pending {
    color: $text 50%;
    text-style: italic;
}

.status-downloading {
    color: $primary;
    text-style: bold;
}

.status-completed {
    color: $success;
    text-style: bold;
}

.status-failed {
    color: $error;
    text-style: bold;
}

.status-cancelled {
    color: $warning;
    text-style: bold;
}

.status-retrying {
    color: $accent;
    text-style: bold;
}

/* ═══════════════════════════════════════════════════════════════
   任务列表屏幕样式
   ═══════════════════════════════════════════════════════════════ */

#tasks-container {
    padding: 1 1 1 4;
    margin-left: 2;
}

#tasks-header {
    height: 3;
    margin-bottom: 1;
}

#tasks-title {
    text-align: left;
    text-style: bold;
    color: $accent;
    padding: 0 1;
    min-width: 20;
    margin-left: 2;
}

#search-input {
    width: 1fr;
    margin: 0 1 0 0;
    border: wide;
}

#filter-container {
    height: 3;
    margin: 0 3 1 5;
    padding: 0 1;
}

#filter-container Button {
    margin: 0 1;
    padding: 0 1;
}

#tasks-table {
    height: 18;
    border: solid $panel;
    margin: 0 3 0 5;
}

#actions-container Button {
    margin: 0 1;
    padding: 0 2;
}

/* 任务列表操作按钮容器 */
#actions-container {
    margin: 0 3 0 5;
}

/* ═══════════════════════════════════════════════════════════════
   通知/Toast 样式
   ═══════════════════════════════════════════════════════════════ */

Notification {
    background: $panel;
    border: tall $accent;
    padding: 1 2;
}
"""


# =============================================================================
# 首页专用样式 - 覆盖全局样式
# =============================================================================
HOME_CSS = """
/* 首页特有样式 */

/* 按钮悬停效果增强 */
Button:hover {
    text-style: bold;
}

/* 表格行悬停 */
DataTable:hover {
    border: solid $accent;
}
"""


# =============================================================================
# 任务列表专用样式
# =============================================================================
TASKS_CSS = """
/* 任务列表屏幕特有样式 */

/* 筛选按钮激活状态 */
#filter-container Button.-active {
    border: solid $accent;
    text-style: bold;
    color: $accent;
}

/* 搜索框聚焦 */
#search-input:focus {
    border: solid $accent;
}
"""


# =============================================================================
# 下载管理专用样式
# =============================================================================
DOWNLOAD_CSS = """
/* 下载管理屏幕特有样式 */

/* 下载容器 */
#download-container {
    padding: 1 1 1 4;
    margin-left: 2;
}

/* 标题 */
#download-title {
    text-align: left;
    text-style: bold;
    color: $accent;
    margin-top: 1;
    margin-bottom: 2;
    margin-left: 2;
}

/* 进度区域 */
#progress-section {
    height: 8;
    margin: 1 3 1 5;
    padding: 1 1;
}

#progress-label {
    text-align: left;
    text-style: bold;
    margin-bottom: 1;
    color: $text 80%;
}

#overall-progress {
    width: 1fr;
    margin: 0 0;
}

#progress-stats {
    height: 2;
    margin-top: 1;
}

#progress-stats Label {
    width: 1fr;
    text-align: center;
}

/* 活动任务区域 */
#active-tasks-section {
    height: 16;
    margin: 1 3 1 5;
    padding: 0 1;
}

#active-label {
    text-align: left;
    text-style: bold;
    margin-bottom: 1;
    color: $text 80%;
}

#active-table {
    height: 1fr;
    border: solid $panel;
}

/* 控制按钮区域 */
#control-section {
    height: 3;
    margin: 1 3 1 5;
    padding: 0 1;
}

#control-section Button {
    width: 1fr;
    margin: 0 1;
    padding: 0 1;
}
"""


# =============================================================================
# 组件样式常量（供 Python 代码使用）
# =============================================================================

# 状态颜色映射（优化后的配色方案）
STATUS_COLORS = {
    "pending": "grey",
    "downloading": "cyan",
    "completed": "green",
    "failed": "red",
    "cancelled": "yellow",
    "retrying": "magenta",
}

# CSS 类名映射
STATUS_CSS_CLASSES = {
    "pending": "status-pending",
    "downloading": "status-downloading",
    "completed": "status-completed",
    "failed": "status-failed",
    "cancelled": "status-cancelled",
    "retrying": "status-retrying",
}


# =============================================================================
# 主题获取函数
# =============================================================================

def get_global_styles() -> str:
    """获取全局 CSS 样式

    Returns:
        str: 全局 CSS 样式字符串
    """
    return GLOBAL_CSS


def get_home_styles() -> str:
    """获取首页专用 CSS 样式

    Returns:
        str: 首页 CSS 样式字符串
    """
    return HOME_CSS


def get_tasks_styles() -> str:
    """获取任务列表屏幕专用 CSS 样式

    Returns:
        str: 任务列表 CSS 样式字符串
    """
    return TASKS_CSS


def get_download_styles() -> str:
    """获取下载管理屏幕专用 CSS 样式

    Returns:
        str: 下载管理 CSS 样式字符串
    """
    return DOWNLOAD_CSS


def get_status_color(status: str) -> str:
    """获取状态对应的颜色

    Args:
        status: 任务状态（pending/downloading/completed/failed/cancelled/retrying）

    Returns:
        str: Textual 颜色标识
    """
    return STATUS_COLORS.get(status, "white")


def get_status_css_class(status: str) -> str:
    """获取状态对应的 CSS 类名

    Args:
        status: 任务状态（pending/downloading/completed/failed/cancelled/retrying）

    Returns:
        str: CSS 类名
    """
    return STATUS_CSS_CLASSES.get(status, "")


# =============================================================================
# 主题配置（多主题支持）
# =============================================================================

THEME_CONFIGS = {
    "dashboard": {
        "name": "专业数据仪表盘",
        "description": "深色主题，青色强调，适合长时间使用的专业数据工具界面",
        "style": "dark",
        "primary_accent": "cyan",
    },
}


def get_available_themes() -> list:
    """获取可用主题列表

    Returns:
        list: 主题标识符列表
    """
    return list(THEME_CONFIGS.keys())


def get_theme_info(theme_id: str) -> dict:
    """获取主题信息

    Args:
        theme_id: 主题标识符

    Returns:
        dict: 主题信息字典（包含 name 和 description）
    """
    return THEME_CONFIGS.get(theme_id, THEME_CONFIGS["dashboard"])
