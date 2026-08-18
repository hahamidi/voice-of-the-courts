"""
Test 09: ProcessingHandler dry run — no network, no API keys.

Verifies:
  - @item.field / @settings / @input resolution
  - LiteLLM model id construction (provider + name -> "provider/name")
  - split -> llm (looped) -> merge -> llm chain wiring, with _call_llm stubbed

Run: python tests/09_processing_dry.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.handlers import processing
from src.handlers.processing import (
    ProcessingHandler,
    build_model_id,
    _resolve_item_fields,
    _resolve_settings,
)


def test_reference_helpers():
    item = {"case_name": "R. v. Test", "citation": "2024 SCC 1"}
    out = _resolve_item_fields("Case: @item.case_name (@item.citation) @audience", item)
    assert out == "Case: R. v. Test (2024 SCC 1) @audience", out

    out = _resolve_settings("For @audience in @tone. Keep @item.case_name", {"audience": "public", "tone": "warm"})
    assert out == "For public in warm. Keep @item.case_name", out
    print("  reference helpers ok")


def test_model_id():
    assert build_model_id("openai", "gpt-4o-mini") == "openai/gpt-4o-mini"
    assert build_model_id("anthropic", "claude-sonnet-5") == "anthropic/claude-sonnet-5"
    assert build_model_id("ollama", "llama3") == "ollama_chat/llama3"
    assert build_model_id("groq", "llama-3.1-8b") == "groq/llama-3.1-8b"
    print("  model id mapping ok")


def test_chain_with_stub():
    calls = []

    def fake_call_llm(model_id, prompt, temperature, api_base=None, max_tokens=None, api_key=None, stream=False):
        calls.append({"model": model_id, "prompt": prompt, "temp": temperature, "base": api_base, "max": max_tokens})
        return f"<summary of {prompt.splitlines()[0]}>"

    original = processing._call_llm
    processing._call_llm = fake_call_llm
    try:
        config = {
            "models": {
                "fast": {"provider": "ollama", "name": "llama3", "temperature": 0.1},
                "smart": {"provider": "openai", "name": "gpt-4o-mini", "max_tokens": 500},
            },
            "chain": [
                {"name": "split", "type": "function", "function": "split", "input": "@filter_data"},
                {"name": "sum", "type": "llm", "model": "fast", "input": "@split.output",
                 "prompt": "@item.case_name for @audience\n@item.text"},
                {"name": "merge", "type": "function", "function": "merge", "input": "@sum.output", "join": "\n--\n"},
                {"name": "digest", "type": "llm", "model": "smart", "input": "@merge.output",
                 "prompt": "Digest for @audience:\n@input"},
            ],
        }
        cases = [
            {"name_en": "A v. B", "citation_en": "2024 SCC 1", "unofficial_text_en": "text one"},
            {"name_en": "C v. D", "citation_en": "2024 SCC 2", "unofficial_text_en": "text two"},
        ]
        handler = ProcessingHandler(config, settings={"audience": "public"})
        out = handler.run(cases)
    finally:
        processing._call_llm = original

    assert len(calls) == 3, calls
    assert calls[0]["model"] == "ollama_chat/llama3"
    assert calls[0]["base"] == "http://localhost:11434"
    assert calls[0]["temp"] == 0.1
    assert calls[0]["prompt"].startswith("A v. B for public\ntext one")
    assert calls[2]["model"] == "openai/gpt-4o-mini"
    assert calls[2]["max"] == 500
    assert calls[2]["temp"] == 0.3  # default
    assert "<summary of A v. B for public>" in calls[2]["prompt"]
    assert "<summary of C v. D for public>" in calls[2]["prompt"]
    assert out["digest"].startswith("<summary of Digest for public:>")
    print("  chain wiring ok")


if __name__ == "__main__":
    print("=" * 60)
    print("PROCESSING DRY RUN")
    print("=" * 60)
    test_reference_helpers()
    test_model_id()
    test_chain_with_stub()
    print("all passed")
