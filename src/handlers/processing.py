from __future__ import annotations

"""
Processing handler — runs an LLM block chain on filtered legal data.

Reads the "processing:" section of a unified podcast YAML.

Block types:
  - function: split  — 1 list → many items
  - function: merge  — many items → 1 string
  - llm              — calls a model; loops automatically if input is a list

@ references:
  @filter_data         — data from the filter handler
  @blockname.output    — output of a previous block
  @input               — resolved input inside a prompt
  @item.field          — field from current item (case_name, citation, text, date, court)
  @settings keys       — values from podcast-level settings (audience, tone, etc.)
"""

import re

PROVIDERS = {
    "openai": "_call_openai",
    "anthropic": "_call_anthropic",
    "ollama": "_call_ollama",
}

_REF_PATTERN = re.compile(r"@(\w+(?:\.\w+)*)")


# ---------------------------------------------------------------------------
#  Model clients (lazy-imported)
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


_CALL_FNS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "ollama": _call_ollama,
}


# ---------------------------------------------------------------------------
#  @ reference helpers
# ---------------------------------------------------------------------------


def _resolve_item_fields(text: str, item: dict) -> str:
    def _replace(m):
        ref = m.group(1)
        if ref.startswith("item."):
            return str(item.get(ref[5:], ""))
        return m.group(0)
    return _REF_PATTERN.sub(_replace, text)


def _resolve_settings(text: str, settings: dict) -> str:
    def _replace(m):
        ref = m.group(1)
        if ref in settings:
            return str(settings[ref])
        return m.group(0)
    return _REF_PATTERN.sub(_replace, text)


def _normalize_case(item: dict) -> dict:
    return {
        "case_name": item.get("name_en") or item.get("name", ""),
        "citation": item.get("citation_en") or item.get("citation", ""),
        "court": item.get("dataset", ""),
        "date": str(item.get("document_date_en", ""))[:10],
        "url": item.get("url_en", ""),
        "text": item.get("unofficial_text_en", "") or item.get("snippet", ""),
        **item,
    }


# ---------------------------------------------------------------------------
#  ProcessingHandler
# ---------------------------------------------------------------------------


class ProcessingHandler:
    """Execute the LLM block chain from the processing: section."""

    def __init__(self, config: dict, settings: dict | None = None):
        self.models: dict = config.get("models", {})
        self.chain: list[dict] = config.get("chain", [])
        self.settings: dict = settings or {}
        self._outputs: dict[str, object] = {}

    def run(self, filter_data: list[dict]) -> dict[str, object]:
        """
        Execute every block in order.

        Args:
            filter_data: list of case/law dicts from FilterHandler.run()

        Returns:
            dict mapping block name -> its output
        """
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

            if isinstance(result, list):
                print(f"  [{name}] done — {len(result)} items")
            else:
                preview = str(result)[:80].replace("\n", " ")
                print(f"  [{name}] done — {preview}...")

        return dict(self._outputs)

    # ---- Resolve input reference ----------------------------------------

    def _resolve_input(self, block: dict) -> object:
        raw = block.get("input", "")
        if not isinstance(raw, str):
            return raw
        if raw == "@filter_data":
            return self._outputs["filter_data"]
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
            return list(data) if isinstance(data, list) else [data]
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

        model_conf = self.models.get(model_key, {})
        provider = model_conf.get("provider", "openai")
        model_name = model_conf.get("name", model_key)
        temperature = model_conf.get("temperature", 0.3)

        call_fn = _CALL_FNS.get(provider)
        if call_fn is None:
            raise ValueError(f"Unknown provider: {provider}")

        if isinstance(data, list):
            results = []
            for i, item in enumerate(data):
                item_dict = item if isinstance(item, dict) else {"text": str(item)}
                prompt = self._render_prompt(prompt_template, str(item), item_dict)
                print(f"    processing item {i + 1}/{len(data)}...")
                results.append(call_fn(model_name, prompt, temperature))
            return results

        item_dict = data if isinstance(data, dict) else {}
        prompt = self._render_prompt(prompt_template, str(data), item_dict)
        return call_fn(model_name, prompt, temperature)

    def _render_prompt(self, template: str, input_text: str, item: dict) -> str:
        result = template
        result = _resolve_item_fields(result, item)
        result = _resolve_settings(result, self.settings)
        result = result.replace("@input", input_text)
        return result

    def __repr__(self) -> str:
        block_names = [b["name"] for b in self.chain]
        return f"ProcessingHandler(blocks={block_names})"
