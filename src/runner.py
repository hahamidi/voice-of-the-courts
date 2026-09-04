from __future__ import annotations

"""
PodcastRunner — loads a unified podcast YAML and runs each handler in order.

Sections:
  podcast:     general info (name, description, schedule, language, audience, tone)
  filter:      what to fetch from A2AJ
  processing:  LLM chain to transform the data
  tts:         synthesize the final digest into audio
  telegram:    send digest text and audio to a channel
"""

from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.handlers.filter import FilterHandler
from src.handlers.processing import ProcessingHandler
from src.handlers.telegram import TelegramHandler
from src.handlers.tts import TTSHandler


# Load API keys from <project_root>/.env if present (never overrides real env vars)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class PodcastRunner:
    """Orchestrate a complete podcast pipeline from a single YAML."""

    def __init__(self, config: dict):
        self._raw = config
        self.podcast: dict = config.get("podcast", {})
        self.name: str = self.podcast.get("name", "Untitled Podcast")

    @classmethod
    def load(cls, path: str) -> "PodcastRunner":
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        return cls(config)

    def run(self) -> dict:
        """
        Run the full pipeline:
          1. filter  — fetch cases from A2AJ
          2. processing — run LLM chain
          3. tts — synthesize audio from the final digest
          4. telegram — send digest text and audio

        Returns dict with outputs from each stage.
        """
        result = {}

        print(f"\n{'=' * 60}")
        print(f"  Podcast: {self.name}")
        print(f"{'=' * 60}\n")

        # --- 1. Filter ---
        filter_config = self._raw.get("filter")
        if filter_config:
            print("[Stage 1: Filter]")
            handler = FilterHandler(
                config=filter_config,
                podcast_name=self.name,
                language=self.podcast.get("language", "en"),
            )
            cases = handler.run()
            result["filter"] = cases
            result["_filter_handler"] = handler
            print()
        else:
            print("[Stage 1: Filter] — skipped (no filter: section)")
            cases = []

        if not cases:
            print("No cases to process. Pipeline complete.")
            result["final"] = ""
            return result

        # --- 2. Processing ---
        processing_config = self._raw.get("processing")
        if processing_config:
            print("[Stage 2: Processing]")
            # Pass podcast-level fields as settings for @ references
            settings = {
                "audience": self.podcast.get("audience", ""),
                "tone": self.podcast.get("tone", ""),
                "language": self.podcast.get("language", "en"),
                "name": self.name,
                "description": self.podcast.get("description", ""),
                "show_name": self.podcast.get("name", ""),
            }
            handler = ProcessingHandler(
                config=processing_config,
                settings=settings,
            )
            outputs = handler.run(cases)
            result["processing"] = outputs

            # The final output is the last block's output
            last_block_name = processing_config["chain"][-1]["name"]
            result["final"] = outputs.get(last_block_name, "")
            print()
        else:
            print("[Stage 2: Processing] — skipped (no processing: section)")

        # --- 3. TTS ---
        tts_config = self._raw.get("tts")
        if tts_config and result.get("final"):
            print("[Stage 3: TTS]")
            handler = TTSHandler(config=tts_config, podcast_name=self.name)
            result["audio_path"] = handler.run(result["final"])
            print()
        else:
            print("[Stage 3: TTS] — skipped (no tts: section or empty digest)")

        # --- 4. Telegram ---
        telegram_config = self._raw.get("telegram")
        if telegram_config:
            print("[Stage 4: Telegram]")
            handler = TelegramHandler(
                config=telegram_config,
                podcast_name=self.name,
            )
            digest_text = result.get("final", "")
            audio_path = result.get("audio_path")
            telegram_result = handler.run(
                digest_text=digest_text,
                audio_path=audio_path,
            )
            result["telegram"] = telegram_result
            print()
        else:
            print("[Stage 4: Telegram] — skipped (no telegram: section)")

        # --- Mark cases as processed so the next run skips them ---
        filter_handler = result.get("_filter_handler")
        if filter_handler is not None and result.get("final"):
            filter_handler.mark_all_processed(cases)
            print(f"[Dedup] marked {len(cases)} case(s) as processed")

        print(f"{'=' * 60}")
        print(f"  Pipeline complete for: {self.name}")
        print(f"{'=' * 60}")

        return result

    def __repr__(self) -> str:
        sections = [k for k in self._raw if k != "podcast"]
        return f"PodcastRunner(name={self.name!r}, sections={sections})"
