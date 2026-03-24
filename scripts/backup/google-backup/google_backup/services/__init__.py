"""Service registry — discovers and exposes all backup service modules."""

from google_backup.services.base import BaseService, SyncResult as SyncResult

# Registry populated by import side-effects; each service module appends itself.
_registry: dict[str, type[BaseService]] = {}


def register(cls: type[BaseService]) -> type[BaseService]:
    """Decorator: register a service class by its name."""
    _registry[cls.name] = cls
    return cls


def get_all() -> dict[str, type[BaseService]]:
    """Return all registered services. Imports modules to trigger registration."""
    # Import each service module so @register decorators fire.
    from google_backup.services import (  # noqa: F401
        calendar,
        contacts,
        drive,
        gmail,
        tasks,
        youtube,
    )
    return dict(_registry)


def get(name: str) -> type[BaseService]:
    """Return a single registered service by name."""
    all_services = get_all()
    if name not in all_services:
        raise KeyError(f"Unknown service: {name}. Available: {', '.join(all_services)}")
    return all_services[name]
