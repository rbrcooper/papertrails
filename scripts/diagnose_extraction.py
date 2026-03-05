
import json
from pathlib import Path
from processes.pdf_extractor import PDFExtractor

def diagnose():
    extractor = PDFExtractor(debug_mode=True, use_ai_extraction=True)
    with open("tests/ground_truth.json", "r", encoding="utf-8") as f:
        ground_truth = json.load(f)
    
    for case in ground_truth["test_cases"]:
        pdf_path = case["pdf_path"]
        expected = case["expected"]
        
        print(f"\n--- DIAGNOSING: {pdf_path} ---")
        if not Path(pdf_path).exists():
            print("FILE MISSING")
            continue
            
        actual = extractor.process_single_pdf(pdf_path)
        
        print("\nMETADATA COMPARISON:")
        for field in ["issue_date", "maturity_date", "currency", "coupon_rate"]:
            exp = expected["metadata"].get(field)
            act = actual["metadata"].get(field)
            status = "MATCH" if str(exp).lower() == str(act).lower() else "MISMATCH"
            print(f"  {field:<15} | Expected: {exp!r:<15} | Actual: {act!r:<15} | {status}")
            
        print("\nBANKS COMPARISON:")
        exp_banks = sorted([b.lower() for b in expected["banks"]])
        act_banks = sorted([b["raw_name"].lower() for b in actual.get("extracted_banks", [])])
        print(f"  Expected Count: {len(exp_banks)}")
        print(f"  Actual Count:   {len(act_banks)}")
        
        missing = [b for b in exp_banks if b not in act_banks]
        extra = [b for b in act_banks if b not in exp_banks]
        
        if missing:
            print(f"  MISSING: {missing}")
        if extra:
            print(f"  EXTRA:   {extra}")

if __name__ == "__main__":
    diagnose()
