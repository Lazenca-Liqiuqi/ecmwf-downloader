"""TaskService 单元测试"""

from pathlib import Path
from unittest.mock import ANY, Mock
from uuid import UUID

import pytest

from src.core.config import DatasetType, DownloadConfig
from src.core.progress import ProgressManager, TaskInfo, TaskStatus
from src.core.request_builder import DownloadRequest, RequestBuilder
from src.core.task_service import TaskService


class TestTaskService:
    """TaskService 测试类"""

    @pytest.fixture
    def mock_progress_manager(self):
        """创建 Mock ProgressManager"""
        mock = Mock(spec=ProgressManager)
        mock.create_task = Mock(
            return_value=TaskInfo(
                task_id="test-task-id",
                filename="test.nc",
                status=TaskStatus.PENDING,
            )
        )
        return mock

    @pytest.fixture
    def sample_config(self, tmp_path):
        """创建测试配置"""
        return DownloadConfig(
            dataset=DatasetType.ERA5_PRESSURE_LEVELS,
            variables=["temperature"],
            years=[2020, 2021],
            months=[1, 2],
            output_dir=tmp_path,
        )

    @pytest.fixture
    def task_service(self, mock_progress_manager):
        """创建默认 TaskService 实例"""
        return TaskService(mock_progress_manager)

    def test_init_default_builder(self, mock_progress_manager):
        """测试初始化时自动创建 RequestBuilder"""
        service = TaskService(mock_progress_manager)
        assert isinstance(service.request_builder, RequestBuilder)

    def test_init_custom_builder(self, mock_progress_manager):
        """测试初始化时使用自定义 RequestBuilder"""
        custom_builder = Mock(spec=RequestBuilder)
        service = TaskService(mock_progress_manager, request_builder=custom_builder)
        assert service.request_builder is custom_builder

    def test_create_single_task(self, task_service, sample_config, mock_progress_manager):
        """测试创建单个任务"""
        task_id = task_service.create_single_task(sample_config)

        # 验证任务ID是有效UUID字符串
        assert isinstance(task_id, str)
        assert UUID(task_id)

        # 验证已调用进度管理器创建任务
        mock_progress_manager.create_task.assert_called_once()
        create_kwargs = mock_progress_manager.create_task.call_args.kwargs
        assert create_kwargs["task_id"] == task_id
        assert create_kwargs["filename"].endswith(".nc")

    def test_create_single_task_with_metadata(
        self, task_service, sample_config, mock_progress_manager
    ):
        """测试创建任务时合并额外元数据"""
        extra_metadata = {"source": "ui", "priority": 10}

        task_id = task_service.create_single_task(sample_config, metadata=extra_metadata)
        create_kwargs = mock_progress_manager.create_task.call_args.kwargs
        task_metadata = create_kwargs["metadata"]

        assert create_kwargs["task_id"] == task_id
        assert task_metadata["source"] == "ui"
        assert task_metadata["priority"] == 10
        assert "download_params" in task_metadata
        assert "time_range" in task_metadata
        assert isinstance(task_metadata["download_params"]["output_path"], str)

    def test_create_batch_tasks_month_strategy(
        self, task_service, sample_config, mock_progress_manager
    ):
        """测试按月策略创建批量任务"""
        task_ids = task_service.create_batch_tasks(sample_config, split_strategy="month")

        assert len(task_ids) == 4  # 2年 x 2月
        assert len(set(task_ids)) == 4
        assert mock_progress_manager.create_task.call_count == 4

    def test_create_batch_tasks_year_strategy(
        self, task_service, sample_config, mock_progress_manager
    ):
        """测试按年策略创建批量任务"""
        task_ids = task_service.create_batch_tasks(sample_config, split_strategy="year")

        assert len(task_ids) == 2  # 2年
        assert mock_progress_manager.create_task.call_count == 2

    def test_create_batch_tasks_none_strategy(
        self, task_service, sample_config, mock_progress_manager
    ):
        """测试不拆分策略创建批量任务"""
        task_ids = task_service.create_batch_tasks(sample_config, split_strategy="none")

        assert len(task_ids) == 1
        mock_progress_manager.create_task.assert_called_once()

    def test_preview_tasks(self, task_service, sample_config, mock_progress_manager):
        """测试预览任务不会实际创建任务"""
        preview_items = task_service.preview_tasks(sample_config, split_strategy="month")

        assert len(preview_items) == 4
        mock_progress_manager.create_task.assert_not_called()

    def test_preview_tasks_structure(self, task_service, sample_config):
        """测试预览任务返回结构完整"""
        preview_items = task_service.preview_tasks(sample_config, split_strategy="none")

        assert len(preview_items) == 1
        item = preview_items[0]
        assert {"dataset", "filename", "output_path", "time_range", "api_params"} <= set(item)
        assert item["dataset"] == DatasetType.ERA5_PRESSURE_LEVELS.value
        assert isinstance(item["output_path"], Path)
        assert isinstance(item["time_range"], dict)
        assert isinstance(item["api_params"], dict)

    def test_progress_manager_integration_with_mock(
        self, task_service, sample_config, mock_progress_manager
    ):
        """测试与 ProgressManager 的集成调用参数"""
        task_service.create_single_task(sample_config, metadata={"tag": "integration"})

        mock_progress_manager.create_task.assert_called_once_with(
            task_id=ANY,
            filename=ANY,
            metadata=ANY,
        )
        create_kwargs = mock_progress_manager.create_task.call_args.kwargs
        assert create_kwargs["metadata"]["tag"] == "integration"
        assert create_kwargs["metadata"]["download_params"]["dataset"] == (
            DatasetType.ERA5_PRESSURE_LEVELS.value
        )
        assert isinstance(create_kwargs["metadata"]["download_params"]["output_path"], str)

    def test_create_task_validation_failure(self, mock_progress_manager):
        """测试请求校验失败时抛出异常"""
        invalid_request = DownloadRequest(
            dataset="",
            api_params={},
            output_path=Path("invalid.nc"),
            filename="",
            time_range={"years": [], "months": []},
        )

        mock_builder = Mock(spec=RequestBuilder)
        mock_builder.build_request.return_value = invalid_request
        mock_builder.validate_request.return_value = (False, ["dataset不能为空", "filename不能为空"])

        service = TaskService(mock_progress_manager, request_builder=mock_builder)

        with pytest.raises(ValueError, match="下载请求校验失败"):
            service.create_single_task(
                DownloadConfig(
                    dataset=DatasetType.ERA5_PRESSURE_LEVELS,
                    variables=["temperature"],
                    years=[2020],
                    months=[1],
                    output_dir=Path("."),
                )
            )

        mock_progress_manager.create_task.assert_not_called()
