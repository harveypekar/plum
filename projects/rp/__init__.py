from contextlib import asynccontextmanager
from fastapi import FastAPI


def register(app: FastAPI, ollama, resolve_model=None):
    """Register RP plugin routes on the aiserver app."""
    from . import routes, db

    # Wrap existing lifespan to add DB init/close
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def extended_lifespan(app):
        await db.init_schema()
        await routes.init_mcp()
        async with original_lifespan(app) as state:
            yield state
        await db.close()

    app.router.lifespan_context = extended_lifespan
    routes.setup(app, ollama, resolve_model=resolve_model)
