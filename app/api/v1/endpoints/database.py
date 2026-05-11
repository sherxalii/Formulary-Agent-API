from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from app.models.schemas import DatabaseInfo, DatabaseListResponse, EmbeddingStatusResponse
from app.services.database_service import DatabaseService
from app.services.rag_service import RagService, RagManager
from app.core.dependencies import get_database_service, get_rag_service, get_rag_manager
from app.core.config import settings
import os
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload-pdf")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    pdf: UploadFile = File(...),
    db_service: DatabaseService = Depends(get_database_service)
):
    filename = pdf.filename
    if not filename:
        return JSONResponse({'success': False, 'error': 'No filename provided.'}, status_code=400)
    if not db_service.allowed_file(filename):
        return JSONResponse({'success': False, 'error': 'Invalid file type. Only PDF allowed.'}, status_code=400)
    
    save_path = db_service.get_pdf_path(filename)
    with open(save_path, "wb") as f:
        f.write(await pdf.read())
    
    background_tasks.add_task(db_service.embed_pdf_sync, filename)
    return {"success": True, "filename": filename}

@router.get("/embedding-status/{filename}", response_model=EmbeddingStatusResponse)
async def get_embedding_status(
    filename: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    status = db_service.get_status(filename)
    return EmbeddingStatusResponse(status=status)

@router.get("/list-pdfs")
async def list_pdfs(db_service: DatabaseService = Depends(get_database_service)):
    pdfs = await db_service.list_pdfs()
    return {"pdfs": pdfs}

@router.get("/databases", response_model=DatabaseListResponse)
@router.get("/database-status", response_model=DatabaseListResponse)
@router.get("/list-databases", response_model=DatabaseListResponse)
async def list_databases(
    db_service: DatabaseService = Depends(get_database_service),
    rag_manager: RagManager = Depends(get_rag_manager)
):
    database_base_dir = settings.DATABASE_DIR
    logger.info(f"DEBUG: CWD: {os.getcwd()}")
    logger.info(f"DEBUG: DATABASE_DIR (relative): {database_base_dir}")
    logger.info(f"DEBUG: DATABASE_DIR (absolute): {os.path.abspath(database_base_dir)}")
    logger.info(f"DEBUG: database_base_dir exists: {os.path.exists(database_base_dir)}")
    databases = []
    
    if os.path.exists(database_base_dir):
        raw_list = os.listdir(database_base_dir)
        logger.info(f"DEBUG: Raw listdir results: {raw_list}")
        db_dirs = [d for d in raw_list
                  if os.path.isdir(os.path.join(database_base_dir, d)) and not d.startswith('.')]
        logger.info(f"DEBUG: Filtered db_dirs: {db_dirs}")
        
        for actual_name in db_dirs:
            db_path = database_base_dir / actual_name
            pdf_filename = f"{actual_name}.pdf"
            pdf_path = settings.PDF_DIR / pdf_filename
            
            status = 'Ready' if db_path.exists() else 'Not Processed'
            current_status = db_service.get_status(pdf_filename)
            if current_status != "not_found":
                status = current_status
                
            size = 'Unknown'
            uploaded_at = None
            if pdf_path.exists():
                size = f"{os.path.getsize(pdf_path) / 1024 / 1024:.2f} MB"
                uploaded_at = datetime.fromtimestamp(os.path.getmtime(pdf_path)).isoformat()
            
            databases.append(DatabaseInfo(
                id=actual_name,
                name=actual_name.replace('_', ' ').replace('-', ' '),
                filename=pdf_filename,
                status=status,
                size=size,
                uploadedAt=uploaded_at,
                processed=db_path.exists(),
                drugCount=0,
                genericPercent=0.0,
                tierCount=4
            ))
            
    return DatabaseListResponse(databases=databases, success=True)

@router.get("/database/{database_id}/drugs")
async def get_database_drugs(
    database_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    drugs = await db_service.get_drugs(database_id)
    return {"success": True, "drugs": drugs}

@router.get("/download-embedding/{database_id}")
async def download_embedding(
    database_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """Download a ZIP archive of the vectorstore."""
    zip_path = await db_service.download_embedding(database_id)
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Embedding ZIP not found or could not be created")
    
    return FileResponse(
        zip_path, 
        media_type='application/zip', 
        filename=f"{database_id}_embedding.zip"
    )

@router.post("/cleanup")
async def cleanup_database(
    database_id: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    """Trigger manual cleanup of invalid database entries."""
    result = await db_service.cleanup_database(database_id)
    return result

@router.get("/view-pdf/{filename}")
async def view_pdf(
    filename: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    if '..' in filename or filename.startswith('/') or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    pdf_path = db_service.get_pdf_path(filename)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(pdf_path, media_type='application/pdf')

@router.delete("/delete-embedding/{filename}")
async def delete_embedding(
    filename: str,
    db_service: DatabaseService = Depends(get_database_service)
):
    try:
        deleted_items, errors = await db_service.delete_database(filename)
        if deleted_items:
            message = f"Successfully deleted: {', '.join(deleted_items)}"
            if errors:
                message += f". Warnings: {', '.join(errors)}"
            return {"success": True, "message": message, "deleted": deleted_items}
        return {"success": False, "error": f"Nothing to delete. {', '.join(errors)}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
