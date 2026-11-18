#!/home/madmax/.local/share/uv/tools/harbor/bin/python
"""Launch Harbor with a fast Docker server check on this WSL host.

Docker Desktop's `docker info` takes >20 seconds here, exceeding Harbor's
10-second preflight limit even though the daemon is healthy. Query the server
version instead; leave all trial execution, task files, and scoring unchanged.
Use as run_eval.py's --harbor-bin executable on this machine.
"""
from importlib.metadata import distribution
import shutil
import subprocess

from harbor.environments.docker.docker import DockerEnvironment


def check_docker_server(cls):
    if not shutil.which("docker"):
        raise SystemExit("Docker is not installed or not on PATH.")
    try:
        result = subprocess.run(
            cls._engine_cmd("version", "--format", "{{.Server.Version}}"),
            capture_output=True, text=True, timeout=30, check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"Docker server check failed: {exc}") from exc
    if not result.stdout.strip():
        raise SystemExit("Docker server check returned no server version.")
    print(f"Docker server verified: {result.stdout.strip()}", flush=True)


DockerEnvironment.preflight = classmethod(check_docker_server)
entrypoint = next(ep for ep in distribution("harbor").entry_points if ep.name == "harbor")
entrypoint.load()()
