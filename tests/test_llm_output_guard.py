"""Tests for the garbled-output (token salad) guard and the console chat retry."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from ollama import ChatResponse, Message

from services.llm_output_guard import analyse_garble, looks_garbled
from services.ollama_service import GarbledOutputError, OllamaService

TOKEN_SALAD = (
    "HOWEVER *\n女性朋友帳號$um leftright性价celainparagus10SingleOrDefaultiad年'icon中 \"\");"
    "(coeffscratch)(设计器.requestFocus2 get reap fierc\")\n.ElementAtoes(#)CLUDING%\n"
    " nâ.Once；améli笑了笑 pounds8SingleOrDefaultToLeft *</版权归‘precistrtotime女性朋友rix查看详情性价 "
    "pérdida1Bฉาย:nameacam>>>>>>>相关负责 maç \\Sharper四年ngine'=>\" pérdida什么 tendência后者--[[ynet "
    "máreff Rencontres) strugg tô9 xamarin BusinessExceptionpõe】"
)

CLEAN_REPLIES = [
    "Let's practice a bus trip to the store!\n"
    "バスに乗ります (basu ni norimasu) — I get on the bus.\n"
    "店に行きます (mise ni ikimasu) — I go to the store.\n"
    "The kanji 行 means \"go\" and 店 means \"shop\". 出口 (deguchi) is the exit.",
    "PythonでデータをPandasで処理します。LLMの出力をチェックし、FastAPIのエンドポイントで返します。",
    "I built LinkedIn SSI Booster with SQLAlchemy, NetworkX and PostgreSQL. FastAPI and "
    "LangChain helped early on; GraphQL calls go through BufferService.",
    "Use session.query(User) and call obj.toDict(); getElementById is a DOM method.",
    "J'ai créé un outil pour améliorer le café. Très bien, déjà vu, à côté.",
    "",
]


def test_token_salad_is_flagged() -> None:
    report = analyse_garble(TOKEN_SALAD)
    assert report.is_garbled
    assert report.script_switches > 0 and report.code_tokens > 0
    assert looks_garbled(TOKEN_SALAD)


@pytest.mark.parametrize("text", CLEAN_REPLIES)
def test_clean_replies_are_not_flagged(text: str) -> None:
    assert not looks_garbled(text)


def _response(content: str) -> ChatResponse:
    return ChatResponse(message=Message(role="assistant", content=content))


@pytest.fixture
def ai_client(monkeypatch: pytest.MonkeyPatch) -> tuple[OllamaService, Mock]:
    client = Mock()
    monkeypatch.setattr("services.ollama_service.ollama.Client", Mock(return_value=client))
    ai = OllamaService(model="test-model")
    monkeypatch.setattr(ai, "unload", Mock(return_value=True))
    return ai, client


def test_chat_returns_clean_reply_without_retry(ai_client: tuple[OllamaService, Mock]) -> None:
    ai, client = ai_client
    client.chat.return_value = _response("店に行きます (mise ni ikimasu) — I go to the store.")
    assert ai.chat_as_persona([{"role": "user", "content": "Hi"}]).startswith("店に行きます")
    client.chat.assert_called_once()
    ai.unload.assert_not_called()  # type: ignore[attr-defined]


def test_chat_retries_once_after_cache_reset(ai_client: tuple[OllamaService, Mock]) -> None:
    ai, client = ai_client
    client.chat.side_effect = [_response(TOKEN_SALAD), _response("A clean reply.")]
    assert ai.chat_as_persona([{"role": "user", "content": "Hi"}]) == "A clean reply."
    assert client.chat.call_count == 2
    ai.unload.assert_called_once()  # type: ignore[attr-defined]


def test_chat_raises_clear_error_when_retry_is_also_garbled(
    ai_client: tuple[OllamaService, Mock],
) -> None:
    ai, client = ai_client
    client.chat.return_value = _response(TOKEN_SALAD)
    with pytest.raises(GarbledOutputError, match="garbled output twice"):
        ai.chat_as_persona([{"role": "user", "content": "Hi"}])
    assert client.chat.call_count == 2
