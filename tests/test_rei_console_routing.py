"""Unit tests for Rei Toei console routing integration."""

import asyncio

from unittest.mock import AsyncMock, MagicMock, patch

from services.console_grounding._rei_console import (
    REI_DEFAULT_PROMPT,
    _build_rei_system_prompt,
    _handle_conversation,
    _handle_llm_song_generation,
    _handle_suno_request,
    _extract_song_topic,
    extract_rei_input,
    handle_rei_console,
    is_rei_song_request,
    should_handle_rei_turn,
)


class TestReiConsoleRouting:
    """Test /rei-toei and /rei command routing in console mode."""

    def test_rei_toei_command_parsing(self):
        user_input = "/rei-toei generate a strudel pattern about recursion"
        extracted = user_input[len("/rei-toei"):].strip()
        assert extracted == "generate a strudel pattern about recursion"

    def test_rei_command_parsing(self):
        user_input = "/rei what's your name?"
        extracted = user_input[len("/rei"):].strip()
        assert extracted == "what's your name?"

    def test_rei_toei_empty_message_default(self):
        user_input = "/rei-toei"
        extracted = user_input[len("/rei-toei"):].strip()
        if not extracted:
            extracted = REI_DEFAULT_PROMPT
        assert extracted == REI_DEFAULT_PROMPT

    def test_rei_empty_message_default(self):
        user_input = "/rei"
        extracted = user_input[len("/rei"):].strip()
        if not extracted:
            extracted = REI_DEFAULT_PROMPT
        assert extracted == REI_DEFAULT_PROMPT

    def test_rei_toei_command_routing_logic(self):
        test_cases = [
            ("/rei-toei hello", True, "hello"),
            ("/rei-toei", True, ""),
            ("/rei world", False, "world"),
            ("/rei", False, ""),
            ("/reload", None, None),
            ("generate a song", None, None),
        ]
        for user_input, is_rei_toei, expected_message in test_cases:
            cmd = user_input.lower()
            if cmd.startswith("/rei-toei"):
                assert is_rei_toei is True
                extracted = user_input[len("/rei-toei"):].strip()
                assert extracted == expected_message
            elif cmd.startswith("/rei"):
                assert is_rei_toei is False
                extracted = user_input[len("/rei"):].strip()
                assert extracted == expected_message
            else:
                assert is_rei_toei is None

    def test_rei_command_case_insensitivity(self):
        for user_input in [
            "/rei-toei test",
            "/REI-TOEI test",
            "/Rei-Toei test",
            "/rei test",
            "/REI test",
            "/Rei test",
        ]:
            cmd = user_input.lower()
            assert cmd.startswith("/rei-toei") or cmd.startswith("/rei")

    def test_rei_command_no_conflict_with_known_commands(self):
        known_commands = ["/help", "/reset", "/reload", "/exit", "/verify", "/avatar-explain", "/dot-report", "/graph-stats"]
        rei_commands = ["/rei-toei", "/rei"]
        for rei_cmd in rei_commands:
            for known_cmd in known_commands:
                assert not rei_cmd.startswith(known_cmd)
                assert not known_cmd.startswith(rei_cmd)

    def test_rei_toei_with_whitespace_variations(self):
        for user_input in ["/rei-toei   hello", "/rei-toei\thello", "/rei-toei    "]:
            extracted = user_input[len("/rei-toei"):].strip()
            assert isinstance(extracted, str)

    def test_rei_message_extraction_preserves_content(self):
        user_input = "/rei-toei generate a complex strudel pattern with multiple synths and effects"
        extracted = user_input[len("/rei-toei"):].strip()
        assert "complex" in extracted
        assert "multiple synths" in extracted
        assert "effects" in extracted

    def test_rei_mode_stays_active_for_plain_text_turns(self):
        assert should_handle_rei_turn("can you create me a new song for today?", "rei") is True
        assert should_handle_rei_turn("can you create me a new song for today?", "sam") is False

    def test_rei_mode_does_not_swallow_other_slash_commands(self):
        assert should_handle_rei_turn("/help", "rei") is False
        assert should_handle_rei_turn("/reload", "rei") is False

    def test_extract_rei_input_handles_both_prefixes(self):
        assert extract_rei_input("/rei write a jungle song") == "write a jungle song"
        assert extract_rei_input("/rei-toei write a jungle song") == "write a jungle song"

    def test_song_request_heuristic_matches_genre_plus_generation_verb(self):
        assert is_rei_song_request("create me something jungle for today") is True
        assert is_rei_song_request("write lyrics and style for a new jungle track") is True

    def test_extract_song_topic_prefers_about_clause(self):
        topic = _extract_song_topic("create me a song about competition for a marketing engineer role")
        assert topic is not None
        assert "competition" in topic.lower()

    def test_extract_song_topic_returns_none_for_generic_request(self):
        assert _extract_song_topic("just give me a song") is None
        assert _extract_song_topic("make me a track") is None


