"""
任务存储层模块

提供任务持久化的抽象接口和实现，支持单文件和多文件存储策略。
"""

import json
import os
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from src.core.exceptions import ProgressLoadError, ProgressSaveError
from src.core.models import TaskInfo, TaskStatus


class TaskStore(ABC):
    """任务存储抽象接口

    定义任务持久化的统一接口，支持不同的存储策略实现。
    """

    @abstractmethod
    def load(self) -> Dict[str, TaskInfo]:
        """加载所有任务

        Returns:
            Dict[str, TaskInfo]: 任务ID到任务信息的映射

        Raises:
            ProgressLoadError: 加载失败时抛出
        """
        pass

    @abstractmethod
    def save(self, tasks: Dict[str, TaskInfo]) -> None:
        """保存所有任务

        Args:
            tasks: 任务ID到任务信息的映射

        Raises:
            ProgressSaveError: 保存失败时抛出
        """
        pass

    @abstractmethod
    def save_task(self, task_id: str, task: TaskInfo) -> None:
        """保存单个任务

        对于多文件存储，此方法只写入对应文件，效率更高。
        对于单文件存储，此方法会重写整个文件。

        Args:
            task_id: 任务ID
            task: 任务信息

        Raises:
            ProgressSaveError: 保存失败时抛出
            ProgressLoadError: 读取现有数据失败时抛出（单文件实现需要先加载）
        """
        pass

    @abstractmethod
    def delete_task(self, task_id: str) -> None:
        """删除单个任务

        Args:
            task_id: 要删除的任务ID

        Raises:
            ProgressSaveError: 保存失败时抛出
            ProgressLoadError: 读取现有数据失败时抛出（单文件实现需要先加载）
        """
        pass

    @abstractmethod
    def load_tasks_by_status(self, status: TaskStatus) -> Dict[str, TaskInfo]:
        """按状态加载任务

        对于多文件存储，此方法只读取对应状态的文件，效率更高。
        对于单文件存储，此方法会加载全部任务后过滤。

        Args:
            status: 任务状态

        Returns:
            Dict[str, TaskInfo]: 符合状态的任务映射

        Raises:
            ProgressLoadError: 加载失败时抛出
        """
        pass

    @abstractmethod
    def get_storage_info(self) -> Dict[str, str]:
        """获取存储信息

        Returns:
            Dict[str, str]: 存储类型、路径等信息的字典
        """
        pass


