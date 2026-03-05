"""
Extraction Quality Benchmark
----------------------------
Runs the full extraction pipeline on a set of known PDFs and compares
results against hand-curated ground truth.
"""
import json
import sys
import logging
from pathlib import Path
from processes.pdf_extractor import PDFExtractor

# Set up logging to be less noisy
logging.basicConfig(level=logging.ERROR)

GROUND_TRUTH_FILE = Path("tests/ground_truth.json")
TEMPLATE_FILE = Path("tests/ground_truth_template.json")

def load_ground_truth():
    if not GROUND_TRUTH_FILE.exists():
        if TEMPLATE_FILE.exists():
            print(f"ERROR: {GROUND_TRUTH_FILE} not found. Please copy {TEMPLATE_FILE} to {GROUND_TRUTH_FILE} and populate it.")
        else:
            print(f"ERROR: Ground truth file not found at {GROUND_TRUTH_FILE}")
        sys.exit(1)
        
    with open(GROUND_TRUTH_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_benchmark():
    extractor = PDFExtractor(debug_mode=False, use_ai_extraction=True)
    ground_truth = load_ground_truth()
    
    results = {"total": 0, "field_scores": {}}
    
    print(f"\nStarting Extraction Benchmark on {len(ground_truth['test_cases'])} cases...")
    
    for test_case in ground_truth["test_cases"]:
        pdf_path = test_case["pdf_path"]
        expected = test_case["expected"]
        
        if not Path(pdf_path).exists():
            print(f"SKIP: {pdf_path} not found")
            continue
        
        print(f"Processing {Path(pdf_path).name}...", end="", flush=True)
        actual = extractor.process_single_pdf(pdf_path)
        print(" Done.")
        
        results["total"] += 1
        
        # Compare each metadata field
        for field in ["issue_date", "maturity_date", "currency", "coupon_rate"]:
            expected_val = expected.get("metadata", {}).get(field)
            actual_val = actual.get("metadata", {}).get(field)
            
            key = f"metadata.{field}"
            if key not in results["field_scores"]:
                results["field_scores"][key] = {"correct": 0, "total": 0}
            
            if expected_val is not None:
                results["field_scores"][key]["total"] += 1
                if str(expected_val).lower() == str(actual_val).lower():
                    results["field_scores"][key]["correct"] += 1
        
        # Compare banks
        expected_banks = set(b.lower() for b in expected.get("banks", []))
        actual_banks_raw = actual.get("extracted_banks", [])
        actual_banks = set()
        for b in actual_banks_raw:
            if isinstance(b, dict):
                actual_banks.add(b.get("raw_name", "").lower())
            elif isinstance(b, str):
                actual_banks.add(b.lower())
        
        key = "banks"
        if key not in results["field_scores"]:
            results["field_scores"][key] = {"correct": 0, "total": 0}
        
        if expected_banks:
            results["field_scores"][key]["total"] += 1
            overlap = expected_banks & actual_banks
            # We count as correct if all expected banks are found
            if expected_banks.issubset(actual_banks):
                results["field_scores"][key]["correct"] += 1
            else:
                print(f"  BANK MISMATCH for {Path(pdf_path).name}:")
                print(f"    Missing: {expected_banks - actual_banks}")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"BENCHMARK RESULTS ({results['total']} PDFs tested)")
    print(f"{'='*60}")
    for field, scores in results["field_scores"].items():
        pct = (scores["correct"] / scores["total"] * 100) if scores["total"] > 0 else 0
        print(f"  {field:<15}: {scores['correct']}/{scores['total']} ({pct:.0f}%)")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    run_benchmark()
