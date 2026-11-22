"""Run the development retrieval evaluation and write inspectable artifacts."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from retrieval.dev_retriever import DevelopmentRetriever
DATASET = ROOT / "retrieval" / "evaluation_dataset.json"
CHUNKS = ROOT / "data" / "dev_extracted" / "charaka_vanloon_volume1_dev_chunks.json"
REPORT = ROOT / "docs" / "source_inspection" / "charaka_retrieval_evaluation_report.md"
RATINGS = ROOT / "retrieval" / "manual_ratings.json"


def inspect_chunks(chunks: list[dict]) -> dict:
    short = [c for c in chunks if len(c.get("text", "")) < 100]
    heading_like = [c for c in chunks if len(c.get("text", "").strip()) < 100 or not any(ch.isalpha() for ch in c.get("text", ""))]
    missing_page = [c for c in chunks if not c.get("metadata", {}).get("page_number")]
    unknown = [c for c in chunks if c.get("metadata", {}).get("provenance_role") == "unknown"]
    by_text = Counter(c.get("text", "").strip() for c in chunks)
    duplicates = {text: count for text, count in by_text.items() if text and count > 1}
    return {"total": len(chunks), "short_under_100": len(short), "short_ids": [c["id"] for c in short[:100]],
            "heading_or_page_like": len(heading_like), "missing_page_metadata": len(missing_page),
            "unknown_provenance": len(unknown), "exact_duplicate_groups": len(duplicates),
            "duplicate_examples": [{"text": text[:180], "count": count} for text, count in list(duplicates.items())[:20]],
            "provenance_counts": dict(Counter(c.get("metadata", {}).get("provenance_role", "missing") for c in chunks))}


def evaluate(*, top_k: int = 5, abstention_distance: float | None = None, judgments: dict | None = None) -> tuple[list[dict], dict]:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    retriever = DevelopmentRetriever()
    results = []
    for item in dataset:
        hits = retriever.search(item["query"], top_k=top_k, provenance=item.get("provenance_filter"))
        top = hits[0] if hits else None
        abstained = bool(top and abstention_distance is not None and top["distance"] > abstention_distance)
        results.append({"id": item["id"], "query": item["query"], "expected_topic": item["expected_topic"],
                        "expected_provenance": item["expected_provenance"], "provenance_filter": item.get("provenance_filter"),
                        "hits": hits, "actual_provenance": [h["metadata"].get("provenance_role") for h in hits],
                        "provenance_matches": [h["metadata"].get("provenance_role") == item["expected_provenance"] for h in hits],
                        "top_result": {"distance": top["distance"], "similarity": top["cosine_similarity"], "abstained": abstained} if top else None})
    metrics = {"recall_at_5": None, "mrr": None, "judgments_supplied": bool(judgments)}
    if judgments:
        recalls, reciprocal = [], []
        for row in results:
            relevant = set(judgments.get(row["id"], []))
            ranks = [hit["rank"] for hit in row["hits"] if hit["id"] in relevant]
            recalls.append(bool(ranks)); reciprocal.append(1 / min(ranks) if ranks else 0.0)
        metrics["recall_at_5"] = sum(recalls) / len(recalls) if recalls else 0.0
        metrics["mrr"] = sum(reciprocal) / len(reciprocal) if reciprocal else 0.0
    return results, metrics


def write_report(results: list[dict], metrics: dict, chunk_quality: dict, *, abstention_distance: float | None) -> None:
    lines = ["# Charaka development retrieval evaluation", "", "This report evaluates only `data/dev_chroma/charaka_vanloon_dev`. Production collections were not opened or modified.", "",
             f"- Query count: {len(results)}", f"- Top-k: {len(results[0]['hits']) if results else 0}", f"- Provenance filters: per-query dataset values",
             f"- Experimental abstention distance threshold: `{abstention_distance if abstention_distance is not None else 'disabled'}`",
             f"- Recall@5: `{metrics['recall_at_5'] if metrics['recall_at_5'] is not None else 'not calculated (no explicit judgments)'}`",
             f"- MRR: `{metrics['mrr'] if metrics['mrr'] is not None else 'not calculated (no explicit judgments)'}`", ""]
    lines += ["## Query results", "", "Distances are Chroma cosine distances (lower is closer); similarity is reported as `1 - distance`. Results are inspectable below and are not medical conclusions.", ""]
    for row in results:
        lines += [f"### {row['id']}: {row['query']}", f"Expected topic: {row['expected_topic']} | Expected provenance: `{row['expected_provenance']}` | Filter: `{row['provenance_filter']}`", ""]
        for hit in row["hits"]:
            md = hit["metadata"]
            excerpt = " ".join(hit["text"].split())[:240].replace("|", "\\|")
            lines.append(f"{hit['rank']}. `{hit['id']}` - distance `{hit['distance']:.5f}`, similarity `{hit['cosine_similarity']:.5f}`, page `{md.get('pdf_page', md.get('page_number'))}`, chapter `{md.get('chapter_reference')}`, provenance `{md.get('provenance_role')}`, expected-provenance-match `{md.get('provenance_role') == row['expected_provenance']}` - {excerpt}")
        if row["top_result"]:
            lines.append(f"Top-result abstention: `{row['top_result']['abstained']}` (distance `{row['top_result']['distance']:.5f}`, similarity `{row['top_result']['similarity']:.5f}`).")
        lines.append("")
    lines += ["## Chunk-quality findings", "", f"- Total chunks: {chunk_quality['total']}", f"- Under 100 characters: {chunk_quality['short_under_100']}", f"- Heading/page-like: {chunk_quality['heading_or_page_like']}", f"- Missing page metadata: {chunk_quality['missing_page_metadata']}", f"- Unknown provenance: {chunk_quality['unknown_provenance']}", f"- Exact duplicate groups: {chunk_quality['exact_duplicate_groups']}", "", "Short, unknown, editorial-note, and broken-boundary examples are retained in evaluation_results.json for manual inspection. Do not delete or rewrite indexed records.", "", "Abstention thresholds are experimental and corpus/model-specific. A distance threshold can cause false positives (abstaining from a relevant result) and false negatives (returning an unrelated result that happens to be close). It must not be treated as a universal confidence measure.", "", "Recall@5 and MRR require explicit human relevance labels and are not reported for this run.", ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--abstention-distance", type=float, default=None, help="Experimental cosine-distance threshold; abstain when top distance exceeds it.")
    args = parser.parse_args()
    chunks = json.loads(CHUNKS.read_text(encoding="utf-8"))
    results, metrics = evaluate(top_k=args.top_k, abstention_distance=args.abstention_distance)
    quality = inspect_chunks(chunks)
    output = ROOT / "retrieval" / "evaluation_results.json"
    output.write_text(json.dumps({"metrics": metrics, "chunk_quality": quality, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    manual = [{"query_id": row["id"], "query": row["query"], "results": [{"rank": h["rank"], "chunk_id": h["id"], "rating": None, "rating_scale": "0=irrelevant, 1=partially relevant, 2=directly relevant", "notes": ""} for h in row["hits"]]} for row in results]
    RATINGS.write_text(json.dumps(manual, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(results, metrics, quality, abstention_distance=args.abstention_distance)
    print(json.dumps({"metrics": metrics, "chunk_quality": quality, "results_path": str(output), "report_path": str(REPORT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
