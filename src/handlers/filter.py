from __future__ import annotations

"""
Filter handler — fetches and filters legal data from the A2AJ API.

Reads the "filter:" section of a unified podcast YAML.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests

BASE_URL = "https://api.a2aj.ca"


class FilterHandler:
    """Fetch and filter cases/laws from A2AJ based on config."""

    def __init__(self, config: dict, podcast_name: str = "default", language: str = "en"):
        self._raw = config
        self._podcast_name = podcast_name

        # --- Core API filters ---
        self.doc_type: str = config.get("doc_type", "cases")
        self.datasets: list[str] = config.get("datasets", [])
        self.date_range: dict = config.get("date_range", {})
        self.query: str = config.get("query", "")
        self.search_type: str = config.get("search_type", "full_text")
        self.language: str = config.get("language", language)
        self.sort: str = config.get("sort", "newest_first")
        self.max_results: int = min(config.get("max_results", 20), 50)
        self.fetch_full_text: bool = config.get("fetch_full_text", True)
        self.max_text_chars: int | None = config.get("max_text_chars", None)

        # --- Post-fetch filters ---
        self.keyword_include: list[str] = config.get("keyword_include", [])
        self.keyword_exclude: list[str] = config.get("keyword_exclude", [])
        self.min_text_length: int = config.get("min_text_length", 0)

        # --- Dedup state ---
        self._processed_citations: set[str] = set()
        self._dedup_path = self._resolve_dedup_path()
        self._load_processed()

    # ------------------------------------------------------------------ #
    #  Main entry point                                                    #
    # ------------------------------------------------------------------ #

    def run(self) -> list[dict]:
        """
        Execute the filter pipeline:
          1. Search the A2AJ API
          2. Optionally fetch full text
          3. Apply post-fetch filters
          4. Deduplicate
        """
        print("  [filter] searching A2AJ API...")
        results = self._search()
        print(f"  [filter] found {len(results)} results")

        if self.fetch_full_text:
            print("  [filter] fetching full text...")
            enriched = []
            for item in results:
                citation = item.get("citation_en") or item.get("citation", "")
                if not citation:
                    continue
                try:
                    full = self._fetch_full_text(citation)
                    if full:
                        enriched.append({**item, **full})
                except requests.HTTPError as e:
                    print(f"  [filter] warning: failed to fetch {citation}: {e}")
                    enriched.append(item)  # keep the search result without full text
            results = enriched
            print(f"  [filter] fetched text for {len(results)} cases")

        results = self._apply_post_filters(results)
        print(f"  [filter] {len(results)} after post-filters")

        results = self._deduplicate(results)
        print(f"  [filter] {len(results)} after dedup")

        return results

    # ------------------------------------------------------------------ #
    #  API interaction                                                     #
    # ------------------------------------------------------------------ #

    def _build_search_params(self) -> dict:
        start_date, end_date = self._resolve_date_range()
        params = {
            "query": self.query,
            "search_type": self.search_type,
            "doc_type": self.doc_type,
            "size": self.max_results,
            "sort_results": self.sort,
        }
        if self.datasets:
            params["dataset"] = ",".join(self.datasets)
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if self.language:
            params["search_language"] = self.language
        return params

    def _search(self) -> list[dict]:
        params = self._build_search_params()
        resp = requests.get(f"{BASE_URL}/search", params=params)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("results", [])

    def _fetch_full_text(self, citation: str) -> dict:
        params = {
            "citation": citation,
            "doc_type": self.doc_type,
            "output_language": self.language,
        }
        if self.max_text_chars is not None:
            params["start_char"] = 0
            params["end_char"] = self.max_text_chars
        resp = requests.get(f"{BASE_URL}/fetch", params=params)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [data])
        return results[0] if results else {}

    # ------------------------------------------------------------------ #
    #  Date resolution                                                     #
    # ------------------------------------------------------------------ #

    def _resolve_date_range(self) -> tuple[str | None, str | None]:
        if not self.date_range:
            return None, None
        mode = self.date_range.get("mode", "absolute")
        if mode == "relative":
            days = self.date_range.get("last_n_days", 7)
            end = datetime.now()
            start = end - timedelta(days=days)
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        return self.date_range.get("start_date"), self.date_range.get("end_date")

    # ------------------------------------------------------------------ #
    #  Post-fetch filters                                                  #
    # ------------------------------------------------------------------ #

    def _apply_post_filters(self, results: list[dict]) -> list[dict]:
        filtered = []
        for item in results:
            text = (item.get("unofficial_text_en", "") or item.get("snippet", "")).lower()
            if self.min_text_length and len(text) < self.min_text_length:
                continue
            if self.keyword_include:
                if not any(kw.lower() in text for kw in self.keyword_include):
                    continue
            if self.keyword_exclude:
                if any(kw.lower() in text for kw in self.keyword_exclude):
                    continue
            filtered.append(item)
        return filtered

    # ------------------------------------------------------------------ #
    #  Deduplication                                                       #
    # ------------------------------------------------------------------ #

    def _deduplicate(self, results: list[dict]) -> list[dict]:
        novel = []
        for item in results:
            citation = item.get("citation_en") or item.get("citation", "")
            if citation and citation not in self._processed_citations:
                novel.append(item)
        return novel

    def mark_all_processed(self, results: list[dict]):
        for item in results:
            citation = item.get("citation_en") or item.get("citation", "")
            if citation:
                self._processed_citations.add(citation)
        self._save_processed()

    def reset_processed(self):
        self._processed_citations.clear()
        self._save_processed()

    # ------------------------------------------------------------------ #
    #  Dedup persistence                                                   #
    # ------------------------------------------------------------------ #

    def _resolve_dedup_path(self) -> str:
        base_dir = Path(__file__).resolve().parent.parent.parent / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._podcast_name.lower().replace(" ", "_").replace("/", "_")
        return str(base_dir / f"processed_{safe_name}.json")

    def _load_processed(self):
        if os.path.exists(self._dedup_path):
            with open(self._dedup_path, "r") as f:
                self._processed_citations = set(json.load(f))

    def _save_processed(self):
        with open(self._dedup_path, "w") as f:
            json.dump(sorted(self._processed_citations), f, indent=2)
