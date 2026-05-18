from projects.rp.prompt_builder import (
    get_ai_name, get_user_name, get_ai_personality, get_ai_pronouns,
    build_chat_messages, build_ollama_options, scale_num_predict,
    budget_to_json, CHAT_DEFAULTS,
)


def _card(name="Char", description="", personality="", pronouns=""):
    return {"card_data": {"data": {
        "name": name, "description": description, "personality": personality,
        "pronouns": pronouns,
    }}}


def _ctx(ai_name="Char", user_name="User", ai_desc="", messages=None,
         ai_pronouns=""):
    return {
        "ai_card": _card(ai_name, description=ai_desc, pronouns=ai_pronouns),
        "user_card": _card(user_name),
        "system_prompt": "System prompt",
        "post_prompt": "Post prompt",
        "messages": messages or [],
    }


class TestGetAiName:
    def test_extracts_name(self):
        assert get_ai_name(_ctx(ai_name="Jessica")) == "Jessica"

    def test_default(self):
        assert get_ai_name({}) == "Character"

    def test_flat_card_data(self):
        ctx = {"ai_card": {"card_data": {"name": "Sol"}}}
        assert get_ai_name(ctx) == "Sol"


class TestGetUserName:
    def test_extracts_name(self):
        assert get_user_name(_ctx(user_name="Val")) == "Val"

    def test_default(self):
        assert get_user_name({}) == "User"


class TestGetAiPersonality:
    def test_extracts_description(self):
        assert get_ai_personality(_ctx(ai_desc="A painter")) == "A painter"

    def test_default(self):
        assert get_ai_personality({}) == ""


class TestBuildChatMessages:
    def test_structure(self):
        ctx = _ctx(ai_name="Jess", messages=[
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ])
        msgs = build_chat_messages(ctx)
        assert msgs[0] == {"role": "system", "content": "System prompt"}
        assert msgs[1] == {"role": "user", "content": "Hi"}
        assert msgs[2] == {"role": "assistant", "content": "Hello"}
        assert msgs[3] == {"role": "system", "content": "Post prompt"}
        assert msgs[4] == {"role": "assistant", "content": "Jess "}

    def test_no_post_prompt(self):
        ctx = _ctx(ai_name="Jess")
        ctx["post_prompt"] = ""
        msgs = build_chat_messages(ctx)
        assert len(msgs) == 2
        assert msgs[-1]["content"] == "Jess "

    def test_empty_messages(self):
        msgs = build_chat_messages(_ctx())
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["role"] == "assistant"


class TestAuthorsNoteInjection:
    def test_injects_at_depth(self):
        ctx = _ctx(ai_name="Jess", messages=[
            {"role": "user", "content": "M1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "M2"},
            {"role": "assistant", "content": "A2"},
            {"role": "user", "content": "M3"},
            {"role": "assistant", "content": "A3"},
        ])
        ctx["authors_note"] = "Write poetically"
        ctx["authors_note_depth"] = 4
        msgs = build_chat_messages(ctx)
        note_msgs = [m for m in msgs if "Author's Note" in m.get("content", "")]
        assert len(note_msgs) == 1
        idx = msgs.index(note_msgs[0])
        assert msgs[idx + 4]["content"] == "A3"

    def test_no_injection_when_empty(self):
        ctx = _ctx(ai_name="Jess", messages=[
            {"role": "user", "content": "Hi"},
        ])
        ctx["authors_note"] = ""
        msgs = build_chat_messages(ctx)
        assert not any("Author's Note" in m.get("content", "") for m in msgs)

    def test_depth_clamps_to_start(self):
        ctx = _ctx(ai_name="Jess", messages=[
            {"role": "user", "content": "Hi"},
        ])
        ctx["authors_note"] = "Be bold"
        ctx["authors_note_depth"] = 100
        msgs = build_chat_messages(ctx)
        note_idx = next(i for i, m in enumerate(msgs) if "Author's Note" in m.get("content", ""))
        assert note_idx == 1


class TestBuildOllamaOptions:
    def test_defaults(self):
        opts = build_ollama_options({})
        assert opts == CHAT_DEFAULTS

    def test_overrides(self):
        opts = build_ollama_options({"temperature": 0.5})
        assert opts["temperature"] == 0.5
        assert opts["num_predict"] == CHAT_DEFAULTS["num_predict"]

    def test_ignores_model_key(self):
        opts = build_ollama_options({"model": "something", "temperature": 0.8})
        assert "model" not in opts
        assert opts["temperature"] == 0.8

    def test_ignores_max_context_tokens(self):
        opts = build_ollama_options({"max_context_tokens": 4096})
        assert "max_context_tokens" not in opts


class TestScaleNumPredict:
    def test_short_message(self):
        opts = scale_num_predict({"num_predict": 768}, "hi")
        assert opts["num_predict"] == 1024

    def test_long_message(self):
        long_msg = "word " * 5000
        opts = scale_num_predict({"num_predict": 768}, long_msg)
        assert opts["num_predict"] == 2048

    def test_preserves_other_keys(self):
        opts = scale_num_predict({"num_predict": 768, "temperature": 0.8}, "hello")
        assert opts["temperature"] == 0.8


class TestGetAiPronouns:
    def test_extracts_pronouns(self):
        ctx = {"ai_card": _card("Kasa", pronouns="she/her")}
        assert get_ai_pronouns(ctx) == "she/her"

    def test_default_empty(self):
        assert get_ai_pronouns({}) == ""

    def test_no_pronouns_in_card(self):
        ctx = {"ai_card": _card("Kasa")}
        assert get_ai_pronouns(ctx) == ""


class TestBuildChatMessagesWithPronouns:
    def test_includes_pronouns_in_anchor(self):
        ctx = _ctx(ai_name="Kasa", ai_pronouns="she/her")
        msgs = build_chat_messages(ctx)
        assert msgs[-1]["content"] == "Kasa [she/her] "

    def test_no_pronouns_plain_anchor(self):
        ctx = _ctx(ai_name="Kasa")
        msgs = build_chat_messages(ctx)
        assert msgs[-1]["content"] == "Kasa "

    def test_he_him_pronouns(self):
        ctx = _ctx(ai_name="Marcus", ai_pronouns="he/him")
        msgs = build_chat_messages(ctx)
        assert msgs[-1]["content"] == "Marcus [he/him] "

    def test_they_them_pronouns(self):
        ctx = _ctx(ai_name="River", ai_pronouns="they/them")
        msgs = build_chat_messages(ctx)
        assert msgs[-1]["content"] == "River [they/them] "


class TestBudgetToJson:
    def test_no_report(self):
        assert budget_to_json({}) is None

    def test_non_report_value(self):
        assert budget_to_json({"_budget_report": "not a report"}) is None
