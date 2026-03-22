from projects.rp.db import (
    _hash_data,
    compute_card_hash,
    compute_scenario_hash,
    compute_combo_hash,
)


class TestHashData:
    def test_deterministic(self):
        assert _hash_data({"a": 1}) == _hash_data({"a": 1})

    def test_key_order_irrelevant(self):
        assert _hash_data({"a": 1, "b": 2}) == _hash_data({"b": 2, "a": 1})

    def test_different_data_different_hash(self):
        assert _hash_data({"a": 1}) != _hash_data({"a": 2})

    def test_returns_16_char_hex(self):
        h = _hash_data("test")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestComputeCardHash:
    def _card(self, **overrides):
        data = {
            "description": "tall",
            "personality": "kind",
            "system_prompt": "",
            "first_mes": "Hi",
            "mes_example": "",
        }
        data.update(overrides)
        return {"card_data": {"data": data}}

    def test_same_card_same_hash(self):
        c = self._card()
        assert compute_card_hash(c) == compute_card_hash(c)

    def test_ignores_name(self):
        c1 = self._card()
        c1["card_data"]["data"]["name"] = "Alice"
        c2 = self._card()
        c2["card_data"]["data"]["name"] = "Bob"
        assert compute_card_hash(c1) == compute_card_hash(c2)

    def test_description_change_changes_hash(self):
        c1 = self._card(description="tall")
        c2 = self._card(description="short")
        assert compute_card_hash(c1) != compute_card_hash(c2)

    def test_personality_change_changes_hash(self):
        c1 = self._card(personality="kind")
        c2 = self._card(personality="rude")
        assert compute_card_hash(c1) != compute_card_hash(c2)

    def test_flat_card_format(self):
        card = {"card_data": {"description": "flat", "personality": "x",
                              "system_prompt": "", "first_mes": "", "mes_example": ""}}
        h = compute_card_hash(card)
        assert len(h) == 16


class TestComputeScenarioHash:
    def test_none_scenario(self):
        h = compute_scenario_hash(None)
        assert len(h) == 16

    def test_same_scenario_same_hash(self):
        s = {"description": "park", "first_message": "You arrive."}
        assert compute_scenario_hash(s) == compute_scenario_hash(s)

    def test_description_change(self):
        s1 = {"description": "park", "first_message": "Hi"}
        s2 = {"description": "beach", "first_message": "Hi"}
        assert compute_scenario_hash(s1) != compute_scenario_hash(s2)

    def test_empty_scenario(self):
        h = compute_scenario_hash({})
        assert len(h) == 16


class TestComputeComboHash:
    def test_deterministic(self):
        h = compute_combo_hash("abc", "def", "model1")
        assert h == compute_combo_hash("abc", "def", "model1")

    def test_model_change_changes_hash(self):
        h1 = compute_combo_hash("abc", "def", "model1")
        h2 = compute_combo_hash("abc", "def", "model2")
        assert h1 != h2

    def test_card_hash_change(self):
        h1 = compute_combo_hash("abc", "def", "m")
        h2 = compute_combo_hash("xyz", "def", "m")
        assert h1 != h2
