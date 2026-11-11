from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, List, Dict, Sequence

# DeepEval Native Imports
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from deepeval.metrics import ContextualPrecisionMetric, ContextualRecallMetric

# Project Paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "evaluation" / "goldens" / "retriever_golden_dataset.json"
DEFAULT_REPORT = PROJECT_ROOT / "evaluation" / "results" / "retriever_report.json"

logger = logging.getLogger("evaluation.retriever")


@dataclass
class LocalUpload:
    """Streamlit-compatible file wrapper accepted by ingest_documents()."""
    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    def getvalue(self) -> bytes:
        return self.path.read_bytes()


class GeminiJudge(DeepEvalBaseLLM):
    """DeepEval LLM Judge wrapping the project's ChatGoogleGenerativeAI model with API key fallback."""

    def __init__(self, llm: Any, model_name: str = "gemini-3.5-flash-lite"):
        self.llm = llm
        self.model_name = model_name

    def load_model(self) -> Any:
        return self.llm

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(getattr(item, "text", item)))
            return "".join(parts)
        return str(content or "")

    def generate(self, prompt: str, schema: Any = None) -> Any:
        chain = self.llm.with_structured_output(schema) if schema else self.llm
        response = chain.invoke(prompt)
        raw = getattr(response, "content", response)
        return self._extract_text(raw) if not schema else raw

    async def a_generate(self, prompt: str, schema: Any = None) -> Any:
        chain = self.llm.with_structured_output(schema) if schema else self.llm
        response = await chain.ainvoke(prompt)
        raw = getattr(response, "content", response)
        return self._extract_text(raw) if not schema else raw

    def get_model_name(self) -> str:
        return self.model_name

OllamaJudge = GeminiJudge


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    """Load evaluation records from a JSON file."""
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records") if isinstance(data, dict) else data

    if not isinstance(records, list) or not records:
        raise ValueError(f"Dataset must contain a non-empty list of test records: {path}")

    # Validate required fields
    required = {"id", "query", "golden_context", "reference_answer"}
    for idx, r in enumerate(records):
        missing = required - set(r.keys())
        if missing:
            raise ValueError(f"Record #{idx} ({r.get('id', 'unknown')}) missing required fields: {missing}")

    return records


def evaluate_retriever(
    retriever: Any,
    records: List[Dict[str, Any]],
    judge_model: OllamaJudge,
    threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """Run queries through the retriever and score each using DeepEval metrics."""
    recall_metric = ContextualRecallMetric(threshold=threshold, model=judge_model)
    precision_metric = ContextualPrecisionMetric(threshold=threshold, model=judge_model)

    results = []
    total = len(records)

    for idx, record in enumerate(records, 1):
        query = record["query"]
        expected_answer = record["reference_answer"]
        logger.info(f"[{idx}/{total}] Evaluating: '{record['id']}' | Query: {query[:60]}...")

        # 1. Retrieve context chunks from retriever
        docs = retriever.invoke(query)
        retrieval_context = [doc.page_content for doc in docs if getattr(doc, "page_content", "").strip()]

        if not retrieval_context:
            logger.warning(f"No context retrieved for record '{record['id']}'.")

        # 2. Build DeepEval LLMTestCase
        test_case = LLMTestCase(
            input=query,
            actual_output=expected_answer,
            expected_output=expected_answer,
            retrieval_context=retrieval_context
        )

        # 3. Score with DeepEval metrics
        recall_metric.measure(test_case)
        precision_metric.measure(test_case)

        results.append({
            "id": record["id"],
            "paper": record.get("paper", "Unknown"),
            "query": query,
            "retrieved_context_count": len(retrieval_context),
            "retrieved_context": retrieval_context,
            "contextual_recall": {
                "score": float(recall_metric.score) if recall_metric.score is not None else 0.0,
                "reason": recall_metric.reason,
                "passed": bool(recall_metric.is_successful())
            },
            "contextual_precision": {
                "score": float(precision_metric.score) if precision_metric.score is not None else 0.0,
                "reason": precision_metric.reason,
                "passed": bool(precision_metric.is_successful())
            }
        })

    return results


def build_summary_report(
    dataset_path: Path,
    results: List[Dict[str, Any]],
    threshold: float
) -> Dict[str, Any]:
    """Compile overall metric scores, averages, and pass rate."""
    recalls = [r["contextual_recall"]["score"] for r in results]
    precisions = [r["contextual_precision"]["score"] for r in results]

    avg_recall = round(mean(recalls), 4) if recalls else 0.0
    avg_precision = round(mean(precisions), 4) if precisions else 0.0
    passed_cases = sum(
        1 for r in results
        if r["contextual_recall"]["passed"] and r["contextual_precision"]["passed"]
    )

    return {
        "dataset": str(dataset_path),
        "total_cases": len(results),
        "threshold": threshold,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "avg_contextual_recall": avg_recall,
            "avg_contextual_precision": avg_precision,
            "passed_cases": passed_cases,
            "pass_rate_percent": round((passed_cases / len(results)) * 100, 1) if results else 0.0
        },
        "results": results
    }


