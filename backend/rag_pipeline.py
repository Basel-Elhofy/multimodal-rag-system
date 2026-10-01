"""Multimodal RAG pipeline: orchestrates document processing, embedding, storage, and retrieval."""
import time
from loguru import logger
from config import settings
from document_processor import DocumentProcessor
from embedding_engine import EmbeddingEngine
from vector_store import VectorStore
from llm_engine import LLMEngine


class RAGPipeline:
    """Complete multimodal RAG pipeline for document ingestion and querying."""

    def __init__(self):
        self.processor = DocumentProcessor()
        self.embedder = EmbeddingEngine()
        self.vector_store = VectorStore()
        self.llm = LLMEngine()

    def ingest_document(self, file_path: str, filename: str) -> dict:
        """Process and ingest a document into the knowledge base."""
        logger.info(f"Ingesting document: {filename}")

        # Extract text, chunks, and images
        result = self.processor.process_file(file_path, filename)

        # Generate embeddings and add text chunks to vector store
        if result["chunks"]:
            text_embeddings = self.embedder.encode_texts(result["chunks"])
            metadata = [result["metadata"]] * len(result["chunks"])
            self.vector_store.add_text_chunks(
                document_id=0,  # Will be updated by caller
                chunks=result["chunks"],
                embeddings=text_embeddings,
                metadata=metadata,
            )

        # Generate embeddings and add image chunks to vector store
        if result["images"]:
            image_paths = [img["image_path"] for img in result["images"]]
            image_embeddings = self.embedder.encode_images(image_paths)
            image_metadata = [{**result["metadata"], **img} for img in result["images"]]
            self.vector_store.add_image_chunks(
                document_id=0,  # Will be updated by caller
                image_paths=image_paths,
                embeddings=image_embeddings,
                metadata=image_metadata,
            )

        logger.info(f"Document '{filename}' ingested: {result['chunk_count']} text chunks, {result['image_count']} images")
        return result

    def query(self, question: str, user_image_path: str = None) -> dict:
        """Query the knowledge base with text + optional image and generate a response."""
        start_time = time.time()

        # Encode query with optional image
        query_embedding = self.embedder.encode_query(question, user_image_path)

        # Search for relevant chunks (both text and image)
        relevant_chunks = self.vector_store.search(query_embedding)

        # Generate response
        answer = self.llm.generate_response(question, relevant_chunks, user_image_path)

        response_time = time.time() - start_time

        # Format sources
        sources = []
        for chunk in relevant_chunks:
            source = {
                "filename": chunk.get("metadata", {}).get("filename", "Unknown"),
                "similarity": round(chunk.get("similarity", 0), 3),
                "chunk_type": chunk.get("chunk_type", "text"),
            }
            if chunk.get("chunk_type") == "text":
                source["content_preview"] = chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"]
            else:
                source["image_path"] = chunk.get("image_path", "")
                source["page_num"] = chunk.get("metadata", {}).get("page_num", "?")
            sources.append(source)

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "response_time": round(response_time, 2),
            "chunks_found": len(relevant_chunks),
        }

    def get_stats(self) -> dict:
        """Get system statistics."""
        return {
            "vector_store": self.vector_store.get_stats(),
            "embedding_model": settings.EMBEDDING_MODEL,
            "llm_model": settings.LLM_MODEL,
            "chunk_size": settings.CHUNK_SIZE,
            "chunk_overlap": settings.CHUNK_OVERLAP,
        }
