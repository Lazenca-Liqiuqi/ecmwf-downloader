"""
AI 参数生成服务

基于 OpenAI 兼容 API，根据用户自然语言需求智能生成数据集下载参数。
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple

from src.core.ai_config import AIConfig, AIConfigLoader

logger = logging.getLogger(__name__)


class AIGeneratorError(Exception):
    """AI 生成器错误基类"""
    pass


class AIConfigError(AIGeneratorError):
    """AI 配置错误"""
    pass


class AIAPIError(AIGeneratorError):
    """AI API 调用错误"""
    pass


class AIResponseError(AIGeneratorError):
    """AI 响应解析错误"""
    pass


class AIGenerator:
    """AI 参数生成器

    使用 OpenAI 兼容 API 根据用户需求生成下载参数。

    使用示例：
        generator = AIGenerator()
        result = generator.generate(field_schema, "下载2024年1月的温度数据")
    """

    def __init__(self, config: Optional[AIConfig] = None):
        """初始化 AI 生成器

        Args:
            config: AI 配置，如果为 None 则从默认配置文件加载
        """
        if config is None:
            config = AIConfigLoader.load()
        self._config = config
        self._client = None

    @property
    def config(self) -> AIConfig:
        """获取当前配置"""
        return self._config

    @property
    def is_enabled(self) -> bool:
        """检查 AI 功能是否启用"""
        return self._config.enabled and bool(self._config.api_key)

    @property
    def is_configured(self) -> bool:
        """检查 AI 是否已正确配置"""
        return (
            self._config.enabled
            and bool(self._config.api_key)
            and bool(self._config.base_url)
            and bool(self._config.model)
        )

    def _get_client(self):
        """获取 OpenAI 客户端（延迟导入和初始化）

        Returns:
            OpenAI 客户端实例
        """
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise AIConfigError(
                    "未安装 openai 库，请运行: pip install openai"
                )

            self._client = OpenAI(
                api_key=self._config.get_resolved_api_key(),
                base_url=self._config.base_url,
                timeout=self._config.timeout,
            )
        return self._client

    def generate(
        self,
        field_schema: Dict[str, Any],
        user_request: str,
    ) -> Dict[str, Any]:
        """根据用户需求生成参数配置

        Args:
            field_schema: 字段定义（包含 field_type、values、selected 等）
            user_request: 用户的自然语言需求

        Returns:
            生成的参数配置（包含 selected 字段）

        Raises:
            AIConfigError: 配置错误
            AIAPIError: API 调用错误
            AIResponseError: 响应解析错误
        """
        if not self.is_configured:
            raise AIConfigError(
                "AI 功能未配置，请在 config/ai_config.yaml 中设置 api_key"
            )

        # 1. 准备输入 JSON（清空 selected）
        input_json = self._prepare_input_json(field_schema)

        # 2. 构建用户消息
        user_message = f"""以下是数据集的字段定义（JSON 格式），所有 selected 字段当前为空。

{json.dumps(input_json, indent=2, ensure_ascii=False)}

用户需求：{user_request}

请根据用户需求，从每个字段的 values 中选择合适的值填入 selected 字段。只输出 JSON，不要有其他文字。"""

        # 3. 调用 API
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": self._config.system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
        except Exception as e:
            logger.error(f"AI API 调用失败: {e}")
            raise AIAPIError(f"AI API 调用失败: {e}")

        # 4. 解析响应
        try:
            content = response.choices[0].message.content
            if not content:
                raise AIResponseError("AI 返回空响应")

            # 提取 JSON（可能被 markdown 代码块包裹）
            result_json = self._extract_json(content)

            # 验证并修复结果
            validated_result = self._validate_and_fix_result(
                input_json,
                result_json,
                field_schema,
            )

            return validated_result

        except (KeyError, IndexError) as e:
            raise AIResponseError(f"AI 响应格式错误: {e}")

    def _prepare_input_json(self, field_schema: Dict[str, Any]) -> Dict[str, Any]:
        """准备输入 JSON（清空 selected，保留 values）

        Args:
            field_schema: 原始字段定义

        Returns:
            处理后的字段定义（selected 为空）
        """
        result = {}
        for field_name, field_info in field_schema.items():
            if not isinstance(field_info, dict):
                continue

            result[field_name] = {
                "field_type": field_info.get("field_type", "string_list"),
                "values": field_info.get("values", []),
                "selected": [],  # 清空已选项
            }

        return result

    def _extract_json(self, content: str) -> Dict[str, Any]:
        """从 AI 响应中提取 JSON

        支持以下格式：
        - 纯 JSON
        - Markdown 代码块包裹的 JSON
        - 带有额外文本的 JSON

        Args:
            content: AI 响应内容

        Returns:
            解析后的 JSON 对象

        Raises:
            AIResponseError: 无法解析 JSON
        """
        content = content.strip()

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 markdown 代码块中的 JSON
        import re
        code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
        matches = re.findall(code_block_pattern, content)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # 尝试找到第一个 { 和最后一个 } 之间的内容
        start_idx = content.find("{")
        end_idx = content.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(content[start_idx : end_idx + 1])
            except json.JSONDecodeError:
                pass

        raise AIResponseError(f"无法从 AI 响应中提取有效 JSON: {content[:200]}...")

    def _validate_and_fix_result(
        self,
        input_json: Dict[str, Any],
        result_json: Dict[str, Any],
        original_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """验证并修复 AI 生成的结果

        确保生成的 selected 值都在 values 列表中。

        Args:
            input_json: 输入的字段定义
            result_json: AI 返回的结果
            original_schema: 原始字段定义（包含完整信息）

        Returns:
            验证后的结果
        """
        validated = {}

        for field_name, field_info in input_json.items():
            if field_name not in result_json:
                # AI 没有返回该字段，保持空选择
                validated[field_name] = {
                    **field_info,
                    "selected": [],
                }
                continue

            result_field = result_json[field_name]
            if not isinstance(result_field, dict):
                validated[field_name] = {
                    **field_info,
                    "selected": [],
                }
                continue

            # 获取原始可选值
            original_values = set(str(v) for v in field_info.get("values", []))

            # 过滤 selected，只保留有效值
            raw_selected = result_field.get("selected", [])
            if not isinstance(raw_selected, list):
                raw_selected = [raw_selected] if raw_selected else []

            valid_selected = []
            for value in raw_selected:
                str_value = str(value)
                if str_value in original_values:
                    valid_selected.append(str_value)

            validated[field_name] = {
                **field_info,
                "selected": valid_selected,
            }

        return validated

    def test_connection(self) -> Tuple[bool, str]:
        """测试 AI API 连接

        Returns:
            (是否成功, 消息)
        """
        if not self.is_configured:
            return False, "AI 功能未配置"

        try:
            client = self._get_client()
            # 发送一个简单的测试请求
            response = client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "user", "content": "Hello, this is a test. Reply with 'OK'."},
                ],
                max_tokens=10,
            )
            # 调试：打印完整响应
            logger.debug(f"API Response: {response}")
            if response.choices:
                content = response.choices[0].message.content
                if content:
                    return True, f"AI API 连接成功: {content}"
                else:
                    return False, f"AI API 响应异常: choices[0].message.content 为空, response={response}"
            return False, f"AI API 响应异常: 无 choices, response={response}"
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"AI API 连接失败: {e}\n{error_detail}")
            return False, f"AI API 连接失败: {str(e)}\n{error_detail}"
