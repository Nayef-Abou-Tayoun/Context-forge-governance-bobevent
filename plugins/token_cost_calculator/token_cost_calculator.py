# -*- coding: utf-8 -*-
"""Location: ./plugins/token_cost_calculator/token_cost_calculator.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0

Token Cost Calculator Plugin.

Calculates and displays token costs for tool responses.
Cost per token: $0.000001

Hook: tool_post_invoke
"""

# Future
from __future__ import annotations

# Standard
import json
import logging
from typing import Any, Dict

# Third-Party
from pydantic import BaseModel

# First-Party
from mcpgateway.plugins.framework import (
    Plugin,
    PluginConfig,
    PluginContext,
)
from mcpgateway.plugins.framework.hooks.tools import (
    ToolPostInvokePayload,
    ToolPostInvokeResult,
)

logger = logging.getLogger(__name__)


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
        """Calculate token cost after tool execution and append to response content.

        Args:
            payload: Tool response payload containing result content.
            context: Plugin execution context.

        Returns:
            Result with cost information appended to content and in metadata.
        """
        logger.info("TokenCostCalculatorPlugin.tool_post_invoke called")
        logger.info(f"Tool name: {payload.tool_name}")
        logger.info(f"Payload result type: {type(payload.result)}")
        
        try:
            # Only count tokens for ServiceNow tools
            if not payload.tool_name or "servicenow" not in payload.tool_name.lower():
                logger.info(f"Skipping token count for non-ServiceNow tool: {payload.tool_name}")
                return ToolPostInvokeResult(continue_processing=True)
            
            if not payload.result:
                logger.warning("No result in payload, returning early")
                return ToolPostInvokeResult(continue_processing=True)

            # Count tokens from tool result content (not from our own cost display)
            total_tokens = 0
            
            # Extract text from the tool result
            result_content = payload.result
            logger.info(f"Processing result_content type: {type(result_content)}")
            
            if isinstance(result_content, dict):
                # Handle dict results - look for content fields
                if "content" in result_content:
                    content = result_content["content"]
                    if isinstance(content, list):
                        for item in content:
                            text = _extract_text_from_content(item)
                            total_tokens += _count_tokens(text)
                    else:
                        text = _extract_text_from_content(content)
                        total_tokens += _count_tokens(text)
                else:
                    # Count all dict content
                    text = json.dumps(result_content)
                    total_tokens += _count_tokens(text)
            elif isinstance(result_content, list):
                # Handle list results
                for item in result_content:
                    text = _extract_text_from_content(item)
                    total_tokens += _count_tokens(text)
            else:
                # Handle string or other results
                text = str(result_content)
                total_tokens += _count_tokens(text)

            # Calculate cost
            total_cost = total_tokens * self._cfg.cost_per_token
            logger.info(f"Calculated: {total_tokens} tokens, ${total_cost:.6f} cost")

            # Create cost display text
            cost_text = f"\n\n---\n💰 **Token Cost**: {total_tokens} tokens × ${self._cfg.cost_per_token:.6f} = ${total_cost:.6f}"

            # Append cost information to the response content
            modified_result = payload.result
            if isinstance(modified_result, dict) and "content" in modified_result:
                content = modified_result["content"]
                if isinstance(content, list) and len(content) > 0:
                    # Append to the last text content item
                    last_item = content[-1]
                    if isinstance(last_item, dict) and last_item.get("type") == "text":
                        last_item["text"] = str(last_item.get("text", "")) + cost_text
                    else:
                        # Add new text content item
                        content.append({"type": "text", "text": cost_text})
                elif isinstance(content, str):
                    modified_result["content"] = content + cost_text
            elif isinstance(modified_result, str):
                modified_result = modified_result + cost_text

            # Add cost information to metadata
            cost_info = {
                "token_count": total_tokens,
                "cost_per_token": self._cfg.cost_per_token,
                "total_cost_usd": round(total_cost, 6),
                "cost_display": f"${total_cost:.6f}",
            }

            logger.info(f"Returning modified result with cost info: {cost_info}")
            return ToolPostInvokeResult(
                continue_processing=True,
                result=modified_result,
                metadata=cost_info,
            )
        except Exception as e:
            logger.error(f"Error in TokenCostCalculatorPlugin: {e}", exc_info=True)
            return ToolPostInvokeResult(continue_processing=True)

# Made with Bob