def test_handle_rei_console_routes_plain_song_request_to_suno():
    with (
        patch("services.console_grounding._rei_console.load_rei_persona", return_value=MagicMock()),
        patch("services.console_grounding._rei_console.load_rei_domain_knowledge", return_value=MagicMock()),
        patch("services.console_grounding._rei_console.load_strudel_patterns", return_value=MagicMock()),
        patch("services.console_grounding._rei_console._handle_suno_request", new=AsyncMock(return_value=("song", []))) as mock_suno,
        patch("services.console_grounding._rei_console._handle_conversation", new=AsyncMock(return_value=("chat", []))) as mock_chat,
    ):
        reply, _history = asyncio.run(
            handle_rei_console(
                "can you create me a new song for today?",
                MagicMock(),
                [],
            )
        )

    assert reply == "song"
    mock_suno.assert_awaited_once()
    mock_chat.assert_not_called()


# ---------------------------------------------------------------------------
# Rei system-prompt + LLM fallback tests
# ---------------------------------------------------------------------------

class TestReiSystemPrompt:
    """_build_rei_system_prompt should produce Rei-specific text, NOT Sam's profile."""

    def _make_persona(self, name="Rei Toei", role="AI Music Avatar", aesthetic="cyberpunk industrial"):
        p = MagicMock()
        p.identity = {"name": name, "role": role, "aesthetic": aesthetic}
        p.personality_traits = ["precise", "high-energy", "algorithmic"]
        return p

    def _make_domain(self):
        d = MagicMock()
        d.genre_production_techniques = {"jungle": {}, "techno": {}, "industrial": {}}
        return d

    def test_prompt_contains_rei_identity(self):
        prompt = _build_rei_system_prompt(self._make_persona(), self._make_domain())
        assert "Rei Toei" in prompt
        assert "AI Music Avatar" in prompt

    def test_prompt_contains_music_generation_directive(self):
        prompt = _build_rei_system_prompt(self._make_persona(), self._make_domain())
        assert "MUSIC GENERATION" in prompt
        assert "Suno" in prompt

    def test_prompt_never_refuses_audio(self):
        prompt = _build_rei_system_prompt(self._make_persona(), self._make_domain())
        assert "NEVER refuse" in prompt or "NEVER say" in prompt

    def test_prompt_does_not_reference_sam_persona(self):
        """Rei's system prompt must not contain any Sam-specific fragments."""
        from services.shared import PERSONA_SYSTEM_PROMPT
        prompt = _build_rei_system_prompt(self._make_persona(), self._make_domain())
        # The two prompts share no line that starts with "You are" for Sam's identity
        first_line = PERSONA_SYSTEM_PROMPT.strip().split("\n")[0]
        assert first_line not in prompt

    def test_prompt_lists_genre_specialties(self):
        prompt = _build_rei_system_prompt(self._make_persona(), self._make_domain())
        assert "jungle" in prompt or "techno" in prompt


