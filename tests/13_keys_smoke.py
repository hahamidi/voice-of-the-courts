"""
Test 13: Key smoke test — one tiny call per configured provider.

Reads .env, then for each key that is set:
  - LLM providers: one short completion via LiteLLM
  - ElevenLabs:    one short TTS clip written to data/audio/

Costs: a few tokens / ~100 characters per provider.

Run: python tests/13_keys_smoke.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from src.handlers.processing import _call_llm
from src.handlers.tts import TTSHandler

LLM_PROVIDERS = {
    # env var            : LiteLLM model id
    "OPENAI_API_KEY":     "openai/gpt-4o-mini",
    "ANTHROPIC_API_KEY":  "anthropic/claude-haiku-4-5-20251001",
    "TOGETHER_API_KEY":   "together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "GROQ_API_KEY":       "groq/llama-3.3-70b-versatile",
    "OPENROUTER_API_KEY": "openrouter/meta-llama/llama-3.3-70b-instruct",
}

TTS_PROVIDERS = {
    "OPENAI_API_KEY":     {"provider": "openai", "model": "tts-1", "voice": "alloy"},
    "ELEVENLABS_API_KEY": {"provider": "elevenlabs", "model": "eleven_flash_v2_5", "voice": "alloy"},
}

PROMPT = "Reply with exactly three words: Voice of Courts"
SPEECH = "Voice of the Courts. Test clip."


def main():
    ok, fail, skipped = [], [], []

    print("=" * 60)
    print("LLM PROVIDERS")
    print("=" * 60)
    for env, model_id in LLM_PROVIDERS.items():
        if not os.environ.get(env):
            skipped.append(env)
            continue
        try:
            out = _call_llm(model_id, PROMPT, temperature=0.0, max_tokens=20)
            print(f"  OK   {model_id}: {out.strip()[:60]!r}")
            ok.append(model_id)
        except Exception as e:
            print(f"  FAIL {model_id}: {type(e).__name__}: {str(e)[:200]}")
            fail.append(model_id)

    print()
    print("=" * 60)
    print("TTS PROVIDERS")
    print("=" * 60)
    for env, cfg in TTS_PROVIDERS.items():
        if not os.environ.get(env):
            skipped.append(env)
            continue
        cfg = {**cfg, "output_dir": "data/audio", "filename": "smoke_{podcast}_{datetime}.mp3"}
        try:
            handler = TTSHandler(cfg, podcast_name=cfg["provider"])
            path = handler.run(SPEECH)
            size = os.path.getsize(path)
            assert size > 1000, f"file too small: {size} bytes"
            print(f"  OK   {handler.model_id}: {path} ({size} bytes)")
            ok.append(handler.model_id)
        except Exception as e:
            print(f"  FAIL {cfg['provider']}: {type(e).__name__}: {str(e)[:200]}")
            fail.append(cfg["provider"])

    print()
    print(f"ok={len(ok)} fail={len(fail)} skipped(no key)={len(skipped)}")
    if skipped:
        print("  skipped:", ", ".join(skipped))
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
