"""
ECMWF下载器账号池管理单元测试

测试账号池的线程安全操作、状态管理和持久化功能。
"""

import tempfile
import threading
import time
from pathlib import Path
from typing import List

import pytest
import yaml

from src.core.config import AccountInfo, AccountStatus
from src.core.exceptions import AccountPoolError
from src.core.account_pool import AccountPool


@pytest.fixture
def temp_accounts_file(tmp_path):
    """创建临时账号配置文件"""
    accounts_data = {
        "accounts": [
            {
                "id": "account_1",
                "uid": "uid1",
                "key": "key1",
                "status": "active",
                "url": "https://cds.climate.copernicus.eu/api",
                "used_count": 0,
                "last_used": None,
                "fail_count": 0
            },
            {
                "id": "account_2",
                "uid": "uid2",
                "key": "key2",
                "status": "active",
                "url": "https://cds.climate.copernicus.eu/api",
                "used_count": 5,
                "last_used": "2024-01-25T12:00:00",
                "fail_count": 1
            },
            {
                "id": "account_3",
                "uid": "uid3",
                "key": "key3",
                "status": "disabled",
                "url": "https://cds.climate.copernicus.eu/api",
                "used_count": 0,
                "last_used": None,
                "fail_count": 0
            }
        ],
        "auto_disable_threshold": 5
    }

    file_path = tmp_path / "accounts.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(accounts_data, f)

    return file_path


@pytest.fixture
def sample_accounts():
    """创建示例账号列表"""
    return [
        AccountInfo(
            id="account_1",
            uid="uid1",
            key="key1",
            status=AccountStatus.ACTIVE
        ),
        AccountInfo(
            id="account_2",
            uid="uid2",
            key="key2",
            status=AccountStatus.ACTIVE
        ),
        AccountInfo(
            id="account_3",
            uid="uid3",
            key="key3",
            status=AccountStatus.DISABLED
        ),
    ]


class TestAccountPoolInit:
    """测试AccountPool初始化"""

    def test_init_without_config_file(self, sample_accounts):
        """测试不使用配置文件初始化"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        assert pool.get_total_count() == 3
        assert pool.get_available_count() == 2

    def test_init_with_empty_pool_raises_error(self):
        """测试空账号池抛出异常"""
        with pytest.raises(AccountPoolError, match="账号池为空"):
            AccountPool(config_file=None, auto_disable_threshold=5)

    def test_init_with_config_file(self, temp_accounts_file):
        """测试使用配置文件初始化"""
        pool = AccountPool(config_file=temp_accounts_file)

        assert pool.get_total_count() == 3
        assert pool.get_available_count() == 2
        assert pool.config_file == temp_accounts_file


class TestAccountPoolLoadSave:
    """测试账号池加载和保存"""

    def test_load_from_file(self, temp_accounts_file):
        """测试从文件加载账号"""
        pool = AccountPool(config_file=temp_accounts_file)

        accounts = pool.get_all_accounts()
        assert len(accounts) == 3
        assert accounts[0].id == "account_1"
        assert accounts[1].id == "account_2"
        assert accounts[2].id == "account_3"

    def test_load_from_nonexistent_file(self):
        """测试加载不存在的文件"""
        with pytest.raises(AccountPoolError, match="账号配置文件不存在"):
            AccountPool(config_file=Path("/nonexistent/file.yaml"))

    def test_save_to_file(self, tmp_path, sample_accounts):
        """测试保存到文件"""
        # 创建池但不从文件加载
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = tmp_path / "save_test.yaml"
        pool.auto_disable_threshold = 3

        pool.save_to_file()

        # 验证文件内容
        with open(pool.config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert len(data["accounts"]) == 3
        assert data["auto_disable_threshold"] == 3

    def test_save_without_config_file_raises_error(self, sample_accounts):
        """测试未指定配置文件时保存抛出异常"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        with pytest.raises(AccountPoolError, match="未指定配置文件路径"):
            pool.save_to_file()


class TestAccountPoolGetNext:
    """测试获取下一个账号"""

    def test_get_next_account_rotation(self, sample_accounts):
        """测试账号轮换"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        # 获取账号应该轮换
        acc1 = pool.get_next_account()
        acc2 = pool.get_next_account()
        acc3 = pool.get_next_account()
        acc4 = pool.get_next_account()

        assert acc1.id == "account_1"
        assert acc2.id == "account_2"
        # account_3是disabled，应该跳过
        assert acc3.id == "account_1"  # 回到第一个
        assert acc4.id == "account_2"

    def test_get_next_skips_disabled(self, sample_accounts):
        """测试自动跳过禁用账号"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        for _ in range(5):
            account = pool.get_next_account()
            assert account.status == AccountStatus.ACTIVE
            assert account.id != "account_3"

    def test_get_next_when_no_active_accounts(self):
        """测试没有可用账号时抛出异常"""
        all_disabled = [
            AccountInfo(
                id="acc1",
                uid="uid",
                key="key",
                status=AccountStatus.DISABLED
            )
        ]

        pool = AccountPool.__new__(AccountPool)
        pool.accounts = all_disabled
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        with pytest.raises(AccountPoolError, match="没有可用的账号"):
            pool.get_next_account()


