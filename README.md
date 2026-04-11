# Voice of the Courts

Automated AI legal digest and podcast built on [A2AJ Canadian Legal Data](https://a2aj.ca/canadian-legal-data/). Fetches court decisions, summarizes them via LLM, and delivers plain-language digests to Telegram.

## Setup

```bash
# Install uv (package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
cd A2AJ
uv sync

# Set API keys
export OPENAI_API_KEY="your-openai-key"
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export TELEGRAM_TEST_CHANNEL="-your-channel-id"
```

## Run a podcast

Each podcast is a single YAML file in `podcasts/`. To run one:

```bash
uv run python -c "
from src.runner import PodcastRunner
runner = PodcastRunner.load('podcasts/scc_weekly_roundup.yaml')
result = runner.run()
"
```

Available podcasts:
- `scc_weekly_roundup.yaml` — Supreme Court of Canada weekly digest
- `irb_refugee_weekly.yaml` — Immigration & Refugee Board digest
- `sst_disability_monitor.yaml` — Social Security Tribunal disability decisions

## How it works

One YAML defines the entire pipeline:

```yaml
podcast:      # name, audience, tone, schedule
filter:       # what to fetch from A2AJ (courts, date range, keywords)
processing:   # LLM chain (split → summarize → merge → digest)
telegram:     # send digest to a Telegram channel
```

The runner executes each section in order:

```
A2AJ API → filter → LLM processing → Telegram
```

## Project structure

```
podcasts/           # one YAML per podcast
src/
  runner.py         # orchestrates the pipeline
  handlers/
    filter.py       # fetches & filters cases from A2AJ API
    processing.py   # LLM block chain (OpenAI / Anthropic / Ollama)
    telegram.py     # sends digest & audio to Telegram
tests/              # API exploration and integration tests
```

## Telegram setup

1. Message `@BotFather` on Telegram, create a bot, copy the token
2. Create a channel, add the bot as **admin**
3. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_TEST_CHANNEL` env vars
4. Enable `telegram:` section in your podcast YAML
