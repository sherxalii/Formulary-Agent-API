#!/usr/bin/env python3
"""
Script to reload database embeddings by deleting existing vectorstores and recreating them from source PDFs.
"""

import os
import sys
import shutil
import time
from pathlib import Path

# Add the backend directory to the path so we can import modules
sys.path.append(str(Path(__file__).parent / "backend"))

from backend.formulary_drug_rag import FormularyDrugRAG
from backend import config
from langchain_core.documents import Document

def reload_embeddings():
    """Reload all database embeddings from source PDFs."""

    # Load environment variables
    try:
        import dotenv
        dotenv.load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv not available, using environment variables directly")

    openai_api_key = config.OPENAI_CONFIG['API_KEY'] or os.getenv("OPENAI_API_KEY", "")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not set")
        return

    # Get paths
    pdf_dir = Path(config.PDF_DIR)
    database_dir = Path(config.DATABASE_DIR)

    if not pdf_dir.exists():
        print(f"PDF directory not found: {pdf_dir}")
        return

    if not database_dir.exists():
        print(f"Database directory not found: {database_dir}")
        return

    # Get all PDFs
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found")
        return

    print(f"Found {len(pdf_files)} PDF files to process")

    for pdf_path in pdf_files:
        pdf_name = pdf_path.stem  # Remove .pdf extension

        # Find corresponding database directory
        # Try exact match first, then some variations
        possible_db_names = [
            pdf_name,
            f"{pdf_name}_formulary",
            pdf_name.replace("_", "-"),
            pdf_name.replace("-", "_"),
        ]

        db_dir = None
        for db_name in possible_db_names:
            candidate_dir = database_dir / db_name
            if candidate_dir.exists():
                db_dir = candidate_dir
                break

        if not db_dir:
            print(f"No existing database found for {pdf_name}, creating new one")
            # Create a new database directory with the PDF name
            db_dir = database_dir / pdf_name

        print(f"Reloading embeddings for: {pdf_name}")

        try:
            # Check if database already exists
            if db_dir.exists():
                print(f"   Found existing database: {db_dir}")
                print(f"   Updating with new data from PDF (not deleting existing embeddings)")

                # Load existing RAG instance
                rag = FormularyDrugRAG(
                    openai_api_key=openai_api_key,
                    chroma_persist_directory=str(db_dir),
                    model_name=config.OPENAI_CONFIG['MODEL_NAME'],
                    embedding_model=config.OPENAI_CONFIG['EMBEDDING_MODEL'],
                    enable_ai_enhancement=True,
                    enable_llm_prevalidation=True,
                    auto_cleanup=True
                )

                # Try to load existing vectorstore
                if rag.load_existing_vectorstore():
                    print(f"   Loaded existing database with {len(rag.vectorstore.get()['documents'])} documents")

                    # Load new documents from PDF
                    new_documents = rag.load_formulary_documents([str(pdf_path)])
                    if new_documents:
                        print(f"   Loaded {len(new_documents)} new documents from PDF")

                        # Add new documents to existing vectorstore
                        rag.vectorstore.add_documents(new_documents)
                        print(f"   Added new documents to existing database")

                        # Re-setup retriever and hybrid search
                        rag.retriever = rag.vectorstore.as_retriever(
                            search_type="similarity",
                            search_kwargs={"k": 6}
                        )

                        # Get all documents for hybrid retriever setup
                        all_docs_data = rag.vectorstore.get()
                        if 'documents' in all_docs_data and 'metadatas' in all_docs_data:
                            # Reconstruct documents for hybrid setup
                            existing_documents = []
                            for content, metadata in zip(all_docs_data['documents'], all_docs_data['metadatas']):
                                if content and metadata:
                                    doc = Document(page_content=content, metadata=metadata)
                                    existing_documents.append(doc)

                            # Add new documents to the list
                            all_documents = existing_documents + new_documents

                            # Setup hybrid retriever with all documents
                            rag.hybrid_retriever = rag._setup_hybrid_retriever(all_documents)
                            print(f"   Updated hybrid retriever with {len(all_documents)} total documents")
                        else:
                            rag.hybrid_retriever = rag.retriever
                            print(f"   Could not setup hybrid retriever, using semantic only")

                        rag.setup_rag_chain()
                        print(f"   Updated retrievers and RAG chain")
                    else:
                        print(f"    No new documents found in PDF")
                else:
                    print(f"   Could not load existing database, recreating...")
                    # Fall back to creating new database
                    documents = rag.load_formulary_documents([str(pdf_path)])
                    if documents:
                        rag.create_vectorstore(documents)
                        rag.setup_rag_chain()
                        print(f"   Created new database with {len(documents)} documents")
                    else:
                        print(f"   No documents loaded from {pdf_name}")
            else:
                print(f"   Creating new database: {db_dir}")
                # Create new vectorstore
                vectorstore_path = str(db_dir)

                rag = FormularyDrugRAG(
                    openai_api_key=openai_api_key,
                    chroma_persist_directory=vectorstore_path,
                    model_name=config.OPENAI_CONFIG['MODEL_NAME'],
                    embedding_model=config.OPENAI_CONFIG['EMBEDDING_MODEL'],
                    enable_ai_enhancement=True,
                    enable_llm_prevalidation=True,
                    auto_cleanup=True
                )

                # Load documents and create vectorstore
                documents = rag.load_formulary_documents([str(pdf_path)])
                if documents:
                    rag.create_vectorstore(documents)
                    rag.setup_rag_chain()
                    print(f"   Successfully created database for {pdf_name}")
                else:
                    print(f"   No documents loaded from {pdf_name}")

        except Exception as e:
            print(f"    Error reloading {pdf_name}: {str(e)}")

    print("Embedding reload process completed!")

if __name__ == "__main__":
    reload_embeddings()