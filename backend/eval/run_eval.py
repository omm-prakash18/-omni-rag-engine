"""
eval/run_eval.py — Offline Evaluation Harness for Contradiction Classifier Precision.

Evaluates the LangGraph 4-node pipeline against the hand-labeled eval_set.json.
Measures:
- Precision: % of detected contradictions matching expected taxonomy type
- Target Gate: >85% precision before Phase 2 unlock
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

# Set pure python protobuf implementation before importing any modules
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

# Reconfigure stdout for UTF-8 on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add parent backend dir to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.pipeline import run_omni_pipeline
from app.database import startup as db_startup
from app.services.ingestion import run_ingestion_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eval_harness")


async def run_evaluation():
    # 1. Startup DB & run ingestion pipeline to seed vector/graph stores
    await db_startup()
    print("Seeding vector store and event log with demo articles...")
    await run_ingestion_pipeline()

    eval_file = os.path.join(os.path.dirname(__file__), "eval_set.json")
    with open(eval_file, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    print("=" * 70)
    print("  OMNI-PERSPECTIVE ENGINE — CONTRADICTION CLASSIFIER EVALUATION")
    print("=" * 70)
    print(f"Total Eval Cases: {len(eval_cases)}\n")

    correct_type = 0
    total_evaluated = 0

    for case in eval_cases:
        cid = case["id"]
        query = case["query"]
        expected_type = case["expected_type"]

        print(f"[{cid}] Running Query: '{query}'")
        response = await run_omni_pipeline(query)

        detected = response.contradictions
        print(f"     Found {len(detected)} contradiction(s):")

        matched = False
        for c in detected:
            actual_type = c.contradiction_type.value
            print(f"       * Entity: {c.entity} | Type: {actual_type} | Confidence: {c.confidence:.2f}")
            print(f"         Reason: {c.reason}")
            if actual_type == expected_type:
                matched = True

        if matched or (not detected and expected_type == "none"):
            correct_type += 1
            print("     Result: [PASS] Matching Taxonomy Type")
        else:
            print(f"     Result: [MISMATCH] (Expected: {expected_type})")

        total_evaluated += 1
        print("-" * 70)

    precision = (correct_type / total_evaluated * 100) if total_evaluated > 0 else 0.0

    print("\n" + "=" * 70)
    print("  EVALUATION SUMMARY REPORT")
    print("=" * 70)
    print(f"  Total Cases Evaluated:   {total_evaluated}")
    print(f"  Taxonomy Matches:        {correct_type}")
    print(f"  Classifier Precision:    {precision:.1f}%")
    print(f"  Phase 1 Gate Target:     >85.0%")
    print(f"  Gate Status:             {'[PASSED] (Ready for Phase 2)' if precision >= 85.0 else '[BELOW GATE TARGET] (Refine classifier prompts)'}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
