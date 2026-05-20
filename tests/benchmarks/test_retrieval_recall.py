"""Retrieval recall benchmark test."""

import json
import pytest
from pathlib import Path

BENCHMARK_DATA = Path(__file__).with_name("data") / "benchmark_queries.json"


@pytest.mark.benchmark
def test_retrieval_recall():
    if not BENCHMARK_DATA.exists():
        pytest.skip("Benchmark data not found")
    data = json.loads(BENCHMARK_DATA.read_text())
    for item in data:
        query = item["query"]
        expected = item["expected_ids"]
        # TODO: run retrieval and compute recall
