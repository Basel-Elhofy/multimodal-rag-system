"""Multimodal embedding engine using CLIP for text and image embeddings."""
import numpy as np
from sentence_transformers import SentenceTransformer
from PIL import Image
from loguru import logger
from config import settings


class EmbeddingEngine:
    """Generate multimodal embeddings for text and images using CLIP."""

    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the CLIP model."""
        try:
            logger.info(f"Loading multimodal embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Multimodal embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        """Encode text into embeddings."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def encode_image(self, image_path: str) -> list[float]:
        """Encode a single image into an embedding."""
        try:
            image = Image.open(image_path).convert("RGB")
            embedding = self.model.encode([image], normalize_embeddings=True)
            return embedding[0].tolist()
        except Exception as e:
            logger.error(f"Error encoding image {image_path}: {e}")
            return [0.0] * settings.EMBEDDING_DIMENSION

    def encode_images(self, image_paths: list[str]) -> list[list[float]]:
        """Encode multiple images into embeddings."""
        if not image_paths:
            return []
        images = []
        for path in image_paths:
            try:
                images.append(Image.open(path).convert("RGB"))
            except Exception as e:
                logger.error(f"Error loading image {path}: {e}")
                continue
        if not images:
            return []
        embeddings = self.model.encode(images, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def encode_query(self, text: str, image_path: str = None) -> list[float]:
        """Encode a query with optional image. Returns combined embedding."""
        text_embedding = self.model.encode([text], normalize_embeddings=True)[0]

        if image_path:
            try:
                image = Image.open(image_path).convert("RGB")
                image_embedding = self.model.encode([image], normalize_embeddings=True)[0]
                # Average text and image embeddings for multimodal query
                combined = (text_embedding + image_embedding) / 2
                return combined.tolist()
            except Exception as e:
                logger.error(f"Error encoding query image: {e}")

        return text_embedding.tolist()
