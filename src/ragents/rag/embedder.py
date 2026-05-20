"""Embedding wrapper (OpenAI / local models)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ragents.errors import EmbeddingError, EmbeddingModelError
from ragents.utils.logger import logger

if TYPE_CHECKING:
    from ragents.utils.config import Settings


class Embedder(ABC):
    """Abstract base for embedding generators."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        return self.embed([text])[0]

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the output embedding dimension."""
        ...


class APIEmbedder(Embedder):
    """Embedding via OpenAI-compatible API (OpenAI, DeepSeek, etc.)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ):
        if not api_key:
            raise EmbeddingError(
                "API key is required for APIEmbedder",
                context={"model": model},
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._dimension = dimension
        self._client = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using OpenAI-compatible API."""
        if not texts:
            return []

        # Lazy import to avoid hard dependency
        try:
            from openai import OpenAI
        except ImportError as e:
            raise EmbeddingModelError(
                "openai package not installed. Run: pip install openai"
            ) from e

        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

        logger.info(
            "api_embedding",
            model=self.model,
            batch_size=len(texts),
        )

        try:
            response = self._client.embeddings.create(
                model=self.model,
                input=texts,
            )
            vectors = [item.embedding for item in response.data]
            logger.info(
                "api_embedding_done",
                model=self.model,
                batch_size=len(texts),
                dimension=self._dimension,
            )
            return vectors
        except Exception as e:
            logger.error(
                "api_embedding_failed",
                model=self.model,
                error=str(e),
            )
            raise EmbeddingError(
                f"API embedding failed: {e}",
                context={"model": self.model, "batch_size": len(texts)},
            ) from e


class LocalEmbedder(Embedder):
    """Embedding via local sentence-transformers model."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._dimension: int | None = None

    def _load_model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise EmbeddingModelError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            ) from e

        logger.info(
            "loading_local_embedding_model",
            model=self.model_name,
            device=self.device,
        )
        self._model = SentenceTransformer(self.model_name, device=self.device)
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(
            "local_model_loaded",
            model=self.model_name,
            dimension=self._dimension,
        )

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._load_model()
        return self._dimension or 384  # default for MiniLM

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using local model."""
        if not texts:
            return []

        self._load_model()

        logger.info(
            "local_embedding",
            model=self.model_name,
            batch_size=len(texts),
        )

        try:
            vectors = self._model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            # Convert numpy arrays to Python lists
            result = [v.tolist() for v in vectors]
            logger.info(
                "local_embedding_done",
                model=self.model_name,
                batch_size=len(texts),
                dimension=self._dimension,
            )
            return result
        except Exception as e:
            logger.error(
                "local_embedding_failed",
                model=self.model_name,
                error=str(e),
            )
            raise EmbeddingError(
                f"Local embedding failed: {e}",
                context={"model": self.model_name, "batch_size": len(texts)},
            ) from e


def create_embedder(settings: Settings) -> Embedder:
    """Factory: create embedder from settings."""
    provider = settings.llm.embedding_provider.lower()

    if provider in ("openai", "deepseek", "api"):
        # Determine which API key and base URL to use
        if settings.deepseek_api_key:
            api_key = settings.deepseek_api_key
            base_url = settings.deepseek_base_url_openai
            model = settings.deepseek_model
            dimension = settings.llm.embedding_dimension or 1536
        elif settings.openai_api_key:
            api_key = settings.openai_api_key
            base_url = settings.openai_base_url
            model = settings.openai_model
            dimension = settings.llm.embedding_dimension or 1536
        else:
            logger.warning(
                "no_api_key_for_embedding",
                provider=provider,
                fallback="local",
            )
            return LocalEmbedder(
                model_name=settings.llm.embedding_model,
            )

        return APIEmbedder(
            api_key=api_key,
            base_url=base_url,
            model=model,
            dimension=dimension,
        )

    # Default: local
    return LocalEmbedder(
        model_name=settings.llm.embedding_model,
    )
