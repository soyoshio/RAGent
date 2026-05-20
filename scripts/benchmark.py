"""Recall benchmark script."""

import json
import time
from pathlib import Path


def benchmark(index_path: str, queries_path: str):
    queries = json.loads(Path(queries_path).read_text())
    results = []
    for q in queries:
        start = time.time()
        # TODO: run retrieval
        latency = time.time() - start
        results.append({"query": q["query"], "latency_ms": latency * 1000})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="data/chunk_index.json")
    parser.add_argument("--queries", default="tests/benchmarks/data/benchmark_queries.json")
    args = parser.parse_args()
    benchmark(args.index, args.queries)
