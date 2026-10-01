"""Multimodal LLM engine: generates responses using text + image context with LongCat."""
import base64
import httpx
from loguru import logger
from config import settings
from PIL import Image
import io


class LLMEngine:
    """Generate responses using LongCat with multimodal context."""

    def __init__(self):
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.MAX_TOKENS
        self.temperature = settings.TEMPERATURE
        self.api_base = "https://api.opencode.ai/v1"

    def generate_response(self, query: str, context_chunks: list[dict], user_image_path: str = None) -> str:
        """Generate a response based on query, context chunks, and optional user image."""
        context = self._build_context(context_chunks)
        return self._longcat_generate(query, context, user_image_path)

    def _build_context(self, chunks: list[dict]) -> str:
        """Build context string from retrieved chunks with deduplication and ranking."""
        if not chunks:
            return "No relevant documents found."

        # Separate text and image chunks
        text_chunks = [c for c in chunks if c.get("chunk_type") == "text"]
        image_chunks = [c for c in chunks if c.get("chunk_type") == "image"]

        context_parts = []

        # Add text chunks
        if text_chunks:
            seen_contents = set()
            unique_texts = []
            for chunk in text_chunks:
                content_preview = chunk['content'][:100].strip()
                if content_preview not in seen_contents:
                    seen_contents.add(content_preview)
                    unique_texts.append(chunk)

            for i, chunk in enumerate(unique_texts, 1):
                source = chunk.get("metadata", {}).get("filename", "Unknown")
                similarity = chunk.get("similarity", 0)
                context_parts.append(f"[Text Source {i}: {source} (relevance: {similarity:.0%})]\n{chunk['content']}")

        # Add image chunks with descriptions
        if image_chunks:
            context_parts.append("\n[Images from documents]")
            for i, chunk in enumerate(image_chunks, 1):
                source = chunk.get("metadata", {}).get("filename", "Unknown")
                page = chunk.get("metadata", {}).get("page_num", "?")
                similarity = chunk.get("similarity", 0)
                context_parts.append(f"  Image {i}: From {source}, page {page} (relevance: {similarity:.0%})")

        return "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

    def _encode_image_base64(self, image_path: str) -> str:
        """Encode image to base64 for API transmission."""
        try:
            with Image.open(image_path) as img:
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Error encoding image: {e}")
            return ""

    def _longcat_generate(self, query: str, context: str, user_image_path: str = None) -> str:
        """Generate response using LongCat via OpenCode Zen API."""
        try:
            system_prompt = """You are a helpful AI assistant with access to a multimodal knowledge base containing both text and images.
Answer the user's question based on the provided context and any images.
If the context doesn't contain enough information, say so clearly.
Always cite your sources when possible.
Be concise, accurate, and helpful."""

            user_content = f"Context:\n{context}\n\nQuestion: {query}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature,
                    },
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()

        except httpx.HTTPStatusError as e:
            logger.error(f"LongCat API HTTP error: {e.response.status_code} - {e.response.text}")
            return self._fallback_generate(query, context)
        except Exception as e:
            logger.error(f"LongCat API error: {e}")
            return self._fallback_generate(query, context)

    def _fallback_generate(self, query: str, context: str) -> str:
        """Simple fallback response when API is unavailable."""
        if context == "No relevant documents found.":
            return (
                "I don't have enough information in the knowledge base to answer your question. "
                "Please upload more relevant documents and try again."
            )

        lines = context.split("\n")
        relevant_lines = []
        query_words = set(query.lower().split())

        for line in lines:
            line_words = set(line.lower().split())
            overlap = len(query_words & line_words)
            if overlap > 0:
                relevant_lines.append((overlap, line))

        relevant_lines.sort(reverse=True)
        top_lines = [line for _, line in relevant_lines[:5]]

        if top_lines:
            response = "Based on the knowledge base, here's what I found:\n\n"
            response += "\n".join(top_lines)
            response += "\n\n(Note: LongCat API was unavailable, showing extracted passages.)"
            return response

        return (
            "I found some related documents but couldn't extract a specific answer. "
            "Try rephrasing your question or uploading more relevant documents."
        )
