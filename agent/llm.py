"""
agent/llm.py
Thin wrapper around AWS Bedrock for Claude.
All agent reasoning flows through this module — nowhere else.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config.settings import AWS_ACCESS_KEY, AWS_REGION, AWS_SECRET_KEY, AWS_BEDROCK_MODEL_ID

logger = logging.getLogger(__name__)


class BedrockLLM:
    """Synchronous Claude-on-Bedrock client."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
        )
        self.model_id = AWS_BEDROCK_MODEL_ID
        logger.info("BedrockLLM ready – model=%s region=%s", self.model_id, AWS_REGION)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, Any]],
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """
        Send a conversation turn and return the assistant text.

        Parameters
        ----------
        messages : list of {"role": "user"|"assistant", "content": str}
        system   : optional system prompt string
        """
        body: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            body["system"] = system

        try:
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            return result["content"][0]["text"]
        except (BotoCoreError, ClientError) as exc:
            logger.error("Bedrock call failed: %s", exc)
            raise

    def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        """Convenience wrapper – single user turn."""
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            **kwargs,
        )


# Singleton
_llm: BedrockLLM | None = None


def get_llm() -> BedrockLLM:
    global _llm
    if _llm is None:
        _llm = BedrockLLM()
    return _llm
