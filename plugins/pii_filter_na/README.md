# PII Filter NA Plugin for ContextForge

> Author: Based on original by Mihai Criveti
> Version: 2.0.0

A plugin for detecting and masking Canadian Personally Identifiable Information (PII) in ContextForge prompts and responses.

## Canadian PII Types Supported

### Social Insurance Number (SIN)
- **Format**: `XXX-XXX-XXX` (9 digits with dashes)
- **Example**: `123-456-789`
- **Masking**: Shows last 3 digits (`***-***-789`)

### Postal Code
- **Format**: `A1A 1A1` (letter-digit-letter space digit-letter-digit)
- **Example**: `K1A 0B1`, `M5W 1E6`
- **Masking**: Shows first 3 characters (`K1A ***`)

### Health Card Numbers
Provincial formats supported:
- **Ontario**: `1234-567-890` (10 digits with dashes)
- **Quebec**: `ABCD 1234 5678` (4 letters + 8 digits)
- **BC**: `9123456789` (10 digits starting with 9)
- **Masking**: Shows last 3 digits (`****-***-890`)

## Configuration Example

```yaml
plugins:
  - name: "PIIFilterNAPlugin"
    kind: "plugins.pii_filter_na.pii_filter_na.PIIFilterNAPlugin"
    description: "Canadian PII detection and masking"
    version: "2.0"
    hooks: ["prompt_pre_fetch", "prompt_post_fetch", "tool_pre_invoke", "tool_post_invoke"]
    tags: ["security", "pii", "compliance", "canada", "privacy"]
    mode: "enforce"
    priority: 51
    config:
      # Canadian PII detection
      detect_sin: true
      detect_canadian_postal_code: true
      detect_canadian_health_card: true
      
      # Masking strategy
      default_mask_strategy: "partial"  # Shows partial info
      redaction_text: "[REDACTED]"
      
      # Behavior
      block_on_detection: false  # Set true to block requests with PII
      log_detections: true
      include_detection_details: true
```

## Masking Strategies

- **PARTIAL** (default): Shows partial information for identification
  - SIN: `***-***-789`
  - Postal Code: `K1A ***`
  - Health Card: `****-***-890`
- **REDACT**: Replaces with `[REDACTED]`
- **HASH**: Replaces with hash value
- **TOKENIZE**: Replaces with token
- **REMOVE**: Removes entirely

## Testing

```bash
pytest tests/unit/mcpgateway/plugins/pii_filter_na/ -v
```

## License

Apache-2.0