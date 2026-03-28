"""
Test 9: ChainEngine dry run — tests the plumbing without calling any LLM API.

Verifies: split, merge, @ reference resolution, prompt rendering, looping.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.chain_engine import ChainEngine, _resolve_item_fields, _resolve_settings

# --- Test @ reference helpers ---

def test_resolve_item_fields():
    text = "Case: @item.case_name (@item.citation) on @item.date"
    item = {"case_name": "R. v. Test", "citation": "2023 SCC 99", "date": "2023-06-01"}
    result = _resolve_item_fields(text, item)
    assert "R. v. Test" in result
    assert "2023 SCC 99" in result
    assert "2023-06-01" in result
    print("  resolve_item_fields: OK")


def test_resolve_settings():
    text = "Audience: @audience, Tone: @tone"
    settings = {"audience": "students", "tone": "friendly"}
    result = _resolve_settings(text, settings)
    assert "students" in result
    assert "friendly" in result
    print("  resolve_settings: OK")


# --- Test function blocks ---

def test_split_and_merge():
    config = {
        "settings": {},
        "models": {},
        "chain": [
            {"name": "split", "type": "function", "function": "split", "input": "@filter_data"},
            {"name": "merge", "type": "function", "function": "merge", "input": "@split.output", "join": " | "},
        ],
    }
    engine = ChainEngine(config)

    fake_data = [
        {"name_en": "Case A", "citation_en": "2023 SCC 1", "dataset": "SCC"},
        {"name_en": "Case B", "citation_en": "2023 SCC 2", "dataset": "SCC"},
        {"name_en": "Case C", "citation_en": "2023 SCC 3", "dataset": "SCC"},
    ]

    outputs = engine.run(fake_data)

    # split should produce a list of 3
    assert isinstance(outputs["split"], list)
    assert len(outputs["split"]) == 3
    print("  split: OK (3 items)")

    # merge should join them with " | "
    merged = outputs["merge"]
    assert isinstance(merged, str)
    assert " | " in merged
    print(f"  merge: OK (joined string, {len(merged)} chars)")


# --- Test prompt rendering ---

def test_prompt_rendering():
    config = {
        "settings": {"audience": "test audience", "tone": "casual"},
        "models": {
            "mock": {"provider": "openai", "name": "mock", "temperature": 0},
        },
        "chain": [
            {"name": "split", "type": "function", "function": "split", "input": "@filter_data"},
            {
                "name": "process",
                "type": "llm",
                "model": "mock",
                "input": "@split.output",
                "prompt": "For @audience (@tone): Summarize @item.case_name (@item.citation)\n\nText: @item.text",
            },
        ],
    }
    engine = ChainEngine(config)

    fake_data = [
        {
            "name_en": "R. v. Mock",
            "citation_en": "2023 SCC 99",
            "dataset": "SCC",
            "unofficial_text_en": "This is the decision text.",
        },
    ]

    # We can't actually call the LLM, but we can test prompt rendering
    # by calling _render_prompt directly
    engine._outputs = {"filter_data": [{"case_name": "R. v. Mock", "citation": "2023 SCC 99", "text": "This is the decision text."}]}

    prompt = engine._render_prompt(
        config["chain"][1]["prompt"],
        "some input",
        {"case_name": "R. v. Mock", "citation": "2023 SCC 99", "text": "This is the decision text."},
    )

    assert "test audience" in prompt
    assert "casual" in prompt
    assert "R. v. Mock" in prompt
    assert "2023 SCC 99" in prompt
    assert "This is the decision text." in prompt
    print(f"  prompt rendering: OK")
    print(f"    rendered prompt:\n{prompt}")


# --- Run all ---

if __name__ == "__main__":
    print("=" * 60)
    print("ChainEngine Dry Run Tests")
    print("=" * 60)

    print("\n@ reference helpers:")
    test_resolve_item_fields()
    test_resolve_settings()

    print("\nFunction blocks:")
    test_split_and_merge()

    print("\nPrompt rendering:")
    test_prompt_rendering()

    print("\n" + "=" * 60)
    print("All dry-run tests passed.")
