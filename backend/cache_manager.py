"""
Cache Manager
Intelligent caching system for PDF processing to avoid reprocessing unchanged files
"""

import os
import json
import hashlib
from typing import Dict, Optional, Set
from datetime import datetime
from .config import APP_CONFIG


class PDFCacheManager:
    """Manages caching of processed PDF content"""
    
    def __init__(self, data_folder: str = None, cache_folder: str = None):
        self.data_folder = data_folder or APP_CONFIG['data_folder']
        self.cache_folder = cache_folder or APP_CONFIG['cache_folder']
        self.cache_file = os.path.join(self.cache_folder, APP_CONFIG['cache_file'])
        
        # Ensure cache directory exists
        os.makedirs(self.cache_folder, exist_ok=True)
        
        # Load existing cache
        self.cache_data = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache data from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    # Validate cache structure
                    if isinstance(cache_data, dict) and 'files' in cache_data and 'metadata' in cache_data:
                        return cache_data
            except Exception as e:
                print(f"Warning: Could not load cache file: {e}")
        
        # Return empty cache structure
        return {
            'files': {},
            'metadata': {
                'created': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'version': '1.0'
            }
        }
    
    def _save_cache(self):
        """Save cache data to file"""
        try:
            self.cache_data['metadata']['last_updated'] = datetime.now().isoformat()
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save cache file: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """Generate hash for file content and metadata"""
        try:
            # Get file stats
            stat = os.stat(file_path)
            file_info = f"{stat.st_size}_{stat.st_mtime}"
            
            # For small files, include content hash for extra safety
            if stat.st_size < 1024 * 1024:  # Files smaller than 1MB
                with open(file_path, 'rb') as f:
                    content = f.read()
                    content_hash = hashlib.md5(content).hexdigest()
                    file_info += f"_{content_hash}"
            
            return hashlib.md5(file_info.encode()).hexdigest()
        except:
            return None
    
    def get_files_to_process(self) -> Dict[str, str]:
        """Get dictionary of files that need processing: {filename: filepath}"""
        if not os.path.exists(self.data_folder):
            return {}
        
        files_to_process = {}
        current_files = {}
        
        # Get all current files in data folder
        for filename in os.listdir(self.data_folder):
            if filename.lower().endswith(('.pdf', '.txt')):
                filepath = os.path.join(self.data_folder, filename)
                if os.path.isfile(filepath):
                    current_files[filename] = filepath
        
        # Check each current file
        for filename, filepath in current_files.items():
            file_hash = self._get_file_hash(filepath)
            cached_info = self.cache_data['files'].get(filename)
            
            # File needs processing if:
            # 1. Not in cache
            # 2. Hash doesn't match (file changed)
            # 3. Cached content is missing
            if (not cached_info or 
                cached_info.get('hash') != file_hash or 
                not cached_info.get('content')):
                files_to_process[filename] = filepath
        
        return files_to_process
    
    def get_cached_content(self, filename: str) -> Optional[str]:
        """Get cached content for a file"""
        cached_info = self.cache_data['files'].get(filename)
        if cached_info and cached_info.get('content'):
            return cached_info['content']
        return None
    
    def cache_file_content(self, filename: str, filepath: str, content: str, processing_info: Dict = None):
        """Cache processed content for a file with size limits"""
        
        # Limit content size to prevent memory issues
        max_content_size = 400_000  # 400KB per file (reduced from 500KB)
        original_size = len(content)
        if len(content) > max_content_size:
            content = content[:max_content_size] + "\n... [Content truncated for memory management]"
        
        file_hash = self._get_file_hash(filepath)
        if file_hash:
            cache_entry = {
                'hash': file_hash,
                'content': content,
                'filepath': filepath,
                'processed_at': datetime.now().isoformat(),
                'processing_info': processing_info or {}
            }
            
            # Add truncation info if content was truncated
            if original_size > max_content_size:
                cache_entry['processing_info']['truncated'] = True
                cache_entry['processing_info']['original_size'] = original_size
                cache_entry['processing_info']['cached_size'] = len(content)
            
            self.cache_data['files'][filename] = cache_entry
            self._save_cache()
    
    def remove_deleted_files(self):
        """Remove cache entries for files that no longer exist"""
        if not os.path.exists(self.data_folder):
            # If data folder doesn't exist, clear all cache
            self.cache_data['files'] = {}
            self._save_cache()
            return
        
        current_files = set()
        for filename in os.listdir(self.data_folder):
            if filename.lower().endswith(('.pdf', '.txt')):
                filepath = os.path.join(self.data_folder, filename)
                if os.path.isfile(filepath):
                    current_files.add(filename)
        
        # Remove cache entries for files that no longer exist
        cached_files = set(self.cache_data['files'].keys())
        deleted_files = cached_files - current_files
        
        if deleted_files:
            for filename in deleted_files:
                del self.cache_data['files'][filename]
            self._save_cache()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_cached = len(self.cache_data['files'])
        total_current = 0
        files_to_process = 0
        
        if os.path.exists(self.data_folder):
            current_files = [f for f in os.listdir(self.data_folder) 
                           if f.lower().endswith(('.pdf', '.txt'))]
            total_current = len(current_files)
            files_to_process = len(self.get_files_to_process())
        
        return {
            'total_cached_files': total_cached,
            'total_current_files': total_current,
            'files_needing_processing': files_to_process,
            'cache_hit_rate': ((total_current - files_to_process) / total_current * 100) if total_current > 0 else 0,
            'cache_file_size': os.path.getsize(self.cache_file) if os.path.exists(self.cache_file) else 0,
            'last_updated': self.cache_data['metadata'].get('last_updated', 'Never')
        }
    
    def clear_cache(self):
        """Clear all cache data"""
        self.cache_data = {
            'files': {},
            'metadata': {
                'created': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'version': '1.0'
            }
        }
        self._save_cache()
    
    def get_all_cached_content(self) -> Dict[str, str]:
        """Get all cached content as a dictionary"""
        content_dict = {}
        for filename, file_info in self.cache_data['files'].items():
            if file_info.get('content'):
                content_dict[filename] = file_info['content']
        return content_dict
