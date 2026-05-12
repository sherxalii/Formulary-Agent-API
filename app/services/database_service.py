import os
import shutil
import zipfile
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from app.core.config import settings
from backend.formulary_drug_rag import FormularyDrugRAG
from app.services.rag_service import RagManager
from app.core.database import engine
from app.models.drug import ProcessedDrug
from sqlmodel import select, delete, Session, func, or_

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self, rag_manager: RagManager):
        self.rag_manager = rag_manager
        self.embedding_status = {}
        # SQLModel handles table creation via init_db() in main.py

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
            
        # Clean up related records in SQLModel DB
        try:
            with Session(engine) as session:
                statement = delete(ProcessedDrug).where(ProcessedDrug.plan_id == db_name)
                session.exec(statement)
                session.commit()
            deleted_items.append('metadata records')
        except Exception as e:
            logger.error(f"Failed to delete metadata: {e}")
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

            with Session(engine) as session:
                # Clear existing drugs for this plan to avoid duplicates
                statement = delete(ProcessedDrug).where(ProcessedDrug.plan_id == plan_id)
                session.exec(statement)
                
                for drug in drugs:
                    processed_drug = ProcessedDrug(
                        drug_name=drug.get('drug_name'),
                        generic_name=drug.get('generic_name'),
                        therapeutic_class=drug.get('therapeutic_class'),
                        dosage_form=drug.get('dosage_form'),
                        strength=drug.get('strength'),
                        plan_id=plan_id,
                        source_pdf=filename
                    )
                    session.add(processed_drug)
                session.commit()
            logger.info(f"Successfully cached {len(drugs)} drugs from {filename}")
        except Exception as e:
            logger.error(f"Failed to cache drugs to SQLModel: {e}")

    def get_status(self, filename: str) -> str:
        return self.embedding_status.get(filename, "not_found")

    async def get_database_stats(self, database_id: str) -> Dict[str, Any]:
        """Fetch drug count and generic percentage using optimized SQLModel queries."""
        try:
            with Session(engine) as session:
                # Get total count
                count_stmt = select(func.count()).select_from(ProcessedDrug).where(ProcessedDrug.plan_id == database_id)
                drug_count = session.exec(count_stmt).one()
                
                # Get generic count (where name equals generic name)
                generic_stmt = select(func.count()).select_from(ProcessedDrug).where(
                    ProcessedDrug.plan_id == database_id,
                    func.lower(func.trim(ProcessedDrug.drug_name)) == func.lower(func.trim(ProcessedDrug.generic_name))
                )
                generic_count = session.exec(generic_stmt).one()
                
                generic_percent = (generic_count / drug_count * 100) if drug_count > 0 else 0.0
                
                return {
                    'drugCount': drug_count,
                    'genericPercent': round(generic_percent, 1)
                }
        except Exception as e:
            logger.error(f"Error fetching database stats: {e}")
            return {'drugCount': 0, 'genericPercent': 0.0}

    async def search_drugs(self, query: str) -> List[Dict[str, Any]]:
        """Search for drugs across all plan formularies."""
        try:
            with Session(engine) as session:
                # Universal case-insensitive fuzzy search using ILIKE
                search_term = f"%{query}%"
                statement = select(ProcessedDrug).where(
                    or_(
                        ProcessedDrug.drug_name.ilike(search_term),
                        ProcessedDrug.generic_name.ilike(search_term),
                        ProcessedDrug.therapeutic_class.ilike(search_term)
                    )
                ).limit(10)
                
                results = session.exec(statement).all()
                return [{
                    'name': d.drug_name,
                    'genericName': d.generic_name,
                    'class': d.therapeutic_class,
                    'strength': d.strength,
                    'form': d.dosage_form,
                    'availability': 'Formulary'
                } for d in results]
        except Exception as e:
            logger.error(f"Drug search failed: {e}")
            return []

    async def get_drugs(self, database_id: str) -> List[Dict[str, Any]]:
        """Fetch drugs from SQLModel (faster) or fallback to ChromaDB."""
        try:
            with Session(engine) as session:
                statement = select(ProcessedDrug).where(ProcessedDrug.plan_id == database_id)
                results = session.exec(statement).all()
                if results:
                    return [{
                        'id': d.id,
                        'name': d.drug_name,
                        'genericName': d.generic_name,
                        'class': d.therapeutic_class,
                        'strength': d.strength,
                        'form': d.dosage_form,
                        'availability': 'Formulary'
                    } for d in results]
        except Exception as e:
            logger.error(f"Failed to fetch drugs from SQLModel: {e}")
            pass
            
        # Fallback to direct ChromaDB extraction if SQLModel is empty
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
