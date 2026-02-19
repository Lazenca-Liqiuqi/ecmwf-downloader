"""
AI 参数生成服务

基于 OpenAI 兼容 API，根据用户自然语言需求智能生成数据集下载参数。
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.core.ai_config import AIConfig, AIConfigLoader

logger = logging.getLogger(__name__)

# AI 日志目录
AI_LOG_DIR = Path("logs/ai")


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

    def _write_log(self, log_data: Dict[str, Any]) -> None:
        """写入 AI 交互日志

        Args:
            log_data: 日志数据
        """
        try:
            # 确保日志目录存在
            AI_LOG_DIR.mkdir(parents=True, exist_ok=True)

            # 生成日志文件名（每次请求一个单独的文件，使用时间戳）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            status = log_data.get("status", "unknown")
            log_file = AI_LOG_DIR / f"ai_{timestamp}_{status}.log"

            # 格式化写入日志（易读格式）
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("=" * 60 + "\n")
                f.write(f"时间: {log_data.get('timestamp', 'N/A')}\n")
                f.write(f"状态: {log_data.get('status', 'N/A')}\n")
                f.write(f"耗时: {log_data.get('elapsed_time', 'N/A')}s\n")
                f.write("-" * 60 + "\n")

                # 请求信息
                request = log_data.get("request", {})
                f.write(f"模型: {request.get('model', 'N/A')}\n")
                f.write(f"温度: {request.get('temperature', 'N/A')}\n")
                f.write(f"最大Token: {request.get('max_tokens', 'N/A')}\n")
                f.write(f"超时: {request.get('timeout', 'N/A')}s\n")

                # 请求消息
                f.write("\n[请求消息]\n")
                for msg in request.get("messages", []):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    f.write(f"--- {role.upper()} ---\n")
                    f.write(content + "\n")

                # 响应信息
                response = log_data.get("response", {})
                if response:
                    f.write("-" * 60 + "\n")
                    f.write("[响应内容]\n")
                    f.write(response.get("content", "N/A") + "\n")

                    usage = response.get("usage", {})
                    if usage:
                        f.write("\n[Token 使用]\n")
                        f.write(f"  Prompt: {usage.get('prompt_tokens', 'N/A')}\n")
                        f.write(f"  Completion: {usage.get('completion_tokens', 'N/A')}\n")
                        f.write(f"  Total: {usage.get('total_tokens', 'N/A')}\n")

                # 错误信息
                if log_data.get("status") == "error":
                    f.write("-" * 60 + "\n")
                    f.write(f"[错误] {log_data.get('error', 'Unknown error')}\n")

                f.write("=" * 60 + "\n")

            logger.info(f"AI 日志已写入: {log_file}")
        except Exception as e:
            logger.warning(f"写入 AI 日志失败: {e}")

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

        # 记录开始时间
        start_time = time.time()

        # 1. 准备输入 JSON（清空 selected）
        input_json = self._prepare_input_json(field_schema)

        # 2. 构建用户消息
        user_message = f"""以下是数据集的字段定义（JSON 格式），所有 selected 字段当前为空。

{json.dumps(input_json, indent=2, ensure_ascii=False)}

用户需求：{user_request}

请根据用户需求，从每个字段的 values 中选择合适的值填入 selected 字段。只输出 JSON，不要有其他文字。"""

        # 构建完整的 messages
        messages = [
            {"role": "system", "content": self._config.system_prompt},
            {"role": "user", "content": user_message},
        ]

        # 记录请求日志
        logger.info(f"AI 请求开始 - 模型: {self._config.model}, 用户需求: {user_request[:50]}...")

        # 3. 调用 API（带超时控制）
        try:
            client = self._get_client()
            logger.debug(f"AI API 超时设置: {self._config.timeout}s")

            response = client.chat.completions.create(
                model=self._config.model,
                messages=messages,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                timeout=self._config.timeout,
            )
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = str(e)

            # 写入失败日志
            self._write_log({
                "timestamp": datetime.now().isoformat(),
                "elapsed_time": round(elapsed_time, 2),
                "status": "error",
                "error": error_msg,
                "request": {
                    "model": self._config.model,
                    "temperature": self._config.temperature,
                    "max_tokens": self._config.max_tokens,
                    "timeout": self._config.timeout,
                    "messages": messages,
                },
            })

            logger.error(f"AI API 调用失败 ({elapsed_time:.2f}s): {e}")
            raise AIAPIError(f"AI API 调用失败: {e}")

        # 计算耗时
        elapsed_time = time.time() - start_time

        # 4. 解析响应
        try:
            # 获取原始响应内容
            raw_content = response.choices[0].message.content if response.choices else None

            # 写入成功日志
            self._write_log({
                "timestamp": datetime.now().isoformat(),
                "elapsed_time": round(elapsed_time, 2),
                "status": "success",
                "request": {
                    "model": self._config.model,
                    "temperature": self._config.temperature,
                    "max_tokens": self._config.max_tokens,
                    "timeout": self._config.timeout,
                    "messages": messages,
                },
                "response": {
                    "content": raw_content,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                        "completion_tokens": response.usage.completion_tokens if response.usage else None,
                        "total_tokens": response.usage.total_tokens if response.usage else None,
                    },
                },
            })

            if not raw_content:
                raise AIResponseError("AI 返回空响应")

            logger.info(f"AI 响应成功 ({elapsed_time:.2f}s), 响应长度: {len(raw_content)} 字符")

            # 提取 JSON（可能被 markdown 代码块包裹）
            result_json = self._extract_json(raw_content)

            # 验证并修复结果
            validated_result = self._validate_and_fix_result(
                input_json,
                result_json,
                field_schema,
            )

            return validated_result

        except (KeyError, IndexError) as e:
            logger.error(f"AI 响应格式错误: {e}")
            raise AIResponseError(f"AI 响应格式错误: {e}")

    def _smart_sort_values(self, values: list) -> list:
        """智能排序值列表

        排序规则：
        - 纯数字：按数值大小排序
        - 纯字符串：按字母顺序排序
        - 混合：数字在前（按数值），字符串在后（按字母）

        Args:
            values: 待排序的值列表

        Returns:
            排序后的值列表
        """
        if not values:
            return []

        numeric_values = []
        string_values = []

        for v in values:
            str_v = str(v)
            try:
                num = int(str_v)
                numeric_values.append((num, v))
            except ValueError:
                try:
                    num = float(str_v)
                    numeric_values.append((num, v))
                except ValueError:
                    string_values.append((str_v.lower(), v))

        numeric_values.sort(key=lambda x: x[0])
        string_values.sort(key=lambda x: x[0])

        return [v for _, v in numeric_values] + [v for _, v in string_values]

    def _prepare_input_json(self, field_schema: Dict[str, Any]) -> Dict[str, Any]:
        """准备输入 JSON（清空 selected，保留 values 并智能排序）

        Args:
            field_schema: 原始字段定义

        Returns:
            处理后的字段定义（selected 为空，values 智能排序）
        """
        result = {}
        for field_name, field_info in field_schema.items():
            if not isinstance(field_info, dict):
                continue

            raw_values = field_info.get("values", [])
            # 对 values 进行智能排序
            sorted_values = self._smart_sort_values(raw_values)

            result[field_name] = {
                "field_type": field_info.get("field_type", "string_list"),
                "values": sorted_values,
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
