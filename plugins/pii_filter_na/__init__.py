# -*- coding: utf-8 -*-
"""North America PII Filter Plugin Package.

Location: ./plugins/pii_filter_na/__init__.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0

This package provides PII detection and masking specifically for North American
data formats including Canadian SIN, US EIN, Canadian postal codes, and more.
"""

from .pii_filter_na import PIIFilterNAPlugin, PIIFilterNAConfig

__all__ = ["PIIFilterNAPlugin", "PIIFilterNAConfig"]

# Made with Bob
