from fastapi import FastAPI


def register(app: FastAPI, ollama):
    """Register RP plugin routes on the aiserver app."""
    from . import routes
    routes.setup(app, ollama)
