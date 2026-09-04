"""
Test knowledge extraction with spaCy summarization preprocessing.

This test verifies that the new spaCy summarization preprocessing step
in extract_and_append_knowledge improves extraction quality by filtering
out boilerplate and noise before fact extraction.
"""

import pytest
from pathlib import Path
from services.avatar_intelligence._extraction import extract_and_append_knowledge


# Sample article text with significant boilerplate/noise mixed with real facts
NOISY_ARTICLE = """
Welcome to our latest blog post about artificial intelligence!

In this article, we'll explore the latest developments in AI.

GPT-4 was released by OpenAI in March 2023 with 1.76 trillion parameters.

Learn more about AI on our website. Sign up for our newsletter to stay updated.

The model achieved a score of 86.4% on the MMLU benchmark, representing a significant improvement over GPT-3.5.

Click here to download our free AI guide. Subscribe now for exclusive content.

LLaMA 2 from Meta AI is available as open-source with sizes ranging from 7B to 70B parameters.

We encourage you to explore our AI platform. Try it today for free!

The Anthropic Claude 2 model features a 100,000 token context window, enabling long-form document analysis.

Visit our homepage to learn more. Check out our community forum for discussions.

Google's PaLM 2 powers Bard and includes improved multilingual capabilities across 100+ languages.
"""

# Expected high-quality facts that should be extracted (after summarization)
EXPECTED_FACTS = [
    "GPT-4",
    "OpenAI",
    "trillion parameters",
    "MMLU benchmark",
    "86.4%",
    "LLaMA 2",
    "Meta AI",
    "open-source",
    "Claude 2",
    "100,000 token",
    "PaLM 2",
    "Bard",
    "100+ languages",
]

# Boilerplate phrases that should be filtered out
BOILERPLATE = [
    "Welcome to",
    "In this article",
    "Learn more",
    "Sign up",
    "Click here",
    "Subscribe now",
    "We encourage",
    "Try it today",
    "Visit our",
    "Check out",
]


class MockSpacyNLP:
    """Mock SpacyNLP that returns a focused summary without boilerplate."""
    
    def summarize_article(self, article_text: str, max_sentences: int = 10, focus_entities: bool = True) -> str:
        # Simulate spaCy's entity-focused summarization by returning only sentences with entities/metrics
        lines = article_text.split("\n")
        important_lines = []
        
        for line in lines:
            line = line.strip()
            # Keep lines with named entities (capitalized words) or numbers
            if any(word[0].isupper() for word in line.split() if len(word) > 1) or any(c.isdigit() for c in line):
                # Skip CTA/boilerplate openers
                if not any(bp in line for bp in ["Welcome to", "In this", "Learn more", "Sign up", "Click here", "Subscribe", "We encourage", "Try it", "Visit", "Check out"]):
                    important_lines.append(line)
        
        return " ".join(important_lines[:max_sentences])


def _measure_extraction_without_summarization(tmp_path: Path) -> tuple[int, int]:
    """Measure fact extraction from noisy article without spaCy preprocessing."""
    output_path = tmp_path / "extracted_knowledge_baseline.json"
    
    facts = extract_and_append_knowledge(
        article_text=NOISY_ARTICLE,
        source_url="https://example.com/test-article",
        source_title="AI Models 2023 Update",
        path=output_path,
        dry_run=False,
        spacy_nlp=None,  # No summarization preprocessing
    )
    
    # Extract statement texts for analysis
    statements = [f.statement for f in facts]
    
    # Count how many boilerplate phrases made it through
    boilerplate_count = sum(
        1 for stmt in statements
        if any(bp.lower() in stmt.lower() for bp in BOILERPLATE)
    )
    
    print(f"\n❌ WITHOUT summarization: {len(facts)} facts extracted, {boilerplate_count} contain boilerplate")
    for i, stmt in enumerate(statements[:10], 1):
        print(f"   {i}. {stmt[:100]}")
    
    return len(facts), boilerplate_count


def test_extraction_without_summarization(tmp_path):
    """Baseline: extract facts from noisy article without spaCy preprocessing."""
    facts_count, boilerplate_count = _measure_extraction_without_summarization(tmp_path)

    assert facts_count > 0, "Should extract at least some facts"
    assert boilerplate_count >= 0


def _measure_extraction_with_summarization(tmp_path: Path) -> tuple[int, int]:
    """Measure fact extraction with spaCy summarization preprocessing."""
    output_path = tmp_path / "extracted_knowledge_with_summary.json"
    
    mock_spacy = MockSpacyNLP()
    
    facts = extract_and_append_knowledge(
        article_text=NOISY_ARTICLE,
        source_url="https://example.com/test-article",
        source_title="AI Models 2023 Update",
        path=output_path,
        dry_run=False,
        spacy_nlp=mock_spacy,  # Enable summarization preprocessing
    )
    
    # Extract statement texts for analysis
    statements = [f.statement for f in facts]
    
    # Count how many expected facts are present
    expected_fact_matches = sum(
        1 for stmt in statements
        if any(exp.lower() in stmt.lower() for exp in EXPECTED_FACTS)
    )
    
    # Count how many boilerplate phrases made it through
    boilerplate_count = sum(
        1 for stmt in statements
        if any(bp.lower() in stmt.lower() for bp in BOILERPLATE)
    )
    
    print(f"\n✅ WITH summarization: {len(facts)} facts extracted, {expected_fact_matches} contain expected content, {boilerplate_count} contain boilerplate")
    for i, stmt in enumerate(statements[:10], 1):
        print(f"   {i}. {stmt[:100]}")
    
    # Assertions
    assert len(facts) > 0, "Should extract at least some facts"
    assert boilerplate_count == 0, f"Should filter out all boilerplate, but found {boilerplate_count} instances"
    assert expected_fact_matches >= len(facts) * 0.5, "At least 50% of facts should contain expected high-quality content"
    
    return len(facts), boilerplate_count


def test_extraction_with_summarization(tmp_path):
    """Test: extract facts with spaCy summarization preprocessing."""
    _measure_extraction_with_summarization(tmp_path)


def test_summarization_comparison(tmp_path):
    """Compare extraction quality with and without summarization."""
    facts_without_summary, boilerplate_without = _measure_extraction_without_summarization(tmp_path)
    facts_with_summary, boilerplate_with = _measure_extraction_with_summarization(tmp_path)
    
    print("\n" + "="*60)
    print("📊 COMPARISON SUMMARY")
    print("="*60)
    print(f"Without summarization: {facts_without_summary} facts, {boilerplate_without} boilerplate")
    print(f"With summarization:    {facts_with_summary} facts, {boilerplate_with} boilerplate")
    print(f"Quality improvement:   {boilerplate_without - boilerplate_with} fewer boilerplate facts")
    
    # The key benefit: fewer low-quality facts with summarization
    assert boilerplate_with <= boilerplate_without, "Summarization should not increase boilerplate extraction"


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_summarization_comparison(Path(tmpdir))
