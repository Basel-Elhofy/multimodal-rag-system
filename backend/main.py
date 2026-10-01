"""FastAPI main application for the Multimodal RAG System."""
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from config import settings
from database import init_db, get_db
from models import Document, Chunk, Query
from rag_pipeline import RAGPipeline

rag_pipeline: Optional[RAGPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the application."""
    global rag_pipeline
    await init_db()
    rag_pipeline = RAGPipeline()
    logger.info("Multimodal RAG Pipeline initialized")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Multimodal RAG System - Upload documents, ask questions with text + image",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (frontend assets)
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def root():
    """Serve the frontend."""
    frontend_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    return FileResponse(frontend_path)


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload and process a document (PDF, DOCX, TXT, MD, images)."""
    if not rag_pipeline:
        raise HTTPException(status_code=500, detail="RAG pipeline not initialized")

    file_type = rag_pipeline.processor.get_file_type(file.filename)
    if not file_type:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: PDF, DOCX, TXT, MD, PNG, JPG, JPEG, TIFF, BMP, WEBP",
        )

    file_path = settings.UPLOAD_DIR / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    doc = Document(
        filename=file.filename,
        file_type=file_type,
        file_path=str(file_path),
        file_size=os.path.getsize(file_path),
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        result = rag_pipeline.processor.process_file(str(file_path), file.filename)

        # Add text chunks to vector store
        if result["chunks"]:
            text_embeddings = rag_pipeline.embedder.encode_texts(result["chunks"])
            metadata = [result["metadata"]] * len(result["chunks"])
            rag_pipeline.vector_store.add_text_chunks(
                document_id=doc.id,
                chunks=result["chunks"],
                embeddings=text_embeddings,
                metadata=metadata,
            )

        # Add image chunks to vector store
        if result["images"]:
            image_paths = [img["image_path"] for img in result["images"]]
            image_embeddings = rag_pipeline.embedder.encode_images(image_paths)
            image_metadata = [{**result["metadata"], **img} for img in result["images"]]
            rag_pipeline.vector_store.add_image_chunks(
                document_id=doc.id,
                image_paths=image_paths,
                embeddings=image_embeddings,
                metadata=image_metadata,
            )

        doc.content_text = result["content_text"][:10000]
        doc.chunk_count = result["chunk_count"]
        doc.metadata_json = result["metadata"]
        doc.status = "completed"
        await db.commit()

        return {
            "success": True,
            "document_id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "chunk_count": doc.chunk_count,
            "image_count": result["image_count"],
            "file_size": doc.file_size,
        }

    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)
        await db.commit()
        logger.error(f"Error processing document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


class QueryRequest(BaseModel):
    question: str


@app.post("/api/query")
async def query_knowledge_base(
    question: str = Form(...),
    image: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Query the knowledge base with text + optional image."""
    if not rag_pipeline:
        raise HTTPException(status_code=500, detail="RAG pipeline not initialized")

    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Save uploaded image if provided
    user_image_path = None
    if image and image.filename:
        try:
            image_ext = Path(image.filename).suffix
            temp_image = settings.UPLOAD_DIR / f"query_image_{os.urandom(4).hex()}{image_ext}"
            with open(temp_image, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            user_image_path = str(temp_image)
        except Exception as e:
            logger.error(f"Error saving query image: {e}")

    try:
        result = rag_pipeline.query(question, user_image_path)

        # Save query to database
        query_record = Query(
            question=question,
            answer=result["answer"],
            sources=result["sources"],
            response_time=result["response_time"],
        )
        db.add(query_record)
        await db.commit()

        return result

    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/api/documents")
async def list_documents(db: AsyncSession = Depends(get_db)):
    """List all uploaded documents."""
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    documents = result.scalars().all()

    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "chunk_count": doc.chunk_count,
                "status": doc.status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in documents
        ],
        "total": len(documents),
    }


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a document and its chunks."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if rag_pipeline:
        rag_pipeline.vector_store.delete_document(document_id)

    try:
        os.remove(doc.file_path)
    except Exception:
        pass

    await db.delete(doc)
    await db.commit()

    return {"success": True, "message": f"Document {document_id} deleted"}


@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get system statistics."""
    if not rag_pipeline:
        raise HTTPException(status_code=500, detail="RAG pipeline not initialized")

    stats = rag_pipeline.get_stats()
    result = await db.execute(select(Document))
    stats["total_documents"] = len(result.scalars().all())
    return stats


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "rag_ready": rag_pipeline is not None}
