"""
Test 1: /coverage endpoint
Returns statistics on courts/tribunals or legislation covered by A2AJ.
"""

import requests
import json

BASE_URL = "https://api.a2aj.ca"


def test_coverage_cases():
    print("=" * 60)
    print("Coverage: Cases")
    print("=" * 60)
    response = requests.get(f"{BASE_URL}/coverage", params={"doc_type": "cases"})
    print(f"Status: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
    print()


def test_coverage_laws():
    print("=" * 60)
    print("Coverage: Laws")
    print("=" * 60)
    response = requests.get(f"{BASE_URL}/coverage", params={"doc_type": "laws"})
    print(f"Status: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
    print()


if __name__ == "__main__":
    test_coverage_cases()
    test_coverage_laws()
