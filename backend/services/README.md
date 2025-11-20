# Cron Service

Runs lightweight scheduled jobs (backed by the `schedule` Python library).

### Current jobs
- Delete `in_progress` games whose `updated_at` is older than 30 minutes (runs every 10 minutes by default).
- Sync OpenRouter catalog and add any new models as inactive/`untested` (runs daily by default, requires `OPENROUTER_API_KEY`).

### Run locally
```bash
cd backend
python services/cron_service.py
```

### Environment controls
- `STALE_GAME_MAX_MINUTES` (default `30`)
- `CRON_INTERVAL_MINUTES` (default `10`)
- `OPENROUTER_SYNC_ENABLED` (default `true`)
- `OPENROUTER_SYNC_INTERVAL_MINUTES` (default `1440` — once per day)
- `OPENROUTER_API_KEY` (required for OpenRouter sync)
- `SCHEDULER_LOOP_SLEEP_SECONDS` (default `5`)
- `CRON_LOG_LEVEL` (default `INFO`)

# Webhook Service

This service handles sending webhook notifications to external services like Zapier.

## Setup

Add your Zapier webhook URL to your `.env` file:

```bash
ZAPIER_WEBHOOK_URL=https://hooks.zapier.com/hooks/catch/YOUR_WEBHOOK_ID/
```

## Evaluation Complete Webhook

When a model evaluation completes, the following JSON payload is sent:

```json
{
  "event": "evaluation_complete",
  "timestamp": "2025-01-15T10:30:45Z",
  "model": {
    "name": "OpenAI: GPT-4o Mini",
    "final_elo": 1523.45,
    "elo_rating": 1523.45
  },
  "results": {
    "games_played": 10,
    "wins": 6,
    "losses": 3,
    "ties": 1,
    "win_rate": 60.0
  },
  "cost": {
    "total": 0.0234,
    "per_game": 0.00234,
    "currency": "USD"
  }
}
```

## Zapier Integration

1. Create a Zap with a "Webhooks by Zapier" trigger (Catch Hook)
2. Copy the webhook URL and add it to your `.env` file
3. Set up your action (e.g., send Slack message, email, SMS, etc.)
4. Use the webhook data in your message template

Example message template:
```
Model {{model__name}} evaluation complete!
ELO: {{model__final_elo}}
Record: {{results__wins}}-{{results__losses}}-{{results__ties}}
Cost: ${{cost__total}}
```

## Available Webhooks

- `send_evaluation_complete_webhook()` - Sent when model evaluation finishes
- `send_game_complete_webhook()` - Sent when a single game finishes (optional)
- `send_new_model_webhook()` - Sent when a new OpenRouter model is discovered (inactive/untested)
