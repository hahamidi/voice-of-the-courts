"""
Test 5: End-to-end mini pipeline — mimics the "Voice of the Courts" ingest flow.

Steps:
  1. Search for recent SCC decisions
  2. Fetch full text of the top result
  3. Print a plain-language stub (where an LLM would normally summarise)
"""

import requests
import textwrap

BASE_URL = "https://api.a2aj.ca"


def search_recent_scc(n=3):
    """Return the n most recent SCC decisions."""
    params = {
        "query": "Canada",      # broad term to pull recent decisions
        "search_type": "full_text",
        "doc_type": "cases",
        "dataset": "SCC",
        "size": n,
        "sort_results": "newest_first",
    }
    r = requests.get(f"{BASE_URL}/search", params=params)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("results", [])


def fetch_decision(citation, max_chars=3000):
    """Fetch the first max_chars characters of a decision."""
    params = {
        "citation": citation,
        "doc_type": "cases",
        "output_language": "en",
        "start_char": 0,
        "end_char": max_chars,
    }
    r = requests.get(f"{BASE_URL}/fetch", params=params)
    r.raise_for_status()
    data = r.json()
    # Unwrap 'results' list
    results = data.get("results", [data])
    return results[0] if results else {}


def plain_language_stub(decision: dict) -> str:
    """
    Placeholder for an LLM summarisation step.
    In the full system this would call Claude / GPT to produce a plain-language summary.
    """
    name = decision.get("name_en") or decision.get("citation_en", "Unknown")
    date = str(decision.get("document_date_en", "Unknown date"))[:10]
    text = decision.get("unofficial_text_en", "")
    preview = text[:600].replace("\n", " ").strip()
    return (
        f"CASE   : {name}\n"
        f"DATE   : {date}\n"
        f"EXCERPT: {preview}...\n"
        f"\n[LLM SUMMARY GOES HERE — connect to Claude / OpenAI to produce plain-language output]"
    )


def run_pipeline():
    print("=" * 60)
    print("Voice of the Courts — Mini Ingest Pipeline")
    print("=" * 60)

    print("\nStep 1: Fetching recent SCC decisions...")
    results = search_recent_scc(n=3)
    print(f"  Found {len(results)} result(s)")

    if not results:
        print("  No results returned. Exiting.")
        return

    for idx, item in enumerate(results, 1):
        citation = item.get("citation_en") or item.get("citation", "")
        name = item.get("name_en") or item.get("name", citation)
        date = str(item.get("document_date_en") or item.get("date", ""))[:10]
        print(f"\n{'─' * 60}")
        print(f"  Decision {idx}: {name}")
        print(f"  Citation : {citation}")
        print(f"  Date     : {date}")

        if not citation:
            print("  [No citation — skipping fetch]")
            continue

        print(f"\nStep 2: Fetching full text for '{citation}'...")
        try:
            decision = fetch_decision(citation)
        except requests.HTTPError as e:
            print(f"  Fetch failed: {e}")
            continue

        print(f"\nStep 3: Generating plain-language stub...")
        summary = plain_language_stub(decision)
        print(textwrap.indent(summary, "  "))

    print("\n" + "=" * 60)
    print("Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
