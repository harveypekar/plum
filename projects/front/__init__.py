from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path


def register(app: FastAPI, ollama, resolve_model=None):
    """Register front dashboard plugin: API endpoints + static files."""
    from . import api

    api.setup(app)

    # Serve static files (HTML/CSS/JS) at /front/
    static_dir = Path(__file__).parent
    app.mount('/front', StaticFiles(directory=str(static_dir), html=True), name='front')
