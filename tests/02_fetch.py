"""
Test 2: /fetch endpoint
Retrieves full text of specific cases or legislation by citation.
"""

import requests
import json

BASE_URL = "https://api.a2aj.ca"


def extract_result(data):
    """The API wraps the result in a 'results' list. Unpack it."""
    results = data.get("results", [data])
    return results[0] if results else {}


def test_fetch_case():
    print("=" * 60)
    print("Fetch: Supreme Court case (2023 SCC 17)")
    print("=" * 60)
    params = {
        "citation": "2023 SCC 17",
        "doc_type": "cases",
        "output_language": "en",
    }
    response = requests.get(f"{BASE_URL}/fetch", params=params)
    print(f"Status: {response.status_code}")
    item = extract_result(response.json())
    print(f"  Name     : {item.get('name_en')}")
    print(f"  Citation : {item.get('citation_en')}")
    print(f"  Date     : {str(item.get('document_date_en',''))[:10]}")
    print(f"  Dataset  : {item.get('dataset')}")
    print(f"  URL      : {item.get('url_en')}")
    text = item.get("unofficial_text_en", "")
    print(f"  Text len : {len(text):,} chars")
    print(f"\n  [Text preview]\n  {text[:500]}...")
    print()


def test_fetch_law():
    print("=" * 60)
    print("Fetch: Canadian Charter of Rights and Freedoms")
    print("=" * 60)
    params = {
        "citation": "Canadian Charter of Rights and Freedoms",
        "doc_type": "laws",
        "output_language": "en",
    }
    response = requests.get(f"{BASE_URL}/fetch", params=params)
    print(f"Status: {response.status_code}")
    item = extract_result(response.json())
    print(f"  Name     : {item.get('name_en')}")
    print(f"  Citation : {item.get('citation_en')}")
    print(f"  Date     : {str(item.get('document_date_en',''))[:10]}")
    text = item.get("unofficial_text_en", "")
    print(f"  Text len : {len(text):,} chars")
    print(f"\n  [Text preview]\n  {text[:500]}...")
    print()


def test_fetch_partial():
    """Fetch only a chunk of a document using start_char/end_char."""
    print("=" * 60)
    print("Fetch: Partial text (chars 0–1000) of 2023 SCC 17")
    print("=" * 60)
    params = {
        "citation": "2023 SCC 17",
        "doc_type": "cases",
        "output_language": "en",
        "start_char": 0,
        "end_char": 1000,
    }
    response = requests.get(f"{BASE_URL}/fetch", params=params)
    print(f"Status: {response.status_code}")
    item = extract_result(response.json())
    text = item.get("unofficial_text_en", "")
    print(f"  Returned text length: {len(text):,} chars")
    print(f"  Preview: {text[:400]}")
    print()


if __name__ == "__main__":
    test_fetch_case()
    test_fetch_law()
    test_fetch_partial()
