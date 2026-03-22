from __future__ import annotations

"""
ChainEngine — YAML-driven block chain for processing legal data through LLMs.

Block types:
  - function: split  — takes a list, outputs individual items
  - function: merge  — takes many items, joins into one string
  - llm              — calls a model; loops automatically if input is a list

@ references:
  @filter_data         — raw data from FilterProfile
  @blockname.output    — output of a previous block
  @input               — resolved input inside a prompt
  @item.field          — field from current item when looping (case_name, citation, text, date, court)
  @settings keys       — values from the settings section (e.g. @audience, @tone)
"""

import re
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
#  Model clients
# ---------------------------------------------------------------------------


def _call_openai(model_name: str, prompt: str, temperature: float) -> str:
    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content


def _call_anthropic(model_name: str, prompt: str, temperature: float) -> str:
    from anthropic import Anthropic

    client = Anthropic()
    resp = client.messages.create(
        model=model_name,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.content[0].text


def _call_ollama(model_name: str, prompt: str, temperature: float) -> str:
    import requests

    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        },
    )
    resp.raise_for_status()
    return resp.json()["response"]


PROVIDERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "ollama": _call_ollama,
}

# ---------------------------------------------------------------------------
#  @ reference helpers
# ---------------------------------------------------------------------------

# Matches @word.word or @word — but not inside quotes that look like emails
_REF_PATTERN = re.compile(r"@(\w+(?:\.\w+)*)")


def _resolve_item_fields(text: str, item: dict) -> str:
    """Replace @item.field references with actual values from a dict."""

    def _replace(m):
        ref = m.group(1)
        if ref.startswith("item."):
            field = ref[5:]  # strip "item."
            return str(item.get(field, ""))
        return m.group(0)  # leave other refs alone

    return _REF_PATTERN.sub(_replace, text)


def _resolve_settings(text: str, settings: dict) -> str:
    """Replace @key references that match settings keys."""

    def _replace(m):
        ref = m.group(1)
        if ref in settings:
            return str(settings[ref])
        return m.group(0)

    return _REF_PATTERN.sub(_replace, text)


def _normalize_case(item: dict) -> dict:
    """Map raw A2AJ API fields to clean @item.field names."""
    return {
        "case_name": item.get("name_en") or item.get("name", ""),
        "citation": item.get("citation_en") or item.get("citation", ""),
        "court": item.get("dataset", ""),
        "date": str(item.get("document_date_en", ""))[:10],
        "url": item.get("url_en", ""),
        "text": item.get("unofficial_text_en", "")
        or item.get("snippet", ""),
        # keep all original fields too
        **item,
    }


# ---------------------------------------------------------------------------
#  ChainEngine
# ---------------------------------------------------------------------------


class ChainEngine:
    """Load a recipe YAML and execute the block chain."""

    def __init__(self, config: dict):
        self._raw = config
        self.settings: dict = config.get("settings", {})
        self.models: dict = config.get("models", {})
        self.chain: list[dict] = config.get("chain", [])
        # stores output of each block by name
        self._outputs: dict[str, object] = {}

    # ---- Loading --------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "ChainEngine":
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        return cls(config)

    # ---- Run the full chain ---------------------------------------------

    def run(self, filter_data: list[dict]) -> dict[str, object]:
        """
        Execute every block in order.

        Args:
            filter_data: list of case/law dicts from FilterProfile.fetch()

        Returns:
            dict mapping block name -> its output
        """
        # Normalise field names so @item.case_name etc. work
        normalised = [_normalize_case(item) for item in filter_data]
        self._outputs = {"filter_data": normalised}

        for block in self.chain:
            name = block["name"]
            block_type = block.get("type", "llm")

            print(f"  [{name}] running ({block_type})...")

            if block_type == "function":
                result = self._run_function(block)
            elif block_type == "llm":
                result = self._run_llm(block)
            else:
                raise ValueError(f"Unknown block type: {block_type}")

            self._outputs[name] = result
            # Show a short status
            if isinstance(result, list):
                print(f"  [{name}] done — {len(result)} items")
            else:
                preview = str(result)[:80].replace("\n", " ")
                print(f"  [{name}] done — {preview}...")

        return dict(self._outputs)

    # ---- Resolve input reference ----------------------------------------

    def _resolve_input(self, block: dict) -> object:
        """Resolve the input field of a block to actual data."""
        raw = block.get("input", "")
        if not isinstance(raw, str):
            return raw

        # @filter_data
        if raw == "@filter_data":
            return self._outputs["filter_data"]

        # @blockname.output
        m = re.match(r"^@(\w+)\.output$", raw)
        if m:
            ref_name = m.group(1)
            if ref_name not in self._outputs:
                raise ValueError(
                    f"Block '{block['name']}' references @{ref_name}.output "
                    f"but '{ref_name}' hasn't run yet"
                )
            return self._outputs[ref_name]

        return raw

    # ---- Function blocks ------------------------------------------------

    def _run_function(self, block: dict) -> object:
        func = block.get("function", "")

        if func == "split":
            data = self._resolve_input(block)
            if not isinstance(data, list):
                return [data]
            return list(data)

        if func == "merge":
            data = self._resolve_input(block)
            join_str = block.get("join", "\n---\n")
            if isinstance(data, list):
                return join_str.join(str(item) for item in data)
            return str(data)

        raise ValueError(f"Unknown function: {func}")

    # ---- LLM blocks -----------------------------------------------------

    def _run_llm(self, block: dict) -> object:
        data = self._resolve_input(block)
        prompt_template = block.get("prompt", "")
        model_key = block.get("model", "")

        # Resolve model config
        model_conf = self.models.get(model_key, {})
        provider = model_conf.get("provider", "openai")
        model_name = model_conf.get("name", model_key)
        temperature = model_conf.get("temperature", 0.3)

        call_fn = PROVIDERS.get(provider)
        if call_fn is None:
            raise ValueError(f"Unknown provider: {provider}")

        # If input is a list, loop over each item
        if isinstance(data, list):
            results = []
            for i, item in enumerate(data):
                item_dict = item if isinstance(item, dict) else {"text": str(item)}
                prompt = self._render_prompt(prompt_template, str(item), item_dict)
                print(f"    processing item {i + 1}/{len(data)}...")
                result = call_fn(model_name, prompt, temperature)
                results.append(result)
            return results

        # Single input
        item_dict = data if isinstance(data, dict) else {}
        prompt = self._render_prompt(prompt_template, str(data), item_dict)
        return call_fn(model_name, prompt, temperature)

    def _render_prompt(self, template: str, input_text: str, item: dict) -> str:
        """Replace all @ references in a prompt template."""
        result = template

        # 1. Replace @item.field references
        result = _resolve_item_fields(result, item)

        # 2. Replace @settings keys (audience, tone, etc.)
        result = _resolve_settings(result, self.settings)

        # 3. Replace @input with the resolved input text
        result = result.replace("@input", input_text)

        return result

    # ---- Repr -----------------------------------------------------------

    def __repr__(self) -> str:
        block_names = [b["name"] for b in self.chain]
        return f"ChainEngine(blocks={block_names})"
