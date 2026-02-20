"""
AI 参数填充服务

封装 AI 参数生成功能。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.ai_generator import AIGenerator, AIGeneratorError


@dataclass
class AIFillResult:
    """AI 填充结果

    Attributes:
        success: 是否成功
        filled_fields: 已填充的字段名称列表（成功时）
        field_config: 生成的字段配置（成功时）
        error: 错误信息（失败时）
    """
    success: bool
    filled_fields: List[str] = field(default_factory=list)
    field_config: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


class AIFillService:
    """AI 参数填充服务

    封装 AIGenerator 的操作，提供更友好的接口。

    使用示例:
        service = AIFillService()
        if service.is_configured:
            result = service.generate(field_schema, "下载2024年1月的温度数据")
            if result.success:
                print(f"已填充: {result.filled_fields}")
    """

    def __init__(self, generator: Optional[AIGenerator] = None):
        """初始化 AI 填充服务

        Args:
            generator: 可选的 AIGenerator 实例（用于依赖注入测试）
        """
        self._generator = generator

    def _get_generator(self) -> AIGenerator:
        """获取或创建 AI 生成器实例"""
        if self._generator is None:
            self._generator = AIGenerator()
        return self._generator

    @property
    def is_configured(self) -> bool:
        """检查 AI 是否已配置

        Returns:
            是否已配置 API 密钥
        """
        return self._get_generator().is_configured

    def generate(
        self,
        field_schema: Dict[str, Dict[str, Any]],
        user_request: str,
    ) -> AIFillResult:
        """根据用户需求生成参数

        Args:
            field_schema: 字段 Schema 字典，格式为：
                {
                    "field_name": {
                        "field_type": "string_list",
                        "values": ["value1", "value2"],
                        "selected": [],
                    },
                    ...
                }
            user_request: 用户的自然语言需求

        Returns:
            AIFillResult 对象，包含生成结果
        """
        try:
            generator = self._get_generator()
            result = generator.generate(field_schema, user_request)

            # 提取已填充的字段名
            filled_fields = [
                name for name, info in result.items()
                if info.get("selected")
            ]

            return AIFillResult(
                success=True,
                filled_fields=filled_fields,
                field_config=result,
            )

        except AIGeneratorError as e:
            return AIFillResult(
                success=False,
                error=str(e),
            )
        except Exception as e:
            return AIFillResult(
                success=False,
                error=f"未知错误: {str(e)}",
            )

    def prepare_field_schema(
        self,
        form_fields: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """准备用于 AI 生成的字段 Schema

        将 DynamicFormField 字典转换为适合 AI 生成的格式。

        Args:
            form_fields: DynamicFormField 字典

        Returns:
            格式化后的字段 Schema
        """
        field_schema = {}
        for field_name, field in form_fields.items():
            field_schema[field_name] = {
                "field_type": field.field_type.value,
                "values": list(field.values),
                "selected": [],  # 清空已选项
            }
        return field_schema
