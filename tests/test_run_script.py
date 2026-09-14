"""Tests for the Docker Compose launcher."""

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_one_off_app_run_rebuilds_image(tmp_path: Path) -> None:
    """One-off app commands must include current source copied into the image."""
    captured_args = tmp_path / "docker-args.txt"
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$@" > "$CAPTURED_DOCKER_ARGS"\n',
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{tmp_path}:{environment['PATH']}"
    environment["CAPTURED_DOCKER_ARGS"] = str(captured_args)

    result = subprocess.run(
        [
            "bash",
            "run.sh",
            "--profile",
            "core",
            "run",
            "--rm",
            "app",
            "python",
            "main.py",
            "--rei-generate",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    docker_args = captured_args.read_text(encoding="utf-8").splitlines()
    run_index = docker_args.index("run")
    assert docker_args[run_index + 1 : run_index + 4] == ["--build", "--rm", "app"]