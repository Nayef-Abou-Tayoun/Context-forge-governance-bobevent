# -*- coding: utf-8 -*-
"""Location: ./plugins/token_cost_calculator/token_cost_calculator.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0

Token Cost Calculator Plugin.

Calculates and displays token costs for tool invocations.
Cost per token: $0.000001

Hook: tool_post_invoke
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
    ToolPostInvokePayload,
    ToolPostInvokeResult,
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

    async def tool_post_invoke(self, payload: ToolPostInvokePayload, context: PluginContext) -> ToolPostInvokeResult:
        """Calculate token cost after tool invocation.

        Args:
            payload: Tool invocation result payload.
            context: Plugin execution context.

        Returns:
            Result with cost information appended to message content.
        """
        if not payload.result or not self._cfg.display_in_metadata:
            return ToolPostInvokeResult(continue_processing=True)

        # Count tokens from tool result content
        total_tokens = 0
        original_content = []
        for content_item in payload.result.content:
            text = _extract_text_from_content(content_item)
            total_tokens += _count_tokens(text)
            original_content.append(content_item)

        # Calculate cost
        total_cost = total_tokens * self._cfg.cost_per_token

        # Create cost display text
        cost_text = f"\n\n💰 **Token Cost**: {total_tokens} tokens × ${self._cfg.cost_per_token:.6f} = ${total_cost:.6f}"

        # Append cost to the last text content item
        modified_content = []
        for i, content_item in enumerate(original_content):
            if i == len(original_content) - 1:  # Last item
                if isinstance(content_item, dict) and "text" in content_item:
                    # Modify dict content
                    modified_item = content_item.copy()
                    modified_item["text"] = str(content_item["text"]) + cost_text
                    modified_content.append(modified_item)
                elif hasattr(content_item, "text"):
                    # Modify object with text attribute
                    modified_item = type(content_item)(
                        type=getattr(content_item, "type", "text"),
                        text=str(content_item.text) + cost_text
                    )
                    modified_content.append(modified_item)
                else:
                    # Fallback: append as string
                    modified_content.append(str(content_item) + cost_text)
            else:
                modified_content.append(content_item)

        # Create modified payload
        from copy import deepcopy
        modified_result = deepcopy(payload.result)
        modified_result.content = modified_content
        
        modified_payload = ToolPostInvokePayload(
            tool_name=payload.tool_name,
            arguments=payload.arguments,
            result=modified_result
        )

        # Add cost information to metadata
        cost_info = {
            "token_count": total_tokens,
            "cost_per_token": self._cfg.cost_per_token,
            "total_cost_usd": round(total_cost, 6),
            "cost_display": f"${total_cost:.6f}",
        }

        return ToolPostInvokeResult(
            modified_payload=modified_payload,
            continue_processing=True,
            metadata=cost_info,
        )

# Made with Bob
