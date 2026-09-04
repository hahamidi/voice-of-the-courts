"""
Test 12: TTS handler.

Part 1 (offline): Markdown stripping and chunking.
Part 2 (needs OPENAI_API_KEY): synthesize a short digest to data/audio/.

Run: python tests/12_tts.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from src.handlers.tts import TTSHandler, _strip_markdown, _split_text

SAMPLE = """**Weekly Supreme Court Roundup**

This week, the Supreme Court of Canada issued two notable decisions.

---

## Mental Health in Murder Trials

In *R. v. Lawlor*, the Court ordered a new trial. See [the ruling](https://example.com).

- Point one
- Point two
"""


def test_offline():
    clean = _strip_markdown(SAMPLE)
    assert "**" not in clean and "##" not in clean and "---" not in clean, clean
    assert "*R. v. Lawlor*" not in clean and "R. v. Lawlor" in clean
    assert "the ruling" in clean and "https://" not in clean
    assert "- Point one" not in clean and "Point one" in clean

    chunks = _split_text("para one.\n\npara two.\n\npara three.", limit=15)
    assert chunks == ["para one.", "para two.", "para three."], chunks
    assert all(len(c) <= 15 for c in chunks)

    handler = TTSHandler({"provider": "openai", "model": "tts-1", "voice": "alloy"}, podcast_name="Test Show")
    assert handler.model_id == "openai/tts-1"
    assert handler._render_filename().startswith("test_show_")
    print("  offline checks ok")


def test_synthesize():
    handler = TTSHandler(
        {"provider": "openai", "model": "tts-1", "voice": "alloy",
         "output_dir": "data/audio", "filename": "tts_test_{datetime}.mp3", "max_chars": 200},
        podcast_name="TTS Test",
    )
    path = handler.run(SAMPLE)
    assert os.path.exists(path), path
    size = os.path.getsize(path)
    assert size > 1000, f"suspiciously small file: {size} bytes"
    print(f"  wrote {path} ({size} bytes)")


if __name__ == "__main__":
    print("=" * 60)
    print("TTS HANDLER")
    print("=" * 60)
    test_offline()
    if os.environ.get("OPENAI_API_KEY"):
        test_synthesize()
    else:
        print("OPENAI_API_KEY not set — skipping synthesis test.")
