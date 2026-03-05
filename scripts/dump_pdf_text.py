"""Dump extracted text from a PDF to a .txt file for manual inspection."""
import sys
from pathlib import Path
# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
from processes.pdf_extraction.core import ExtractionEngine

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/dump_pdf_text.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    print(f"Extracting text from {pdf_path}...")
    engine = ExtractionEngine(use_ocr=True)
    text = engine.extract_text(pdf_path)
    
    out_path = Path(pdf_path).with_suffix('.extracted.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"Wrote {len(text)} characters to {out_path}")

if __name__ == "__main__":
    main()
