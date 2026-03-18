import subprocess
import time
from pathlib import Path

from fastapi import FastAPI

PLUM_ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = PLUM_ROOT / 'logs'

SERVICE_PROCESS_MAP = {
    'postgresql': 'postgres',
    'ollama': 'ollama',
    'aiserver': 'uvicorn',
    'rp': 'uvicorn',
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
        process_name = SERVICE_PROCESS_MAP.get(service)
        if not process_name:
            return {'service': service, 'status': 'unknown'}

        running = _check_process_running(process_name)
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
