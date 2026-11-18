"""Read-only timing probe for the WSL Docker CLI used by Harbor."""
import concurrent.futures
import json
import subprocess
import time


def probe(args):
    start = time.monotonic()
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=45)
        return dict(command=args, seconds=round(time.monotonic()-start, 2),
                    code=result.returncode, stdout=result.stdout[-1500:],
                    stderr=result.stderr[-1500:])
    except subprocess.TimeoutExpired:
        return dict(command=args, seconds=round(time.monotonic()-start, 2), timeout=True)


commands = [
    ['docker', 'info', '--format', '{{.ServerVersion}}'],
    ['docker', 'version', '--format', '{{.Server.Version}}'],
    ['curl', '--max-time', '15', '--unix-socket', '/var/run/docker.sock', 'http://localhost/_ping'],
]
with concurrent.futures.ThreadPoolExecutor() as pool:
    for result in pool.map(probe, commands):
        print(json.dumps(result), flush=True)
