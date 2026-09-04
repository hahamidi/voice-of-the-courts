from __future__ import annotations

"""
TTS handler — converts the final digest text into an audio file via LiteLLM.

Reads the "tts:" section of a unified podcast YAML:

  tts:
    provider: openai          # any LiteLLM speech provider (openai, elevenlabs, azure, gemini, ...)
    model: tts-1              # provider model name (e.g. tts-1, gpt-4o-mini-tts)
    voice: alloy              # provider voice id
    output_dir: data/audio    # relative to project root, or absolute
    filename: "{podcast}_{date}.mp3"
    max_chars: 4000           # per-request input cap (OpenAI limit is 4096)
    api_base: null            # optional custom endpoint
    api_key_env: null         # env var holding the key for a custom endpoint

OpenAI-compatible endpoints (Together AI, Groq, local servers) work with
provider: openai + api_base + api_key_env, e.g.
    provider: openai
    model: hexgrad/Kokoro-82M
    voice: af_heart
    api_base: https://api.together.ai/v1
    api_key_env: TOGETHER_API_KEY

Long texts are split on paragraph boundaries, synthesized chunk by chunk,
and the MP3 chunks are byte-concatenated (MP3 frames are self-contained,
so simple concatenation yields a playable file).
"""

import os
import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF\u2B00-\u2BFF\uFE0F\u200D]+"
)


def _strip_markdown(text: str) -> str:
    """Remove Markdown syntax so the voice does not read symbols aloud."""
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)  # hr
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)  # bold
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)  # italic
    text = re.sub(r"`+", "", text)  # code ticks
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # bullets
    text = _EMOJI_RE.sub("", text)  # emoji / pictographs
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_text(text: str, limit: int) -> list[str]:
    """Split text into chunks of at most `limit` chars, preferring paragraph breaks."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n\n", 0, limit)
        if split_at <= 0:
            split_at = text.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = text.rfind(". ", 0, limit)
            if split_at > 0:
                split_at += 1
        if split_at <= 0:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n ")
    return [c for c in chunks if c.strip()]


class TTSHandler:
    """Synthesize digest text into an audio file."""

    def __init__(self, config: dict, podcast_name: str = ""):
        self.provider: str = config.get("provider", "openai")
        self.model: str = config.get("model", "tts-1")
        self.voice: str = config.get("voice", "alloy")
        self.max_chars: int = config.get("max_chars", 4000)
        self.api_base: str | None = config.get("api_base")
        self.api_key: str | None = None
        key_env = config.get("api_key_env")
        if key_env:
            self.api_key = os.environ.get(key_env)
            if not self.api_key:
                raise ValueError(f"TTS api_key_env set but {key_env} is not in the environment")
        self.filename: str = config.get("filename", "{podcast}_{date}.mp3")
        self._podcast_name = podcast_name

        out = Path(config.get("output_dir", "data/audio"))
        self.output_dir = out if out.is_absolute() else PROJECT_ROOT / out

    @property
    def model_id(self) -> str:
        return f"{self.provider}/{self.model}"

    def run(self, text: str) -> str:
        """Synthesize `text` and return the path of the written audio file."""
        clean = _strip_markdown(text)
        if not clean:
            raise ValueError("TTS input is empty after stripping Markdown")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.output_dir / self._render_filename()

        chunks = _split_text(clean, self.max_chars)
        print(f"  [tts] {self.model_id} voice={self.voice} — {len(chunks)} chunk(s)")

        with open(out_path, "wb") as out:
            for i, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    print(f"    synthesizing chunk {i + 1}/{len(chunks)}...")
                out.write(self._synthesize(chunk))

        size_kb = os.path.getsize(out_path) / 1024
        print(f"  [tts] wrote {out_path} ({size_kb:.0f} KB)")
        return str(out_path)

    def _synthesize(self, text: str) -> bytes:
        import litellm

        litellm.suppress_debug_info = True
        kwargs = {"model": self.model_id, "voice": self.voice, "input": text}
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        resp = litellm.speech(**kwargs)
        return resp.content

    def _render_filename(self) -> str:
        safe = (self._podcast_name or "podcast").lower().replace(" ", "_").replace("/", "_")
        return self.filename.format(
            podcast=safe,
            date=datetime.now().strftime("%Y-%m-%d"),
            datetime=datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        )

    def __repr__(self) -> str:
        return f"TTSHandler(model={self.model_id!r}, voice={self.voice!r})"
