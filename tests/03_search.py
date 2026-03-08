"""
Test 3: /search endpoint
Full-text or name-based search across cases or legislation.
"""

import requests
import json

BASE_URL = "https://api.a2aj.ca"


def test_search_fulltext():
    print("=" * 60)
    print("Search: Full-text — 'right to housing'")
    print("=" * 60)
    params = {
        "query": "right to housing",
        "search_type": "full_text",
        "doc_type": "cases",
        "size": 5,
    }
    response = requests.get(f"{BASE_URL}/search", params=params)
    print(f"Status: {response.status_code}")
    data = response.json()
    results = data if isinstance(data, list) else data.get("results", data)
    for i, item in enumerate(results[:5], 1):
        print(f"\n  [{i}] {item.get('name_en') or item.get('citation_en')}")
        print(f"      Citation : {item.get('citation_en')}")
        print(f"      Date     : {str(item.get('document_date_en',''))[:10]}")
        print(f"      Dataset  : {item.get('dataset')}")
        snippet = item.get("snippet", "")
        if snippet:
            print(f"      Snippet  : {snippet[:200]}")
    print()


def test_search_refugee_cases():
    print("=" * 60)
    print("Search: Refugee cases from IRB datasets (2022–2024)")
    print("=" * 60)
    params = {
        "query": "refugee protection removal",
        "search_type": "full_text",
        "doc_type": "cases",
        "size": 5,
        "dataset": "RAD,RPD",
        "start_date": "2022-01-01",
        "end_date": "2024-12-31",
        "sort_results": "newest_first",
    }
    response = requests.get(f"{BASE_URL}/search", params=params)
    print(f"Status: {response.status_code}")
    data = response.json()
    results = data if isinstance(data, list) else data.get("results", data)
    for i, item in enumerate(results[:5], 1):
        print(f"\n  [{i}] {item.get('name_en') or item.get('citation_en')}")
        print(f"      Citation : {item.get('citation_en')}")
        print(f"      Date     : {str(item.get('document_date_en',''))[:10]}")
        print(f"      Dataset  : {item.get('dataset')}")
    print()


def test_search_disability_benefits():
    print("=" * 60)
    print("Search: Disability benefits — Social Security Tribunal")
    print("=" * 60)
    params = {
        "query": "disability benefits CPP",
        "search_type": "full_text",
        "doc_type": "cases",
        "size": 5,
        "dataset": "SST",
    }
    response = requests.get(f"{BASE_URL}/search", params=params)
    print(f"Status: {response.status_code}")
    data = response.json()
    results = data if isinstance(data, list) else data.get("results", data)
    for i, item in enumerate(results[:5], 1):
        print(f"\n  [{i}] {item.get('name_en') or item.get('citation_en')}")
        print(f"      Citation : {item.get('citation_en')}")
        print(f"      Date     : {str(item.get('document_date_en',''))[:10]}")
    print()


def test_search_scc_by_name():
    print("=" * 60)
    print("Search: Name search — 'R v' in Supreme Court of Canada")
    print("=" * 60)
    params = {
        "query": "R v",
        "search_type": "name",
        "doc_type": "cases",
        "size": 5,
        "dataset": "SCC",
        "sort_results": "newest_first",
    }
    response = requests.get(f"{BASE_URL}/search", params=params)
    print(f"Status: {response.status_code}")
    data = response.json()
    results = data if isinstance(data, list) else data.get("results", data)
    for i, item in enumerate(results[:5], 1):
        print(f"\n  [{i}] {item.get('name_en') or item.get('citation_en')}")
        print(f"      Citation : {item.get('citation_en')}")
        print(f"      Date     : {str(item.get('document_date_en',''))[:10]}")
    print()


def test_search_laws():
    print("=" * 60)
    print("Search: Laws — 'immigration and refugee'")
    print("=" * 60)
    params = {
        "query": "immigration and refugee",
        "search_type": "full_text",
        "doc_type": "laws",
        "size": 5,
    }
    response = requests.get(f"{BASE_URL}/search", params=params)
    print(f"Status: {response.status_code}")
    data = response.json()
    results = data if isinstance(data, list) else data.get("results", data)
    for i, item in enumerate(results[:5], 1):
        name = item.get('name_en') or item.get('name') or item.get('citation_en') or item.get('citation')
        citation = item.get('citation_en') or item.get('citation')
        print(f"\n  [{i}] {name}")
        print(f"      Citation : {citation}")
    print()


if __name__ == "__main__":
    test_search_fulltext()
    test_search_refugee_cases()
    test_search_disability_benefits()
    test_search_scc_by_name()
    test_search_laws()
