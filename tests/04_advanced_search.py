"""
Test 4: Advanced search operators
A2AJ supports Boolean logic, phrase search, wildcards, and proximity operators.
"""

import requests

BASE_URL = "https://api.a2aj.ca"


def search(label, query, doc_type="cases", dataset=None, size=3, **kwargs):
    print(f"\n{'=' * 60}")
    print(f"{label}")
    print(f"  Query: {query!r}")
    print("=" * 60)
    params = {
        "query": query,
        "search_type": "full_text",
        "doc_type": doc_type,
        "size": size,
    }
    if dataset:
        params["dataset"] = dataset
    params.update(kwargs)
    response = requests.get(f"{BASE_URL}/search", params=params)
    print(f"Status: {response.status_code}")
    data = response.json()
    results = data if isinstance(data, list) else data.get("results", data)
    for i, item in enumerate(results[:size], 1):
        citation = str(item.get('citation_en') or item.get('citation') or '')
        date = str(item.get('document_date_en') or item.get('date') or '')[:10]
        name = str(item.get('name_en') or item.get('name') or '')
        print(f"  [{i}] {citation:30s}  {date}  {name[:60]}")
    return results


if __name__ == "__main__":
    # Boolean AND (both terms must appear)
    search("Boolean AND", "charter AND discrimination", dataset="SCC")

    # Boolean OR (either term)
    search("Boolean OR", "refugee OR asylum", dataset="RAD,RPD", size=4)

    # Boolean NOT (exclude term)
    search("Boolean NOT", "immigration NOT removal", dataset="FC,FCA")

    # Exact phrase
    search('Exact phrase', '"right to counsel"', dataset="SCC,ONCA")

    # Wildcard (prefix match)
    search("Wildcard", "disabilit*", dataset="SST")

    # Proximity search — words within N positions of each other
    search("Proximity", '"housing discrimination"~5', dataset="CHRT")

    # Combined: phrase + date filter
    search(
        "Phrase + date filter",
        '"freedom of expression"',
        dataset="SCC",
        start_date="2020-01-01",
        sort_results="newest_first",
    )
