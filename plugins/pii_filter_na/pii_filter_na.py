# -*- coding: utf-8 -*-
"""Location: ./plugins/pii_filter_na/pii_filter_na.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

Canadian PII Filter Plugin for ContextForge.
This plugin detects and masks Personally Identifiable Information (PII) specific to
Canada, including SIN, postal codes, and health card numbers.
"""

# Standard
from enum import Enum
import logging
import re
from typing import Any, Dict, List, Pattern, Tuple

# Third-Party
import orjson
from pydantic import BaseModel, Field

# First-Party
from mcpgateway.plugins.framework import (
    Plugin,
    PluginConfig,
    PluginContext,
    PluginViolation,
    PromptPosthookPayload,
    PromptPosthookResult,
    PromptPrehookPayload,
    PromptPrehookResult,
    ToolPostInvokePayload,
    ToolPostInvokeResult,
    ToolPreInvokePayload,
    ToolPreInvokeResult,
)
from mcpgateway.services.logging_service import LoggingService

# Initialize logging service first
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)

# Try to import Rust-accelerated implementation
_RUST_AVAILABLE = False
_RustPIIDetector = None

try:
    # Import from installed Rust package (two-level deep call)
    from pii_filter_rust.pii_filter_rust import PIIDetectorRust as _RustPIIDetector

    _RUST_AVAILABLE = True
    logger.info("🦀 Rust PII filter available - using high-performance implementation (5-100x speedup)")
except ImportError as e:
    logger.debug(f"Rust PII filter not available (will use Python): {e}")
    _RUST_AVAILABLE = False
except Exception as e:
    logger.warning(f"⚠️  Unexpected error loading Rust module: {e}", exc_info=True)
    _RUST_AVAILABLE = False


class PIIType(str, Enum):
    """Types of PII that can be detected - Canadian specific."""

    # Canada-specific
    SIN = "sin"  # Canadian Social Insurance Number
    CANADIAN_POSTAL_CODE = "canadian_postal_code"
    CANADIAN_HEALTH_CARD = "canadian_health_card"
    CUSTOM = "custom"


class MaskingStrategy(str, Enum):
    """Strategies for masking detected PII."""

    REDACT = "redact"  # Replace with [REDACTED]
    PARTIAL = "partial"  # Show partial info (e.g., ***-**-1234)
    HASH = "hash"  # Replace with hash
    TOKENIZE = "tokenize"  # Replace with token
    REMOVE = "remove"  # Remove entirely


class PIIPattern(BaseModel):
    """Configuration for a PII pattern."""

    type: PIIType
    pattern: str
    description: str
    mask_strategy: MaskingStrategy = MaskingStrategy.REDACT
    enabled: bool = True


class PIIFilterNAConfig(BaseModel):
    """Configuration for the Canadian PII Filter plugin."""

    # Canada-specific PII types
    detect_sin: bool = Field(default=True, description="Detect Canadian Social Insurance Numbers")
    detect_canadian_postal_code: bool = Field(default=True, description="Detect Canadian postal codes")
    detect_canadian_health_card: bool = Field(default=True, description="Detect Canadian health card numbers")

    # Masking configuration
    default_mask_strategy: MaskingStrategy = Field(default=MaskingStrategy.PARTIAL, description="Default masking strategy")
    redaction_text: str = Field(default="[REDACTED]", description="Text to use for redaction")

    # Behavior configuration
    block_on_detection: bool = Field(default=False, description="Block request if PII is detected")
    log_detections: bool = Field(default=True, description="Log PII detections")
    include_detection_details: bool = Field(default=True, description="Include detection details in metadata")

    # Custom patterns
    custom_patterns: List[PIIPattern] = Field(default_factory=list, description="Custom PII patterns to detect")

    # Whitelist configuration
    whitelist_patterns: List[str] = Field(default_factory=list, description="Patterns to exclude from PII detection")


