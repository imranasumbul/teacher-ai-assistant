"""
Text Extraction Module
Extracts text from PDF and .txt files
"""

from pypdf import PdfReader
import os


def extract_text(filepath):
    """
    Extract text from uploaded file (PDF or .txt)
    
    Args:
        filepath (str): Path to the uploaded file
        
    Returns:
        str: Extracted text content
        
    Raises:
        ValueError: If file type is not supported
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    
    # Get file extension
    file_ext = filepath.rsplit('.', 1)[1].lower()
    
    extracted_text = ""
    
    # Extract based on file type
    if file_ext == 'pdf':
        extracted_text = extract_from_pdf(filepath)
    elif file_ext == 'txt':
        extracted_text = extract_from_txt(filepath)
    else:
        raise ValueError(f"Unsupported file type: .{file_ext}")
    
    # Print extracted text to console
    print("\n" + "="*80)
    print(f"📄 TEXT EXTRACTED FROM: {os.path.basename(filepath)}")
    print("="*80)
    print(extracted_text[:500])  # Print first 500 characters
    if len(extracted_text) > 500:
        print(f"\n... (Total length: {len(extracted_text)} characters)")
    print("="*80 + "\n")
    
    return extracted_text


def extract_from_pdf(filepath):
    """
    Extract text from PDF file
    
    Args:
        filepath (str): Path to PDF file
        
    Returns:
        str: Extracted text from all pages
    """
    try:
        reader = PdfReader(filepath)
        text_parts = []
        
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        
        extracted_text = "\n\n".join(text_parts)
        
        print(f"   📑 PDF Pages: {len(reader.pages)}")
        print(f"   📝 Total Characters: {len(extracted_text)}")
        
        return extracted_text
    
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")


def extract_from_txt(filepath):
    """
    Extract text from .txt file
    
    Args:
        filepath (str): Path to .txt file
        
    Returns:
        str: File content
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        
        print(f"   📝 Total Characters: {len(text)}")
        
        return text
    
    except UnicodeDecodeError:
        # Try with different encoding if UTF-8 fails
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                text = f.read()
            print(f"   ⚠️  Used latin-1 encoding")
            print(f"   📝 Total Characters: {len(text)}")
            return text
        except Exception as e:
            raise Exception(f"Failed to read text file: {str(e)}")
    
    except Exception as e:
        raise Exception(f"Failed to extract text from file: {str(e)}")


if __name__ == "__main__":
    # Test the extractor with a sample file
    print("Text Extractor Module - Ready to use")
    print("Import this module in app.py to extract text from uploaded files")