def print_cli_summary(summary_data: Dict[str, Any], threshold: float) -> None:
    """Print a clean CLI summary table of results."""
    s = summary_data["summary"]
    print("\n" + "=" * 70)
    print("DEEPEVAL RETRIEVER EVALUATION REPORT")
    print("=" * 70)
    print(f"Total Test Cases : {summary_data['total_cases']}")
    print(f"Target Threshold : {threshold}")
    print(f"Passed Cases     : {s['passed_cases']} / {summary_data['total_cases']} ({s['pass_rate_percent']}%)")
    print("-" * 70)
    print(f"Avg Contextual Recall    : {s['avg_contextual_recall']:.4f}  {'✅' if s['avg_contextual_recall'] >= threshold else '⚠️'}")
    print(f"Avg Contextual Precision : {s['avg_contextual_precision']:.4f}  {'✅' if s['avg_contextual_precision'] >= threshold else '⚠️'}")
    print("=" * 70 + "\n")


def start_mlflow_run(args: argparse.Namespace, records: Sequence[Dict[str, Any]]) -> Any:
    """Start a DagsHub MLflow run and log safe hybrid-retriever parameters."""
    if args.no_mlflow:
        return None
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env.rag", override=False)
    try:
        import mlflow
    except ImportError as exc:
        raise RuntimeError("MLflow is not installed. Install project requirements first: pip install -r requirements.txt") from exc

    tracking_uri = os.getenv("mlflow_tracking_uri") or os.getenv("MLFLOW_TRACKING_URI")
    repo_name = os.getenv("repo_name") or os.getenv("DAGSHUB_REPO_NAME")
    repo_owner = os.getenv("repo_owner") or os.getenv("DAGSHUB_REPO_OWNER")
    dagshub_token = os.getenv("dagshub_token") or os.getenv("DAGSHUB_TOKEN")
    if not all((tracking_uri, repo_name, repo_owner, dagshub_token)):
        raise RuntimeError(
            "MLflow configuration is incomplete. Expected mlflow_tracking_uri, repo_name, "
            "repo_owner, and dagshub_token in .env.rag."
        )

    # DagsHub accepts MLflow basic authentication. Never log the token.
    os.environ.setdefault("MLFLOW_TRACKING_USERNAME", repo_owner)
    os.environ.setdefault("MLFLOW_TRACKING_PASSWORD", dagshub_token)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(repo_name)
    run = mlflow.start_run(run_name=f"hybrid-retriever-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}")

    from backend.config import (CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_DIMENSION,
                                EMBEDDING_MODEL_NAME, RETRIEVER_K, QDRANT_COLLECTION_NAME)
    from backend.ingestion.retriever import configured_collection_name, indexing_signature

    params = {
        "retriever_type": "hybrid_rrf",
        "bm25_weight": 0.5,
        "semantic_weight": 0.5,
        "retriever_k": RETRIEVER_K,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "qdrant_collection": QDRANT_COLLECTION_NAME,
        "configured_collection": configured_collection_name(),
        "indexing_signature": indexing_signature(),
        "dataset": str(args.dataset.resolve()),
        "dataset_records": len(records),
        "metric_threshold": args.threshold,
    }
    mlflow.log_params({key: str(value) for key, value in params.items()})
    mlflow.set_tags({"repo_owner": repo_owner, "repo_name": repo_name, "evaluation": "retriever"})
    logger.info("MLflow run started in %s/%s.", repo_owner, repo_name)
    return mlflow


