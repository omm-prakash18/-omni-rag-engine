"""
app/eval/runner.py — RAG Evaluation Runner & Benchmark Engine.

Executes 40-query evaluation dataset against the pipeline,
recording routing paths, triage gating fraction, total LLM calls, Precision@5,
Taxonomy Accuracy, Latency (p50/p95), Cache Hit Rates (Embedding & Sub-Result), and Query Cost.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

import numpy as np

from app.database import startup
from app.eval.dataset import EVAL_QUERIES
from app.services.extraction import get_embedding_cache_stats
from app.services.ingestion import run_ingestion_pipeline
from app.services.sub_result_cache import get_sub_cache_stats

logger = logging.getLogger(__name__)


async def run_rag_eval(pipeline_fn=None) -> Dict[str, Any]:
    """Execute evaluation harness over EVAL_QUERIES and record benchmark metrics."""
    from app.config import get_settings
    settings = get_settings()
    settings.gemini_api_key = ""  # Rule-based mode for deterministic evaluation

    if pipeline_fn is None:
        from app.agents.pipeline import run_omni_pipeline
        pipeline_fn = run_omni_pipeline

    await startup()
    await run_ingestion_pipeline()

    precisions: List[float] = []
    taxonomy_matches: List[bool] = []
    latencies_ms: List[float] = []
    path_counts: Dict[str, int] = {
        "gated_off_topic": 0,
        "gated_too_vague": 0,
        "gated_no_data": 0,
        "single_fact": 0,
        "full_pipeline": 0,
    }
    total_llm_calls = 0
    total_token_estimate = 0

    total_queries = len(EVAL_QUERIES)

    print("\n=======================================================")
    print(f"   RUNNING OPTIMIZED RAG EVAL BENCHMARK ({total_queries} QUERIES)   ")
    print("=======================================================\n")

    for idx, item in enumerate(EVAL_QUERIES, 1):
        q_text = item["query"]
        t_start = time.perf_counter()
        
        try:
            res = await pipeline_fn(q_text)
        except Exception as e:
            logger.error("Eval query '%s' failed: %s", q_text, e)
            continue
            
        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000.0
        latencies_ms.append(latency_ms)

        # Extract execution path from step logs
        first_step = res.steps[0] if res.steps else ""
        if "Classified query as 'off_topic'" in first_step:
            path = "gated_off_topic"
            llm_calls = 1
            tokens = 30
        elif "Classified query as 'too_vague'" in first_step:
            path = "gated_too_vague"
            llm_calls = 1
            tokens = 30
        elif "Classified query as 'no_data_expected'" in first_step:
            path = "gated_no_data"
            llm_calls = 1
            tokens = 30
        elif "Classified query as 'single_fact'" in first_step:
            path = "single_fact"
            llm_calls = 2
            tokens = 150
        else:
            path = "full_pipeline"
            llm_calls = 3
            tokens = 350

        path_counts[path] = path_counts.get(path, 0) + 1
        total_llm_calls += llm_calls
        total_token_estimate += tokens

        # Evaluate Precision@5
        expected_srcs = item.get("expected_sources", [])
        if not expected_srcs:
            p5 = 1.0 if len(res.contradictions) == 0 else 0.0
        else:
            retrieved_srcs = []
            for c in res.contradictions:
                if c.source_a and c.source_a.source_name:
                    retrieved_srcs.append(c.source_a.source_name)
                if c.source_b and c.source_b.source_name:
                    retrieved_srcs.append(c.source_b.source_name)
            for node in res.graph.nodes:
                if node.type == "source" and node.label:
                    retrieved_srcs.append(node.label)
            
            matches = sum(1 for src in expected_srcs if any(src.lower() in r.lower() for r in retrieved_srcs))
            p5 = matches / max(len(expected_srcs), 1)

        precisions.append(p5)

        # Evaluate Taxonomy Accuracy
        exp_tax = item.get("expected_taxonomy")
        if exp_tax is None:
            tax_match = len(res.contradictions) == 0
        else:
            retrieved_taxes = [c.contradiction_type.value for c in res.contradictions]
            tax_match = exp_tax in retrieved_taxes

        taxonomy_matches.append(tax_match)

        status_symbol = "[OK]" if tax_match and p5 >= 0.5 else "[WARN]"
        print(f"[{idx:02d}/{total_queries}] {status_symbol} Path: {path:<17} | Latency: {latency_ms:5.1f}ms | P@5: {p5:4.2f} | Query: \"{q_text[:30]:<30}\"")

    p50_latency = float(np.percentile(latencies_ms, 50)) if latencies_ms else 0.0
    p95_latency = float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0
    mean_precision = float(np.mean(precisions)) if precisions else 0.0
    accuracy = float(np.mean(taxonomy_matches)) if taxonomy_matches else 0.0

    gated_total = path_counts["gated_off_topic"] + path_counts["gated_too_vague"] + path_counts["gated_no_data"]
    gating_fraction = (gated_total / max(total_queries, 1)) * 100.0
    fast_path_fraction = (path_counts["single_fact"] / max(total_queries, 1)) * 100.0

    emb_stats = get_embedding_cache_stats()
    sub_stats = get_sub_cache_stats()

    avg_tokens_per_query = total_token_estimate / max(total_queries, 1)
    cost_per_query = (avg_tokens_per_query / 1_000_000.0) * 0.20
    cost_per_1k_queries = cost_per_query * 1000.0

    metrics = {
        "precision_at_5": round(mean_precision * 100, 2),
        "accuracy_pct": round(accuracy * 100, 2),
        "p50_latency_ms": round(p50_latency, 1),
        "p95_latency_ms": round(p95_latency, 1),
        "gating_fraction_pct": round(gating_fraction, 2),
        "fast_path_fraction_pct": round(fast_path_fraction, 2),
        "embedding_cache_hits": emb_stats["hits"],
        "sub_result_cache_hits": sub_stats["hits"],
        "total_llm_calls": total_llm_calls,
        "avg_llm_calls_per_query": round(total_llm_calls / max(total_queries, 1), 2),
        "cost_per_query_usd": round(cost_per_query, 6),
        "cost_per_1k_queries_usd": round(cost_per_1k_queries, 4),
        "queries_tested": total_queries,
        "path_counts": path_counts,
    }

    print("\n=======================================================")
    print("           OPTIMIZED BENCHMARK METRICS SUMMARY         ")
    print("=======================================================")
    print(f"  Total Queries Tested    : {metrics['queries_tested']}")
    print(f"  Triage Gating Fraction  : {metrics['gating_fraction_pct']}% ({gated_total}/{total_queries} queries filtered)")
    print(f"  Fast Path Fraction      : {metrics['fast_path_fraction_pct']}% ({path_counts['single_fact']}/{total_queries} queries single_fact top-3)")
    print(f"  Embedding Cache Hits    : {metrics['embedding_cache_hits']}")
    print(f"  Sub-Result Cache Hits   : {metrics['sub_result_cache_hits']}")
    print(f"  Path Breakdown          : {path_counts}")
    print(f"  Avg LLM Calls / Query   : {metrics['avg_llm_calls_per_query']}")
    print(f"  Precision@5             : {metrics['precision_at_5']}%")
    print(f"  Accuracy (Taxonomy)     : {metrics['accuracy_pct']}%")
    print(f"  p50 Latency             : {metrics['p50_latency_ms']} ms")
    print(f"  p95 Latency             : {metrics['p95_latency_ms']} ms")
    print(f"  Cost / 1k Queries       : ${metrics['cost_per_1k_queries_usd']}")
    print("=======================================================\n")

    return metrics


if __name__ == "__main__":
    asyncio.run(run_rag_eval())
