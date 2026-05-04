"""
Model2Vec-based text classification service.

Provides fast, static embedding-based text classification using the
minishlab/potion-base-8M model. Classifies articles and posts into
predefined and custom categories, with SSI component mapping.

Gracefully degrades when model2vec is not installed — returns empty
classifications without interrupting the curation pipeline.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency — model2vec
# ---------------------------------------------------------------------------

try:
    from model2vec import StaticModel
    import numpy as np
    _MODEL2VEC_AVAILABLE = True
except ImportError:  # pragma: no cover
    _MODEL2VEC_AVAILABLE = False
    StaticModel = None  # type: ignore[assignment,misc]
    np = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

MODEL2VEC_MODEL_NAME: str = os.getenv(
    "MODEL2VEC_MODEL_NAME", "minishlab/potion-base-8M"
)
MODEL2VEC_CONFIDENCE_THRESHOLD: float = float(
    os.getenv("MODEL2VEC_CONFIDENCE_THRESHOLD", "0.0")
)
MODEL2VEC_ENABLED: bool = (
    os.getenv("MODEL2VEC_ENABLED", "true").lower() == "true"
)
MODEL2VEC_BATCH_SIZE: int = int(os.getenv("MODEL2VEC_BATCH_SIZE", "50"))

# ---------------------------------------------------------------------------
# Default categories — mapped to SSI components
# ---------------------------------------------------------------------------

DEFAULT_CATEGORIES: dict[str, dict[str, str]] = {
    "Technology": {
        "description": (
            "Software engineering, hardware, programming languages, developer tools, "
            "cloud computing, open source, DevOps, and technical infrastructure"
        ),
        "ssi_component": "establish_brand",
    },
    "Artificial Intelligence": {
        "description": (
            "Machine learning, large language models, neural networks, AI research, "
            "RAG, embeddings, vector search, NLP, AI agents, and model development"
        ),
        "ssi_component": "establish_brand",
    },
    "Business": {
        "description": (
            "Entrepreneurship, startups, business strategy, management, leadership, "
            "enterprise software, SaaS, B2B, and professional services"
        ),
        "ssi_component": "find_right_people",
    },
    "Science": {
        "description": (
            "Scientific research, discoveries, academic papers, data science, "
            "mathematics, physics, biology, and research methodology"
        ),
        "ssi_component": "engage_with_insights",
    },
    "Education": {
        "description": (
            "Online learning, courses, tutorials, skill development, certifications, "
            "universities, and professional training programs"
        ),
        "ssi_component": "engage_with_insights",
    },
    "Politics": {
        "description": (
            "Government, policy, regulation, legislation, public sector, governance, "
            "compliance, and political developments affecting technology"
        ),
        "ssi_component": "build_relationships",
    },
    "Health": {
        "description": (
            "Healthcare technology, digital health, medical AI, wellness, "
            "biotechnology, and health informatics"
        ),
        "ssi_component": "find_right_people",
    },
    "Sports": {
        "description": (
            "Sports analytics, sports technology, athletic performance, "
            "data-driven coaching, and sports business"
        ),
        "ssi_component": "build_relationships",
    },
    "Entertainment": {
        "description": (
            "Media, streaming, gaming, content creation, digital entertainment, "
            "AR/VR, and creative technology"
        ),
        "ssi_component": "build_relationships",
    },
    "Travel": {
        "description": (
            "Travel technology, location-based services, remote work, "
            "global workforce, and geographic diversity"
        ),
        "ssi_component": "build_relationships",
    },
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class CategoryPrediction:
    """A single category prediction with confidence score."""

    category: str
    confidence: float
    description: str
    ssi_component: str


@dataclass
class ClassificationResult:
    """Result of classifying one text item."""

    text_hash: str
    predictions: list[CategoryPrediction]
    processing_time_ms: float
    primary_category: str = ""
    primary_ssi_component: str = ""

    def __post_init__(self) -> None:
        if self.predictions and not self.primary_category:
            self.primary_category = self.predictions[0].category
            self.primary_ssi_component = self.predictions[0].ssi_component

    @property
    def top_category(self) -> Optional[CategoryPrediction]:
        """Return the highest-confidence category, or None if empty."""
        return self.predictions[0] if self.predictions else None

    @property
    def top_confidence(self) -> float:
        """Return the confidence of the best prediction, or 0.0."""
        return self.predictions[0].confidence if self.predictions else 0.0


@dataclass
class CategoryMetadata:
    """Internal metadata for a registered category."""

    name: str
    description: str
    ssi_component: str
    custom: bool = False
    embedding: "Optional[np.ndarray]" = field(default=None, repr=False)  # type: ignore[name-defined]


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------


class Model2VecService:
    """
    Fast static embedding-based text classifier.

    Uses minishlab/potion-base-8M to embed both the input text and each
    category description, then ranks categories by cosine similarity.

    Degrades gracefully when model2vec is not installed — all classification
    methods return empty results so the rest of the pipeline is unaffected.
    """

    def __init__(
        self,
        model_name: str = MODEL2VEC_MODEL_NAME,
        confidence_threshold: float = MODEL2VEC_CONFIDENCE_THRESHOLD,
        batch_size: int = MODEL2VEC_BATCH_SIZE,
    ) -> None:
        self._model_name = model_name
        self._confidence_threshold = confidence_threshold
        self._batch_size = batch_size
        self._model: "Optional[StaticModel]" = None  # type: ignore[name-defined]
        self._categories: dict[str, CategoryMetadata] = {}
        self._initialized = False

        if MODEL2VEC_ENABLED and _MODEL2VEC_AVAILABLE:
            self._register_default_categories()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _load_model(self) -> bool:
        """Lazy-load the Model2Vec model on first use."""
        if self._initialized:
            return self._model is not None

        if not _MODEL2VEC_AVAILABLE:
            logger.debug("model2vec not installed — classification disabled")
            self._initialized = True
            return False

        if not MODEL2VEC_ENABLED:
            logger.debug("MODEL2VEC_ENABLED=false — classification disabled")
            self._initialized = True
            return False

        try:
            t0 = time.time()
            if not _MODEL2VEC_AVAILABLE:
                return False
            assert StaticModel is not None
            self._model = StaticModel.from_pretrained(self._model_name)
            
            elapsed = time.time() - t0
            logger.info(
                "Model2Vec: loaded '%s' in %.1fs", self._model_name, elapsed
            )
            # Pre-compute category embeddings now that the model is ready
            self._compute_all_embeddings()
            self._initialized = True
            return True
        except Exception as exc:
            logger.warning(
                "Model2Vec: model load failed ('%s'): %s — classification disabled",
                self._model_name,
                exc,
            )
            self._initialized = True
            return False

    def _register_default_categories(self) -> None:
        """Populate internal category registry from DEFAULT_CATEGORIES."""
        for name, meta in DEFAULT_CATEGORIES.items():
            self._categories[name] = CategoryMetadata(
                name=name,
                description=meta["description"],
                ssi_component=meta["ssi_component"],
                custom=False,
            )

    def _compute_all_embeddings(self) -> None:
        """Compute embeddings for every registered category."""
        if self._model is None:
            return
        for cat in self._categories.values():
            if cat.embedding is None:
                try:
                    cat.embedding = self._model.encode([cat.description])[0]
                except Exception as exc:
                    logger.debug(
                        "Model2Vec: embedding failed for category '%s': %s",
                        cat.name,
                        exc,
                    )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: "np.ndarray", b: "np.ndarray") -> float:  # type: ignore[name-defined]
        """Compute cosine similarity between two vectors."""
        try:
            import numpy as np_local
        except ImportError:
            raise RuntimeError("numpy is required for cosine similarity")
        
        norm_a = float(np_local.linalg.norm(a))
        norm_b = float(np_local.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np_local.dot(a, b) / (norm_a * norm_b))

    @staticmethod
    def _text_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]

    def _predict_for_embedding(
        self, text_embedding: "np.ndarray", top_k: int  # type: ignore[name-defined]
    ) -> list[CategoryPrediction]:
        """Score all categories against a pre-computed text embedding."""
        scored: list[tuple[float, CategoryMetadata]] = []
        for cat in self._categories.values():
            if cat.embedding is None:
                continue
            sim = self._cosine_similarity(text_embedding, cat.embedding)
            if sim >= self._confidence_threshold:
                scored.append((sim, cat))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            CategoryPrediction(
                category=cat.name,
                confidence=round(score, 4),
                description=cat.description,
                ssi_component=cat.ssi_component,
            )
            for score, cat in scored[:top_k]
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_text(
        self, text: str, top_k: int = 3
    ) -> ClassificationResult:
        """Classify a single text string.

        Returns a ClassificationResult with up to *top_k* predictions sorted
        by descending confidence.  Returns an empty result on failure.
        """
        if not text or not text.strip():
            return ClassificationResult(
                text_hash="",
                predictions=[],
                processing_time_ms=0.0,
            )

        if not self._load_model() or self._model is None:
            return ClassificationResult(
                text_hash=self._text_hash(text),
                predictions=[],
                processing_time_ms=0.0,
            )

        t0 = time.time()
        try:
            embedding = self._model.encode([text[:2000]])[0]
            predictions = self._predict_for_embedding(embedding, top_k)
            elapsed_ms = (time.time() - t0) * 1000
            return ClassificationResult(
                text_hash=self._text_hash(text),
                predictions=predictions,
                processing_time_ms=round(elapsed_ms, 2),
            )
        except Exception as exc:
            logger.debug("Model2Vec: classify_text failed: %s", exc)
            elapsed_ms = (time.time() - t0) * 1000
            return ClassificationResult(
                text_hash=self._text_hash(text),
                predictions=[],
                processing_time_ms=round(elapsed_ms, 2),
            )

    def batch_classify(
        self, texts: list[str], top_k: int = 1
    ) -> list[ClassificationResult]:
        """Classify multiple texts efficiently in batches.

        Returns a list of ClassificationResult in the same order as *texts*.
        Empty results are returned for any item that fails.
        """
        if not texts:
            return []

        if not self._load_model() or self._model is None:
            return [
                ClassificationResult(
                    text_hash=self._text_hash(t),
                    predictions=[],
                    processing_time_ms=0.0,
                )
                for t in texts
            ]

        results: list[ClassificationResult] = []
        t0_all = time.time()

        for batch_start in range(0, len(texts), self._batch_size):
            batch = texts[batch_start : batch_start + self._batch_size]
            truncated = [t[:2000] if t else "" for t in batch]
            try:
                t0 = time.time()
                embeddings = self._model.encode(truncated)
                elapsed_ms = (time.time() - t0) * 1000 / max(len(batch), 1)

                for text, embedding in zip(batch, embeddings):
                    preds = self._predict_for_embedding(embedding, top_k)
                    results.append(
                        ClassificationResult(
                            text_hash=self._text_hash(text),
                            predictions=preds,
                            processing_time_ms=round(elapsed_ms, 2),
                        )
                    )
            except Exception as exc:
                logger.debug(
                    "Model2Vec: batch_classify failed for batch %d: %s",
                    batch_start,
                    exc,
                )
                for text in batch:
                    results.append(
                        ClassificationResult(
                            text_hash=self._text_hash(text),
                            predictions=[],
                            processing_time_ms=0.0,
                        )
                    )

        elapsed_total_ms = (time.time() - t0_all) * 1000
        logger.debug(
            "Model2Vec: batch_classify %d texts in %.1fms",
            len(texts),
            elapsed_total_ms,
        )
        return results

    def add_category(self, name: str, description: str, ssi_component: str = "engage_with_insights") -> bool:
        """Add a custom category with the given description.

        Returns True on success, False if the name already exists or
        if the model is unavailable.
        """
        if name in self._categories:
            logger.warning(
                "Model2Vec: category '%s' already exists — use a unique name",
                name,
            )
            return False

        cat = CategoryMetadata(
            name=name,
            description=description,
            ssi_component=ssi_component,
            custom=True,
        )

        if self._load_model() and self._model is not None:
            try:
                cat.embedding = self._model.encode([description])[0]
            except Exception as exc:
                logger.warning(
                    "Model2Vec: could not embed category '%s': %s", name, exc
                )

        self._categories[name] = cat
        logger.info("Model2Vec: added custom category '%s'", name)
        return True

    def batch_add_categories(
        self, categories: list[dict[str, str]]
    ) -> list[bool]:
        """Bulk-add multiple categories.

        Each dict must have 'name' and 'description' keys; 'ssi_component'
        is optional (defaults to 'engage_with_insights').
        Returns a list of booleans in the same order as *categories*.
        """
        results = []
        for cat_def in categories:
            name = cat_def.get("name", "").strip()
            description = cat_def.get("description", "").strip()
            ssi = cat_def.get("ssi_component", "engage_with_insights")
            if not name or not description:
                logger.warning(
                    "Model2Vec: skipping category with missing name/description: %s",
                    cat_def,
                )
                results.append(False)
                continue
            results.append(self.add_category(name, description, ssi))
        return results

    def remove_categories(self, names: list[str]) -> list[bool]:
        """Remove categories by name.

        Default (non-custom) categories cannot be removed.
        Returns a boolean per name indicating success.
        """
        results = []
        for name in names:
            cat = self._categories.get(name)
            if cat is None:
                logger.warning(
                    "Model2Vec: category '%s' not found — skipping", name
                )
                results.append(False)
            elif not cat.custom:
                logger.warning(
                    "Model2Vec: default category '%s' cannot be removed", name
                )
                results.append(False)
            else:
                del self._categories[name]
                logger.info("Model2Vec: removed custom category '%s'", name)
                results.append(True)
        return results

    def list_categories(self) -> dict[str, dict[str, str]]:
        """Return all registered categories with metadata."""
        return {
            name: {
                "description": cat.description,
                "ssi_component": cat.ssi_component,
                "custom": str(cat.custom),
            }
            for name, cat in self._categories.items()
        }

    def is_available(self) -> bool:
        """Return True if the model can be used for classification."""
        return _MODEL2VEC_AVAILABLE and MODEL2VEC_ENABLED


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_SERVICE_INSTANCE: Optional[Model2VecService] = None


def get_model2vec_service() -> Model2VecService:
    """Return a shared Model2VecService singleton."""
    global _SERVICE_INSTANCE
    if _SERVICE_INSTANCE is None:
        _SERVICE_INSTANCE = Model2VecService()
    return _SERVICE_INSTANCE


def classify_article(article: dict, top_k: int = 1) -> ClassificationResult:
    """Classify an article dict (with 'title' and 'summary' keys).

    Convenience wrapper used by the content curation pipeline.
    """
    text = f"{article.get('title', '')} {article.get('summary', '')}".strip()
    svc = get_model2vec_service()
    result = svc.classify_text(text, top_k=top_k)
    return result


def batch_classify_articles(
    articles: list[dict], top_k: int = 1
) -> list[ClassificationResult]:
    """Batch-classify a list of article dicts.

    Convenience wrapper used by the content curation pipeline.
    """
    texts = [
        f"{a.get('title', '')} {a.get('summary', '')}".strip()
        for a in articles
    ]
    svc = get_model2vec_service()
    return svc.batch_classify(texts, top_k=top_k)
