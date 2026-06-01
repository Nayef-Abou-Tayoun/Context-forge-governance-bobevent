# Token Cost Calculator Plugin

A simple plugin that calculates and displays token costs for agent chat responses.

## Features

- Counts tokens in agent responses (approximation: 1 token ≈ 4 characters)
- Calculates cost based on configurable rate (default: $0.000001 per token)
- Adds cost information to message metadata for display in agent chat

## Configuration

```yaml
- name: "TokenCostCalculatorPlugin"
  kind: "plugins.token_cost_calculator.token_cost_calculator.TokenCostCalculatorPlugin"
  description: "Calculates and displays token costs for agent responses"
  version: "1.0.0"
  author: "ContextForge Team"
  hooks: ["agent_post_invoke"]
  mode: "enforce"
  priority: 100
  config:
    cost_per_token: 0.000001  # $0.000001 per token
    display_in_metadata: true
```

## Output

The plugin adds the following metadata to each agent response:

- `token_count`: Number of tokens in the agent's response
- `cost_per_token`: Cost per token in USD
- `total_cost_usd`: Total cost rounded to 6 decimal places
- `cost_display`: Formatted cost string (e.g., "$0.000123")

## Example

For an agent response with 1000 tokens:
```json
{
  "token_count": 1000,
  "cost_per_token": 0.000001,
  "total_cost_usd": 0.001,
  "cost_display": "$0.001000"
}
```

## Hook

- `agent_post_invoke`: Runs after agent generates a response to calculate cost