class TestAccountPoolMarkStatus:
    """测试标记账号状态"""

    def test_mark_account_failed(self, sample_accounts):
        """测试标记账号失败"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 3

        pool.mark_account_failed("account_1")

        account = pool._find_account_by_id("account_1")
        assert account.fail_count == 1
        assert account.status == AccountStatus.ACTIVE

    def test_mark_account_failed_auto_disable(self, sample_accounts):
        """测试失败达到阈值自动禁用"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 2

        # 标记失败两次
        pool.mark_account_failed("account_1")
        pool.mark_account_failed("account_1")

        account = pool._find_account_by_id("account_1")
        assert account.fail_count == 2
        assert account.status == AccountStatus.DISABLED

    def test_mark_account_success_resets_fail_count(self, sample_accounts):
        """测试成功后重置失败计数"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        # 先标记失败
        pool.mark_account_failed("account_1")
        assert pool._find_account_by_id("account_1").fail_count == 1

        # 标记成功
        pool.mark_account_success("account_1")
        assert pool._find_account_by_id("account_1").fail_count == 0

    def test_mark_nonexistent_account_no_error(self, sample_accounts):
        """测试标记不存在的账号不抛出异常"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        # 不应该抛出异常
        pool.mark_account_failed("nonexistent")
        pool.mark_account_success("nonexistent")


class TestAccountPoolUpdateUsage:
    """测试更新使用统计"""

    def test_update_usage_stats(self, sample_accounts):
        """测试更新使用统计"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        pool.update_usage_stats("account_1")

        account = pool._find_account_by_id("account_1")
        assert account.used_count == 1
        assert account.last_used is not None


class TestAccountPoolManagement:
    """测试账号池管理操作"""

    def test_add_account(self, sample_accounts):
        """测试添加账号"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        new_account = AccountInfo(
            id="account_4",
            uid="uid4",
            key="key4"
        )
        pool.add_account(new_account)

        assert pool.get_total_count() == 4
        assert pool._find_account_by_id("account_4") is not None

    def test_add_duplicate_account_raises_error(self, sample_accounts):
        """测试添加重复账号ID抛出异常"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        duplicate = AccountInfo(
            id="account_1",  # 已存在
            uid="new_uid",
            key="new_key"
        )

        with pytest.raises(AccountPoolError, match="账号ID已存在"):
            pool.add_account(duplicate)

    def test_remove_account(self, sample_accounts):
        """测试移除账号"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        pool.remove_account("account_2")

        assert pool.get_total_count() == 2
        assert pool._find_account_by_id("account_2") is None

    def test_enable_account(self, sample_accounts):
        """测试启用账号"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        # account_3是disabled
        pool.enable_account("account_3")

        account = pool._find_account_by_id("account_3")
        assert account.status == AccountStatus.ACTIVE
        assert account.fail_count == 0

    def test_disable_account(self, sample_accounts):
        """测试禁用账号"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        pool.disable_account("account_1")

        account = pool._find_account_by_id("account_1")
        assert account.status == AccountStatus.DISABLED

    def test_reset_fail_counts(self, sample_accounts):
        """测试重置所有失败计数"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        # 设置一些失败计数
        pool.mark_account_failed("account_1")
        pool.disable_account("account_2")

        pool.reset_fail_counts()

        assert pool._find_account_by_id("account_1").fail_count == 0
        assert pool._find_account_by_id("account_2").status == AccountStatus.ACTIVE


class TestAccountPoolQuery:
    """测试账号池查询操作"""

    def test_get_available_count(self, sample_accounts):
        """测试获取可用账号数量"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        assert pool.get_available_count() == 2

    def test_get_total_count(self, sample_accounts):
        """测试获取总账号数量"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        assert pool.get_total_count() == 3

    def test_get_all_accounts_returns_copy(self, sample_accounts):
        """测试获取所有账号返回副本"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        accounts = pool.get_all_accounts()
        accounts.append(AccountInfo(id="fake", uid="u", key="k"))

        # 原始列表不应改变
        assert pool.get_total_count() == 3

    def test_get_usage_summary(self, sample_accounts):
        """测试获取使用摘要"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        summary = pool.get_usage_summary()

        assert summary["total_accounts"] == 3
        assert summary["active_accounts"] == 2
        assert summary["disabled_accounts"] == 1
        assert "accounts" in summary


class TestAccountPoolThreadSafety:
    """测试账号池线程安全"""

    def test_concurrent_get_next_account(self, sample_accounts):
        """测试多线程并发获取账号"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        results = []
        num_threads = 10

        def get_account():
            for _ in range(100):
                account = pool.get_next_account()
                results.append(account.id)

        threads = [
            threading.Thread(target=get_account)
            for _ in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 所有操作都应该成功
        assert len(results) == num_threads * 100
        # 不应该获取到disabled账号
        assert "account_3" not in results

    def test_concurrent_mark_failed(self, sample_accounts):
        """测试多线程并发标记失败"""
        pool = AccountPool.__new__(AccountPool)
        pool.accounts = sample_accounts
        pool._current_index = 0
        pool._lock = threading.RLock()
        pool.config_file = None
        pool.auto_disable_threshold = 5

        num_threads = 10
        num_iterations = 5

        def mark_failed():
            for _ in range(num_iterations):
                pool.mark_account_failed("account_1")

        threads = [
            threading.Thread(target=mark_failed)
            for _ in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 失败计数应该是线程数 * 迭代次数
        account = pool._find_account_by_id("account_1")
        assert account.fail_count == num_threads * num_iterations
