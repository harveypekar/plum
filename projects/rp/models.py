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


class ScenarioCreate(BaseModel):
    name: str
    description: str = ""
    first_message: str = ""
    settings: dict = {}


class ScenarioResponse(BaseModel):
    id: int
    name: str
    description: str
    first_message: str = ""
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
    scene_state: str = ""
    category: str = "user"
    authors_note: str = ""
    authors_note_depth: int = 4
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


class SavePartialRequest(BaseModel):
    content: str
    role: str = "assistant"


class EditMessageRequest(BaseModel):
    content: str


class SceneStateRequest(BaseModel):
    scene_state: str


class AuthorsNoteRequest(BaseModel):
    note: str
    depth: int = 4


class LorebookEntryCreate(BaseModel):
    name: str = ""
    keys: list[str] = []
    secondary_keys: list[str] = []
    content: str = ""
    enabled: bool = True
    constant: bool = False
    selective: bool = False
    position: str = "after_char"
    insertion_order: int = 100
    priority: int = 100
    comment: str = ""


class LorebookEntryResponse(LorebookEntryCreate):
    id: int
    lorebook_id: int
    created_at: str
    updated_at: str


class LorebookUpdate(BaseModel):
    name: str | None = None
    scan_depth: int | None = None
    token_budget: int | None = None
    recursive_scan: bool | None = None
    enabled: bool | None = None


class LorebookResponse(BaseModel):
    id: int
    card_id: int
    name: str
    scan_depth: int
    token_budget: int
    recursive_scan: bool
    enabled: bool
    entries: list[LorebookEntryResponse] = []
    created_at: str
    updated_at: str


class CompareConfig(BaseModel):
    label: str = ""
    model: str | None = None
    temperature: float | None = None
    num_predict: int | None = None
    response_reserve: int | None = None


class CompareRequest(BaseModel):
    content: str
    configs: list[CompareConfig]


class SelectCandidateRequest(BaseModel):
    candidate_id: int
    preference_tags: list[str] = []
