from processes.pdf_extractor import PDFExtractor
import json

def main():
    extractor = PDFExtractor()
    pdf_path = 'data/downloads/1732028111004_1732028109848_FC298561058_20241119_10978357.pdf'
    result = extractor.process_single_pdf(pdf_path)
    if result:
        print("\nExtracted Bank Information:")
        print(json.dumps(result['bank_info'], indent=2))
    else:
        print("No results found")

if __name__ == '__main__':
    main() 