"""Multimodal vector store using ChromaDB for text and image chunks."""
import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger
from config import settings


class VectorStore:
    """ChromaDB-based vector store for both text and image document chunks."""

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=str(settings.VECTOR_DB_PATH),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        """Get or create the document chunks collection."""
        try:
            collection = self.client.get_collection("document_chunks")
            logger.info(f"Loaded existing collection with {collection.count()} chunks")
        except Exception:
            collection = self.client.create_collection(
                name="document_chunks",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Created new document_chunks collection")
        return collection

    def add_text_chunks(self, document_id: int, chunks: list[str], embeddings: list[list[float]], metadata: list[dict]):
        """Add text chunks with embeddings to the vector store."""
        if not chunks:
            return

        ids = [f"doc_{document_id}_text_{i}" for i in range(len(chunks))]
        metadatas = [
            {**meta, "document_id": document_id, "chunk_index": i, "chunk_type": "text"}
            for i, meta in enumerate(metadata)
        ]

        self.collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"Added {len(chunks)} text chunks for document {document_id}")

    def add_image_chunks(self, document_id: int, image_paths: list[str], embeddings: list[list[float]], metadata: list[dict]):
        """Add image chunks with embeddings to the vector store."""
        if not image_paths:
            return

        ids = [f"doc_{document_id}_image_{i}" for i in range(len(image_paths))]
        metadatas = [
            {**meta, "document_id": document_id, "chunk_index": i, "chunk_type": "image", "image_path": path}
            for i, (meta, path) in enumerate(zip(metadata, image_paths))
        ]

        # Use image paths as documents (for retrieval reference)
        self.collection.add(
            ids=ids,
            documents=[f"Image from {m.get('filename', 'unknown')}" for m in metadata],
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"Added {len(image_paths)} image chunks for document {document_id}")

    def search(self, query_embedding: list[float], top_k: int = None) -> list[dict]:
        """Search for similar chunks (both text and image)."""
        if top_k is None:
            top_k = settings.TOP_K

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i]
                similarity = 1 - distance
                if similarity >= settings.SIMILARITY_THRESHOLD:
                    chunk_meta = results["metadatas"][0][i]
                    chunks.append({
                        "content": doc,
                        "metadata": chunk_meta,
                        "similarity": similarity,
                        "chunk_type": chunk_meta.get("chunk_type", "text"),
                        "image_path": chunk_meta.get("image_path", None),
                    })

        return chunks

    def delete_document(self, document_id: int):
        """Delete all chunks for a document."""
        try:
            self.collection.delete(where={"document_id": document_id})
            logger.info(f"Deleted chunks for document {document_id}")
        except Exception as e:
            logger.warning(f"Error deleting document {document_id}: {e}")

    def get_stats(self) -> dict:
        """Get vector store statistics."""
        count = self.collection.count()
        return {
            "total_chunks": count,
            "collection_name": "document_chunks",
        }
