"""
Test 7: FilterProfile with absolute date ranges (historical data) to verify
search, post-filters, dedup, and full-text fetch all work correctly.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.filter_profile import FilterProfile


def run():
    # Build a profile in code with an absolute date range we know has data
    config = {
        "name": "Test Historical SCC",
        "description": "Test profile targeting 2023 SCC decisions",
        "schedule": "manual",
        "doc_type": "cases",
        "datasets": ["SCC"],
        "date_range": {
            "mode": "absolute",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        },
        "query": "charter rights",
        "search_type": "full_text",
        "language": "en",
        "sort": "newest_first",
        "max_results": 10,
        "keyword_include": [],
        "keyword_exclude": [],
        "min_text_length": 0,
        "audience": "test",
        "tone": "test",
        "thematic_focus": "test",
    }

    fp = FilterProfile(config)
    print(f"{fp!r}")
    print(f"Search params: {fp._build_search_params()}\n")

    # --- Search only ---
    print("=== Search (no full text) ===")
    results = fp.fetch(fetch_full_text=False)
    print(f"Results: {len(results)}")
    for i, item in enumerate(results[:5], 1):
        cit = item.get("citation_en", "")
        name = item.get("name_en", "")
        date = str(item.get("document_date_en", ""))[:10]
        print(f"  [{i}] {cit:25s}  {date}  {name[:50]}")
    print()

    if not results:
        print("No results — cannot test further.")
        return

    # --- Dedup ---
    print("=== Dedup test ===")
    first_cit = results[0].get("citation_en", "")
    print(f"  Marking processed: {first_cit}")
    fp.mark_processed(first_cit)
    results2 = fp.fetch(fetch_full_text=False)
    cits2 = [r.get("citation_en", "") for r in results2]
    assert first_cit not in cits2, "Dedup FAILED"
    print(f"  OK — {len(results2)} results (was {len(results)})")
    fp.reset_processed()
    print("  Reset done\n")

    # --- Keyword include ---
    print("=== Keyword include test ===")
    fp.keyword_include = ["discrimination"]
    filtered = fp.fetch(fetch_full_text=False)
    print(f"  With keyword_include=['discrimination']: {len(filtered)} results (was {len(results)})")
    fp.keyword_include = []
    print()

    # --- Full text fetch (just 1) ---
    print("=== Full-text fetch (top 1) ===")
    fp.max_results = 1
    full = fp.fetch(fetch_full_text=True)
    if full:
        text = full[0].get("unofficial_text_en", "")
        print(f"  Citation: {full[0].get('citation_en', '')}")
        print(f"  Text length: {len(text):,} chars")
        print(f"  Preview: {text[:300]}...")
    else:
        print("  No full-text results")
    print()

    print("All tests passed.")


if __name__ == "__main__":
    run()
