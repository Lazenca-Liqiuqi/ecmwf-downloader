"""
ECMWF下载器配置模型单元测试

测试Pydantic配置模型的验证和序列化功能。
"""

from pathlib import Path
from typing import List
import pytest
import tempfile
import shutil

from pydantic import ValidationError

from src.core.config import (
    DatasetType,
    AccountStatus,
    AccountInfo,
    AccountPoolConfig,
    ConcurrencyConfig,
    DownloadConfig,
    ProgressConfig,
    LoggingConfig,
    AppConfig,
)


class TestDatasetType:
    """测试DatasetType枚举"""

    def test_era5_pressure_levels_value(self):
        """测试ERA5气压层数据集枚举值"""
        assert DatasetType.ERA5_PRESSURE_LEVELS == "reanalysis-era5-pressure-levels"


class TestAccountStatus:
    """测试AccountStatus枚举"""

    def test_active_value(self):
        """测试ACTIVE状态值"""
        assert AccountStatus.ACTIVE == "active"

    def test_failed_value(self):
        """测试FAILED状态值"""
        assert AccountStatus.FAILED == "failed"

    def test_disabled_value(self):
        """测试DISABLED状态值"""
        assert AccountStatus.DISABLED == "disabled"


class TestAccountInfo:
    """测试AccountInfo模型"""

    def test_create_with_required_fields(self):
        """测试使用必填字段创建账号信息"""
        account = AccountInfo(
            id="account_1",
            uid="test_uid",
            key="test_key"
        )
        assert account.id == "account_1"
        assert account.uid == "test_uid"
        assert account.key == "test_key"
        assert account.status == AccountStatus.ACTIVE  # 默认值
        assert account.url == "https://cds.climate.copernicus.eu/api"  # 默认值
        assert account.used_count == 0  # 默认值
        assert account.fail_count == 0  # 默认值

    def test_create_with_all_fields(self):
        """测试使用所有字段创建账号信息"""
        account = AccountInfo(
            id="account_2",
            uid="another_uid",
            key="another_key",
            status=AccountStatus.DISABLED,
            url="https://custom.api.com",
            used_count=10,
            last_used="2024-01-25T12:00:00",
            fail_count=3
        )
        assert account.id == "account_2"
        assert account.status == AccountStatus.DISABLED
        assert account.used_count == 10
        assert account.fail_count == 3

    def test_used_count_validation_positive(self):
        """测试used_count必须非负"""
        with pytest.raises(ValidationError):
            AccountInfo(
                id="account_1",
                uid="uid",
                key="key",
                used_count=-1
            )

    def test_fail_count_validation_positive(self):
        """测试fail_count必须非负"""
        with pytest.raises(ValidationError):
            AccountInfo(
                id="account_1",
                uid="uid",
                key="key",
                fail_count=-1
            )


class TestAccountPoolConfig:
    """测试AccountPoolConfig模型"""

    def test_create_empty_accounts_list(self):
        """测试创建空账号列表"""
        config = AccountPoolConfig(accounts=[])
        assert config.accounts == []
        assert config.auto_disable_threshold == 5  # 默认值

    def test_create_with_accounts(self):
        """测试创建包含账号的配置"""
        accounts = [
            AccountInfo(id="acc1", uid="uid1", key="key1"),
            AccountInfo(id="acc2", uid="uid2", key="key2"),
        ]
        config = AccountPoolConfig(accounts=accounts)
        assert len(config.accounts) == 2

    def test_unique_account_ids(self):
        """测试账号ID必须唯一"""
        accounts = [
            AccountInfo(id="acc1", uid="uid1", key="key1"),
            AccountInfo(id="acc1", uid="uid2", key="key2"),  # 重复ID
        ]
        with pytest.raises(ValidationError, match="账号ID必须唯一"):
            AccountPoolConfig(accounts=accounts)

    def test_auto_disable_threshold_default(self):
        """测试auto_disable_threshold默认值"""
        config = AccountPoolConfig(accounts=[])
        assert config.auto_disable_threshold == 5

    def test_auto_disable_threshold_validation(self):
        """测试auto_disable_threshold必须>=1"""
        with pytest.raises(ValidationError):
            AccountPoolConfig(accounts=[], auto_disable_threshold=0)

    def test_get_active_accounts(self):
        """测试获取可用账号"""
        accounts = [
            AccountInfo(id="acc1", uid="uid1", key="key1", status=AccountStatus.ACTIVE),
            AccountInfo(id="acc2", uid="uid2", key="key2", status=AccountStatus.DISABLED),
            AccountInfo(id="acc3", uid="uid3", key="key3", status=AccountStatus.ACTIVE),
        ]
        config = AccountPoolConfig(accounts=accounts)
        active = config.get_active_accounts()
        assert len(active) == 2
        assert active[0].id == "acc1"
        assert active[1].id == "acc3"


