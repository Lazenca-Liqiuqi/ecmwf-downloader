"""
AI 配置模型

定义 AI 生成功能的配置结构，支持 OpenAI 兼容 API。
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class AIConfig(BaseModel):
    """AI 生成配置模型

    支持 OpenAI 兼容 API（OpenAI、Azure OpenAI、本地 LLM 等）。

    Attributes:
        enabled: 是否启用 AI 生成功能
        base_url: API 基础 URL
        api_key: API 密钥（支持环境变量替换）
        model: 使用的模型名称
        temperature: 生成温度（0-2，较低值更稳定）
        max_tokens: 最大生成 token 数
        timeout: 请求超时时间（秒）
        system_prompt: 系统提示词
    """

    enabled: bool = Field(default=True, description="是否启用 AI 生成功能")
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="API 基础 URL",
    )
    api_key: str = Field(
        default="",
        description="API 密钥（支持环境变量 ${VAR_NAME} 格式）",
    )
    model: str = Field(
        default="gpt-4o",
        description="使用的模型名称",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="生成温度（0-2，较低值更稳定）",
    )
    max_tokens: int = Field(
        default=8192,
        ge=1,
        description="最大生成 token 数",
    )
    timeout: int = Field(
        default=60,
        ge=1,
        description="请求超时时间（秒）",
    )
    system_prompt: str = Field(
        default="",
        description="系统提示词",
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def expand_env_vars(cls, v: str) -> str:
        """展开环境变量

        支持 ${VAR_NAME} 格式的环境变量替换。

        Args:
            v: 原始值

        Returns:
            替换环境变量后的值
        """
        if not v:
            return v

        def replace_env(match: re.Match) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, "")

        return re.sub(r"\$\{([^}]+)\}", replace_env, v)

    @field_validator("base_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """移除末尾斜杠"""
        if v.endswith("/"):
            return v[:-1]
        return v

    def get_resolved_api_key(self) -> str:
        """获取解析后的 API 密钥

        Returns:
            解析环境变量后的 API 密钥
        """
        return self.api_key


class AIConfigLoader:
    """AI 配置加载器

    从 YAML 文件加载 AI 配置，支持默认值和配置验证。
    """

    DEFAULT_CONFIG_PATH = Path("config/ai_config.yaml")

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> AIConfig:
        """加载 AI 配置

        Args:
            config_path: 配置文件路径，默认为 config/ai_config.yaml

        Returns:
            AIConfig 实例

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置文件格式错误
        """
        if config_path is None:
            config_path = cls.DEFAULT_CONFIG_PATH

        if not config_path.exists():
            # 配置文件不存在时返回默认配置
            return AIConfig()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            if not raw_config:
                return AIConfig()

            # 提取 ai 节点
            ai_config = raw_config.get("ai", {})
            return AIConfig(**ai_config)

        except yaml.YAMLError as e:
            raise ValueError(f"AI 配置文件格式错误: {e}")
        except Exception as e:
            raise ValueError(f"加载 AI 配置失败: {e}")

    @classmethod
    def save(cls, config: AIConfig, config_path: Optional[Path] = None) -> None:
        """保存 AI 配置

        Args:
            config: AIConfig 实例
            config_path: 配置文件路径，默认为 config/ai_config.yaml
        """
        if config_path is None:
            config_path = cls.DEFAULT_CONFIG_PATH

        config_path.parent.mkdir(parents=True, exist_ok=True)

        config_dict = config.model_dump()
        # 脱敏 API Key（只保留前后各4位）
        if config_dict.get("api_key") and len(config_dict["api_key"]) > 12:
            key = config_dict["api_key"]
            config_dict["api_key"] = f"{key[:4]}...{key[-4:]}"

        raw_config = {"ai": config_dict}

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw_config, f, allow_unicode=True, default_flow_style=False)
