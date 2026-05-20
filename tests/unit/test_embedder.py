"""Unit tests for embedder module."""

from unittest.mock import MagicMock, patch

import pytest

from ragents.errors import EmbeddingError, EmbeddingModelError
from ragents.rag.embedder import APIEmbedder, Embedder, LocalEmbedder, create_embedder
from ragents.utils.config import Settings


class TestEmbedderABC:
    """Tests for the abstract Embedder base class."""

    def test_embedder_is_abstract(self):
        """Cannot instantiate abstract base class."""
        with pytest.raises(TypeError):
            Embedder()

    def test_embed_query_delegates_to_embed(self):
        """embed_query should call embed with single-item list."""

        class ConcreteEmbedder(Embedder):
            @property
            def dimension(self):
                return 128

            def embed(self, texts):
                return [[0.1] * self.dimension] * len(texts)

        embedder = ConcreteEmbedder()
        result = embedder.embed_query("hello")

        assert result == [0.1] * 128


class TestAPIEmbedder:
    """Tests for APIEmbedder."""

    def test_init_requires_api_key(self):
        """Empty API key should raise EmbeddingError."""
        with pytest.raises(EmbeddingError) as exc:
            APIEmbedder(api_key="", base_url="https://api.openai.com")
        assert "API key is required" in str(exc.value)

    def test_init_strips_trailing_slash(self):
        """base_url trailing slash should be stripped."""
        embedder = APIEmbedder(
            api_key="test-key",
            base_url="https://api.openai.com/",
        )
        assert embedder.base_url == "https://api.openai.com"

    def test_dimension_property(self):
        """dimension property returns configured value."""
        embedder = APIEmbedder(
            api_key="test-key",
            base_url="https://api.openai.com",
            dimension=768,
        )
        assert embedder.dimension == 768

    def test_embed_empty_list(self):
        """Empty input returns empty list without API call."""
        embedder = APIEmbedder(
            api_key="test-key",
            base_url="https://api.openai.com",
        )
        result = embedder.embed([])
        assert result == []

    def test_embed_success(self):
        """Successful embedding returns vectors."""
        mock_client = MagicMock()
        mock_item = MagicMock()
        mock_item.embedding = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.data = [mock_item]
        mock_client.embeddings.create.return_value = mock_response

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "openai":
                    mod = MagicMock()
                    mod.OpenAI = MagicMock(return_value=mock_client)
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            embedder = APIEmbedder(
                api_key="test-key",
                base_url="https://api.openai.com",
                model="text-embedding-3-small",
                dimension=3,
            )
            result = embedder.embed(["hello"])

        assert result == [[0.1, 0.2, 0.3]]
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["hello"],
        )

    def test_embed_lazy_client(self):
        """Client is lazily initialized on first embed call."""
        embedder = APIEmbedder(
            api_key="test-key",
            base_url="https://api.openai.com",
        )
        assert embedder._client is None

        mock_client = MagicMock()
        mock_item = MagicMock()
        mock_item.embedding = [0.1]
        mock_response = MagicMock()
        mock_response.data = [mock_item]
        mock_client.embeddings.create.return_value = mock_response

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "openai":
                    mod = MagicMock()
                    mod.OpenAI = MagicMock(return_value=mock_client)
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import
            embedder.embed(["test"])

        assert embedder._client is not None

    def test_embed_reuses_client(self):
        """Subsequent calls reuse the same client instance."""
        mock_client = MagicMock()
        mock_item = MagicMock()
        mock_item.embedding = [0.1]
        mock_response = MagicMock()
        mock_response.data = [mock_item]
        mock_client.embeddings.create.return_value = mock_response

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "openai":
                    mod = MagicMock()
                    mod.OpenAI = MagicMock(return_value=mock_client)
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            embedder = APIEmbedder(
                api_key="test-key",
                base_url="https://api.openai.com",
            )
            embedder.embed(["first"])
            first_client = embedder._client
            embedder.embed(["second"])

        # Same client instance reused
        assert embedder._client is first_client
        assert mock_client.embeddings.create.call_count == 2

    def test_embed_api_error(self):
        """API errors are wrapped in EmbeddingError."""
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("rate limit")

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "openai":
                    mod = MagicMock()
                    mod.OpenAI = MagicMock(return_value=mock_client)
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            embedder = APIEmbedder(
                api_key="test-key",
                base_url="https://api.openai.com",
            )
            with pytest.raises(EmbeddingError) as exc:
                embedder.embed(["hello"])
            assert "rate limit" in str(exc.value)

    def test_embed_missing_openai_package(self):
        """Missing openai package raises EmbeddingModelError."""
        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "openai":
                    raise ImportError("No module named 'openai'")
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            embedder = APIEmbedder(
                api_key="test-key",
                base_url="https://api.openai.com",
            )
            with pytest.raises(EmbeddingModelError) as exc:
                embedder.embed(["hello"])
            assert "openai package not installed" in str(exc.value)

    def test_embed_batch(self):
        """Batch embedding returns multiple vectors."""
        mock_client = MagicMock()
        mock_items = [
            MagicMock(embedding=[0.1, 0.2]),
            MagicMock(embedding=[0.3, 0.4]),
        ]
        mock_response = MagicMock()
        mock_response.data = mock_items
        mock_client.embeddings.create.return_value = mock_response

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "openai":
                    mod = MagicMock()
                    mod.OpenAI = MagicMock(return_value=mock_client)
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            embedder = APIEmbedder(
                api_key="test-key",
                base_url="https://api.openai.com",
                dimension=2,
            )
            result = embedder.embed(["hello", "world"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]


class TestLocalEmbedder:
    """Tests for LocalEmbedder."""

    def test_init_defaults(self):
        """Default model and device."""
        embedder = LocalEmbedder()
        assert embedder.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert embedder.device == "cpu"
        assert embedder._model is None
        assert embedder._dimension is None

    def test_init_custom(self):
        """Custom model and device."""
        embedder = LocalEmbedder(
            model_name="custom-model",
            device="cuda",
        )
        assert embedder.model_name == "custom-model"
        assert embedder.device == "cuda"

    def test_embed_empty_list(self):
        """Empty input returns empty list."""
        embedder = LocalEmbedder()
        result = embedder.embed([])
        assert result == []

    def test_dimension_before_load(self):
        """dimension property triggers lazy load, falls back on import error."""
        embedder = LocalEmbedder()
        assert embedder._dimension is None

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "sentence_transformers":
                    raise ImportError("No module named 'sentence_transformers'")
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            # dimension tries to load, fails with EmbeddingModelError
            with pytest.raises(EmbeddingModelError):
                _ = embedder.dimension

    def test_embed_missing_package(self):
        """Missing sentence-transformers raises EmbeddingModelError."""
        embedder = LocalEmbedder()

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "sentence_transformers":
                    raise ImportError("No module named 'sentence_transformers'")
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            with pytest.raises(EmbeddingModelError) as exc:
                embedder.embed(["hello"])
            assert "sentence-transformers not installed" in str(exc.value)

    def test_embed_success(self):
        """Successful local embedding."""
        import numpy as np

        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.1] * 384])

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "sentence_transformers":
                    mod = MagicMock()
                    mod.SentenceTransformer = MagicMock(return_value=mock_model)
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            embedder = LocalEmbedder()
            result = embedder.embed(["hello"])

        assert len(result) == 1
        assert len(result[0]) == 384
        assert result[0][0] == 0.1
        mock_model.encode.assert_called_once()
        call_kwargs = mock_model.encode.call_args[1]
        assert call_kwargs["convert_to_numpy"] is True
        assert call_kwargs["show_progress_bar"] is False

    def test_dimension_after_load(self):
        """dimension property returns model dimension after load."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "sentence_transformers":
                    mod = MagicMock()
                    mod.SentenceTransformer = MagicMock(return_value=mock_model)
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            embedder = LocalEmbedder()
            assert embedder.dimension == 768
            assert embedder._dimension == 768

    def test_model_cached(self):
        """Model is loaded only once."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384

        call_count = 0

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                nonlocal call_count
                if name == "sentence_transformers":
                    call_count += 1
                    mod = MagicMock()
                    mod.SentenceTransformer = MagicMock(return_value=mock_model)
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            embedder = LocalEmbedder()
            embedder._load_model()
            embedder._load_model()

        assert call_count == 1

    def test_embed_error(self):
        """Encoding errors are wrapped in EmbeddingError."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.side_effect = RuntimeError("OOM")

        with patch("builtins.__import__") as mock_import:
            def fake_import(name, *args, **kwargs):
                if name == "sentence_transformers":
                    mod = MagicMock()
                    mod.SentenceTransformer = MagicMock(return_value=mock_model)
                    return mod
                return __builtins__["__import__"](name, *args, **kwargs)

            mock_import.side_effect = fake_import

            embedder = LocalEmbedder()
            with pytest.raises(EmbeddingError) as exc:
                embedder.embed(["hello"])
            assert "OOM" in str(exc.value)


class TestCreateEmbedder:
    """Tests for create_embedder factory."""

    def test_create_local_embedder_default(self):
        """Default settings create LocalEmbedder."""
        settings = Settings()
        settings.llm.embedding_provider = "local"

        embedder = create_embedder(settings)
        assert isinstance(embedder, LocalEmbedder)

    def test_create_api_embedder_openai(self):
        """OpenAI provider with key creates APIEmbedder."""
        settings = Settings()
        settings.llm.embedding_provider = "openai"
        settings.openai_api_key = "sk-test"

        embedder = create_embedder(settings)
        assert isinstance(embedder, APIEmbedder)
        assert embedder.api_key == "sk-test"

    def test_create_api_embedder_deepseek(self):
        """DeepSeek provider with key creates APIEmbedder."""
        settings = Settings()
        settings.llm.embedding_provider = "deepseek"
        settings.deepseek_api_key = "sk-test"

        embedder = create_embedder(settings)
        assert isinstance(embedder, APIEmbedder)
        assert embedder.api_key == "sk-test"

    def test_create_api_embedder_api_alias(self):
        """'api' provider alias creates APIEmbedder."""
        settings = Settings()
        settings.llm.embedding_provider = "API"
        settings.openai_api_key = "sk-test"

        embedder = create_embedder(settings)
        assert isinstance(embedder, APIEmbedder)

    def test_fallback_to_local_no_key(self):
        """API provider without key falls back to LocalEmbedder."""
        settings = Settings()
        settings.llm.embedding_provider = "openai"
        settings.openai_api_key = ""

        embedder = create_embedder(settings)
        assert isinstance(embedder, LocalEmbedder)

    def test_deepseek_priority_over_openai(self):
        """DeepSeek key takes priority when both are set."""
        settings = Settings()
        settings.llm.embedding_provider = "openai"
        settings.deepseek_api_key = "sk-deepseek"
        settings.openai_api_key = "sk-openai"

        embedder = create_embedder(settings)
        assert isinstance(embedder, APIEmbedder)
        assert embedder.api_key == "sk-deepseek"

    def test_custom_embedding_model(self):
        """Custom embedding model name passed to LocalEmbedder."""
        settings = Settings()
        settings.llm.embedding_provider = "local"
        settings.llm.embedding_model = "custom-model-name"

        embedder = create_embedder(settings)
        assert isinstance(embedder, LocalEmbedder)
        assert embedder.model_name == "custom-model-name"

    def test_embedding_dimension_config(self):
        """Embedding dimension from config passed to APIEmbedder."""
        settings = Settings()
        settings.llm.embedding_provider = "openai"
        settings.openai_api_key = "sk-test"
        settings.llm.embedding_dimension = 768

        embedder = create_embedder(settings)
        assert isinstance(embedder, APIEmbedder)
        assert embedder.dimension == 768