class SingleFileTaskStore(TaskStore):
    """单文件任务存储

    将所有任务存储在单个 JSON 文件中，适合任务数量较少的场景。
    """

    def __init__(self, progress_file: Path):
        """初始化单文件存储

        Args:
            progress_file: 进度文件路径
        """
        self.progress_file = progress_file

    def load(self) -> Dict[str, TaskInfo]:
        """从文件加载所有任务

        Returns:
            Dict[str, TaskInfo]: 任务映射

        Raises:
            ProgressLoadError: 加载失败时抛出
        """
        if not self.progress_file.exists():
            return {}

        try:
            with open(self.progress_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            tasks_data = data.get("tasks", [])
            return {
                task_data["task_id"]: TaskInfo.from_dict(task_data)
                for task_data in tasks_data
            }

        except json.JSONDecodeError as e:
            raise ProgressLoadError(
                f"进度文件JSON格式错误: {e}",
                file_path=str(self.progress_file),
                original_error=e,
            )
        except Exception as e:
            raise ProgressLoadError(
                f"加载进度文件失败: {e}",
                file_path=str(self.progress_file),
                original_error=e,
            )

    def save(self, tasks: Dict[str, TaskInfo]) -> None:
        """保存所有任务到文件

        Args:
            tasks: 任务映射

        Raises:
            ProgressSaveError: 保存失败时抛出
        """
        try:
            data = {
                "tasks": [task.to_dict() for task in tasks.values()],
                "updated_at": datetime.now().isoformat(),
            }

            self.progress_file.parent.mkdir(parents=True, exist_ok=True)

            # 原子写入：先写入临时文件，再原子替换
            tmp_fd, tmp_path = tempfile.mkstemp(
                prefix=f"{self.progress_file.name}.",
                suffix=".tmp",
                dir=str(self.progress_file.parent),
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.progress_file)
            finally:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass

        except Exception as e:
            raise ProgressSaveError(
                f"保存进度文件失败: {e}",
                file_path=str(self.progress_file),
                original_error=e,
            )

    def save_task(self, task_id: str, task: TaskInfo) -> None:
        """保存单个任务（单文件实现需要重写整个文件）

        Args:
            task_id: 任务ID
            task: 任务信息

        Raises:
            ProgressSaveError: 保存失败时抛出
        """
        # 单文件存储需要先加载全部，修改后重写
        # 注意：调用方需要确保线程安全
        tasks = self.load()
        tasks[task_id] = task
        self.save(tasks)

    def delete_task(self, task_id: str) -> None:
        """删除单个任务

        Args:
            task_id: 要删除的任务ID

        Raises:
            ProgressSaveError: 保存失败时抛出
        """
        tasks = self.load()
        if task_id in tasks:
            del tasks[task_id]
            self.save(tasks)

    def load_tasks_by_status(self, status: TaskStatus) -> Dict[str, TaskInfo]:
        """按状态加载任务

        Args:
            status: 任务状态

        Returns:
            Dict[str, TaskInfo]: 符合状态的任务映射
        """
        tasks = self.load()
        return {
            task_id: task
            for task_id, task in tasks.items()
            if task.status == status
        }

    def get_storage_info(self) -> Dict[str, str]:
        """获取存储信息

        Returns:
            Dict[str, str]: 存储信息字典
        """
        return {
            "type": "single_file",
            "path": str(self.progress_file),
        }


# 状态到文件名的映射
STATUS_FILE_MAP: Dict[TaskStatus, str] = {
    TaskStatus.PENDING: "pending_tasks.json",
    TaskStatus.QUEUED: "queued_tasks.json",
    TaskStatus.DOWNLOADING: "downloading_tasks.json",
    TaskStatus.RETRYING: "downloading_tasks.json",  # RETRYING 与 DOWNLOADING 共用文件
    TaskStatus.COMPLETED: "finished_tasks.json",
    TaskStatus.FAILED: "finished_tasks.json",  # 终态共用文件
    TaskStatus.CANCELLED: "finished_tasks.json",
}

# 文件名到状态的映射（反向查找）
FILE_STATUS_MAP: Dict[str, set] = {
    "pending_tasks.json": {TaskStatus.PENDING},
    "queued_tasks.json": {TaskStatus.QUEUED},
    "downloading_tasks.json": {TaskStatus.DOWNLOADING, TaskStatus.RETRYING},
    "finished_tasks.json": {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
}


class MultiFileTaskStore(TaskStore):
    """多文件任务存储

    将不同状态的任务存储到不同的 JSON 文件中，适合任务数量较多、
    需要按状态高效加载/保存的场景。

    文件结构：
    - pending_tasks.json: PENDING 状态
    - queued_tasks.json: QUEUED 状态
    - downloading_tasks.json: DOWNLOADING, RETRYING 状态
    - finished_tasks.json: COMPLETED, FAILED, CANCELLED 状态
    """

    def __init__(self, data_dir: Path):
        """初始化多文件存储

        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_for_status(self, status: TaskStatus) -> Path:
        """获取状态对应的文件路径

        Args:
            status: 任务状态

        Returns:
            Path: 对应的文件路径
        """
        filename = STATUS_FILE_MAP[status]
        return self.data_dir / filename

    def _load_file(self, file_path: Path) -> Dict[str, TaskInfo]:
        """从单个文件加载任务

        Args:
            file_path: 文件路径

        Returns:
            Dict[str, TaskInfo]: 任务映射
        """
        if not file_path.exists():
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            tasks_data = data.get("tasks", [])
            return {
                task_data["task_id"]: TaskInfo.from_dict(task_data)
                for task_data in tasks_data
            }

        except json.JSONDecodeError as e:
            raise ProgressLoadError(
                f"任务文件JSON格式错误: {e}",
                file_path=str(file_path),
                original_error=e,
            )
        except Exception as e:
            raise ProgressLoadError(
                f"加载任务文件失败: {e}",
                file_path=str(file_path),
                original_error=e,
            )

    def _save_file(self, file_path: Path, tasks: Dict[str, TaskInfo]) -> None:
        """保存任务到单个文件

        Args:
            file_path: 文件路径
            tasks: 任务映射

        Raises:
            ProgressSaveError: 保存失败时抛出
        """
        try:
            data = {
                "tasks": [task.to_dict() for task in tasks.values()],
                "updated_at": datetime.now().isoformat(),
            }

            # 原子写入
            tmp_fd, tmp_path = tempfile.mkstemp(
                prefix=f"{file_path.name}.",
                suffix=".tmp",
                dir=str(file_path.parent),
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, file_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass

        except Exception as e:
            raise ProgressSaveError(
                f"保存任务文件失败: {e}",
                file_path=str(file_path),
                original_error=e,
            )

    def _find_task_file(self, task_id: str) -> Optional[Path]:
        """查找任务所在的文件

        Args:
            task_id: 任务ID

        Returns:
            Optional[Path]: 任务所在文件路径，未找到返回 None
        """
        for filename in FILE_STATUS_MAP.keys():
            file_path = self.data_dir / filename
            if file_path.exists():
                tasks = self._load_file(file_path)
                if task_id in tasks:
                    return file_path
        return None

    def load(self) -> Dict[str, TaskInfo]:
        """加载所有任务

        Returns:
            Dict[str, TaskInfo]: 任务ID到任务信息的映射

        Raises:
            ProgressLoadError: 加载失败时抛出
        """
        all_tasks: Dict[str, TaskInfo] = {}
        for filename in FILE_STATUS_MAP.keys():
            file_path = self.data_dir / filename
            if file_path.exists():
                tasks = self._load_file(file_path)
                all_tasks.update(tasks)
        return all_tasks

    def save(self, tasks: Dict[str, TaskInfo]) -> None:
        """保存所有任务

        按状态分组后保存到不同的文件。

        Args:
            tasks: 任务ID到任务信息的映射

        Raises:
            ProgressSaveError: 保存失败时抛出
        """
        # 按状态分组
        grouped: Dict[str, Dict[str, TaskInfo]] = {
            filename: {} for filename in FILE_STATUS_MAP.keys()
        }

        for task_id, task in tasks.items():
            filename = STATUS_FILE_MAP[task.status]
            grouped[filename][task_id] = task

        # 保存到各文件
        for filename, file_tasks in grouped.items():
            file_path = self.data_dir / filename
            if file_tasks:
                self._save_file(file_path, file_tasks)
            elif file_path.exists():
                # 如果该状态没有任务，删除空文件
                try:
                    file_path.unlink()
                except OSError as e:
                    raise ProgressSaveError(
                        f"删除空任务文件失败: {e}",
                        file_path=str(file_path),
                        original_error=e,
                    )

    def save_task(self, task_id: str, task: TaskInfo) -> None:
        """保存单个任务

        如果任务状态变化，会自动迁移到对应的文件。

        Args:
            task_id: 任务ID
            task: 任务信息

        Raises:
            ProgressSaveError: 保存失败时抛出
        """
        # 查找任务当前所在文件
        old_file = self._find_task_file(task_id)
        new_file = self._get_file_for_status(task.status)

        # 从旧文件删除（如果存在且文件不同）
        if old_file is not None and old_file != new_file:
            old_tasks = self._load_file(old_file)
            if task_id in old_tasks:
                del old_tasks[task_id]
                if old_tasks:
                    self._save_file(old_file, old_tasks)
                elif old_file.exists():
                    try:
                        old_file.unlink()
                    except OSError as e:
                        raise ProgressSaveError(
                            f"删除旧任务文件失败: {e}",
                            file_path=str(old_file),
                            original_error=e,
                        )

        # 添加到新文件
        new_tasks = self._load_file(new_file)
        new_tasks[task_id] = task
        self._save_file(new_file, new_tasks)

    def delete_task(self, task_id: str) -> None:
        """删除单个任务

        Args:
            task_id: 要删除的任务ID

        Raises:
            ProgressSaveError: 保存失败时抛出
        """
        file_path = self._find_task_file(task_id)
        if file_path is None:
            return

        tasks = self._load_file(file_path)
        if task_id in tasks:
            del tasks[task_id]
            if tasks:
                self._save_file(file_path, tasks)
            elif file_path.exists():
                try:
                    file_path.unlink()
                except OSError as e:
                    raise ProgressSaveError(
                        f"删除任务文件失败: {e}",
                        file_path=str(file_path),
                        original_error=e,
                    )

    def load_tasks_by_status(self, status: TaskStatus) -> Dict[str, TaskInfo]:
        """按状态加载任务

        只读取对应状态的文件，效率更高。

        Args:
            status: 任务状态

        Returns:
            Dict[str, TaskInfo]: 符合状态的任务映射

        Raises:
            ProgressLoadError: 加载失败时抛出
        """
        file_path = self._get_file_for_status(status)
        tasks = self._load_file(file_path)

        # 如果请求的状态与文件内其他状态共用文件，需要过滤
        file_statuses = FILE_STATUS_MAP.get(file_path.name, set())
        if len(file_statuses) > 1:
            return {
                task_id: task
                for task_id, task in tasks.items()
                if task.status == status
            }
        return tasks

    def get_storage_info(self) -> Dict[str, str]:
        """获取存储信息

        Returns:
            Dict[str, str]: 存储信息字典
        """
        return {
            "type": "multi_file",
            "data_dir": str(self.data_dir),
            "files": ",".join(FILE_STATUS_MAP.keys()),
        }

    def needs_migration(self, single_file_path: Path) -> bool:
        """检查是否需要从单文件迁移

        Args:
            single_file_path: 单文件存储路径

        Returns:
            bool: 是否需要迁移（旧文件存在且新文件不存在）
        """
        # 如果旧文件不存在，不需要迁移
        if not single_file_path.exists():
            return False

        # 如果新文件已存在，不迁移（避免覆盖）
        for filename in FILE_STATUS_MAP.keys():
            if (self.data_dir / filename).exists():
                return False

        return True

    def migrate_from_single_file(
        self,
        single_file_path: Path,
        remove_source: bool = False,
    ) -> int:
        """从单文件存储迁移到多文件存储

        Args:
            single_file_path: 单文件存储路径
            remove_source: 是否删除源文件（默认保留）

        Returns:
            int: 迁移的任务数量

        Raises:
            ProgressLoadError: 加载失败时抛出
            ProgressSaveError: 保存失败时抛出
        """
        if not single_file_path.exists():
            return 0

        # 检查新文件是否已存在
        for filename in FILE_STATUS_MAP.keys():
            if (self.data_dir / filename).exists():
                raise ProgressSaveError(
                    "目标文件已存在，无法迁移",
                    file_path=str(self.data_dir / filename),
                )

        # 使用 SingleFileTaskStore 加载旧数据
        old_store = SingleFileTaskStore(single_file_path)
        tasks = old_store.load()

        if not tasks:
            return 0

        # 保存到新存储
        self.save(tasks)

        # 删除源文件（可选）
        if remove_source:
            try:
                single_file_path.unlink()
            except OSError as e:
                raise ProgressSaveError(
                    f"删除源文件失败: {e}",
                    file_path=str(single_file_path),
                    original_error=e,
                )

        return len(tasks)
