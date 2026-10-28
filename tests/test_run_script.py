"""Offline-safe launcher and model-initializer behavior with fake Docker/Ollama."""

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--profile", "core", "run", "--rm", "app", "python", "main.py", "--rei-preview"],
        ["--profile", "core", "run", "--build", "--rm", "app", "python", "main.py"],
        ["--profile", "full", "up", "-d"],
        ["--profile", "core", "up", "--build", "-d"],
        ["--profile", "core", "build", "app"],
        ["--profile", "core", "run", "--pull", "never", "--name", "a run", "app", "echo", "run"],
    ],
)
def test_launcher_preserves_compose_arguments(tmp_path: Path, arguments: list[str]) -> None:
    captured_args = tmp_path / "docker-args.txt"
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = info ]; then echo nvidia; exit 0; fi\n'
        'if [ "$1" = run ]; then\n'
        '  printf "%s\\n" "$@" > "$CAPTURED_PROBE_ARGS"\n'
        '  exit "${PROBE_EXIT:-0}"\n'
        "fi\n"
        'printf "%s\\n" "$@" > "$CAPTURED_DOCKER_ARGS"\n',
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    nvidia = tmp_path / "nvidia-smi"
    nvidia.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    nvidia.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CAPTURED_DOCKER_ARGS": str(captured_args),
        "CAPTURED_PROBE_ARGS": str(tmp_path / "probe.txt"),
    }

    for probe_exit in ("0", "1"):
        environment["PROBE_EXIT"] = probe_exit
        result = subprocess.run(
            ["bash", "run.sh", *arguments], cwd=PROJECT_ROOT, env=environment,
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        expected = ["compose", "-f", "docker-compose.yml"]
        if probe_exit == "0":
            expected += ["-f", "docker-compose.gpu.yml"]
        else:
            assert "falling back to CPU-only" in result.stdout
        assert captured_args.read_text(encoding="utf-8").splitlines() == expected + arguments
        assert (tmp_path / "probe.txt").read_text().splitlines() == [
            "run", "--pull=never", "--rm", "--gpus", "all",
            "nvidia/cuda:12.4.1-base-ubuntu22.04", "nvidia-smi",
        ]


@pytest.mark.parametrize(
    "cached,fallback,pull_exit,expected,success",
    [
        ("primary fallback", "fallback", "0", ["show primary", "show fallback"], True),
        ("primary", "fallback", "0", ["show primary", "show fallback", "pull fallback"], True),
        ("", "", "0", ["show primary", "pull primary"], True),
        ("", "fallback", "1", ["show primary", "pull primary"], False),
    ],
)
def test_model_init_reuses_cache_and_propagates_pull_failures(
    tmp_path: Path, cached: str, fallback: str, pull_exit: str,
    expected: list[str], success: bool,
) -> None:
    ollama = tmp_path / "ollama"
    ollama.write_text(
        "#!/bin/sh\n"
        'echo "$1 $2" >> "$OLLAMA_CALLS"\n'
        'if [ "$1" = show ]; then\n'
        '  for model in $CACHED_MODELS; do [ "$model" != "$2" ] || exit 0; done\n'
        "  exit 1\n"
        "fi\n"
        'exit "$PULL_EXIT"\n',
        encoding="utf-8",
    )
    ollama.chmod(0o755)
    calls = tmp_path / "calls.txt"
    result = subprocess.run(
        ["sh", "scripts/ensure-ollama-models.sh"], cwd=PROJECT_ROOT,
        env={
            **os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "OLLAMA_CALLS": str(calls), "CACHED_MODELS": cached,
            "PULL_EXIT": pull_exit, "OLLAMA_MODEL": "primary",
            "OLLAMA_MODEL_FALLBACK": fallback,
        },
        capture_output=True, text=True, check=False,
    )
    assert (result.returncode == 0) is success
    assert calls.read_text().splitlines() == expected
    assert ("[ollama-init] Done." in result.stdout) is success
