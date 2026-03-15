"""
Test 6: FilterProfile — load YAML profiles and run them against the live API.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.filter_profile import FilterProfile


def test_load_and_inspect(profile_path):
    print("=" * 60)
    print(f"Loading: {profile_path}")
    print("=" * 60)
    fp = FilterProfile.load(profile_path)
    print(f"  {fp!r}")
    print(f"  Schedule      : {fp.schedule}")
    print(f"  Date range    : {fp.date_range}")
    print(f"  Audience      : {fp.audience}")
    print(f"  Tone          : {fp.tone}")
    print(f"  Thematic focus: {fp.thematic_focus}")
    print(f"  Search params : {fp._build_search_params()}")
    print()
    return fp


def test_search_only(fp):
    print(f"--- Search-only run for: {fp.name} ---")
    results = fp.fetch(fetch_full_text=False)
    print(f"  Results after filtering: {len(results)}")
    for i, item in enumerate(results[:5], 1):
        citation = item.get("citation_en") or item.get("citation", "")
        name = item.get("name_en") or item.get("name", "")
        date = str(item.get("document_date_en", ""))[:10]
        print(f"  [{i}] {citation:30s}  {date}  {name[:50]}")
    print()
    return results


def test_fetch_with_full_text(fp):
    print(f"--- Full-text fetch for: {fp.name} (top 2) ---")
    # Temporarily lower max_results to avoid slow fetches
    original = fp.max_results
    fp.max_results = 2
    results = fp.fetch(fetch_full_text=True)
    fp.max_results = original
    print(f"  Results with full text: {len(results)}")
    for i, item in enumerate(results[:2], 1):
        citation = item.get("citation_en") or item.get("citation", "")
        text = item.get("unofficial_text_en", "")
        print(f"  [{i}] {citation}")
        print(f"      Text length: {len(text):,} chars")
        print(f"      Preview: {text[:200]}...")
    print()
    return results


def test_dedup(fp, results):
    print(f"--- Dedup test for: {fp.name} ---")
    if not results:
        print("  No results to test dedup with")
        return

    # Mark first result as processed
    first_citation = results[0].get("citation_en") or results[0].get("citation", "")
    print(f"  Marking as processed: {first_citation}")
    fp.mark_processed(first_citation)

    # Re-fetch — first result should be gone
    new_results = fp.fetch(fetch_full_text=False)
    new_citations = [
        r.get("citation_en") or r.get("citation", "") for r in new_results
    ]
    if first_citation in new_citations:
        print("  FAIL: dedup did not remove the processed citation")
    else:
        print(f"  OK: dedup removed it. {len(new_results)} results remain")

    # Clean up
    fp.reset_processed()
    print("  Processed state reset")
    print()


if __name__ == "__main__":
    profiles_dir = os.path.join(os.path.dirname(__file__), "..", "profiles")

    # Test all profiles
    for filename in sorted(os.listdir(profiles_dir)):
        if not filename.endswith(".yaml"):
            continue
        path = os.path.join(profiles_dir, filename)
        fp = test_load_and_inspect(path)
        results = test_search_only(fp)
        test_dedup(fp, results)

    # Full-text fetch on just one profile
    scc_path = os.path.join(profiles_dir, "scc_weekly.yaml")
    if os.path.exists(scc_path):
        fp = FilterProfile.load(scc_path)
        test_fetch_with_full_text(fp)
