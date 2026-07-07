"""
Curator configuration — RSS feeds, keyword lists, SSI weights, and env constants.
All values are resolved once at import time from environment variables.
"""

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# General curator settings
# ---------------------------------------------------------------------------

CURATOR_MAX_PER_FEED: int = int(os.getenv("CURATOR_MAX_PER_FEED", "10"))

IDEAS_CACHE_PATH = Path(os.getenv("IDEAS_CACHE_PATH", "data/published_ideas_cache.json"))

# ---------------------------------------------------------------------------
# RSS feeds — override via CURATOR_RSS_FEEDS in .env as a JSON array
# ---------------------------------------------------------------------------

_DEFAULT_RSS_FEEDS: list = [
    # LLM / AI research
    {"name": "Anthropic Blog",              "url": "https://www.anthropic.com/rss.xml"},
    {"name": "Hugging Face Blog",           "url": "https://huggingface.co/blog/feed.xml"},
    {"name": "The Batch (DeepLearning.AI)", "url": "https://www.deeplearning.ai/the-batch/feed/"},
    {"name": "Google AI Blog",              "url": "https://blog.research.google/atom.xml"},
    {"name": "AWS Machine Learning",        "url": "https://aws.amazon.com/blogs/machine-learning/feed/"},
    {"name": "LangChain Blog",              "url": "https://blog.langchain.dev/rss/"},
    {"name": "DeepMind Blog",               "url": "https://deepmind.com/blog/feed/basic/"},
    {"name": "OpenAI Blog",                 "url": "https://openai.com/blog/rss.xml"},
    # Search / graph / data engineering
    {"name": "Elastic Blog",                "url": "https://www.elastic.co/blog/feed"},
    {"name": "Neo4j Blog",                  "url": "https://neo4j.com/blog/feed/"},
    {"name": "TigerGraph Blog",             "url": "https://www.tigergraph.com/feed/"},
    # Java / Spring ecosystem
    {"name": "Spring Blog",                 "url": "https://spring.io/blog.atom"},
    {"name": "Vaadin Blog",                 "url": "https://vaadin.com/blog/rss.xml"},
    {"name": "Inside Java",                 "url": "https://inside.java/feed.xml"},
    {"name": "InfoQ",                       "url": "https://feed.infoq.com/"},
    {"name": "Baeldung",                    "url": "https://feeds.feedburner.com/Baeldung"},
    {"name": "JetBrains Blog",              "url": "https://blog.jetbrains.com/feed/"},
    # Event-driven / messaging / multi-agent
    {"name": "Solace Blog",                 "url": "https://solace.com/blog/feed/"},
    {"name": "Confluent Blog",              "url": "https://www.confluent.io/blog/feed/"},
    {"name": "Apache Pulsar Blog",          "url": "https://pulsar.apache.org/blog/index.xml"},
    {"name": "Temporal Blog",               "url": "https://temporal.io/blog/rss.xml"},
    {"name": "Prefect Blog",                "url": "https://www.prefect.io/blog/rss.xml"},
    # ML engineering & RL
    {"name": "Towards Data Science",        "url": "https://towardsdatascience.com/feed"},
    {"name": "PyTorch Blog",                "url": "https://pytorch.org/blog/feed.xml"},
    # Cloud / Infra
    {"name": "AWS Open Source Blog",        "url": "https://aws.amazon.com/blogs/opensource/feed/"},
    {"name": "Google Cloud Blog",           "url": "https://cloud.google.com/blog/topics/developers-practitioners/rss.xml"},
    # GovTech / broader tech
    {"name": "Apolitical",                  "url": "https://apolitical.co/en/feeds/articles"},
    {"name": "The New Stack",               "url": "https://thenewstack.io/feed/"},
    {"name": "Dr. Ben Goretzel",               "url": "https://bengoertzel.substack.com/feed"},
]

_rss_env = os.getenv("CURATOR_RSS_FEEDS", "")
RSS_FEEDS: list = json.loads(_rss_env) if _rss_env.strip() else _DEFAULT_RSS_FEEDS

# ---------------------------------------------------------------------------
# Keywords — override via CURATOR_KEYWORDS in .env as a comma-separated list
# ---------------------------------------------------------------------------

_DEFAULT_KEYWORDS: list = [
    # LLM / RAG / search — core domain
    "RAG", "retrieval augmented", "LLM", "large language model", "language model",
    "vector search", "hybrid search", "semantic search", "information retrieval",
    "embeddings", "BM25", "kNN", "sentence transformer", "context engineering",
    "elasticsearch", "Solr", "Lucene",
    # Graph / knowledge
    "neo4j", "knowledge graph", "graph database", "graph traversal",
    "vector database",
    # Agents / MCP / orchestration
    "agent", "multi-agent", "MCP", "model context protocol", "FastMCP",
    "agentic", "agentic AI", "tool calling", "function calling",
    # GovTech / regulated AI
    "government AI", "GovTech", "regulatory AI", "compliance AI", "public sector AI",
    # Java / Spring ecosystem
    "Spring AI", "Spring Boot", "Spring Batch", "Java 21", "virtual thread",
    "Java AI", "JMS", "message queue",
    # Event-driven / messaging
    "Solace", "PubSub+", "event broker", "FastMCP",
    # RL / ML engineering
    "reinforcement learning", "Gymnasium", "Stable-Baselines", "reward function",
    "scikit-learn", "feature engineering", "NLP", "neural network",
    # Additional AI / ML tooling
    "Ollama", "Groq", "OpenRouter", "Perplexity AI", "Vaadin", "Supabase",
    "ElevenLabs", "text to speech", "generative media",
    "FastAPI",
]

_kw_env = os.getenv("CURATOR_KEYWORDS", "")
KEYWORDS: list = [k.strip() for k in _kw_env.split(",") if k.strip()] if _kw_env.strip() else _DEFAULT_KEYWORDS

# ---------------------------------------------------------------------------
# SSI post-type focus weights and topic hints
# ---------------------------------------------------------------------------

_SSI_WEIGHTS: dict[str, float] = {
    "establish_brand":      float(os.getenv("SSI_FOCUS_ESTABLISH_BRAND",      "25")),
    "find_right_people":    float(os.getenv("SSI_FOCUS_FIND_RIGHT_PEOPLE",    "27")),
    "engage_with_insights": float(os.getenv("SSI_FOCUS_ENGAGE_WITH_INSIGHTS", "24")),
    "build_relationships":  float(os.getenv("SSI_FOCUS_BUILD_RELATIONSHIPS",  "24")),
}

_SSI_TOPIC_HINTS: dict[str, set[str]] = {
    "establish_brand":      {"nlp", "spacy", "bm25", "rag", "graph", "knowledge"},
    "find_right_people":    {"community", "developer", "platform", "tools", "ecosystem"},
    "engage_with_insights": {"anthropic", "openai", "llm", "agent", "aiops", "aws"},
    "build_relationships":  {"team", "culture", "leadership", "hiring", "lessons"},
}
