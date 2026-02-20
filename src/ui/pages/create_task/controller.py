"""
创建任务页面控制器

负责事件协调、状态管理和异步工作流。
"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional

from src.core.config import DownloadConfig
from src.core.dataset_schema import DynamicFormState, DynamicFormField
from src.core.task_service import TaskService
from src.api.ecmwf_datastores_client import DatastoresService

from .services import (
    SchemaService,
    SchemaLoadResult,
    ConfigStore,
    ConfigMeta,
    AIFillService,
    AIFillResult,
)
from .mappers import FormConfigMapper
from .dialogs import (
    SaveConfigDialog,
    LoadConfigDialog,
    AIGenerateDialog,
)

if TYPE_CHECKING:
    from textual.widget import Widget
    from src.ui.widgets.dynamic_form_field import DynamicFormFieldsContainer


class CreateTaskController:
    """创建任务页面控制器

    职责：
    - 协调 View 与 Services
    - 处理用户事件（load_schema, field_changed, save_config, etc.）
    - 管理异步工作流
    - 状态管理（form_state, constraints_seq）
    """

    def __init__(self, view: "Widget", app_ref: Any):
        """初始化控制器

        Args:
            view: 关联的视图组件（用于 UI 更新）
            app_ref: 应用实例引用
        """
        self._view = view
        self._app_ref = app_ref

        # 核心状态
        self._form_state = DynamicFormState()
        self._is_loading = False
        self._constraints_seq = 0

        # 服务（延迟初始化）
        self._task_service: Optional[TaskService] = None
        self._schema_service: Optional[SchemaService] = None
        self._config_store: Optional[ConfigStore] = None
        self._ai_fill_service: Optional[AIFillService] = None

        # 回调函数（由 View 设置）
        self.on_schema_loaded: Optional[Callable[[SchemaLoadResult], None]] = None
        self.on_fields_rendered: Optional[Callable[[], None]] = None
        self.on_config_loaded: Optional[Callable[[str, str, str], None]] = None  # dataset, output_dir, strategy
        self.on_ai_result_applied: Optional[Callable[[Dict[str, Any]], None]] = None  # AI 生成结果
        self.on_status_changed: Optional[Callable[[str, str], None]] = None
        self.on_notify: Optional[Callable[[str, str, int], None]] = None

    # ==================== 属性访问 ====================

    @property
    def form_state(self) -> DynamicFormState:
        """获取当前表单状态"""
        return self._form_state

    @property
    def is_loading(self) -> bool:
        """是否正在加载"""
        return self._is_loading

    @property
    def is_schema_loaded(self) -> bool:
        """Schema 是否已加载"""
        return self._form_state.is_schema_loaded

    # ==================== 服务访问 ====================

    def _get_task_service(self) -> TaskService:
        """获取任务服务"""
        if self._task_service is None:
            self._task_service = TaskService(self._app_ref.progress_manager)
        return self._task_service

    def _get_schema_service(self) -> SchemaService:
        """获取 Schema 服务"""
        if self._schema_service is None:
            # 从账号池获取凭据
            uid, key, url = None, None, None
            try:
                if hasattr(self._app_ref, "account_pool") and self._app_ref.account_pool:
                    account = self._app_ref.account_pool.get_next_account()
                    if account:
                        uid = account.uid
                        key = account.key
                        url = account.url
            except Exception as e:
                # 获取账号失败时记录警告，但不阻塞流程
                if hasattr(self._view, "log"):
                    self._view.log.warning(f"获取账号凭据失败: {e}")

            self._schema_service = SchemaService(url=url, uid=uid, key=key)
        return self._schema_service

    def _get_config_store(self) -> ConfigStore:
        """获取配置存储服务"""
        if self._config_store is None:
            self._config_store = ConfigStore()
        return self._config_store

    def _get_ai_fill_service(self) -> AIFillService:
        """获取 AI 填充服务"""
        if self._ai_fill_service is None:
            self._ai_fill_service = AIFillService()
        return self._ai_fill_service

    # ==================== 事件处理 ====================

    async def handle_load_schema(self, dataset_id: str) -> None:
        """处理加载 Schema 事件

        Args:
            dataset_id: 数据集 ID
        """
        if self._is_loading:
            return

        if not dataset_id:
            self._notify_status("请输入数据集 ID", "error")
            return

        self._is_loading = True
        self._notify_status("正在加载 Schema...", "loading")

        try:
            service = self._get_schema_service()
            result = await asyncio.to_thread(service.load_schema, dataset_id)

            if result.success:
                # 初始化表单状态
                self._form_state.init_from_schema(result.schema)

                # 通知 View 渲染字段
                if self.on_schema_loaded:
                    self.on_schema_loaded(result)

                self._notify_status(
                    f"已加载: {result.title}（{result.field_count} 个字段）",
                    "success",
                )
            else:
                self._notify_status("加载失败", "error")
                if self.on_notify:
                    self.on_notify(result.error, "error", 10)

        except Exception as e:
            self._notify_status("加载失败", "error")
            if self.on_notify:
                self.on_notify(f"未知错误: {str(e)}", "error", 10)
        finally:
            self._is_loading = False

    def handle_field_changed(
        self,
        field_name: str,
        selected_values: List[Any],
        container: "DynamicFormFieldsContainer",
    ) -> None:
        """处理字段值变化事件

        Args:
            field_name: 变化的字段名称
            selected_values: 新选中的值列表
            container: 动态字段容器
        """
        # 更新表单状态
        self._form_state.set_field_selection(field_name, selected_values)

        # 特殊互斥逻辑：area_group
        self._handle_area_group_change(field_name, selected_values, container)

        # 触发约束更新
        self._schedule_constraints_update(field_name, container)

    def _handle_area_group_change(
        self,
        field_name: str,
        selected_values: List[Any],
        container: "DynamicFormFieldsContainer",
    ) -> None:
        """处理 area_group 字段变化的特殊逻辑"""
        if field_name != "area_group" or not selected_values:
            return

        mode = str(selected_values[0]).strip().lower()
        global_widget = container.get_field_widget("global")
        area_widget = container.get_field_widget("area")

        if mode == "global":
            # global 模式：隐藏 global 开关和 area 输入框
            if global_widget:
                global_widget.set_selected_values(["true"])
                self._form_state.set_field_selection("global", ["true"])
                global_widget.display = False
            if area_widget:
                area_widget.set_selected_values([])
                self._form_state.set_field_selection("area", [])
                area_widget.display = False
        elif mode == "area":
            # area 模式：隐藏 global 开关，显示 area 输入框
            if global_widget:
                global_widget.set_selected_values([])
                self._form_state.set_field_selection("global", [])
                global_widget.display = False
            if area_widget:
                area_widget.display = True
                area_widget.disabled = False

    def _schedule_constraints_update(
        self,
        changed_field: str,
        container: "DynamicFormFieldsContainer",
    ) -> None:
        """调度约束更新"""
        if not self._form_state.is_schema_loaded:
            return

        self._constraints_seq += 1
        seq = self._constraints_seq

        self._view.run_worker(
            self._apply_constraints_update(changed_field, seq, container),
            name="constraints-update",
            group="constraints-update",
            exclusive=True,
            exit_on_error=False,
        )

    async def _apply_constraints_update(
        self,
        changed_field: str,
        seq: int,
        container: "DynamicFormFieldsContainer",
    ) -> None:
        """执行约束更新"""
        if not self._form_state.is_schema_loaded:
            return

        try:
            service = self._get_schema_service()
            current_selection = self._form_state.get_current_selection()

            constraints = await asyncio.to_thread(
                service.apply_constraints,
                self._form_state.collection_id,
                current_selection,
            )

            # 丢弃过期结果
            if seq != self._constraints_seq or not self._view.is_mounted:
                return

            # 更新表单状态
            self._form_state.update_constraints(constraints)

            # 更新 UI
            for field_name, values in constraints.items():
                if field_name != changed_field:
                    container.update_field_values(field_name, values)

        except Exception as e:
            # 约束更新失败不阻塞用户操作
            self._view.log.warning(f"约束更新失败: {str(e)}")

    # ==================== 配置保存/加载 ====================

    def handle_save_config(self, dataset_id: str, output_dir: str, split_strategy: str) -> None:
        """处理保存配置事件

        Args:
            dataset_id: 数据集 ID
            output_dir: 输出目录
            split_strategy: 拆分策略
        """
        # 生成默认名称
        default_name = "".join(
            c if c.isalnum() or c in "-_" else "_"
            for c in (dataset_id or "config")
        )

        def do_save(name: str):
            self._do_save_config(name, dataset_id, output_dir, split_strategy)

        self._app_ref.push_screen(SaveConfigDialog(default_name, do_save))

    def _do_save_config(
        self,
        name: str,
        dataset_id: str,
        output_dir: str,
        split_strategy: str,
    ) -> None:
        """实际执行保存配置"""
        try:
            store = self._get_config_store()
            config_data = FormConfigMapper.serialize_form_state(
                self._form_state,
                dataset_id,
                output_dir,
                split_strategy,
            )
            store.save(name, config_data)
            if self.on_notify:
                self.on_notify(f"配置已保存: {name}", "success", 3)
        except Exception as e:
            if self.on_notify:
                self.on_notify(f"保存失败: {str(e)}", "error", 5)

    def handle_load_config(self) -> None:
        """处理加载配置事件"""
        store = self._get_config_store()
        configs = store.list_configs()

        if not configs:
            if self.on_notify:
                self.on_notify("没有找到保存的配置文件", "warning", 3)
            return

        options = [(c.name, str(c.path)) for c in configs]

        def do_load(path: str):
            self._load_config_from_file(path)

        self._app_ref.push_screen(LoadConfigDialog(options, do_load))

    def _load_config_from_file(self, config_path: str) -> None:
        """从文件加载配置"""
        try:
            store = self._get_config_store()
            config_data = store.load(Path(config_path))

            # 反序列化表单状态
            self._form_state, dataset, output_dir, strategy = (
                FormConfigMapper.deserialize_to_form_state(config_data)
            )

            # 通知 View 渲染动态字段
            if self.on_fields_rendered:
                self.on_fields_rendered()

            # 通知 View 恢复静态字段（dataset, output_dir, strategy）
            if self.on_config_loaded:
                self.on_config_loaded(dataset, output_dir, strategy)

            self._notify_status(
                f"已从配置文件加载（{len(self._form_state.fields)} 个字段）",
                "success",
            )

            if self.on_notify:
                self.on_notify("配置已加载", "success", 3)

        except Exception as e:
            if self.on_notify:
                self.on_notify(f"加载失败: {str(e)}", "error", 5)

    # ==================== AI 生成 ====================

    def handle_ai_generate(self) -> None:
        """处理 AI 生成事件"""
        if not self._form_state.is_schema_loaded:
            if self.on_notify:
                self.on_notify("请先加载数据集 Schema", "warning", 3)
            return

        ai_service = self._get_ai_fill_service()
        if not ai_service.is_configured:
            if self.on_notify:
                self.on_notify(
                    "AI 功能未配置，请在 config/ai_config.yaml 中设置 api_key",
                    "warning",
                    5,
                )
            return

        def do_generate(request_text: str):
            self._execute_ai_generate(request_text)

        self._app_ref.push_screen(AIGenerateDialog(do_generate))

    def _execute_ai_generate(self, user_request: str) -> None:
        """执行 AI 生成（异步 Worker）"""
        self._view.run_worker(
            self._do_ai_generate(user_request),
            name="ai-generate",
            group="ai-generate",
            exclusive=True,
            exit_on_error=False,
        )

    async def _do_ai_generate(self, user_request: str) -> None:
        """实际执行 AI 生成"""
        self._notify_status("AI 正在生成参数...", "loading")

        try:
            ai_service = self._get_ai_fill_service()
            field_schema = ai_service.prepare_field_schema(self._form_state.fields)

            result = await asyncio.to_thread(
                ai_service.generate,
                field_schema,
                user_request,
            )

            if result.success:
                # 将 AI 生成的 selected 应用到表单
                self._apply_ai_result(result.field_config)
                self._notify_status(
                    f"AI 生成完成（已填充 {len(result.filled_fields)} 个字段）",
                    "success",
                )
                if self.on_notify:
                    self.on_notify("AI 参数生成成功", "success", 3)
            else:
                self._notify_status("AI 生成失败", "error")
                if self.on_notify:
                    self.on_notify(f"AI 生成失败: {result.error}", "error", 8)

        except Exception as e:
            self._notify_status("AI 生成异常", "error")
            if self.on_notify:
                self.on_notify(f"AI 生成异常: {str(e)}", "error", 8)

    def _apply_ai_result(
        self,
        result: Dict[str, Any],
    ) -> None:
        """将 AI 生成结果应用到表单

        Args:
            result: AI 生成的字段配置字典
        """
        for field_name, field_info in result.items():
            if field_name not in self._form_state.fields:
                continue

            selected = field_info.get("selected", [])
            if not selected:
                continue

            # 更新表单状态
            self._form_state.set_field_selection(field_name, selected)

        # 通知 View 更新 UI 控件
        if self.on_ai_result_applied:
            self.on_ai_result_applied(result)

    # ==================== 任务创建 ====================

    def build_download_config(
        self,
        dataset_id: str,
        output_dir: str,
    ) -> DownloadConfig:
        """构建下载配置

        Args:
            dataset_id: 数据集 ID
            output_dir: 输出目录

        Returns:
            验证后的 DownloadConfig 对象

        Raises:
            ValueError: 参数验证失败
        """
        return FormConfigMapper.to_download_config(
            self._form_state,
            dataset_id,
            output_dir,
        )

    def preview_tasks(
        self,
        config: DownloadConfig,
        split_strategy: Literal["month", "year", "none"],
    ) -> List[Any]:
        """预览任务拆分

        Args:
            config: 下载配置
            split_strategy: 拆分策略

        Returns:
            预览项目列表
        """
        task_service = self._get_task_service()
        return task_service.preview_tasks(config, split_strategy)

    def create_tasks(
        self,
        config: DownloadConfig,
        split_strategy: Literal["month", "year", "none"],
    ) -> List[str]:
        """创建任务

        Args:
            config: 下载配置
            split_strategy: 拆分策略

        Returns:
            创建的任务 ID 列表
        """
        task_service = self._get_task_service()
        return task_service.create_batch_tasks(config, split_strategy)

    # ==================== 状态重置 ====================

    def reset_form_state(self) -> None:
        """重置表单状态"""
        self._form_state = DynamicFormState()
        self._constraints_seq = 0

    def clear_form_selections(self) -> None:
        """清空表单选择（保留字段定义）"""
        for field_name in self._form_state.fields:
            self._form_state.set_field_selection(field_name, [])

    # ==================== 辅助方法 ====================

    def _notify_status(self, message: str, status_type: str) -> None:
        """通知状态更新"""
        if self.on_status_changed:
            self.on_status_changed(message, status_type)
