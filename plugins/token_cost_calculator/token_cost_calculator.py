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

        # Handle dict results with 'content' key (MCP format)
        if isinstance(payload.result, dict) and "content" in payload.result:
            content_list = payload.result.get("content", [])
            if not content_list:
                return ToolPostInvokeResult(continue_processing=True)

            # Count tokens from content items
            total_tokens = 0
            for content_item in content_list:
                text = _extract_text_from_content(content_item)
                total_tokens += _count_tokens(text)

            # Calculate cost
            total_cost = total_tokens * self._cfg.cost_per_token

            # Create cost display text
            cost_text = f"\n\n💰 **Token Cost**: {total_tokens} tokens × ${self._cfg.cost_per_token:.6f} = ${total_cost:.6f}"

            # Append cost to the last text content item
            modified_content = []
            for i, content_item in enumerate(content_list):
                if i == len(content_list) - 1:  # Last item
                    if isinstance(content_item, dict) and "text" in content_item:
                        # Modify dict content
                        modified_item = content_item.copy()
                        modified_item["text"] = str(content_item["text"]) + cost_text
                        modified_content.append(modified_item)
                    elif hasattr(content_item, "text"):
                        # Modify object with text attribute
                        from copy import deepcopy
                        modified_item = deepcopy(content_item)
                        modified_item.text = str(content_item.text) + cost_text
                        modified_content.append(modified_item)
                    else:
                        # Fallback: append as new text item
                        modified_content.append(content_item)
                        modified_content.append({"type": "text", "text": cost_text})
                else:
                    modified_content.append(content_item)

            # Create modified result
            from copy import deepcopy
            modified_result = deepcopy(payload.result)
            modified_result["content"] = modified_content

            # Create modified payload
            modified_payload = ToolPostInvokePayload(
                name=payload.name,
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