class TestConcurrencyConfig:
    """测试ConcurrencyConfig模型"""

    def test_default_values(self):
        """测试默认值"""
        config = ConcurrencyConfig()
        assert config.batch_size == 4
        assert config.max_workers == 4
        assert config.batch_delay == 1.0
        assert config.max_retries == 3
        assert config.retry_delay == 5.0

    def test_batch_size_validation(self):
        """测试batch_size范围验证（1-10）"""
        # 有效值
        ConcurrencyConfig(batch_size=1)
        ConcurrencyConfig(batch_size=10)

        # 无效值
        with pytest.raises(ValidationError):
            ConcurrencyConfig(batch_size=0)
        with pytest.raises(ValidationError):
            ConcurrencyConfig(batch_size=11)

    def test_max_workers_validation(self):
        """测试max_workers范围验证（1-16）"""
        # 有效值
        ConcurrencyConfig(max_workers=1)
        ConcurrencyConfig(max_workers=16)

        # 无效值
        with pytest.raises(ValidationError):
            ConcurrencyConfig(max_workers=0)
        with pytest.raises(ValidationError):
            ConcurrencyConfig(max_workers=17)

    def test_max_retries_validation(self):
        """测试max_retries范围验证（0-10）"""
        # 有效值
        ConcurrencyConfig(max_retries=0)
        ConcurrencyConfig(max_retries=10)

        # 无效值
        with pytest.raises(ValidationError):
            ConcurrencyConfig(max_retries=-1)
        with pytest.raises(ValidationError):
            ConcurrencyConfig(max_retries=11)


class TestDownloadConfig:
    """测试DownloadConfig模型"""

    def test_create_with_required_fields(self, tmp_path):
        """测试使用必填字段创建下载配置"""
        config = DownloadConfig(
            variables=["temperature", "geopotential"],
            years=[2023],
            months=[1, 2, 3],
            output_dir=tmp_path
        )
        assert config.dataset == DatasetType.ERA5_PRESSURE_LEVELS  # 默认
        assert config.variables == ["temperature", "geopotential"]
        assert config.years == [2023]
        assert config.months == [1, 2, 3]

    def test_years_sorted_and_validated(self, tmp_path):
        """测试年份排序和验证"""
        config = DownloadConfig(
            variables=["temperature"],
            years=[2023, 2021, 2022],  # 无序输入
            months=[1],
            output_dir=tmp_path
        )
        assert config.years == [2021, 2022, 2023]  # 已排序

    def test_years_validation_invalid(self, tmp_path):
        """测试年份范围验证（1940-当前年）"""
        with pytest.raises(ValidationError, match="年份必须在1940-"):
            DownloadConfig(
                variables=["temperature"],
                years=[1800],  # 太早
                months=[1],
                output_dir=tmp_path
            )

        with pytest.raises(ValidationError, match="年份必须在1940-"):
            DownloadConfig(
                variables=["temperature"],
                years=[2100],  # 太晚
                months=[1],
                output_dir=tmp_path
            )

    def test_months_sorted_and_validated(self, tmp_path):
        """测试月份排序和验证"""
        config = DownloadConfig(
            variables=["temperature"],
            years=[2023],
            months=[3, 1, 2],  # 无序输入
            output_dir=tmp_path
        )
        assert config.months == [1, 2, 3]  # 已排序

    def test_months_validation_invalid(self, tmp_path):
        """测试月份范围验证（1-12）"""
        with pytest.raises(ValidationError, match="月份必须在1-12之间"):
            DownloadConfig(
                variables=["temperature"],
                years=[2023],
                months=[0],
                output_dir=tmp_path
            )

        with pytest.raises(ValidationError, match="月份必须在1-12之间"):
            DownloadConfig(
                variables=["temperature"],
                years=[2023],
                months=[13],
                output_dir=tmp_path
            )

    def test_days_validation(self, tmp_path):
        """测试日期验证"""
        # 有效日期
        config = DownloadConfig(
            variables=["temperature"],
            years=[2023],
            months=[1],
            days=[1, 15, 31],
            output_dir=tmp_path
        )
        assert config.days == [1, 15, 31]

        # 无效日期
        with pytest.raises(ValidationError, match="日期必须在1-31之间"):
            DownloadConfig(
                variables=["temperature"],
                years=[2023],
                months=[1],
                days=[0],
                output_dir=tmp_path
            )

    def test_pressure_levels_validation(self, tmp_path):
        """测试气压层验证"""
        # 有效气压层
        valid_levels = [500, 850, 1000]
        config = DownloadConfig(
            variables=["temperature"],
            years=[2023],
            months=[1],
            pressure_levels=valid_levels,
            output_dir=tmp_path
        )
        assert config.pressure_levels == [500, 850, 1000]

        # 无效气压层
        with pytest.raises(ValidationError, match="无效的气压层"):
            DownloadConfig(
                variables=["temperature"],
                years=[2023],
                months=[1],
                pressure_levels=[1500],  # 不在有效列表中
                output_dir=tmp_path
            )

    def test_area_validation(self, tmp_path):
        """测试区域范围验证"""
        # 有效区域 [N, W, S, E]
        config = DownloadConfig(
            variables=["temperature"],
            years=[2023],
            months=[1],
            area=[55, 70, 15, 140],
            output_dir=tmp_path
        )
        assert config.area == [55, 70, 15, 140]

        # 元素数量错误
        with pytest.raises(ValidationError, match="区域范围必须包含4个值"):
            DownloadConfig(
                variables=["temperature"],
                years=[2023],
                months=[1],
                area=[55, 70, 15],
                output_dir=tmp_path
            )

        # 纬度范围无效
        with pytest.raises(ValidationError, match="纬度范围无效"):
            DownloadConfig(
                variables=["temperature"],
                years=[2023],
                months=[1],
                area=[15, 70, 55, 140],  # S > N
                output_dir=tmp_path
            )

        # 经度范围无效
        with pytest.raises(ValidationError, match="经度范围无效"):
            DownloadConfig(
                variables=["temperature"],
                years=[2023],
                months=[1],
                area=[55, 140, 15, 70],  # W > E
                output_dir=tmp_path
            )

    def test_output_dir_creation(self, tmp_path):
        """测试输出目录自动创建"""
        output_dir = tmp_path / "subdir" / "nested"
        config = DownloadConfig(
            variables=["temperature"],
            years=[2023],
            months=[1],
            output_dir=output_dir
        )
        assert output_dir.exists()
        assert config.output_dir == output_dir

    def test_output_dir_string_conversion(self, tmp_path):
        """测试输出目录字符串转换"""
        config = DownloadConfig(
            variables=["temperature"],
            years=[2023],
            months=[1],
            output_dir=str(tmp_path)
        )
        assert isinstance(config.output_dir, Path)


