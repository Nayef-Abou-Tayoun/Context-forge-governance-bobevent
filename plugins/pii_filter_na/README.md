# PII Filter NA Plugin for ContextForge

> Author: Based on original by Mihai Criveti
> Version: 1.0.0

A plugin for detecting and masking Personally Identifiable Information (PII) specific to North America in ContextForge prompts and responses.

## North America-Specific PII Types

### United States
- **SSN** - Social Security Numbers: `123-45-6789`
- **EIN** - Employer Identification Numbers: `12-3456789`
- **ITIN** - Individual Taxpayer Identification Numbers: `9XX-XX-XXXX`

### Canada
- **SIN** - Social Insurance Numbers: `123-456-789`
- **Canadian Postal Codes**: `A1A 1A1`
- **Canadian Health Card Numbers**: Province-specific formats

### Common North America
- Credit Cards, Emails, Phone Numbers, IP Addresses
- Dates of Birth, Passports, Driver's Licenses
- Bank Accounts, Medical Records
- AWS Keys, API Keys, IMEI numbers

## Configuration Example

```yaml
plugins:
  - name: "PIIFilterNAPlugin"
    kind: "plugins.pii_filter_na.pii_filter_na.PIIFilterNAPlugin"
    description: "North America-specific PII detection and masking"
    version: "1.0"
    hooks: ["prompt_pre_fetch", "prompt_post_fetch", "tool_pre_invoke", "tool_post_invoke"]
    tags: ["security", "pii", "compliance", "north-america", "gdpr", "hipaa"]
    mode: "enforce"
    priority: 10
    config:
      # US-specific
      detect_ssn: true
      detect_ein: true
      detect_itin: true
      
      # Canada-specific
      detect_sin: true
      detect_canadian_postal_code: true
      detect_canadian_health_card: true
      
      # Common
      detect_credit_card: true
      detect_email: true
      detect_phone: true
      
      # Masking
      default_mask_strategy: "partial"
      block_on_detection: false
      log_detections: true
```

## Testing

```bash
pytest tests/unit/mcpgateway/plugins/pii_filter_na/ -v
```

## License

Apache-2.0