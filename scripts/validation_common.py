"""Shared helpers for L1/L3 benchmark validation harness."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH = ROOT / "tests" / "ground_truth.json"
TIER1_PATHS = ROOT / "logs" / "benchmark_tier1_paths.json"

DEFAULT_VALIDATION_OLLAMA_TIMEOUT = "60"


def apply_validation_env() -> None:
    os.environ.setdefault("OLLAMA_TIMEOUT", DEFAULT_VALIDATION_OLLAMA_TIMEOUT)


def load_tier1_paths() -> Dict[str, str]:
    if not TIER1_PATHS.exists():
        return {}
    with open(TIER1_PATHS, encoding="utf-8") as f:
        data = json.load(f)
    return {k: str(v) for k, v in data.items() if v}


def resolve_pdf_path(case: Dict[str, Any], tier1_paths: Optional[Dict[str, str]] = None) -> Path:
    """Use benchmark_tier1_paths.json for tier1 rows when a better path exists."""
    rel = case["pdf_path"]
    path = ROOT / rel
    if case.get("doc_kind") != "tier1":
        return path
    tier1_paths = tier1_paths if tier1_paths is not None else load_tier1_paths()
    label = case.get("benchmark") or ""
    override = tier1_paths.get(label)
    if override:
        candidate = ROOT / override
        if candidate.exists():
            return candidate
    return path


def load_benchmark_cases() -> List[Dict[str, Any]]:
    with open(GROUND_TRUTH, encoding="utf-8") as f:
        gt = json.load(f)
    tier1_paths = load_tier1_paths()
    cases = []
    for case in gt.get("test_cases", []):
        rel = case["pdf_path"]
        parts = Path(rel).parts
        company = parts[2] if len(parts) >= 4 else parts[-2]
        resolved = resolve_pdf_path(case, tier1_paths)
        cases.append({
            "company": company,
            "benchmark": case.get("benchmark", company_label(company)),
            "doc_kind": case.get("doc_kind", "tier1"),
            "expect_exact_banks": case.get("expect_exact_banks", True),
            "pdf_rel": rel,
            "pdf_path": resolved,
            "expected": case.get("expected", {}),
        })
    return cases


def company_label(folder_name: str) -> str:
    if "AKER" in folder_name.upper():
        return "AKER"
    if folder_name.upper().startswith("TOTAL"):
        return "TotalEnergies"
    if folder_name.upper() == "OMV" or folder_name.upper().startswith("OMV"):
        return "OMV"
    return folder_name
