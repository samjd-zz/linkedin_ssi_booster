"""Tests for language-agnostic theme grouping and Japanese sentence splitting."""

import re

from unittest.mock import Mock

from services.spacy_nlp import SpacyNLP, _rank_themes

# Mirrors the splitter in services/avatar_intelligence/_extraction.py
_SENTENCE_SPLIT = r"(?<=[。！？])\s*|(?<=[.!?])\s+"


def _split(text: str) -> list[str]:
    return [s for s in re.split(_SENTENCE_SPLIT, text) if s]


class TestSentenceSplitting:
    def test_japanese_splits_on_ideographic_full_stop(self):
        text = "imaseが活動を再開した。復帰曲を配信リリース。EPは全8曲を収録。"
        assert _split(text) == [
            "imaseが活動を再開した。",
            "復帰曲を配信リリース。",
            "EPは全8曲を収録。",
        ]

    def test_japanese_splits_on_full_width_bang_and_question(self):
        assert _split("すごい！本当ですか？はい。") == ["すごい！", "本当ですか？", "はい。"]

    def test_english_decimals_are_not_split(self):
        text = "It cost 3.5 million dollars. Version 2.0 landed."
        assert _split(text) == ["It cost 3.5 million dollars.", "Version 2.0 landed."]

    def test_english_behaviour_matches_previous_splitter(self):
        text = "OpenAI shipped GPT-4. It cost 3.5 million. Version 2.0 landed."
        legacy = [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
        assert _split(text) == legacy


class TestRankThemes:
    def test_longest_first_so_truncation_keeps_specific_themes(self):
        ranked = _rank_themes({"10月2日", "配信リリース", "1年"})
        assert ranked[0] == "配信リリース"

    def test_ties_broken_alphabetically_for_determinism(self):
        assert _rank_themes({"bbb", "aaa"}) == ["aaa", "bbb"]

    def test_demoted_themes_sort_last_even_when_longer(self):
        # Japanese dates are longer than most concepts, so length alone is not enough.
        themes = {"2027年1月16日", "2027年1月22日", "レーベル", "配信リリース"}
        ranked = _rank_themes(themes, demoted={"2027年1月16日", "2027年1月22日"})

        assert ranked[:2] == ["配信リリース", "レーベル"]
        assert set(ranked[2:]) == {"2027年1月16日", "2027年1月22日"}


def _engine_with_doc(ents, chunks):
    ent_mocks = []
    for text, label in ents:
        m = Mock()
        m.text = text
        m.label_ = label
        ent_mocks.append(m)
    chunk_mocks = []
    for text in chunks:
        m = Mock()
        m.text = text
        chunk_mocks.append(m)

    doc = Mock()
    doc.ents = ent_mocks
    doc.noun_chunks = chunk_mocks

    engine = SpacyNLP()
    # Patch the router, not _nlp — get_model_for_text would otherwise load a real
    # language-matched pipeline and bypass the mock entirely.
    engine.get_model_for_text = Mock(return_value=Mock(return_value=doc))
    return engine, doc


class TestExtractThemeGroups:
    def test_entities_come_from_ner_concepts_from_noun_chunks(self):
        engine, _ = _engine_with_doc(
            ents=[("OpenAI", "ORG"), ("2024", "DATE")],
            chunks=["machine learning research"],
        )
        groups = engine.extract_theme_groups("text")

        assert "openai" in groups["entities"]
        assert "2024" in groups["entities"]
        assert "machine learning research" in groups["concepts"]

    def test_japanese_concepts_are_not_forced_into_entities_by_lack_of_spaces(self):
        engine, _ = _engine_with_doc(
            ents=[("9月4日", "DATE")],
            chunks=["配信リリース", "レーベル"],
        )
        groups = engine.extract_theme_groups("テキスト")

        assert groups["entities"] == ["9月4日"]
        assert set(groups["concepts"]) == {"配信リリース", "レーベル"}

    def test_named_entities_outrank_dates(self):
        engine, _ = _engine_with_doc(
            ents=[("2027年1月16日", "DATE"), ("ユニバーサル", "ORG")],
            chunks=[],
        )
        assert engine.extract_theme_groups("テキスト")["entities"][0] == "ユニバーサル"

    def test_entity_text_is_not_duplicated_into_concepts(self):
        engine, _ = _engine_with_doc(ents=[("OpenAI", "ORG")], chunks=["OpenAI"])
        groups = engine.extract_theme_groups("text")

        assert groups["entities"] == ["openai"]
        assert "openai" not in groups["concepts"]

    def test_unlabelled_entities_are_ignored(self):
        engine, _ = _engine_with_doc(ents=[("42", "CARDINAL")], chunks=[])
        assert engine.extract_theme_groups("text")["entities"] == []

    def test_missing_noun_chunks_iterator_degrades_to_ner_only(self):
        engine, doc = _engine_with_doc(ents=[("OpenAI", "ORG")], chunks=[])
        type(doc).noun_chunks = property(
            lambda self: (_ for _ in ()).throw(NotImplementedError())
        )
        try:
            groups = engine.extract_theme_groups("text")
            assert groups["entities"] == ["openai"]
            assert groups["concepts"] == []
        finally:
            del type(doc).noun_chunks

    def test_returns_empty_groups_when_spacy_unavailable(self):
        engine = SpacyNLP()
        engine.get_model_for_text = Mock(return_value=None)
        groups = engine.extract_theme_groups("text")

        assert groups == {"entities": [], "concepts": []}

    def test_returns_empty_groups_when_pipeline_raises(self):
        engine = SpacyNLP()
        engine.get_model_for_text = Mock(
            return_value=Mock(side_effect=Exception("spaCy error"))
        )
        assert engine.extract_theme_groups("text") == {"entities": [], "concepts": []}

    def test_extract_themes_still_returns_merged_flat_list(self):
        engine, _ = _engine_with_doc(
            ents=[("OpenAI", "ORG")], chunks=["machine learning research"]
        )
        flat = engine.extract_themes("text")

        assert "openai" in flat
        assert "machine learning research" in flat
