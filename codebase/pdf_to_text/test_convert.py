import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys

# Add current directory to path to import convert
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from convert import convert_pdf_to_text

class TestPdfToText(unittest.TestCase):
    
    @patch('os.path.exists')
    def test_file_not_found(self, mock_exists):
        # Test that FileNotFoundError is raised if the input PDF doesn't exist
        mock_exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            convert_pdf_to_text("non_existent_file.pdf")
            
    @patch('os.path.exists')
    def test_invalid_extension(self, mock_exists):
        # Test that ValueError is raised if the file is not a PDF
        mock_exists.return_value = True
        with self.assertRaises(ValueError):
            convert_pdf_to_text("invalid_file.txt")

    @patch('os.path.exists')
    @patch('convert.PdfReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_successful_conversion(self, mock_file, mock_pdf_reader, mock_exists):
        mock_exists.return_value = True
        
        # Mock PdfReader and pages
        mock_reader_instance = MagicMock()
        mock_reader_instance.is_encrypted = False
        
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Hello World on Page 1"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "This is Page 2"
        
        mock_reader_instance.pages = [mock_page1, mock_page2]
        mock_pdf_reader.return_value = mock_reader_instance
        
        # Run conversion
        output_path = convert_pdf_to_text("sample.pdf", "output.txt")
        
        # Assertions
        self.assertEqual(output_path, "output.txt")
        mock_file.assert_called_once_with("output.txt", "w", encoding="utf-8")
        
        # Check written content
        handle = mock_file()
        written_content = "".join(call[0][0] for call in handle.write.call_args_list)
        self.assertIn("Hello World on Page 1", written_content)
        self.assertIn("This is Page 2", written_content)

if __name__ == "__main__":
    unittest.main()
