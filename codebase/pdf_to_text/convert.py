import argparse
import os
import sys
from pypdf import PdfReader

def convert_pdf_to_text(pdf_path: str, output_path: str = None) -> str:
    """
    Converts a PDF file to a plain text file.
    
    Args:
        pdf_path (str): Path to the input PDF file.
        output_path (str, optional): Path to the output text file. If None, saves to the same directory with .txt extension.
        
    Returns:
        str: The path to the generated text file.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Error: Input PDF file not found at '{pdf_path}'")
        
    if not pdf_path.lower().endswith('.pdf'):
        raise ValueError("Error: Input file must be a PDF (.pdf)")

    # If output path is not specified, create one in the same directory
    if not output_path:
        base_name = os.path.splitext(pdf_path)[0]
        output_path = f"{base_name}.txt"

    print(f"Reading PDF from: {pdf_path}")
    try:
        reader = PdfReader(pdf_path)
        
        # Check if the PDF is encrypted
        if reader.is_encrypted:
            print("Warning: PDF is encrypted. Attempting to decrypt with empty password...")
            try:
                reader.decrypt("")
            except Exception as e:
                raise ValueError(f"Error: PDF is encrypted and could not be decrypted: {e}")

        text_content = []
        total_pages = len(reader.pages)
        print(f"Total pages: {total_pages}")
        
        for i, page in enumerate(reader.pages):
            print(f"Extracting page {i + 1}/{total_pages}...", end="\r")
            page_text = page.extract_text()
            if page_text:
                text_content.append(f"--- PAGE {i + 1} ---\n{page_text}\n")
            else:
                text_content.append(f"--- PAGE {i + 1} ---\n[No extractable text found on this page]\n")
        
        print("\nExtraction complete. Writing to file...")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(text_content))
            
        print(f"Successfully converted! Saved text file to: {output_path}")
        return output_path
        
    except Exception as e:
        raise RuntimeError(f"Failed to parse PDF: {e}")

def main():
    parser = argparse.ArgumentParser(description="Convert PDF files to plain text.")
    parser.add_argument("pdf_path", help="Path to the PDF file to convert")
    parser.add_argument("-o", "--output", help="Path to save the output text file (optional)", default=None)
    
    args = parser.parse_args()
    
    try:
        convert_pdf_to_text(args.pdf_path, args.output)
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