class TestSunoRequestFallback:
    """When no extracted knowledge exists, _handle_suno_request must delegate to LLM."""

    def _persona_and_domain(self):
        return MagicMock(), MagicMock()

    def test_suno_request_falls_back_to_llm_when_no_knowledge(self):
        mock_ai = MagicMock()
        p, d = self._persona_and_domain()

        with (
            patch("services.console_grounding._rei_console._lav_rei_console", return_value=MagicMock()),
            patch("services.console_grounding._rei_console._normalize_extracted_rei", return_value=[]),
            patch(
                "services.console_grounding._rei_console._handle_llm_song_generation",
                new=AsyncMock(return_value=("llm_song", [])),
            ) as mock_llm,
        ):
            reply, _ = asyncio.run(
                _handle_suno_request("create me a jungle song", mock_ai, p, d, [])
            )

        assert reply == "llm_song"
        mock_llm.assert_awaited_once()

    def test_suno_request_falls_back_to_llm_when_no_themes(self):
        mock_ai = MagicMock()
        p, d = self._persona_and_domain()
        fake_facts = [MagicMock()]

        with (
            patch("services.console_grounding._rei_console._lav_rei_console", return_value=MagicMock()),
            patch("services.console_grounding._rei_console._normalize_extracted_rei", return_value=fake_facts),
            patch("services.console_grounding._rei_console.extract_themes", return_value=[]),
            patch(
                "services.console_grounding._rei_console._handle_llm_song_generation",
                new=AsyncMock(return_value=("llm_song_no_themes", [])),
            ) as mock_llm,
        ):
            reply, _ = asyncio.run(
                _handle_suno_request("write me a jungle track", mock_ai, p, d, [])
            )

        assert reply == "llm_song_no_themes"
        mock_llm.assert_awaited_once()

    def test_suno_request_uses_user_topic_when_provided(self):
        mock_ai = MagicMock()
        p, d = self._persona_and_domain()
        fake_facts = [MagicMock()]
        fake_theme = MagicMock(name="theme")
        fake_concept = MagicMock(
            title="T",
            theme="Competition",
            mood="intense",
            bpm=150,
            genre_tags=["Hard Techno"],
        )
        fake_lyrics = MagicMock()
        fake_suno = MagicMock(lyrics="[Verse 1]\nA", suno_prompt="hardtechno, 150 bpm")

        with (
            patch("services.console_grounding._rei_console._lav_rei_console", return_value=MagicMock()),
            patch("services.console_grounding._rei_console._normalize_extracted_rei", return_value=fake_facts),
            patch("services.console_grounding._rei_console.extract_themes", return_value=[fake_theme]),
            patch("services.console_grounding._rei_console.load_recent_rei_titles", return_value=[]),
            patch("services.console_grounding._rei_console.choose_diverse_theme") as mock_choose,
            patch("services.console_grounding._rei_console.generate_song_concept", return_value=fake_concept) as mock_gen,
            patch("services.console_grounding._rei_console.compose_lyrics", return_value=fake_lyrics),
            patch("services.console_grounding._rei_console.assemble_suno_prompt", return_value=fake_suno),
        ):
            reply, _ = asyncio.run(
                _handle_suno_request(
                    "create me a song about competition and ROI pressure",
                    mock_ai,
                    p,
                    d,
                    [],
                )
            )

        # User-directed topic should bypass autonomous theme picking.
        mock_choose.assert_not_called()
        passed_theme = mock_gen.call_args[0][0]
        assert "competition" in passed_theme.name.lower()
        assert "roi" in passed_theme.name.lower()
        assert "Style tags:" in reply

    def test_suno_request_without_topic_lets_rei_choose_theme(self):
        mock_ai = MagicMock()
        p, d = self._persona_and_domain()
        fake_facts = [MagicMock()]
        chosen_theme = MagicMock(name="chosen_theme")
        fake_concept = MagicMock(
            title="T",
            theme="Autonomous",
            mood="intense",
            bpm=150,
            genre_tags=["Hard Techno"],
        )
        fake_lyrics = MagicMock()
        fake_suno = MagicMock(lyrics="[Verse 1]\nA", suno_prompt="hardtechno, 150 bpm")

        with (
            patch("services.console_grounding._rei_console._lav_rei_console", return_value=MagicMock()),
            patch("services.console_grounding._rei_console._normalize_extracted_rei", return_value=fake_facts),
            patch("services.console_grounding._rei_console.extract_themes", return_value=[MagicMock()]),
            patch("services.console_grounding._rei_console.load_recent_rei_titles", return_value=[]),
            patch("services.console_grounding._rei_console.choose_diverse_theme", return_value=chosen_theme) as mock_choose,
            patch("services.console_grounding._rei_console.generate_song_concept", return_value=fake_concept) as mock_gen,
            patch("services.console_grounding._rei_console.compose_lyrics", return_value=fake_lyrics),
            patch("services.console_grounding._rei_console.assemble_suno_prompt", return_value=fake_suno),
        ):
            asyncio.run(
                _handle_suno_request(
                    "just give me a song",
                    mock_ai,
                    p,
                    d,
                    [],
                )
            )

        mock_choose.assert_called_once()
        assert mock_gen.call_args[0][0] is chosen_theme


class TestConversationHandlerRouting:
    """_handle_conversation must re-route song requests and use Rei's own prompt."""

    def test_conversation_re_routes_song_request_to_suno(self):
        mock_ai = MagicMock()
        p, d = MagicMock(), MagicMock()

        with patch(
            "services.console_grounding._rei_console._handle_suno_request",
            new=AsyncMock(return_value=("suno_reply", [])),
        ) as mock_suno:
            reply, _ = asyncio.run(
                _handle_conversation("create me a new song for today", mock_ai, p, d, [], max_tokens=600)
            )

        assert reply == "suno_reply"
        mock_suno.assert_awaited_once()

    def test_conversation_does_not_route_plain_chat_to_suno(self):
        mock_ai = MagicMock()
        p, d = MagicMock(), MagicMock()

        with (
            patch("services.console_grounding._rei_console._handle_suno_request", new=AsyncMock()) as mock_suno,
            patch("services.console_grounding._rei_console._rei_chat", return_value="chat_reply"),
            patch("services.console_grounding._rei_console._build_rei_system_prompt", return_value="sys"),
        ):
            reply, _ = asyncio.run(
                _handle_conversation("what is your aesthetic?", mock_ai, p, d, [], max_tokens=600)
            )

        mock_suno.assert_not_awaited()
        assert reply == "chat_reply"