import json
import subprocess
from pathlib import Path
from models import GenerateOptions


CONFIG_PATH = Path(__file__).parent / "config.json"


def _wsl_gateway_ip() -> str | None:
    """Get the Windows host IP from WSL2's default gateway."""
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=2,
        )
        for part in result.stdout.split():
            if part.count(".") == 3:
                return part
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def resolve_url(url: str) -> str:
    """Resolve 'wsl-gateway' placeholder to the actual WSL2 gateway IP.

    With mirrored networking (.wslconfig networkingMode=mirrored), localhost
    works across Windows/WSL2 and this function is a no-op. Kept as fallback
    for NAT networking mode.
    """
    if "wsl-gateway" in url:
        gateway = _wsl_gateway_ip()
        if gateway:
            return url.replace("wsl-gateway", gateway)
    return url


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        with open(path) as f:
            raw = json.load(f)
        self.ollama_url: str = resolve_url(raw["ollama_url"])
        self.host: str = raw["host"]
        self.port: int = raw["port"]
        self.default_model: str = raw["default_model"]
        self.aliases: dict[str, str] = raw["aliases"]
        self.default_options = GenerateOptions(**raw["default_options"])
        self.plugins: list[dict] = raw.get("plugins", [])
        self.queue_max_depth: int = raw.get("queue_max_depth", 100)

    def resolve_model(self, model: str | None) -> str:
        """Resolve alias to Ollama model name, or pass through raw name."""
        name = model or self.default_model
        return self.aliases.get(name, name)

    def merge_options(self, options: GenerateOptions | None) -> dict:
        """Merge per-request options over defaults. Returns dict for Ollama API."""
        defaults = self.default_options.model_dump(exclude_none=True)
        if options:
            overrides = options.model_dump(exclude_none=True)
            defaults.update(overrides)
        return defaults
