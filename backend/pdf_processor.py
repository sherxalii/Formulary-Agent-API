"""
PDF Processor
Enhanced PDF processor with OCR and multiple extraction methods
"""

import os
from typing import List, Dict
from .config import (
    PDF_AVAILABLE, PDFPLUMBER_AVAILABLE, OCR_AVAILABLE, 
    APP_CONFIG
)
from .medical_processor import MedicalTextProcessor
from .cache_manager import PDFCacheManager

if PDF_AVAILABLE:
    import PyPDF2

if PDFPLUMBER_AVAILABLE:
    import pdfplumber

if OCR_AVAILABLE:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image


class EnhancedPDFProcessor:
    """Enhanced PDF processor with OCR and multiple extraction methods"""
    
    def __init__(self, data_folder: str = None, progress_callback=None):
        self.data_folder = data_folder or APP_CONFIG['data_folder']
        self.pdf_contents = {}
        self.medical_processor = MedicalTextProcessor()
        self.cache_manager = PDFCacheManager(self.data_folder)
        self.progress_callback = progress_callback
        self._processing_complete = False
        self.load_pdfs()
    
    def load_pdfs(self):
        """Load and extract text from PDFs using intelligent caching"""
        if self._processing_complete:
            return
            
        if not os.path.exists(self.data_folder):
            print(f"Data folder '{self.data_folder}' not found!")
            return
        
        # Clean up cache for deleted files
        self.cache_manager.remove_deleted_files()
        
        # Get cache statistics
        cache_stats = self.cache_manager.get_cache_stats()
        
        # Load cached content first
        cached_content = self.cache_manager.get_all_cached_content()
        self.pdf_contents.update(cached_content)
        
        # Get files that need processing
        files_to_process = self.cache_manager.get_files_to_process()
        
        if not files_to_process and not cached_content:
            print(f"No PDF or text files found in '{self.data_folder}' folder!")
            return
        
        # Show cache performance info
        # if cache_stats['total_current_files'] > 0:
        #     if self.progress_callback:
        #         if cache_stats['files_needing_processing'] == 0:
        #             self.progress_callback(70, f"✅ All {cache_stats['total_current_files']} files loaded from cache (100% cache hit)")
        #         else:
        #             self.progress_callback(15, f"📋 Loaded {cache_stats['total_current_files'] - cache_stats['files_needing_processing']} files from cache, processing {cache_stats['files_needing_processing']} new/changed files")
        
        if not files_to_process:
            # All files are cached, we're done
            self._processing_complete = True
            return
        
        # Process only new/changed files
        successful_files = []
        failed_files = []
        partial_files = []
        total_files_to_process = len(files_to_process)
        
        for idx, (filename, filepath) in enumerate(files_to_process.items(), 1):
            # Update progress if callback provided
            if self.progress_callback:
                base_progress = 15 if cache_stats['total_current_files'] > len(files_to_process) else 10
                progress_percent = base_progress + (55 * idx / total_files_to_process)
                self.progress_callback(int(progress_percent), f"📄 Processing new file {idx}/{total_files_to_process}: {filename}")
            
            try:
                if filename.lower().endswith('.txt'):
                    # Handle text files
                    with open(filepath, 'r', encoding='utf-8') as file:
                        text = file.read()
                        text = self.medical_processor.clean_text(text)
                        self.pdf_contents[filename] = text
                        
                        # Cache the processed content
                        self.cache_manager.cache_file_content(
                            filename, filepath, text, 
                            {'method': 'text_file', 'success': True}
                        )
                        successful_files.append(filename)
                        
                elif filename.lower().endswith('.pdf'):
                    # Handle PDF files with enhanced multiple methods
                    pdf_result = self._process_pdf_with_multiple_methods(filepath, filename)
                    if pdf_result['success']:
                        self.pdf_contents[filename] = pdf_result['text']
                        
                        # Cache the processed content
                        self.cache_manager.cache_file_content(
                            filename, filepath, pdf_result['text'],
                            {
                                'method': pdf_result.get('method', 'unknown'),
                                'success': True,
                                'quality_score': pdf_result.get('quality_score', 0),
                                'partial': pdf_result.get('partial', False)
                            }
                        )
                        
                        if pdf_result.get('partial', False):
                            partial_files.append(filename)
                        else:
                            successful_files.append(filename)
                    else:
                        failed_files.append(filename)
                    
            except Exception as e:
                failed_files.append(f"{filename} (Access error)")
                continue
        
        # Display clean summary to user
        self._display_processing_summary(successful_files, partial_files, failed_files)
        self._processing_complete = True
    
    def _process_pdf_with_multiple_methods(self, file_path: str, file_name: str) -> dict:
        """Use multiple extraction methods for maximum accuracy with memory management"""
        extraction_results = []
        
        # Add file size check to prevent memory issues
        try:
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                return {
                    'success': False, 
                    'text': '', 
                    'method': 'file_too_large',
                    'error': f'File too large: {file_size / (1024*1024):.1f}MB. Maximum 50MB allowed.'
                }
        except:
            pass  # Continue if we can't get file size
        
        # Method 1: pdfplumber (best for tables and structured data)
        if PDFPLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(file_path) as pdf:
                    text = ""
                    # Limit pages to prevent memory overflow
                    max_pages = min(len(pdf.pages), 100)  # Limit to 100 pages
                    for page_num in range(max_pages):
                        if page_num < len(pdf.pages):
                            page_text = pdf.pages[page_num].extract_text()
                            if page_text:
                                text += page_text + "\n"
                        
                        # Check text size to prevent memory issues
                        if len(text) > 800_000:  # 800KB text limit (reduced from 1MB)
                            break
                    
                    if text.strip():
                        extraction_results.append({
                            'method': 'pdfplumber',
                            'text': text,
                            'quality': len(text.split())
                        })
            except:
                pass
        
        # Method 2: PyPDF2 (fallback)
        if PDF_AVAILABLE:
            try:
                pdf_result = self._process_pdf_silently(file_path, file_name)
                if pdf_result['success']:
                    extraction_results.append({
                        'method': 'PyPDF2',
                        'text': pdf_result['text'],
                        'quality': len(pdf_result['text'].split())
                    })
            except:
                pass
        
        # Method 3: OCR for scanned PDFs
        if OCR_AVAILABLE:
            try:
                ocr_text = self._extract_with_ocr(file_path)
                if ocr_text and len(ocr_text.strip()) > 100:
                    extraction_results.append({
                        'method': 'OCR',
                        'text': ocr_text,
                        'quality': len(ocr_text.split())
                    })
            except:
                pass
        
        # Choose best extraction result
        if extraction_results:
            best_result = max(extraction_results, key=lambda x: x['quality'])
            return {
                'success': True,
                'text': self.medical_processor.clean_text(best_result['text']),
                'method': best_result['method'],
                'quality_score': best_result['quality']
            }
        
        return {'success': False, 'text': '', 'method': 'none'}
    
    def _extract_with_ocr(self, file_path: str) -> str:
        """Extract text using OCR for scanned PDFs with memory management"""
        try:
            # Check file size before OCR processing (OCR is very memory intensive)
            file_size = os.path.getsize(file_path)
            if file_size > 20 * 1024 * 1024:  # 20MB limit for OCR
                return ""
            
            # Convert PDF to images with memory-conscious settings
            images = convert_from_path(file_path, dpi=200, first_page=1, last_page=20)  # Limit to 20 pages, reduced DPI
            
            extracted_text = ""
            for i, image in enumerate(images):
                # Use OCR to extract text
                text = pytesseract.image_to_string(image, config='--psm 6')
                extracted_text += text + "\n"
                
                # Limit total extracted text to prevent memory issues
                if len(extracted_text) > 400_000:  # 400KB limit (reduced from 500KB)
                    break
            
            return extracted_text
        except:
            return ""
    
    def _process_pdf_silently(self, file_path: str, file_name: str) -> dict:
        """Process PDF with silent error handling, return success status and text"""
        try:
            with open(file_path, 'rb') as file:
                # Try multiple PDF reading strategies
                strategies = [
                    {'strict': False, 'name': 'Lenient'},
                    {'strict': True, 'name': 'Strict'}
                ]
                
                for strategy in strategies:
                    try:
                        file.seek(0)
                        pdf_reader = PyPDF2.PdfReader(file, strict=strategy['strict'])
                        
                        # Safely get page count
                        try:
                            page_count_total = len(pdf_reader.pages)
                        except:
                            continue
                        
                        if page_count_total == 0:
                            continue
                        
                        text = ""
                        pages_read = 0
                        max_pages_to_read = min(page_count_total, 150)  # Limit to 150 pages max
                        
                        # Process pages with silent error handling
                        for page_num in range(max_pages_to_read):
                            try:
                                if page_num < len(pdf_reader.pages):
                                    page_text = self._extract_page_text_silently(pdf_reader.pages[page_num])
                                    if page_text:
                                        text += page_text + "\n"
                                        pages_read += 1
                                    
                                    # Check text size to prevent memory issues
                                    if len(text) > 800_000:  # 800KB text limit
                                        break
                            except:
                                continue
                        
                        # Check if we got meaningful content
                        if text.strip() and len(text.strip()) > 50:
                            text = self.medical_processor.clean_text(text)
                            
                            success_rate = (pages_read / page_count_total) * 100
                            is_partial = success_rate < 90
                            
                            return {
                                'success': True,
                                'text': text,
                                'partial': is_partial,
                                'pages_read': pages_read,
                                'total_pages': page_count_total
                            }
                    
                    except:
                        continue
                
                # If all strategies failed
                return {'success': False, 'text': '', 'partial': False}
                
        except:
            return {'success': False, 'text': '', 'partial': False}
    
    def _extract_page_text_silently(self, page) -> str:
        """Extract text from a page using multiple methods silently"""
        extraction_methods = [
            lambda p: p.extract_text(),
            lambda p: p.extract_text(extraction_mode="layout") if hasattr(p, 'extract_text') else None,
            lambda p: str(p.extract_text()) if hasattr(p, 'extract_text') else None
        ]
        
        for method in extraction_methods:
            try:
                text = method(page)
                if text and text.strip():
                    return text
            except:
                continue
        
        return ""
    
    def _display_processing_summary(self, successful: list, partial: list, failed: list):
        """Display a clean summary of file processing results with cache information"""
        # Only display if we haven't shown this before
        summary_shown = getattr(self, '_summary_shown', False)
        if summary_shown:
            return
            
        # Get cache statistics for display
        cache_stats = self.cache_manager.get_cache_stats()
        total_current_files = cache_stats['total_current_files']
        cached_files = total_current_files - len(successful) - len(partial) - len(failed)

        if partial:
            print(f"Processed {len(partial)} new files with partial content (some pages may contain images)")
        
        if failed and len(successful + partial) == 0 and cached_files == 0:
            print(f"Could not process any files. Please ensure PDFs contain readable text.")
        elif failed:
            print(f" {len(failed)} files could not be processed (may contain only images or be corrupted)")
        
        # Show cache performance
        if total_current_files > 0:
            cache_hit_rate = cache_stats['cache_hit_rate']

        total_available = len(self.pdf_contents)
        
        # Mark summary as shown
        self._summary_shown = True
    
    def get_available_pdfs(self) -> List[str]:
        """Get list of available PDF files"""
        return list(self.pdf_contents.keys())
    
    def get_pdf_content(self, pdf_name: str) -> str:
        """Get content of a specific PDF"""
        return self.pdf_contents.get(pdf_name, "")
    
    def get_all_contents(self) -> Dict[str, str]:
        """Get all PDF contents"""
        return self.pdf_contents.copy()
    
    def clear_cache(self):
        """Clear all cached content - useful for debugging or forcing reprocessing"""
        self.cache_manager.clear_cache()
        self.pdf_contents.clear()
        self._processing_complete = False
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics for debugging/monitoring"""
        return self.cache_manager.get_cache_stats()
