"""
Test 8: ChainEngine — load a recipe and run it on real A2AJ data.

Uses FilterProfile to fetch cases, then pipes them through the chain.
Set your API key before running:
  export OPENAI_API_KEY=sk-...
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.filter_profile import FilterProfile
from src.chain_engine import ChainEngine


def run():
    # --- Step 1: Get some cases via FilterProfile ---
    print("=" * 60)
    print("Step 1: Fetching cases from A2AJ")
    print("=" * 60)

    profile = FilterProfile({
        "name": "Test Chain",
        "doc_type": "cases",
        "datasets": ["SCC"],
        "date_range": {
            "mode": "absolute",
            "start_date": "2023-06-01",
            "end_date": "2023-12-31",
        },
        "query": "charter rights",
        "search_type": "full_text",
        "language": "en",
        "sort": "newest_first",
        "max_results": 2,  # keep small for testing
    })

    # Fetch with full text but cap at 3000 chars to save tokens
    results = profile._search()
    cases = []
    for item in results[:2]:
        citation = item.get("citation_en", "")
        if citation:
            full = profile._fetch_full_text(citation, max_chars=3000)
            cases.append({**item, **full})

    print(f"  Got {len(cases)} cases")
    for c in cases:
        print(f"    - {c.get('citation_en', '')} | {c.get('name_en', '')}")
    print()

    if not cases:
        print("No cases found. Exiting.")
        return

    # --- Step 2: Run through ChainEngine ---
    print("=" * 60)
    print("Step 2: Running community_newsletter recipe")
    print("=" * 60)

    recipe_path = os.path.join(
        os.path.dirname(__file__), "..", "recipes", "community_newsletter.yaml"
    )
    engine = ChainEngine.load(recipe_path)
    print(f"  {engine!r}")
    print(f"  Settings: {engine.settings}")
    print()

    outputs = engine.run(cases)

    # --- Step 3: Print final output ---
    print()
    print("=" * 60)
    print("FINAL OUTPUT: Weekly Digest")
    print("=" * 60)
    print()
    print(outputs.get("weekly_digest", "(no output)"))


if __name__ == "__main__":
    run()
