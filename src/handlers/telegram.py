from __future__ import annotations

"""
Telegram handler — sends digest text and audio to a Telegram channel.

Reads the "telegram:" section of a unified podcast YAML.

Config:
  bot_token_env: TELEGRAM_BOT_TOKEN       # env var holding the bot token
  channel: "@name" or "-100123..."        # literal chat id, or
  channel_env: TELEGRAM_TEST_CHANNEL      # env var holding the chat id (preferred, keeps ids out of YAML)
  send_digest / send_audio / parse_mode / max_message_length
"""

import os
import re

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def _markdown_to_telegram(text: str) -> str:
    """Telegram's Markdown has no headings or horizontal rules; convert them."""
    text = re.sub(r"^[ \t]*#{1,6}[ \t]*(.+?)[ \t]*$", r"*\1*", text, flags=re.MULTILINE)  # "### Title" -> "*Title*"
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)  # "**bold**" -> "*bold*"
    text = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "", text, flags=re.MULTILINE)  # drop "---"
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class TelegramHandler:
    """Send text digests and audio files to a Telegram channel."""

    def __init__(self, config: dict, podcast_name: str = ""):
        # Channel: literal "channel" or env var name in "channel_env"
        self.channel: str = config.get("channel", "")
        channel_env = config.get("channel_env")
        if channel_env:
            self.channel = os.environ.get(channel_env, "") or self.channel
        if not self.channel:
            raise ValueError("Telegram channel not set. Use channel: or channel_env: in the telegram section.")
        self.send_digest: bool = config.get("send_digest", True)
        self.send_audio: bool = config.get("send_audio", True)
        self.parse_mode: str = config.get("parse_mode", "Markdown")
        self.max_message_length: int = config.get("max_message_length", 4096)
        self._podcast_name = podcast_name

        # Read bot token from env
        token_env = config.get("bot_token_env", "TELEGRAM_BOT_TOKEN")
        self._token = os.environ.get(token_env, "")
        if not self._token:
            raise ValueError(
                f"Telegram bot token not found. Set the {token_env} env var."
            )

        self._base_url = TELEGRAM_API.format(token=self._token)

    def run(self, digest_text: str = "", audio_path: str | None = None) -> dict:
        """
        Send content to the Telegram channel.

        Args:
            digest_text: the text digest to send
            audio_path:  path to an audio file (mp3, m4a, ogg, etc.)

        Returns:
            dict with results from each send operation
        """
        result = {}

        if self.send_digest and digest_text:
            print("  [telegram] sending digest text...")
            result["text"] = self._send_text(digest_text)

        if self.send_audio and audio_path:
            print(f"  [telegram] sending audio: {audio_path}...")
            result["audio"] = self._send_audio(audio_path)

        return result

    # ------------------------------------------------------------------ #
    #  Send text (split if longer than Telegram's limit)                   #
    # ------------------------------------------------------------------ #

    def _send_text(self, text: str) -> list[dict]:
        """Send text message(s). Splits into chunks if too long."""
        if self.parse_mode.lower() == "markdown":
            text = _markdown_to_telegram(text)
        chunks = self._split_text(text)
        responses = []
        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                print(f"    sending text chunk {i + 1}/{len(chunks)}...")
            resp = requests.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self.channel,
                    "text": chunk,
                    **({"parse_mode": self.parse_mode} if self.parse_mode else {}),
                },
            )
            data = resp.json()
            if not data.get("ok"):
                # Do not use raise_for_status: its message includes the URL with the bot token
                raise RuntimeError(
                    f"Telegram sendMessage failed ({resp.status_code}): {data.get('description')}"
                )
            responses.append(data)
        print(f"  [telegram] text sent ({len(chunks)} message(s))")
        return responses

    def _split_text(self, text: str) -> list[str]:
        """Split text into chunks that fit Telegram's message limit."""
        limit = self.max_message_length
        if len(text) <= limit:
            return [text]

        chunks = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break

            # Try to split at a paragraph break
            split_at = text.rfind("\n\n", 0, limit)
            if split_at == -1:
                # Try a single newline
                split_at = text.rfind("\n", 0, limit)
            if split_at == -1:
                # Hard split at the limit
                split_at = limit

            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")

        return chunks

    # ------------------------------------------------------------------ #
    #  Send audio                                                          #
    # ------------------------------------------------------------------ #

    def _send_audio(self, audio_path: str) -> dict:
        """Send an audio file to the channel."""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with open(audio_path, "rb") as f:
            resp = requests.post(
                f"{self._base_url}/sendAudio",
                data={
                    "chat_id": self.channel,
                    "title": self._podcast_name or "Voice of the Courts",
                    "performer": "Voice of the Courts",
                },
                files={"audio": (os.path.basename(audio_path), f)},
            )

        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(
                f"Telegram sendAudio failed ({resp.status_code}): {data.get('description')}"
            )
        print("  [telegram] audio sent")
        return data
