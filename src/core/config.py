"""
ECMWF下载器配置模型

使用Pydantic定义所有配置数据模型，提供类型安全和自动验证功能。
"""

from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class DatasetType(str, Enum):
    """支持的数据集类型枚举

    首期仅支持ERA5 Pressure Levels，后续可扩展其他数据集。
    """

    ERA5_PRESSURE_LEVELS = "reanalysis-era5-pressure-levels"
    # 预留：未来可以添加更多数据集
    # ERA5_SINGLE_LEVELS = "reanalysis-era5-single-levels"
    # ERA5_LAND = "reanalysis-era5-land"
    # ERA5_LAND_MONTHLY = "reanalysis-era5-land-monthly-means"


class AccountStatus(str, Enum):
    """账号状态枚举"""

    ACTIVE = "active"  # 可用
    FAILED = "failed"  # 失败（暂时禁用）
    DISABLED = "disabled"  # 禁用（手动关闭）


class AccountInfo(BaseModel):
    """单个账号信息模型

    用于账号池管理，记录每个API账号的配置和状态。
    """

    id: str = Field(..., description="账号唯一标识符")
    uid: str = Field(..., description="ECMWF用户ID")
    key: str = Field(..., description="ECMWF API密钥")
    status: AccountStatus = Field(default=AccountStatus.ACTIVE, description="账号状态")
    url: str = Field(default="https://cds.climate.copernicus.eu/api", description="CDS API地址")
    used_count: int = Field(default=0, description="已使用次数", ge=0)
    last_used: Optional[str] = Field(default=None, description="最后使用时间（ISO格式）")
    fail_count: int = Field(default=0, description="连续失败次数", ge=0)

    class Config:
        """Pydantic配置"""

        use_enum_values = True


class AccountPoolConfig(BaseModel):
    """账号池配置模型

    管理多个API账号的配置集合。
    """

    accounts: List[AccountInfo] = Field(default_factory=list, description="账号列表")
    auto_disable_threshold: int = Field(
        default=5, description="连续失败多少次后自动禁用账号", ge=1
    )

    @field_validator("accounts")
    @classmethod
    def validate_accounts_unique(cls, v: List[AccountInfo]) -> List[AccountInfo]:
        """验证账号ID唯一性"""
        ids = [account.id for account in v]
        if len(ids) != len(set(ids)):
            raise ValueError("账号ID必须唯一")
        return v

    def get_active_accounts(self) -> List[AccountInfo]:
        """获取所有可用账号"""
        return [acc for acc in self.accounts if acc.status == AccountStatus.ACTIVE]


class ConcurrencyConfig(BaseModel):
    """并发下载配置模型

    控制批量下载时的并发行为。
    """

    batch_size: int = Field(default=4, description="每批处理的任务数", ge=1, le=10)
    max_workers: int = Field(default=4, description="最大并发线程数", ge=1, le=16)
    batch_delay: float = Field(default=1.0, description="批次间延迟（秒）", ge=0)
    max_retries: int = Field(default=3, description="单个任务最大重试次数", ge=0, le=10)
    retry_delay: float = Field(default=5.0, description="重试延迟（秒）", ge=0)