def log_mlflow_results(mlflow: Any, report: Dict[str, Any], report_path: Path) -> None:
    """Log aggregate scores and the full JSON report as an MLflow artifact."""
    summary = report["summary"]
    mlflow.log_metrics({
        "avg_contextual_recall": summary["avg_contextual_recall"],
        "avg_contextual_precision": summary["avg_contextual_precision"],
        "pass_rate_percent": summary["pass_rate_percent"],
        "passed_cases": summary["passed_cases"],
        "total_cases": report["total_cases"],
    })
    mlflow.log_artifact(str(report_path), artifact_path="reports")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG Retriever using DeepEval")
    parser.add_argument("--pdf", nargs="+", type=Path, required=True, help="PDF documents to index and evaluate")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help=f"Golden dataset path (default: {DEFAULT_DATASET})")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT, help=f"JSON report output path (default: {DEFAULT_REPORT})")
    parser.add_argument("--threshold", type=float, default=0.7, help="Metric pass threshold (default: 0.7)")
    parser.add_argument("--min-recall", type=float, default=None, help="CI gate minimum Contextual Recall")
    parser.add_argument("--min-precision", type=float, default=None, help="CI gate minimum Contextual Precision")
    parser.add_argument("--no-mlflow", action="store_true", help="Disable DagsHub MLflow tracking")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    # 1. Validate PDF inputs
    missing_pdfs = [str(p) for p in args.pdf if not p.is_file() or p.suffix.lower() != ".pdf"]
    if missing_pdfs:
        logger.error(f"Invalid or missing PDF files: {', '.join(missing_pdfs)}")
        return 2

    mlflow = None
    try:
        # 2. Load dataset
        records = load_dataset(args.dataset.resolve())
        logger.info(f"Loaded {len(records)} test records from: {args.dataset}")
        mlflow = start_mlflow_run(args, records)

        # 3. Ingest documents into Hybrid Retriever
        from backend.ingestion.pipeline import ingest_documents
        logger.info(f"Ingesting and indexing {len(args.pdf)} PDF(s)...")
        uploads = [LocalUpload(p.resolve()) for p in args.pdf]
        retriever, chunk_count = ingest_documents(uploads)
        logger.info(f"Successfully indexed documents into {chunk_count} chunks.")

        # 4. Initialize Ollama Judge model
        from backend.config import DEFAULT_LLM_MODEL, get_eval_llm
        judge_llm = get_eval_llm()
        judge = OllamaJudge(llm=judge_llm, model_name=DEFAULT_LLM_MODEL)

        # 5. Run DeepEval Evaluation
        logger.info("Running DeepEval contextual evaluation...")
        results = evaluate_retriever(
            retriever=retriever,
            records=records,
            judge_model=judge,
            threshold=args.threshold
        )

        # 6. Build and save report
        report = build_summary_report(args.dataset.resolve(), results, args.threshold)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        logger.info(f"Report saved to: {args.output}")
        if mlflow:
            log_mlflow_results(mlflow, report, args.output)
            logger.info("Logged hybrid retriever parameters, metrics, and report artifact to MLflow.")

        # 7. Print CLI Summary
        print_cli_summary(report, args.threshold)

        # 8. Check CI Gate thresholds
        summary = report["summary"]
        if args.min_recall is not None and summary["avg_contextual_recall"] < args.min_recall:
            logger.error(f"CI Gate Failed: Recall {summary['avg_contextual_recall']:.4f} < {args.min_recall:.4f}")
            return 1
        if args.min_precision is not None and summary["avg_contextual_precision"] < args.min_precision:
            logger.error(f"CI Gate Failed: Precision {summary['avg_contextual_precision']:.4f} < {args.min_precision:.4f}")
            return 1

        return 0

    except Exception as e:
        logger.error(f"Retriever evaluation failed: {e}")
        if mlflow:
            mlflow.set_tag("status", "failed")
        if args.verbose:
            logger.exception("Traceback:")
        return 2
    finally:
        if mlflow:
            mlflow.end_run()


if __name__ == "__main__":
    sys.exit(main())
