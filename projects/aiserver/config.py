import json
from pathlib import Path
from models import GenerateOptions


CONFIG_PATH = Path(__file__).parent / "config.json"


class Config:
    def __init__(self, path: Path = CONFIG_PATH):
        with open(path) as f:
            raw = json.load(f)
        self.ollama_url: str = raw["ollama_url"]
        self.host: str = raw["host"]
        self.port: int = raw["port"]
        self.default_model: str = raw["default_model"]
        self.aliases: dict[str, str] = raw["aliases"]
        self.default_options = GenerateOptions(**raw["default_options"])
        self.plugins: list[dict] = raw.get("plugins", [])

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