class DownloadConfig(BaseModel):
    """下载任务配置模型

    定义单个下载任务的所有参数。
    """

    # 数据集配置
    dataset: DatasetType = Field(
        default=DatasetType.ERA5_PRESSURE_LEVELS, description="数据集类型"
    )
    variables: List[str] = Field(..., description="要下载的变量列表")

    # 时间配置
    years: List[int] = Field(..., description="年份列表")
    months: List[int] = Field(..., description="月份列表（1-12）")
    days: Optional[List[int]] = Field(default=None, description="日期列表（1-31）")
    times: Optional[List[str]] = Field(
        default=None,
        description="时间点列表（如['00:00', '06:00', '12:00', '18:00']）",
    )

    # 空间配置
    pressure_levels: Optional[List[int]] = Field(
        default=None, description="气压层列表（仅用于pressure levels数据集）"
    )
    area: Optional[List[float]] = Field(
        default=None, description="区域范围[N, W, S, E]"
    )

    # 输出配置
    output_dir: Path = Field(..., description="输出目录路径")
    output_format: str = Field(default="netcdf", description="输出文件格式")

    @field_validator("years")
    @classmethod
    def validate_years(cls, v: List[int]) -> List[int]:
        """验证年份范围"""
        current_year = 2024  # TODO: 从datetime获取
        for year in v:
            if year < 1940 or year > current_year:
                raise ValueError(f"年份必须在1940-{current_year}之间: {year}")
        return sorted(v)

    @field_validator("months")
    @classmethod
    def validate_months(cls, v: List[int]) -> List[int]:
        """验证月份范围"""
        for month in v:
            if month < 1 or month > 12:
                raise ValueError(f"月份必须在1-12之间: {month}")
        return sorted(v)

    @field_validator("days")
    @classmethod
    def validate_days(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        """验证日期范围"""
        if v is None:
            return v
        for day in v:
            if day < 1 or day > 31:
                raise ValueError(f"日期必须在1-31之间: {day}")
        return sorted(v)

    @field_validator("pressure_levels")
    @classmethod
    def validate_pressure_levels(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        """验证气压层范围"""
        if v is None:
            return v
        valid_levels = [1, 2, 3, 5, 7, 10, 20, 30, 50, 70, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 775, 800, 825, 850, 875, 900, 925, 950, 975, 1000]
        for level in v:
            if level not in valid_levels:
                raise ValueError(f"无效的气压层: {level}")
        return sorted(v)

    @field_validator("area")
    @classmethod
    def validate_area(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        """验证区域范围格式"""
        if v is None:
            return v
        if len(v) != 4:
            raise ValueError("区域范围必须包含4个值[N, W, S, E]")
        n, w, s, e = v
        if not (-90 <= s <= n <= 90):
            raise ValueError(f"纬度范围无效: N={n}, S={s}")
        if not (-180 <= w <= e <= 180):
            raise ValueError(f"经度范围无效: W={w}, E={e}")
        return v

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, v: Path) -> Path:
        """验证并创建输出目录"""
        if isinstance(v, str):
            v = Path(v)
        # 创建目录（如果不存在）
        v.mkdir(parents=True, exist_ok=True)
        return v


class ProgressConfig(BaseModel):
    """进度管理配置模型"""

    enabled: bool = Field(default=True, description="是否启用进度保存")
    file_path: Path = Field(default="download_progress.json", description="进度文件路径")
    auto_save_interval: int = Field(default=5, description="自动保存间隔（秒）", ge=1)


class LoggingConfig(BaseModel):
    """日志配置模型"""

    level: str = Field(default="INFO", description="日志级别")
    file_path: Optional[Path] = Field(default=None, description="日志文件路径")
    console_output: bool = Field(default=True, description="是否输出到控制台")
    max_bytes: int = Field(default=10485760, description="日志文件最大大小（10MB）", ge=1)
    backup_count: int = Field(default=3, description="保留的日志备份数量", ge=0)


class AppConfig(BaseModel):
    """应用总配置模型

    整合所有配置模块，作为应用的配置入口。
    """

    download: DownloadConfig = Field(..., description="下载任务配置")
    account_pool: AccountPoolConfig = Field(..., description="账号池配置")
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig, description="并发配置")
    progress: ProgressConfig = Field(default_factory=ProgressConfig, description="进度管理配置")
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="日志配置")

    class Config:
        """Pydantic配置"""

        # 允许从别名加载字段
        populate_by_name = True
        # 使用枚举值而非枚举对象
        use_enum_values = True

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """从字典创建配置对象"""
        return cls(**data)

    def to_dict(self) -> dict:
        """转换为字典"""
        return self.model_dump()
