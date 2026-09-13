"""
Test 11: Telegram handler — send a test digest and audio to a channel.

Before running:
  1. Create a bot via @BotFather on Telegram → get the token
  2. Create a channel and add the bot as admin
  3. Set env vars:
       export TELEGRAM_BOT_TOKEN="your-bot-token"
       export TELEGRAM_TEST_CHANNEL="@your_channel_name"  (or numeric ID like -1001234567890)
  4. Run: uv run python tests/11_telegram.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from src.handlers.telegram import TelegramHandler

SAMPLE_DIGEST = """**Weekly Supreme Court Roundup**

This week, the Supreme Court of Canada issued two notable decisions.

---

**Mental Health in Murder Trials**

In *R. v. Lawlor*, the Court overturned a first-degree murder conviction because the jury wasn't properly instructed on how the defendant's mental health affected his intent. A new trial was ordered.

**Why it matters:** Courts must give juries clear guidance on mental health evidence — this protects everyone's right to a fair trial.

---

**Police Accountability**

In *R. v. Lindsay*, the Court upheld an aggravated assault conviction against a police officer who used excessive force on a detainee.

**Why it matters:** Police officers are not above the law. This ruling reinforces accountability.

---

*Stay tuned for next week's digest from Voice of the Courts.*
"""

SAMPLE_AUDIO = os.path.join(os.path.dirname(__file__), "test_voice.m4a")


def test_send_text():
    """Send just the text digest."""
    config = {
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "channel": os.environ.get("TELEGRAM_TEST_CHANNEL", ""),
        "send_digest": True,
        "send_audio": False,
        "parse_mode": "Markdown",
    }
    handler = TelegramHandler(config, podcast_name="Weekly Supreme Court Roundup")
    result = handler.run(digest_text=SAMPLE_DIGEST)
    print(f"  Text result: ok={result['text'][0].get('ok')}")
    return result


def test_send_audio():
    """Send just the audio file."""
    if not os.path.exists(SAMPLE_AUDIO):
        print(f"  Audio file not found: {SAMPLE_AUDIO}")
        return None

    config = {
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "channel": os.environ.get("TELEGRAM_TEST_CHANNEL", ""),
        "send_digest": False,
        "send_audio": True,
    }
    handler = TelegramHandler(config, podcast_name="Weekly Supreme Court Roundup")
    result = handler.run(audio_path=SAMPLE_AUDIO)
    print(f"  Audio result: ok={result['audio'].get('ok')}")
    return result


def test_send_both():
    """Send both text and audio."""
    config = {
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "channel": os.environ.get("TELEGRAM_TEST_CHANNEL", ""),
        "send_digest": True,
        "send_audio": True,
        "parse_mode": "Markdown",
    }
    handler = TelegramHandler(config, podcast_name="Weekly Supreme Court Roundup")
    result = handler.run(digest_text=SAMPLE_DIGEST, audio_path=SAMPLE_AUDIO)
    print(f"  Text result: ok={result['text'][0].get('ok')}")
    if "audio" in result:
        print(f"  Audio result: ok={result['audio'].get('ok')}")
    return result


if __name__ == "__main__":
    # Check env vars
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("TELEGRAM_BOT_TOKEN not set.")
        print("  1. Message @BotFather on Telegram → /newbot → copy the token")
        print("  2. export TELEGRAM_BOT_TOKEN='your-token'")
        sys.exit(1)

    if not os.environ.get("TELEGRAM_TEST_CHANNEL"):
        print("TELEGRAM_TEST_CHANNEL not set.")
        print("  1. Create a channel, add your bot as admin")
        print("  2. export TELEGRAM_TEST_CHANNEL='@your_channel'")
        sys.exit(1)

    print("=" * 60)
    print("Telegram Handler Test")
    print("=" * 60)

    print("\n--- Test 1: Send text only ---")
    test_send_text()

    print("\n--- Test 2: Send audio only ---")
    test_send_audio()

    print("\n--- Test 3: Send both ---")
    test_send_both()

    print("\nAll tests done. Check your Telegram channel!")
