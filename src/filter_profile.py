from __future__ import annotations

"""
FilterProfile — YAML-driven filter engine for the A2AJ ingest pipeline.

Loads a YAML profile that defines which legal decisions to fetch,
calls the A2AJ API, applies post-fetch filters (keyword, dedup, min length),
and returns clean results ready for the AI summarization engine.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
import yaml

BASE_URL = "https://api.a2aj.ca"

# All valid dataset codes recognised by the A2AJ API
VALID_CASE_DATASETS = {
    "SCC", "FC", "FCA", "ONCA", "BCCA", "BCSC",
    "CHRT", "CMAC", "RAD", "RPD", "SST", "TCC", "RLLR",
}
VALID_LAW_DATASETS = {
    "LEGISLATION-FED", "LEGISLATION-ON", "LEGISLATION-BC",
    "REGULATIONS-FED", "REGULATIONS-ON", "REGULATIONS-BC",
}


class FilterProfile:
    """A single filter configuration that drives one ingest run."""

    def __init__(self, config: dict, profile_path: str | None = None):
        self._raw = config
        self._profile_path = profile_path

        # --- Profile metadata ---
        self.name: str = config.get("name", "Untitled Profile")
        self.description: str = config.get("description", "")
        self.schedule: str = config.get("schedule", "manual")

        # --- Core API filters ---
        self.doc_type: str = config.get("doc_type", "cases")
        self.datasets: list[str] = config.get("datasets", [])
        self.date_range: dict = config.get("date_range", {})
        self.query: str = config.get("query", "")
        self.search_type: str = config.get("search_type", "full_text")
        self.language: str = config.get("language", "en")
        self.sort: str = config.get("sort", "newest_first")
        self.max_results: int = min(config.get("max_results", 20), 50)

        # --- Post-fetch filters ---
        self.keyword_include: list[str] = config.get("keyword_include", [])
        self.keyword_exclude: list[str] = config.get("keyword_exclude", [])
        self.min_text_length: int = config.get("min_text_length", 0)

        # --- Downstream hints (not used by this class, passed through) ---
        self.audience: str = config.get("audience", "")
        self.tone: str = config.get("tone", "")
        self.thematic_focus: str = config.get("thematic_focus", "")

        # --- Dedup state ---
        self._processed_citations: set[str] = set()
        self._dedup_path = self._resolve_dedup_path()
        self._load_processed()

    # ------------------------------------------------------------------ #
    #  Loading / saving                                                    #
    # ------------------------------------------------------------------ #

    @classmethod
    def load(cls, path: str) -> "FilterProfile":
        """Load a FilterProfile from a YAML file."""
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        return cls(config, profile_path=path)

    def save(self, path: str | None = None):
        """Save the current configuration back to YAML."""
        target = path or self._profile_path
        if target is None:
            raise ValueError("No path specified and no original path available")
        with open(target, "w") as f:
            yaml.dump(self._raw, f, default_flow_style=False, allow_unicode=True)

    def to_dict(self) -> dict:
        """Return the raw config dict (useful for serialisation or UI)."""
        return dict(self._raw)

    # ------------------------------------------------------------------ #
    #  Core fetch pipeline                                                 #
    # ------------------------------------------------------------------ #

    def fetch(self, fetch_full_text: bool = False) -> list[dict]:
        """
        Run the full pipeline:
          1. Search the A2AJ API using the profile's filters
          2. Optionally fetch full text for each result
          3. Apply post-fetch filters (keywords, min length)
          4. Deduplicate against already-processed citations

        Returns a list of decision dicts ready for downstream processing.
        """
        results = self._search()

        if fetch_full_text:
            enriched = []
            for item in results:
                citation = item.get("citation_en") or item.get("citation", "")
                if not citation:
                    continue
                full = self._fetch_full_text(citation)
                if full:
                    # Merge search metadata with full-text data
                    merged = {**item, **full}
                    enriched.append(merged)
            results = enriched

        results = self._apply_post_filters(results)
        results = self._deduplicate(results)
        return results

    # ------------------------------------------------------------------ #
    #  API interaction                                                     #
    # ------------------------------------------------------------------ #

    def _build_search_params(self) -> dict:
        """Assemble query parameters for GET /search."""
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
        """Call A2AJ /search and return the results list."""
        params = self._build_search_params()
        resp = requests.get(f"{BASE_URL}/search", params=params)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return data.get("results", [])

    def _fetch_full_text(self, citation: str, max_chars: int | None = None) -> dict:
        """Call A2AJ /fetch for a single citation."""
        params = {
            "citation": citation,
            "doc_type": self.doc_type,
            "output_language": self.language,
        }
        if max_chars is not None:
            params["start_char"] = 0
            params["end_char"] = max_chars
        resp = requests.get(f"{BASE_URL}/fetch", params=params)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [data])
        return results[0] if results else {}

    # ------------------------------------------------------------------ #
    #  Date resolution                                                     #
    # ------------------------------------------------------------------ #

    def _resolve_date_range(self) -> tuple[str | None, str | None]:
        """Convert the date_range config into (start_date, end_date) strings."""
        if not self.date_range:
            return None, None

        mode = self.date_range.get("mode", "absolute")

        if mode == "relative":
            days = self.date_range.get("last_n_days", 7)
            end = datetime.now()
            start = end - timedelta(days=days)
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

        # absolute mode
        return (
            self.date_range.get("start_date"),
            self.date_range.get("end_date"),
        )

    # ------------------------------------------------------------------ #
    #  Post-fetch filters                                                  #
    # ------------------------------------------------------------------ #

    def _apply_post_filters(self, results: list[dict]) -> list[dict]:
        """Apply keyword include/exclude and minimum text length filters."""
        filtered = []
        for item in results:
            text = (
                item.get("unofficial_text_en", "")
                or item.get("snippet", "")
            ).lower()

            # Minimum text length
            if self.min_text_length and len(text) < self.min_text_length:
                continue

            # Keyword include — at least one must appear
            if self.keyword_include:
                if not any(kw.lower() in text for kw in self.keyword_include):
                    continue

            # Keyword exclude — none may appear
            if self.keyword_exclude:
                if any(kw.lower() in text for kw in self.keyword_exclude):
                    continue

            filtered.append(item)
        return filtered

    # ------------------------------------------------------------------ #
    #  Deduplication                                                       #
    # ------------------------------------------------------------------ #

    def _deduplicate(self, results: list[dict]) -> list[dict]:
        """Remove results whose citations have already been processed."""
        novel = []
        for item in results:
            citation = item.get("citation_en") or item.get("citation", "")
            if citation and citation not in self._processed_citations:
                novel.append(item)
        return novel

    def mark_processed(self, citation: str):
        """Mark a citation as processed (call after pipeline finishes with it)."""
        self._processed_citations.add(citation)
        self._save_processed()

    def mark_all_processed(self, results: list[dict]):
        """Mark all results as processed in one call."""
        for item in results:
            citation = item.get("citation_en") or item.get("citation", "")
            if citation:
                self._processed_citations.add(citation)
        self._save_processed()

    def reset_processed(self):
        """Clear the dedup state (re-process everything)."""
        self._processed_citations.clear()
        self._save_processed()

    # ------------------------------------------------------------------ #
    #  Dedup persistence                                                   #
    # ------------------------------------------------------------------ #

    def _resolve_dedup_path(self) -> str:
        """Determine where to store the processed-citations file."""
        base_dir = Path(__file__).resolve().parent.parent / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        # Use a sanitised profile name for the filename
        safe_name = self.name.lower().replace(" ", "_").replace("/", "_")
        return str(base_dir / f"processed_{safe_name}.json")

    def _load_processed(self):
        if os.path.exists(self._dedup_path):
            with open(self._dedup_path, "r") as f:
                self._processed_citations = set(json.load(f))

    def _save_processed(self):
        with open(self._dedup_path, "w") as f:
            json.dump(sorted(self._processed_citations), f, indent=2)

    # ------------------------------------------------------------------ #
    #  Repr                                                                #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"FilterProfile(name={self.name!r}, doc_type={self.doc_type!r}, "
            f"datasets={self.datasets}, query={self.query!r})"
        )
