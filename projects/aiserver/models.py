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
    priority: int = 0


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
    git_commit: str = ""
    git_subject: str = ""
    started_at: str = ""


class StatsResponse(BaseModel):
    total_requests: int
    requests_last_hour: int
    avg_tokens_per_second: float
    active_streams: int
    queue_depth: int = 0


class ChatRequest(BaseModel):
    messages: list[dict]
    model: str | None = None
    options: GenerateOptions | None = None
    stop: list[str] | None = None
    stream: bool = True
    priority: int = 5


class QueueEntryStatus(BaseModel):
    id: str
    priority: int
    model: str
    status: str
    position: int
    created_at: float


class QueueStatusResponse(BaseModel):
    entries: list[QueueEntryStatus]
    active: QueueEntryStatus | None
    total: int
