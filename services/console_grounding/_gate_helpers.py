"""Internal helpers for the truth gate: regex constants, BM25/token scoring,
Jaccard overlap, EvidencePath builders, spaCy org extraction, and avatar
state loaders."""

from __future__ import annotations

import logging
import re

from services.console_grounding._models import ProjectFact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BM25 optional import
# ---------------------------------------------------------------------------

try:
    from rank_bm25 import BM25Okapi as _BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BM25_AVAILABLE = False

# ---------------------------------------------------------------------------
# Regex constants for claim detection
# ---------------------------------------------------------------------------

_NUMERIC_CLAIM_RE = re.compile(
    r"\d+(?:\.\d+)?(?:\s*[%x×]"
    r"|\s*(?:percent|million|billion|thousand|ms|seconds?|minutes?|hours?)"
    r"|\s*(?:faster|slower|reduction|improvement|increase|decrease)"
    r")",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_DOLLAR_RE = re.compile(r"\$\s?\d")

# Company-name heuristic: two+ capitalised words preceded by a preposition.
# spaCy NER (Part D) supersedes this when available.
_ORG_NAME_RE = re.compile(
    r"\b(?:at|for|with|from|joined)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# ---------------------------------------------------------------------------
# Avatar state loaders (lazy — avoids circular import)
# ---------------------------------------------------------------------------

def get_domain_facts_from_avatar_state() -> list[ProjectFact]:
    """Load domain facts from avatar state for use as evidence in the truth gate."""
    try:
        from services.avatar_intelligence import (
            load_avatar_state,
            normalize_domain_facts,
            domain_facts_to_project_facts,
        )
        state = load_avatar_state()
        if not state.domain_knowledge:
            return []
        return domain_facts_to_project_facts(normalize_domain_facts(state))
    except Exception as exc:
        logger.debug("Failed to load domain facts: %s", exc)
        return []


def get_all_persona_facts_from_avatar_state() -> list[ProjectFact]:
    """Load *all* persona/evidence facts for token allowlisting.

    Used so that numeric claims established anywhere in the persona are never
    blocked by the truth gate, regardless of the top-N retrieved for the article.
    """
    try:
        from services.avatar_intelligence import (
            load_avatar_state,
            normalize_evidence_facts,
            evidence_facts_to_project_facts,
        )
        state = load_avatar_state()
        return evidence_facts_to_project_facts(normalize_evidence_facts(state))
    except Exception as exc:
        logger.debug("Failed to load all persona facts for allowlist: %s", exc)
        return []


def get_project_names_from_avatar_state() -> set[str]:
    """Return all lowercased project names and aliases from the persona graph.

    Used by the truth gate so spaCy ORG entities that are substrings of a
    known project name (or alias) are never flagged as unsupported_org.
    """
    try:
        from services.avatar_intelligence import load_avatar_state

        state = load_avatar_state()
        names: set[str] = set()
        if not state.persona_graph:
            return names
        for proj in getattr(state.persona_graph, "projects", []):
            raw_name = getattr(proj, "name", None)
            if raw_name:
                names.add(raw_name.lower())
            for alias in getattr(proj, "aliases", []):
                if alias:
                    names.add(alias.lower())
        return names
    except Exception as exc:
        logger.debug("Failed to load project names from avatar state: %s", exc)
        return set()

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def _tokenize_for_bm25(text: str) -> list[str]:
    """Lemmatized, language-aware tokens for BM25 scoring."""
    from services.spacy_nlp import tokenize_for_search

    return tokenize_for_search(text)


def build_bm25_index(article_text: str, facts: list[ProjectFact]) -> Any:
    """Tokenize the evidence corpus and build a BM25 index once.

    Returns None when BM25 or the corpus is unavailable.
    """
    if not _BM25Okapi:
        return None
    corpus_docs: list[str] = [article_text] + [
        f"{f.project} {f.company} {f.years} {f.details}" for f in facts
    ]
    if not any(d.strip() for d in corpus_docs):
        return None
    try:
        from services.spacy_nlp import tokenize_many_for_search

        tokenized_corpus = tokenize_many_for_search(corpus_docs)
        return _BM25Okapi(tokenized_corpus)
    except Exception as exc:
        logger.debug("BM25 index build failed: %s", exc)
        return None


def _build_allowed_tokens(article_text: str, facts: list[ProjectFact]) -> set[str]:
    """Build a set of lowercased tokens considered 'allowed' evidence."""
    allowed: set[str] = set()
    sources = [article_text]
    for f in facts:
        sources.append(f"{f.project} {f.company} {f.years} {f.details}")
    for src in sources:
        for m in re.finditer(r"\d[\d,.*]*\w*", src):
            allowed.add(m.group(0).lower().rstrip("."))
        for m in re.finditer(r"(19|20)\d{2}(?:\s*[-–]\s*(19|20)?\d{2})?", src):
            allowed.add(m.group(0).replace(" ", "").lower())
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", src):
            allowed.add(m.group(0).lower())
        for w in re.findall(r"\b\w{3,}\b", src):
            allowed.add(w.lower())
    return allowed


def _build_project_tech_map(
    facts: list[ProjectFact],
    article_text: str,
) -> dict[str, str]:
    """Map each project name (lowercased) to its concatenated evidence text."""
    article_lower = article_text.lower()
    return {
        fact.project.lower(): f"{fact.project} {fact.details}".lower() + " " + article_lower
        for fact in facts
    }


def _check_project_claim(
    sentence: str,
    project_map: dict[str, str],
    tech_keywords: set[str],
) -> str | None:
    """Return a reason string if the sentence falsely links a tech to a project.

    A keyword is only flagged as a false attribution when it appears in the
    sentence alongside project_name AND no other project mentioned in the same
    sentence already accounts for that keyword.  This prevents false positives
    in sentences that mention multiple projects where one legitimately owns the
    tech (e.g. "Answer42's Spring Batch … while LinkedIn SSI Booster does X").
    """
    sent_lower = sentence.lower()
    for project_name, evidence_text in project_map.items():
        if project_name not in sent_lower:
            continue
        for kw in tech_keywords:
            if kw not in sent_lower or kw in evidence_text:
                continue
            # Before flagging: check if another project mentioned in this
            # sentence already owns this keyword in its evidence.
            other_project_owns = any(
                other_name != project_name
                and other_name in sent_lower
                and kw in other_evidence
                for other_name, other_evidence in project_map.items()
            )
            if other_project_owns:
                continue
            return (
                f"project_claim: '{kw}' attributed to "
                f"'{project_name}' but not in its detail or article"
            )
    return None

# ---------------------------------------------------------------------------
# BM25 sentence scoring
# ---------------------------------------------------------------------------

def _score_sentence_bm25(
    sentence: str,
    article_text: str,
    facts: list[ProjectFact],
    index: Any | None = None,
) -> float:
    """Score a sentence against article text and persona facts using BM25.

    Pass *index* from :func:`build_bm25_index` to avoid re-tokenizing the whole
    corpus for every sentence.
    """
    if not _BM25_AVAILABLE:
        return 0.0
    try:
        bm25 = index if index is not None else build_bm25_index(article_text, facts)
        if bm25 is None:
            return 0.0
        sentence_tokens = _tokenize_for_bm25(sentence)
        if not sentence_tokens:
            return 0.0
        scores = bm25.get_scores(sentence_tokens)
        return float(max(scores)) if len(scores) > 0 else 0.0
    except Exception as exc:
        logger.debug("BM25 scoring failed for sentence: %s", exc)
        return 0.0

# ---------------------------------------------------------------------------
# Jaccard overlap + EvidencePath builder
# ---------------------------------------------------------------------------

def _compute_fact_overlap(sentence_tokens: set[str], fact_tokens: set[str]) -> float:
    """Compute Jaccard token overlap between sentence and fact token sets.

    Returns a value in [0, 1].  Returns 0.0 when either set is empty.  A
    non-zero overlap activates the 4-term DoT formula instead of the 3-term
    fallback.
    """
    if not sentence_tokens or not fact_tokens:
        return 0.0
    intersection = len(sentence_tokens & fact_tokens)
    union = len(sentence_tokens | fact_tokens)
    return intersection / union if union > 0 else 0.0


def _build_evidence_paths_for_sentence(
    sentence: str,
    all_facts: list[ProjectFact],
) -> list:  # list[EvidencePath] — type not imported at module level to avoid circular deps
    """Build EvidencePath objects for a sentence with overlap and source annotation.

    Part A implementation: computes Jaccard token overlap between the sentence and
    each fact's text so the 4-term DoT formula activates when overlap > 0.

    Returns an empty list when DoT is not importable or no facts are provided.
    """
    if not all_facts:
        return []
    try:
        from services.derivative_of_truth import (
            EvidencePath,
            EVIDENCE_TYPE_PRIMARY,
            EVIDENCE_TYPE_SECONDARY,
            REASONING_TYPE_LOGICAL,
            REASONING_TYPE_STATISTICAL,
        )
    except ImportError:
        return []

    sent_tokens = set(_tokenize_for_bm25(sentence))
    paths = []
    for fact in all_facts:
        fact_tokens = set(_tokenize_for_bm25(f"{fact.project} {fact.details}"))
        overlap = _compute_fact_overlap(sent_tokens, fact_tokens)
        src_lower = fact.source.lower()
        if src_lower.startswith("profile_context") or src_lower.startswith("avatar:"):
            evidence_type, credibility = EVIDENCE_TYPE_PRIMARY, 0.90
        elif src_lower.startswith("domain:"):
            evidence_type, credibility = EVIDENCE_TYPE_SECONDARY, 0.70
        elif src_lower.startswith("katzilla:"):
            evidence_type, credibility = EVIDENCE_TYPE_SECONDARY, 0.55
        else:
            evidence_type, credibility = EVIDENCE_TYPE_SECONDARY, 0.60
        tag_set = {t.lower() for t in fact.tags}
        if any(t in tag_set for t in ("statistics", "benchmark", "performance", "measured", "data")):
            reasoning_type = REASONING_TYPE_STATISTICAL
        else:
            reasoning_type = REASONING_TYPE_LOGICAL
        paths.append(
            EvidencePath(
                source=fact.source,
                evidence_type=evidence_type,
                reasoning_type=reasoning_type,
                credibility=credibility,
                overlap=overlap,
            )
        )
    return paths

# ---------------------------------------------------------------------------
# spaCy ORG extraction
# ---------------------------------------------------------------------------

# Abbreviations / short tokens that are concepts, services, or protocols —
# never company names — even when spaCy's NER tags them as ORG.
_CONCEPT_ABBREVS: frozenset[str] = frozenset({
    # AI / ML concepts
    "AGI", "AI", "ML", "DL", "NLP", "LLM", "LLMs", "RAG", "RL", "RLHF",
    "API", "APIs", "SDK", "CLI", "UI", "UX", "DB", "SQL", "NoSQL",
    "CI", "CD", "DevOps", "AIOps", "MLOps", "DataOps", "FinOps", "SRE", "SLA", "SLO",
    "IoT", "AR", "VR", "XR",
    # AWS services
    "S3", "EC2", "RDS", "ECS", "EKS", "IAM", "VPC", "SNS", "SQS",
    "SageMaker", "Lambda", "CloudFront", "DynamoDB", "EMR", "ECR",
    # GCP services
    "GCS", "BigQuery", "Dataflow", "GKE",
    # Azure services
    "AKS",
    # Protocols / web standards
    "REST", "gRPC", "OAuth", "JWT", "HTTPS", "HTTP",
    "GraphQL", "OpenAPI", "Swagger", "YAML", "JSON", "XML", "CSV",
    # Compound tech qualifiers (appear as part of multi-word ORG entities)
    "Q&A",
})

# Programming-language / platform names that, when followed by a version number,
# should never be treated as an organisation (e.g. "Java 21", "Python 3.12").
_TECH_VERSION_PREFIXES: frozenset[str] = frozenset({
    "Java", "Python", "Kotlin", "Scala", "Go", "Rust", "Node",
    "TypeScript", "JavaScript", "Swift", "Ruby", "PHP", "Perl",
    "Spring", "Django", "FastAPI", "Flask", "Rails",
    "Docker", "Kubernetes", "Terraform",
    "Ubuntu", "Debian", "CentOS", "Alpine",
    "Android", "iOS",
})

# Matches "<word> <digit...>" — used to detect tech-version entities.
_TECH_VERSION_RE = re.compile(r"^\S+\s+\d")


def _extract_spacy_orgs(sentence: str, spacy_nlp: object) -> list[str]:
    """Extract ORG named entities from a sentence using spaCy NER.

    Part D implementation: returns a list of org-name strings (original case).
    Returns an empty list when spaCy is unavailable or the model has no NER.
    Callers fall back to ``_ORG_NAME_RE`` regex when this returns [].

    Filters out:
    - Known AI/tech concept abbreviations (AGI, LLM, S3, etc.)
    - Multi-word ORG entities that contain a concept token (e.g. "AI Q&A")
    - Tech-name + version-number entities (e.g. "Java 21", "Python 3.12")
    """
    try:
        nlp = spacy_nlp._ensure_model()  # type: ignore[union-attr]
        if nlp is None:
            return []
        doc = nlp(sentence)
        result = []
        for ent in doc.ents:
            if ent.label_ != "ORG":
                continue
            # Exact match against known concepts/services
            if ent.text in _CONCEPT_ABBREVS:
                continue
            # Multi-word entity that contains a concept token (e.g. "AI Q&A")
            if any(tok in _CONCEPT_ABBREVS for tok in ent.text.split()):
                continue
            # Tech name + version number (e.g. "Java 21", "Python 3.12")
            if (
                _TECH_VERSION_RE.match(ent.text)
                and ent.text.split()[0] in _TECH_VERSION_PREFIXES
            ):
                continue
            result.append(ent.text)
        return result
    except Exception as exc:
        logger.debug("spaCy org extraction failed: %s", exc)
        return []
