"""Tests for thread-safe database singleton engine/session setup."""

from __future__ import annotations

from threading import Thread
from unittest.mock import Mock, patch


def test_get_engine_singleton_under_concurrency(monkeypatch):
    """Concurrent callers should initialize the engine once."""
    from services.database import session as db_session

    db_session._engine = None
    db_session._SessionLocal = None

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/testdb")

    created_engine = Mock(name="engine")
    calls = {"create_engine": 0}

    def fake_create_engine(*args, **kwargs):
        calls["create_engine"] += 1
        return created_engine

    results = []

    with patch("services.database.session.create_engine", side_effect=fake_create_engine), patch(
        "services.database.session._configure_engine_listeners"
    ):
        threads = [Thread(target=lambda: results.append(db_session.get_engine())) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

    assert calls["create_engine"] == 1
    assert len(results) == 8
    assert all(engine is created_engine for engine in results)

    db_session._engine = None
    db_session._SessionLocal = None


def test_get_session_factory_singleton_under_concurrency(monkeypatch):
    """Concurrent callers should initialize the session factory once."""
    from services.database import session as db_session

    db_session._engine = None
    db_session._SessionLocal = None

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/testdb")

    created_engine = Mock(name="engine")
    created_factory = Mock(name="session_factory")

    engine_calls = {"count": 0}
    factory_calls = {"count": 0}

    def fake_create_engine(*args, **kwargs):
        engine_calls["count"] += 1
        return created_engine

    def fake_sessionmaker(*args, **kwargs):
        factory_calls["count"] += 1
        return created_factory

    results = []

    with patch("services.database.session.create_engine", side_effect=fake_create_engine), patch(
        "services.database.session._configure_engine_listeners"
    ), patch("services.database.session.sessionmaker", side_effect=fake_sessionmaker):
        threads = [Thread(target=lambda: results.append(db_session.get_session_factory())) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

    assert engine_calls["count"] == 1
    assert factory_calls["count"] == 1
    assert len(results) == 8
    assert all(factory is created_factory for factory in results)

    db_session._engine = None
    db_session._SessionLocal = None


def test_engine_checkout_listener_registered_on_engine_instance():
    """Engine listener registration should target engine instance, not global Pool."""
    from services.database import session as db_session

    fake_engine = Mock(name="engine")

    with patch("services.database.session.event.listens_for", side_effect=lambda target, name: (lambda fn: fn)) as mocked:
        db_session._configure_engine_listeners(fake_engine)

    # First listener is connect, second should be checkout, both on engine.
    targets = [(args[0], args[1]) for args, _kwargs in mocked.call_args_list]
    assert (fake_engine, "connect") in targets
    assert (fake_engine, "checkout") in targets