class TestProgressConfig:
    """测试ProgressConfig模型"""

    def test_default_values(self):
        """测试默认值"""
        config = ProgressConfig()
        assert config.enabled is True
        # Pydantic v2会自动将字符串默认值转换为Path类型
        # 如果没有转换，则检查字符串值
        actual_path = config.file_path
        expected_path = "download_progress.json"
        assert str(actual_path) == expected_path or actual_path == expected_path
        assert config.auto_save_interval == 5

    def test_auto_save_interval_validation(self):
        """测试auto_save_interval必须>=1"""
        with pytest.raises(ValidationError):
            ProgressConfig(auto_save_interval=0)


class TestLoggingConfig:
    """测试LoggingConfig模型"""

    def test_default_values(self):
        """测试默认值"""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.file_path is None
        assert config.console_output is True
        assert config.max_bytes == 10485760  # 10MB
        assert config.backup_count == 3

    def test_max_bytes_validation(self):
        """测试max_bytes必须>=1"""
        with pytest.raises(ValidationError):
            LoggingConfig(max_bytes=0)

    def test_backup_count_validation(self):
        """测试backup_count必须>=0"""
        # 有效值
        LoggingConfig(backup_count=0)
        LoggingConfig(backup_count=10)

        # 无效值
        with pytest.raises(ValidationError):
            LoggingConfig(backup_count=-1)


class TestAppConfig:
    """测试AppConfig模型"""

    def test_create_from_dict(self, tmp_path):
        """测试从字典创建配置"""
        data = {
            "download": {
                "dataset": "reanalysis-era5-pressure-levels",
                "variables": ["temperature"],
                "years": [2023],
                "months": [1],
                "output_dir": str(tmp_path)
            },
            "account_pool": {
                "accounts": [
                    {
                        "id": "acc1",
                        "uid": "uid1",
                        "key": "key1"
                    }
                ]
            }
        }
        config = AppConfig.from_dict(data)
        assert isinstance(config, AppConfig)
        assert config.download.variables == ["temperature"]
        assert len(config.account_pool.accounts) == 1

    def test_to_dict(self, tmp_path):
        """测试转换为字典"""
        config = AppConfig(
            download=DownloadConfig(
                variables=["temperature"],
                years=[2023],
                months=[1],
                output_dir=tmp_path
            ),
            account_pool=AccountPoolConfig(
                accounts=[AccountInfo(id="acc1", uid="uid", key="key")]
            )
        )
        data = config.to_dict()
        assert isinstance(data, dict)
        assert "download" in data
        assert "account_pool" in data

    def test_default_sub_configs(self, tmp_path):
        """测试子配置的默认值"""
        config = AppConfig(
            download=DownloadConfig(
                variables=["temperature"],
                years=[2023],
                months=[1],
                output_dir=tmp_path
            ),
            account_pool=AccountPoolConfig(accounts=[])
        )
        # 应该使用默认工厂创建
        assert isinstance(config.concurrency, ConcurrencyConfig)
        assert isinstance(config.progress, ProgressConfig)
        assert isinstance(config.logging, LoggingConfig)


@pytest.fixture
def tmp_path():
    """创建临时目录用于测试"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)
