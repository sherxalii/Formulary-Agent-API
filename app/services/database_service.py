import os
import shutil
import zipfile
import logging
import sqlite3
import json
from typing import List, Dict, Any, Optional, Tuple
from app.core.config import settings
from backend.formulary_drug_rag import FormularyDrugRAG
from app.services.rag_service import RagManager

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self, rag_manager: RagManager):
        self.rag_manager = rag_manager
        self.embedding_status = {}
        self._init_drugs_db()

    def _init_drugs_db(self):
        """Initialize the shared drugs metadata SQLite database."""
        conn = sqlite3.connect(settings.DRUGS_DB)
        try:
            conn.execute('''CREATE TABLE IF NOT EXISTS processed_drugs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_name TEXT,
                generic_name TEXT,
                therapeutic_class TEXT,
                dosage_form TEXT,
                strength TEXT,
                indication TEXT,
                plan_id TEXT,
                source_pdf TEXT,
                page_number INTEGER,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit()
        finally:
            conn.close()

    def get_pdf_path(self, filename: str) -> str:
        return str(settings.PDF_DIR / filename)

    def get_vectorstore_dir(self, filename: str) -> str:
        base = settings.DATABASE_DIR / os.path.splitext(filename)[0]
        base.mkdir(parents=True, exist_ok=True)
        return str(base)

    def allowed_file(self, filename: str) -> bool:
        return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

    async def list_pdfs(self) -> List[str]:
        if not settings.PDF_DIR.exists():
            return []
        return [f for f in os.listdir(settings.PDF_DIR) if f.lower().endswith('.pdf')]

    async def delete_database(self, filename: str) -> Tuple[List[str], List[str]]:
        deleted_items = []
        errors = []
        
        db_name = os.path.splitext(filename)[0]
        vectorstore_dir = settings.DATABASE_DIR / db_name
        pdf_path = settings.PDF_DIR / filename
        zip_path = str(vectorstore_dir) + ".zip"

        if vectorstore_dir.exists():
            shutil.rmtree(vectorstore_dir)
            deleted_items.append('embedding')
        else:
            errors.append('Embedding not found')

        if pdf_path.exists():
            os.remove(pdf_path)
            deleted_items.append('PDF file')
        else:
            errors.append('PDF file not found')

        if os.path.exists(zip_path):
            os.remove(zip_path)
            deleted_items.append('embedding zip file')

        if filename in self.embedding_status:
            del self.embedding_status[filename]
            deleted_items.append('embedding status')
            
        # Clean up related records in drugs.db
        try:
            conn = sqlite3.connect(settings.DRUGS_DB)
            conn.execute("DELETE FROM processed_drugs WHERE plan_id = ?", (db_name,))
            conn.commit()
            conn.close()
            deleted_items.append('metadata records')
        except Exception:
            pass

        return deleted_items, errors

    def embed_pdf_sync(self, filename: str):
        """Background task for embedding a PDF with advanced metadata extraction."""
        self.embedding_status[filename] = 'processing'
        try:
            pdf_path = self.get_pdf_path(filename)
            db_name = os.path.splitext(filename)[0]
            vectorstore_dir = self.get_vectorstore_dir(filename)
            
            rag = FormularyDrugRAG(
                openai_api_key=settings.OPENAI_API_KEY,
                chroma_persist_directory=vectorstore_dir,
                model_name=settings.OPENAI_MODEL_NAME,
                embedding_model=settings.OPENAI_EMBEDDING_MODEL,
                enable_ai_enhancement=True,
                enable_llm_prevalidation=True,
                auto_cleanup=True
            )
            
            # Check if already processed (but always ensure drugs are cached)
            is_existing = rag.load_existing_vectorstore()
            
            if not is_existing:
                # Start embedding
                documents = rag.load_formulary_documents([pdf_path])
                
                # Legacy hook for metadata extraction (using GPT)
                rag.create_vectorstore(documents)
                rag.setup_rag_chain()
            
            # Extract and cache drugs to SQLite for fast retrieval (ALWAYS do this to ensure DB is in sync)
            self._cache_drugs_to_db(rag, db_name, filename)
            
            self.embedding_status[filename] = 'done'
        except Exception as e:
            logger.error(f"Embedding failed for {filename}: {e}")
            self.embedding_status[filename] = f'error: {str(e)}'

    def _cache_drugs_to_db(self, rag: FormularyDrugRAG, plan_id: str, filename: str):
        """Extract drugs from vectorstore and cache in SQLite."""
        try:
            # use RAG internal method or direct chroma access
            drugs = rag.extract_unique_medicine_entries_from_vectorstore()
            if not drugs:
                logger.warning(f"No drugs extracted from {filename}")
                return

            conn = sqlite3.connect(settings.DRUGS_DB)
            # Clear existing drugs for this plan to avoid duplicates
            conn.execute("DELETE FROM processed_drugs WHERE plan_id = ?", (plan_id,))
            
            for drug in drugs:
                conn.execute('''
                    INSERT INTO processed_drugs (drug_name, generic_name, therapeutic_class, dosage_form, strength, plan_id, source_pdf)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    drug.get('drug_name'),
                    drug.get('generic_name'),
                    drug.get('therapeutic_class'),
                    drug.get('dosage_form'),
                    drug.get('strength'),
                    plan_id,
                    filename
                ))
            conn.commit()
            conn.close()
            logger.info(f"Successfully cached {len(drugs)} drugs from {filename}")
        except Exception as e:
            logger.error(f"Failed to cache drugs to SQLite: {e}")

    def get_status(self, filename: str) -> str:
        return self.embedding_status.get(filename, "not_found")

    async def get_database_stats(self, database_id: str) -> Dict[str, Any]:
        """Fetch drug count and generic percentage using optimized SQL queries."""
        conn = sqlite3.connect(settings.DRUGS_DB)
        cursor = conn.cursor()
        try:
            # Get total count
            cursor.execute('SELECT COUNT(*) FROM processed_drugs WHERE plan_id = ?', (database_id,))
            drug_count = cursor.fetchone()[0]
            
            # Get generic count
            cursor.execute('''
                SELECT COUNT(*) FROM processed_drugs 
                WHERE plan_id = ? 
                AND LOWER(TRIM(drug_name)) = LOWER(TRIM(generic_name))
            ''', (database_id,))
            generic_count = cursor.fetchone()[0]
            
            generic_percent = (generic_count / drug_count * 100) if drug_count > 0 else 0.0
            
            return {
                'drugCount': drug_count,
                'genericPercent': round(generic_percent, 1)
            }
        except Exception as e:
            logger.error(f"Error fetching database stats: {e}")
            return {'drugCount': 0, 'genericPercent': 0.0}
        finally:
            conn.close()

    async def search_drugs(self, query: str) -> List[Dict[str, Any]]:
        """Search for drugs across all plan formularies."""
        conn = sqlite3.connect(settings.DRUGS_DB)
        cursor = conn.cursor()
        try:
            pattern = f"%{query}%"
            cursor.execute('''
                SELECT DISTINCT drug_name, generic_name, therapeutic_class, strength, dosage_form
                FROM processed_drugs 
                WHERE drug_name LIKE ? OR generic_name LIKE ?
                LIMIT 10
            ''', (pattern, pattern))
            rows = cursor.fetchall()
            return [{
                'name': r[0],
                'genericName': r[1],
                'class': r[2],
                'strength': r[3],
                'form': r[4],
                'availability': 'Formulary'
            } for r in rows]
        except Exception as e:
            logger.error(f"Drug search failed: {e}")
            return []
        finally:
            conn.close()

    async def get_drugs(self, database_id: str) -> List[Dict[str, Any]]:
        """Fetch drugs from SQLite (faster) or fallback to ChromaDB."""
        conn = sqlite3.connect(settings.DRUGS_DB)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, drug_name, generic_name, therapeutic_class, strength, dosage_form 
                FROM processed_drugs WHERE plan_id = ?
            ''', (database_id,))
            rows = cursor.fetchall()
            if rows:
                return [{
                    'id': r[0],
                    'name': r[1],
                    'genericName': r[2],
                    'class': r[3],
                    'strength': r[4],
                    'form': r[5],
                    'availability': 'Formulary'
                } for r in rows]
        except Exception:
            pass
        finally:
            conn.close()
            
        # Fallback to direct ChromaDB extraction if SQLite is empty
        return await self._extract_from_chroma(database_id)

    async def _extract_from_chroma(self, database_id: str) -> List[Dict[str, Any]]:
        """Legacy ChromaDB extraction fallback."""
        vectorstore_path = settings.DATABASE_DIR / database_id
        if not vectorstore_path.exists():
            return []
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(vectorstore_path))
            collections = client.list_collections()
            if not collections: return []
            collection = client.get_collection(collections[0].name)
            results = collection.get(limit=5000)
            seen = set()
            drugs = []
            for metadata in results.get('metadatas', []):
                name = metadata.get('drug_name') or metadata.get('medicine_name')
                if name and name not in seen:
                    seen.add(name)
                    drugs.append({
                        'id': len(drugs) + 1,
                        'name': name,
                        'genericName': metadata.get('generic_name', ''),
                        'class': metadata.get('therapeutic_class', ''),
                        'strength': metadata.get('strength', ''),
                        'form': metadata.get('dosage_form', ''),
                        'availability': 'Formulary'
                    })
            return drugs
        except Exception:
            return []

    async def download_embedding(self, database_id: str) -> Optional[str]:
        """Create a ZIP of the vectorstore for download."""
        source_dir = settings.DATABASE_DIR / database_id
        if not source_dir.exists():
            return None
        
        zip_path = str(source_dir) + ".zip"
        if os.path.exists(zip_path):
            # Refresh if older than 1 hour or always refresh?
            # Legacy behavior: just serve it
            return zip_path

        shutil.make_archive(str(source_dir), 'zip', source_dir)
        return zip_path

    async def cleanup_database(self, database_id: str) -> Dict[str, Any]:
        """Manually trigger RAG cleanup of invalid entries."""
        rag = self.rag_manager.get_instance(database_id)
        if not rag:
            # try finding it path-wise
            path = settings.DATABASE_DIR / database_id
            if path.exists():
                rag = self.rag_manager.get_or_create_instance(database_id, str(path))
        
        if not rag:
            return {'success': False, 'error': 'Database not found'}
            
        results = rag.cleanup_database_invalid_entries()
        return {'success': True, 'cleanup_results': results}
