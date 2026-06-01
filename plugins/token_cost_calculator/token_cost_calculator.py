# -*- coding: utf-8 -*-
"""Location: ./plugins/token_cost_calculator/token_cost_calculator.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0

Token Cost Calculator Plugin.

Calculates and displays token costs for agent responses.
Cost per token: $0.000001

Hook: agent_post_invoke
"""

# Future
from __future__ import annotations

# Standard
import json
from typing import Any, Dict

# Third-Party
from pydantic import BaseModel

# First-Party
from mcpgateway.plugins.framework import (
    Plugin,
    PluginConfig,
    PluginContext,
)
from mcpgateway.plugins.framework.hooks.agents import (
    AgentPostInvokePayload,
    AgentPostInvokeResult,
)


class TokenCostConfig(BaseModel):
    """Configuration for token cost calculation.

    Attributes:
        cost_per_token: Cost per token in USD (default: 0.000001).
        display_in_metadata: Whether to add cost to metadata (default: True).
    """

    cost_per_token: float = 0.000001
    display_in_metadata: bool = True


def _count_tokens(text: str) -> int:
    """Simple token counter (approximation: 1 token ≈ 4 characters).

    Args:
        text: Text to count tokens for.

    Returns:
        Approximate token count.
    """
    return len(text) // 4


def _extract_text_from_content(content: Any) -> str:
    """Extract text from various content formats.

    Args:
        content: Content to extract text from.

    Returns:
        Extracted text string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if "text" in content:
            return str(content["text"])
        return json.dumps(content)
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            elif isinstance(item, str):
                texts.append(item)
        return " ".join(texts)
    return str(content)


class TokenCostCalculatorPlugin(Plugin):
    """Calculate and display token costs for tool invocations."""

    def __init__(self, config: PluginConfig) -> None:
        """Initialize the token cost calculator plugin.

        Args:
            config: Plugin configuration.
        """
        super().__init__(config)
        self._cfg = TokenCostConfig(**(config.config or {}))

    async def agent_post_invoke(self, payload: AgentPostInvokePayload, context: PluginContext) -> AgentPostInvokeResult:
        """Calculate token cost after agent responds.

        Args:
            payload: Agent response payload containing messages.
            context: Plugin execution context.

        Returns:
            Result with cost information in metadata.
        """
        if not payload.messages or not self._cfg.display_in_metadata:
            return AgentPostInvokeResult(continue_processing=True)

        # Count tokens from all agent messages
        total_tokens = 0
        for message in payload.messages:
            # Extract content from message (supports both dict and object formats)
            content = None
            if isinstance(message, dict):
                content = message.get("content", "")
            elif hasattr(message, "content"):
                content = message.content
            
            if content:
                # Handle content that might be a list or string
                if isinstance(content, list):
                    for item in content:
                        text = _extract_text_from_content(item)
                        total_tokens += _count_tokens(text)
                else:
                    text = str(content)
                    total_tokens += _count_tokens(text)

        # Calculate cost
        total_cost = total_tokens * self._cfg.cost_per_token

        # Add cost information to metadata (don't modify the response content)
        cost_info = {
            "token_count": total_tokens,
            "cost_per_token": self._cfg.cost_per_token,
            "total_cost_usd": round(total_cost, 6),
            "cost_display": f"${total_cost:.6f}",
        }

        return AgentPostInvokeResult(
            continue_processing=True,
            metadata=cost_info,
        )

# Made with Bob
