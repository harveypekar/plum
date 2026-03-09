from pydantic import BaseModel


class CardCreate(BaseModel):
    name: str
    card_data: dict = {}


class CardResponse(BaseModel):
    id: int
    name: str
    has_avatar: bool
    card_data: dict
    created_at: str
    updated_at: str


class TemplateCreate(BaseModel):
    name: str
    content: str = ""


class TemplateResponse(BaseModel):
    id: int
    name: str
    content: str
    created_at: str
    updated_at: str


class ScenarioCreate(BaseModel):
    name: str
    description: str = ""
    settings: dict = {}


class ScenarioResponse(BaseModel):
    id: int
    name: str
    description: str
    settings: dict
    created_at: str
    updated_at: str


class ConversationCreate(BaseModel):
    user_card_id: int
    ai_card_id: int
    scenario_id: int | None = None
    model: str


class ConversationResponse(BaseModel):
    id: int
    user_card_id: int
    ai_card_id: int
    scenario_id: int | None
    model: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    raw_response: dict | None
    sequence: int
    created_at: str


class ConversationDetailResponse(BaseModel):
    conversation: ConversationResponse
    user_card: CardResponse
    ai_card: CardResponse
    scenario: ScenarioResponse | None
    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    content: str


class EditMessageRequest(BaseModel):
    content: str
