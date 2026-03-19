import subprocess
import time
from pathlib import Path

import httpx
from fastapi import FastAPI

PLUM_ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = PLUM_ROOT / 'logs'

# Services detected via pgrep
PROCESS_SERVICES = {
    'postgresql': 'postgres',
    'ollama': 'ollama',
}

# Services detected via HTTP health check
HTTP_SERVICES = {
    'aiserver': 'http://127.0.0.1:8080/health',
    'rp': 'http://127.0.0.1:8080/rp/',
}

RESTART_SCRIPTS = {
    'aiserver': str(PLUM_ROOT / 'projects' / 'aiserver' / 'restart.sh'),
}


def _check_process_running(process_name: str) -> bool:
    try:
        result = subprocess.run(
            ['pgrep', '-f', process_name],
            capture_output=True, timeout=3,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def _check_http(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(url)
            return resp.status_code < 500
    except Exception:
        return False


def setup(app: FastAPI):
    @app.get('/api/logs/{service}')
    async def get_service_logs(service: str, lines: int = 20):
        log_path = LOGS_DIR / f'{service}.log'
        if not log_path.exists():
            return {'service': service, 'lines': [], 'error': 'Log file not found'}

        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()

        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return {
            'service': service,
            'lines': [l.rstrip('\n') for l in tail],
            'total_lines': len(all_lines),
            'timestamp': time.time(),
        }

    @app.get('/api/services/{service}/status')
    async def service_status(service: str):
        if service in HTTP_SERVICES:
            running = await _check_http(HTTP_SERVICES[service])
        elif service in PROCESS_SERVICES:
            running = _check_process_running(PROCESS_SERVICES[service])
        else:
            return {'service': service, 'status': 'unknown'}

        return {
            'service': service,
            'status': 'running' if running else 'stopped',
            'timestamp': time.time(),
        }

    @app.post('/api/services/{service}/restart')
    async def restart_service(service: str):
        script = RESTART_SCRIPTS.get(service)
        if not script or not Path(script).exists():
            return {'service': service, 'status': 'failed', 'error': f'No restart script for {service}'}

        subprocess.Popen(
            ['bash', script],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            'service': service,
            'status': 'restarting',
            'timestamp': time.time(),
        }
