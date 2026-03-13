from pydantic import BaseModel


class GenerateOptions(BaseModel):
    temperature: float | None = None
    num_predict: int | None = None
    top_p: float | None = None
    top_k: int | None = None
    think: bool | None = None


class GenerateRequest(BaseModel):
    prompt: str
    model: str | None = None
    system: str | None = None
    options: GenerateOptions | None = None


class DefaultsResponse(BaseModel):
    default_model: str
    aliases: dict[str, str]
    default_options: GenerateOptions


class ModelInfo(BaseModel):
    name: str
    alias: str | None = None
    parameter_size: str | None = None
    quantization_level: str | None = None
    size_bytes: int | None = None
    supports_think: bool = False


class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    available_models: list[ModelInfo]


class StatsResponse(BaseModel):
    total_requests: int
    requests_last_hour: int
    avg_tokens_per_second: float
    active_streams: int