class PIIDetectorNA:
    """Core PII detection logic for North America."""

    def __init__(self, config: PIIFilterNAConfig):
        """Initialize the PII detector with configuration.

        Args:
            config: North America PII filter configuration
        """
        self.config = config
        self.patterns: Dict[PIIType, List[Tuple[Pattern, MaskingStrategy]]] = {}
        self._compile_patterns()
        self._compile_whitelist()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for Canadian PII detection."""
        patterns = []

        # Canadian Social Insurance Number (SIN)
        # Format: XXX-XXX-XXX (9 digits with dashes)
        if self.config.detect_sin:
            patterns.extend([
                PIIPattern(
                    type=PIIType.SIN,
                    pattern=r"\b\d{3}-\d{3}-\d{3}\b",
                    description="Canadian SIN with dashes",
                    mask_strategy=MaskingStrategy.PARTIAL
                ),
                PIIPattern(
                    type=PIIType.SIN,
                    pattern=r"\b(?:SIN|Social Insurance Number)[:\s#]+\d{3}[-\s]?\d{3}[-\s]?\d{3}\b",
                    description="Canadian SIN with label",
                    mask_strategy=MaskingStrategy.PARTIAL
                ),
            ])

        # Canadian Postal Code
        # Format: A1A 1A1 (letter-digit-letter space digit-letter-digit)
        if self.config.detect_canadian_postal_code:
            patterns.append(
                PIIPattern(
                    type=PIIType.CANADIAN_POSTAL_CODE,
                    pattern=r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b",
                    description="Canadian postal code",
                    mask_strategy=MaskingStrategy.PARTIAL
                )
            )

        # Canadian Health Card Numbers (varies by province)
        # Ontario: 1234-567-890 (10 digits with dashes)
        # Quebec: ABCD 1234 5678 (4 letters + 8 digits)
        # BC: 9123456789 (10 digits)
        if self.config.detect_canadian_health_card:
            patterns.extend([
                PIIPattern(
                    type=PIIType.CANADIAN_HEALTH_CARD,
                    pattern=r"\b\d{4}-\d{3}-\d{3}\b",
                    description="Ontario health card",
                    mask_strategy=MaskingStrategy.PARTIAL
                ),
                PIIPattern(
                    type=PIIType.CANADIAN_HEALTH_CARD,
                    pattern=r"\b[A-Z]{4}\s?\d{4}\s?\d{4}\b",
                    description="Quebec health card",
                    mask_strategy=MaskingStrategy.PARTIAL
                ),
                PIIPattern(
                    type=PIIType.CANADIAN_HEALTH_CARD,
                    pattern=r"\b9\d{9}\b",
                    description="BC health card",
                    mask_strategy=MaskingStrategy.PARTIAL
                ),
                PIIPattern(
                    type=PIIType.CANADIAN_HEALTH_CARD,
                    pattern=r"\b(?:Health Card|HC)[:\s#]+[A-Z0-9\s-]{10,15}\b",
                    description="Canadian health card with label",
                    mask_strategy=MaskingStrategy.PARTIAL
                ),
            ])

        # Add custom patterns
        patterns.extend(self.config.custom_patterns)

        # Compile patterns by type
        for pattern_config in patterns:
            if pattern_config.enabled:
                compiled = re.compile(pattern_config.pattern, re.IGNORECASE)
                if pattern_config.type not in self.patterns:
                    self.patterns[pattern_config.type] = []
                self.patterns[pattern_config.type].append((compiled, pattern_config.mask_strategy))

    def _compile_whitelist(self) -> None:
        """Compile whitelist patterns."""
        self.whitelist_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.config.whitelist_patterns]

    def _is_whitelisted(self, text: str, match_start: int, match_end: int) -> bool:
        """Check if a matched pattern is whitelisted.

        Args:
            text: The full text
            match_start: Start position of the match
            match_end: End position of the match

        Returns:
            True if the match is whitelisted
        """
        match_text = text[match_start:match_end]
        for pattern in self.whitelist_patterns:
            if pattern.search(match_text):
                return True
        return False

    def detect(self, text: str) -> Dict[PIIType, List[Dict]]:
        """Detect PII in text.

        Args:
            text: Text to scan for PII

        Returns:
            Dictionary of detected PII by type
        """
        detections = {}

        for pii_type, pattern_list in self.patterns.items():
            type_detections = []
            seen_ranges = []  # Track ranges we've already detected

            for pattern, mask_strategy in pattern_list:
                for match in pattern.finditer(text):
                    if not self._is_whitelisted(text, match.start(), match.end()):
                        # Check if this overlaps with any existing detection
                        overlaps = False
                        for start, end in seen_ranges:
                            if (match.start() >= start and match.start() < end) or (match.end() > start and match.end() <= end) or (match.start() <= start and match.end() >= end):
                                overlaps = True
                                break

                        if not overlaps:
                            type_detections.append({"value": match.group(), "start": match.start(), "end": match.end(), "mask_strategy": mask_strategy})
                            seen_ranges.append((match.start(), match.end()))

            if type_detections:
                detections[pii_type] = type_detections

        return detections

    def mask(self, text: str, detections: Dict[PIIType, List[Dict]]) -> str:
        """Mask detected PII in text.

        Args:
            text: Original text
            detections: Dictionary of detected PII

        Returns:
            Text with PII masked
        """
        if not detections:
            return text

        # Sort all detections by position (reverse order for replacement)
        all_detections = []
        for pii_type, items in detections.items():
            for item in items:
                item["type"] = pii_type
                all_detections.append(item)

        all_detections.sort(key=lambda x: x["start"], reverse=True)

        # Apply masking
        masked_text = text
        for detection in all_detections:
            strategy = detection.get("mask_strategy", self.config.default_mask_strategy)
            masked_value = self._apply_mask(detection["value"], detection["type"], strategy)
            masked_text = masked_text[: detection["start"]] + masked_value + masked_text[detection["end"] :]

        return masked_text

    def _apply_mask(self, value: str, pii_type: PIIType, strategy: MaskingStrategy) -> str:  # noqa: PLR0911
        """Apply masking strategy to a value.

        Args:
            value: Value to mask
            pii_type: Type of PII
            strategy: Masking strategy to apply

        Returns:
            Masked value
        """
        if strategy == MaskingStrategy.REDACT:
            return self.config.redaction_text

        elif strategy == MaskingStrategy.PARTIAL:
            # Show partial information based on type
            if pii_type == PIIType.SIN:
                # Canadian SIN: Show last 3 digits (XXX-XXX-123)
                if len(value) >= 3:
                    return f"***-***-{value[-3:]}"
                return self.config.redaction_text

            elif pii_type == PIIType.CANADIAN_POSTAL_CODE:
                # Canadian Postal Code: Show first 3 characters (K1A XXX)
                if len(value) >= 3:
                    return f"{value[:3]} ***"
                return self.config.redaction_text

            elif pii_type == PIIType.CANADIAN_HEALTH_CARD:
                # Health Card: Show last 3 digits
                if len(value) >= 3:
                    return f"****-***-{value[-3:]}"
                return self.config.redaction_text

            else:
                # For custom types, show first and last characters
                if len(value) > 2:
                    return f"{value[0]}{'*' * (len(value) - 2)}{value[-1]}"
                return self.config.redaction_text

        elif strategy == MaskingStrategy.HASH:
            # Standard
            import hashlib

            return f"[HASH:{hashlib.sha256(value.encode()).hexdigest()[:8]}]"

        elif strategy == MaskingStrategy.TOKENIZE:
            # Standard
            import uuid

            # In production, you'd store the mapping
            return f"[TOKEN:{uuid.uuid4().hex[:8]}]"

        elif strategy == MaskingStrategy.REMOVE:
            return ""

        return self.config.redaction_text


class PIIFilterNAPlugin(Plugin):
    """North America PII Filter plugin for detecting and masking sensitive information."""

    def __init__(self, config: PluginConfig):
        """Initialize the North America PII filter plugin.

        Args:
            config: Plugin configuration
        """
        super().__init__(config)
        self.pii_config = PIIFilterNAConfig.model_validate(self._config.config)

        # Auto-detect and use Rust implementation if available
        if _RUST_AVAILABLE and _RustPIIDetector is not None:
            self.detector = _RustPIIDetector(self.pii_config)
            self.implementation = "Rust"
            logger.info("🦀 PIIFilterNAPlugin initialized with Rust acceleration (5-100x speedup)")
        else:
            self.detector = PIIDetectorNA(self.pii_config)
            self.implementation = "Python"
            logger.info("🐍 PIIFilterNAPlugin initialized with Python implementation")

        self.detection_count = 0
        self.masked_count = 0

    async def prompt_pre_fetch(self, payload: PromptPrehookPayload, context: PluginContext) -> PromptPrehookResult:
        """Process prompt before retrieval to detect and mask PII.

        Args:
            payload: The prompt payload
            context: Plugin context

        Returns:
            Result with masked PII or violation if blocking
        """
        if not payload.args:
            return PromptPrehookResult()

        all_detections = {}
        modified_args = {}

        # Process each argument
        for key, value in payload.args.items():
            if isinstance(value, str):
                detections = self.detector.detect(value)

                if detections:
                    all_detections[key] = detections

                    if self.pii_config.log_detections:
                        logger.warning(f"PII detected in prompt argument '{key}': {', '.join(detections.keys())}")

                    if self.pii_config.block_on_detection:
                        detected_types = list(detections.keys())
                        # Log at DEBUG level with full prompt content
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"PII filter blocking prompt - full content: {value}")
                        else:
                            # Log at WARNING level with redacted content
                            logger.warning(f"PII filter blocked prompt in argument '{key}' - detected types: {detected_types} (content redacted)")
                        violation = PluginViolation(
                            reason="PII detected in prompt",
                            description=f"Sensitive information detected in argument '{key}'",
                            code="PII_DETECTED",
                            details={"field": key, "types": detected_types, "count": sum(len(items) for items in detections.values())},
                        )
                        return PromptPrehookResult(continue_processing=False, violation=violation)

                    # Mask the PII
                    masked_value = self.detector.mask(value, detections)
                    modified_args[key] = masked_value
                    self.masked_count += sum(len(items) for items in detections.values())
                else:
                    modified_args[key] = value
            else:
                modified_args[key] = value

        # Update context with detection metadata
        if all_detections and self.pii_config.include_detection_details:
            context.metadata["pii_detections"] = {
                "pre_fetch": {
                    "detected": True,
                    "fields": list(all_detections.keys()),
                    "types": list(set(pii_type for field_detections in all_detections.values() for pii_type in field_detections.keys())),
                    "total_count": sum(len(items) for field_detections in all_detections.values() for items in field_detections.values()),
                }
            }

        # Return modified payload if PII was masked
        if all_detections:
            return PromptPrehookResult(modified_payload=PromptPrehookPayload(prompt_id=payload.prompt_id, args=modified_args))

        return PromptPrehookResult()

    async def prompt_post_fetch(self, payload: PromptPosthookPayload, context: PluginContext) -> PromptPosthookResult:
        """Process prompt after rendering to detect and mask PII in response.

        Args:
            payload: The prompt result payload
            context: Plugin context

        Returns:
            Result with masked PII in messages
        """
        if not payload.result.messages:
            return PromptPosthookResult()

        modified = False
        all_detections = {}

        # Process each message
        for message in payload.result.messages:
            if message.content and hasattr(message.content, "text"):
                text = message.content.text
                detections = self.detector.detect(text)

                if detections:
                    all_detections[f"message_{message.role}"] = detections

                    if self.pii_config.log_detections:
                        logger.warning(f"PII detected in {message.role} message: {', '.join(detections.keys())}")

                    # Mask the PII
                    masked_text = self.detector.mask(text, detections)
                    message.content.text = masked_text
                    modified = True
                    self.masked_count += sum(len(items) for items in detections.values())

        # Update context with post-fetch detection metadata
        if all_detections and self.pii_config.include_detection_details:
            if "pii_detections" not in context.metadata:
                context.metadata["pii_detections"] = {}

            context.metadata["pii_detections"]["post_fetch"] = {
                "detected": True,
                "messages": list(all_detections.keys()),
                "types": list(set(pii_type for msg_detections in all_detections.values() for pii_type in msg_detections.keys())),
                "total_count": sum(len(items) for msg_detections in all_detections.values() for items in msg_detections.values()),
            }

        # Add summary statistics
        context.metadata["pii_filter_stats"] = {"total_detections": self.detection_count, "total_masked": self.masked_count}

        if modified:
            return PromptPosthookResult(modified_payload=payload)

        return PromptPosthookResult()

    async def tool_pre_invoke(self, payload: ToolPreInvokePayload, context: PluginContext) -> ToolPreInvokeResult:
        """Detect and mask PII in tool arguments before invocation.

        Args:
            payload: The tool payload containing arguments.
            context: Plugin execution context.

        Returns:
            Result with potentially modified tool arguments.
        """
        logger.debug(f"Processing tool pre-invoke for tool '{payload.name}' with {len(payload.args) if payload.args else 0} arguments")

        if not payload.args:
            return ToolPreInvokeResult()

        modified = False
        all_detections = {}

        # Use intelligent nested processing for tool arguments
        modified, detections = self._process_nested_data_for_pii(payload.args, "args", all_detections)

        if detections:
            detected_types = list(set(pii_type for arg_detections in all_detections.values() for pii_type in arg_detections.keys()))
            if self.pii_config.log_detections:
                logger.warning(f"PII detected in tool '{payload.name}' arguments: {', '.join(map(str, detected_types))}")

        if detections and self.pii_config.block_on_detection:
            detected_type_list = list(set(pii_type for arg_detections in all_detections.values() for pii_type in arg_detections.keys()))
            # Log at DEBUG level with full content
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"PII filter blocking tool '{payload.name}' - full arguments: {payload.args}")
            else:
                # Log at WARNING level with redacted content
                logger.warning(f"PII filter blocked tool '{payload.name}' arguments - detected types: {detected_type_list} (content redacted)")
            violation = PluginViolation(
                reason="PII detected in tool arguments",
                description="Detected PII in tool arguments",
                code="PII_DETECTED_IN_TOOL_ARGS",
                details={
                    "detected_types": detected_type_list,
                    "total_count": sum(len(items) for arg_detections in all_detections.values() for items in arg_detections.values()),
                },
            )
            return ToolPreInvokeResult(continue_processing=False, violation=violation)

        # Store detection metadata
        if all_detections and self.pii_config.include_detection_details:
            if "pii_detections" not in context.metadata:
                context.metadata["pii_detections"] = {}

            context.metadata["pii_detections"]["tool_pre_invoke"] = {
                "detected": True,
                "arguments": list(all_detections.keys()),
                "types": list(set(pii_type for arg_detections in all_detections.values() for pii_type in arg_detections.keys())),
                "total_count": sum(len(items) for arg_detections in all_detections.values() for items in arg_detections.values()),
            }

        if modified:
            logger.info(f"Modified tool '{payload.name}' arguments to mask PII")
            return ToolPreInvokeResult(modified_payload=payload)

        return ToolPreInvokeResult()

    async def tool_post_invoke(self, payload: ToolPostInvokePayload, context: PluginContext) -> ToolPostInvokeResult:
        """Detect and mask PII in tool results after invocation.

        Args:
            payload: The tool result payload.
            context: Plugin execution context.

        Returns:
            Result with potentially modified tool results.
        """
        logger.debug(f"Processing tool post-invoke for tool '{payload.name}', result type: {type(payload.result).__name__}")

        if not payload.result:
            return ToolPostInvokeResult()

        modified = False
        all_detections = {}

        # Handle string results
        if isinstance(payload.result, str):
            detections = self.detector.detect(payload.result)
            if detections:
                all_detections["result"] = detections
                self.detection_count += sum(len(items) for items in detections.values())

                if self.pii_config.log_detections:
                    logger.warning(f"PII detected in tool result: {', '.join(detections.keys())}")

                # Check if we should block
                if self.pii_config.block_on_detection:
                    detected_types = list(detections.keys())
                    # Log at DEBUG level with full content
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"PII filter blocking tool '{payload.name}' result - full content: {payload.result}")
                    else:
                        # Log at WARNING level with redacted content
                        logger.warning(f"PII filter blocked tool '{payload.name}' result - detected types: {detected_types} (content redacted)")
                    violation = PluginViolation(
                        reason="PII detected in tool result",
                        description=f"Detected {', '.join(detected_types)} in tool output",
                        code="PII_DETECTED_IN_TOOL_RESULT",
                        details={"detected_types": detected_types, "count": sum(len(items) for items in detections.values())},
                    )
                    return ToolPostInvokeResult(continue_processing=False, violation=violation)

                # Mask the PII
                payload = payload.model_copy(update={"result": self.detector.mask(payload.result, detections)})
                modified = True
                self.masked_count += sum(len(items) for items in detections.values())

                # Handle dictionary results - use recursive traversal
        elif isinstance(payload.result, dict):
            modified, detections = self._process_nested_data_for_pii(payload.result, "result", all_detections)
            if detections and self.pii_config.block_on_detection:
                detected_types = list(set(pii_type for field_detections in all_detections.values() for pii_type in field_detections.keys()))
                # Log at DEBUG level with full content
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"PII filter blocking tool '{payload.name}' result - full content: {payload.result}")
                else:
                    # Log at WARNING level with redacted content
                    logger.warning(f"PII filter blocked tool '{payload.name}' result - detected types: {detected_types} (content redacted)")
                violation = PluginViolation(
                    reason="PII detected in tool result",
                    description="Detected PII in nested tool result data",
                    code="PII_DETECTED_IN_TOOL_RESULT",
                    details={
                        "detected_types": detected_types,
                        "total_count": sum(len(items) for field_detections in all_detections.values() for items in field_detections.values()),
                    },
                )
                return ToolPostInvokeResult(continue_processing=False, violation=violation)

        # Store detection metadata
        if all_detections and self.pii_config.include_detection_details:
            if "pii_detections" not in context.metadata:
                context.metadata["pii_detections"] = {}

            context.metadata["pii_detections"]["tool_post_invoke"] = {
                "detected": True,
                "fields": list(all_detections.keys()),
                "types": list(set(pii_type for field_detections in all_detections.values() for pii_type in field_detections.keys())),
                "total_count": sum(len(items) for field_detections in all_detections.values() for items in field_detections.values()),
            }

        # Update summary statistics
        context.metadata["pii_filter_stats"] = {"total_detections": self.detection_count, "total_masked": self.masked_count}

        if modified:
            logger.info(f"Modified tool '{payload.name}' result to mask PII")
            return ToolPostInvokeResult(modified_payload=payload)

        return ToolPostInvokeResult()

    def _process_nested_data_for_pii(self, data: Any, path: str, all_detections: dict) -> tuple[bool, bool]:
        """
        Recursively process nested data structures to find and mask PII.

        Args:
            data: The data structure to process (dict, list, str, or other)
            path: The current path in the data structure for logging
            all_detections: Dictionary to store all detections found

        Returns:
            Tuple of (modified, has_detections) where:
            - modified: True if any data was modified
            - has_detections: True if any PII was detected
        """
        modified = False
        has_detections = False

        if isinstance(data, str):
            # Process string data - check for PII and also try to parse as JSON
            detections = self.detector.detect(data)
            if detections:
                all_detections[path] = detections
                self.detection_count += sum(len(items) for items in detections.values())
                has_detections = True
                modified = True
                if self.pii_config.log_detections:
                    logger.warning(f"PII detected in tool result at '{path}': {', '.join(detections.keys())}")

            # Try to parse as JSON and process nested content
            try:
                parsed_json = orjson.loads(data)
                json_modified, json_detections = self._process_nested_data_for_pii(parsed_json, f"{path}(json)", all_detections)
                has_detections = has_detections or json_detections
                # Note: JSON modification will be handled by the caller using the detections
                if json_modified:
                    modified = True
            except (orjson.JSONDecodeError, TypeError):
                # Not valid JSON, that's fine
                pass

        elif isinstance(data, dict):
            # Process dictionary recursively
            for key, value in data.items():
                current_path = f"{path}.{key}"
                value_modified, value_detections = self._process_nested_data_for_pii(value, current_path, all_detections)

                if value_modified and isinstance(value, str):
                    # Handle string masking including JSON strings
                    detections = all_detections.get(current_path, {})
                    if detections:
                        data[key] = self.detector.mask(value, detections)
                        modified = True

                    # Also check for JSON content that needs re-serialization
                    json_path = f"{current_path}(json)"
                    if any(path.startswith(json_path) for path in all_detections.keys()):
                        try:
                            parsed_json = orjson.loads(value)
                            # Apply masking to the parsed JSON
                            self._apply_pii_masking_to_parsed_json(parsed_json, json_path, all_detections)
                            # Re-serialize with masked data
                            data[key] = orjson.dumps(parsed_json).decode()
                            modified = True
                        except (orjson.JSONDecodeError, TypeError):
                            pass
                elif value_modified:
                    modified = True

                has_detections = has_detections or value_detections

        elif isinstance(data, list):
            # Process list recursively
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"
                item_modified, item_detections = self._process_nested_data_for_pii(item, current_path, all_detections)

                if item_modified and isinstance(item, str):
                    # Handle string masking in list including JSON strings
                    detections = all_detections.get(current_path, {})
                    if detections:
                        data[i] = self.detector.mask(item, detections)
                        modified = True

                    # Also check for JSON content that needs re-serialization
                    json_path = f"{current_path}(json)"
                    if any(path.startswith(json_path) for path in all_detections.keys()):
                        try:
                            parsed_json = orjson.loads(item)
                            # Apply masking to the parsed JSON
                            self._apply_pii_masking_to_parsed_json(parsed_json, json_path, all_detections)
                            # Re-serialize with masked data
                            data[i] = orjson.dumps(parsed_json).decode()
                            modified = True
                        except (orjson.JSONDecodeError, TypeError):
                            pass
                elif item_modified:
                    modified = True

                has_detections = has_detections or item_detections

        # For other types (int, bool, None, etc.), no processing needed

        return modified, has_detections

    def _apply_pii_masking_to_parsed_json(self, data: Any, base_path: str, all_detections: dict) -> None:
        """
        Apply PII masking to parsed JSON data using detections that were already found.

        Args:
            data: The parsed JSON data structure
            base_path: The base path for this JSON data
            all_detections: Dictionary containing all PII detections

        Returns:
            None: Modifies data in place.
        """
        if isinstance(data, str):
            # Check if this path has detections
            current_detections = all_detections.get(base_path, {})
            if current_detections:
                # Strings are immutable — caller handles assignment
                return

        elif isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{base_path}.{key}"
                if isinstance(value, str):
                    detections = all_detections.get(current_path, {})
                    if detections:
                        data[key] = self.detector.mask(value, detections)
                else:
                    self._apply_pii_masking_to_parsed_json(value, current_path, all_detections)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{base_path}[{i}]"
                if isinstance(item, str):
                    detections = all_detections.get(current_path, {})
                    if detections:
                        data[i] = self.detector.mask(item, detections)
                else:
                    self._apply_pii_masking_to_parsed_json(item, current_path, all_detections)

    async def shutdown(self) -> None:
        """Cleanup when plugin shuts down."""
        logger.info(f"PII Filter plugin ({self.implementation}) shutting down. Total masked: {self.masked_count} items")


# Export Rust implementation for tests
RUST_AVAILABLE = _RUST_AVAILABLE
RustPIIDetector = _RustPIIDetector
