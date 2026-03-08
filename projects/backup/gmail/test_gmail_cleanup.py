from datetime import datetime, timedelta


def _make_msg(msg_id, labels, size, sender, date_ms):
    return {
        "id": msg_id,
        "labelIds": labels,
        "sizeEstimate": size,
        "internalDate": str(date_ms),
        "payload": {"headers": [{"name": "From", "value": sender}]},
    }


def test_rule_matches_category_and_age():
    from gmail_cleanup import matches_rule

    old_date = int((datetime.now() - timedelta(days=400)).timestamp() * 1000)
    msg = _make_msg("m1", ["CATEGORY_PROMOTIONS"], 100, "shop@x.com", old_date)
    rule = {"name": "old-promos", "category": "promotions", "older_than_days": 365, "action": "trash"}
    assert matches_rule(msg, rule) is True


def test_rule_does_not_match_recent():
    from gmail_cleanup import matches_rule

    recent = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
    msg = _make_msg("m2", ["CATEGORY_PROMOTIONS"], 100, "shop@x.com", recent)
    rule = {"name": "old-promos", "category": "promotions", "older_than_days": 365, "action": "trash"}
    assert matches_rule(msg, rule) is False


def test_rule_matches_size():
    from gmail_cleanup import matches_rule

    old_date = int((datetime.now() - timedelta(days=800)).timestamp() * 1000)
    msg = _make_msg("m3", ["INBOX"], 15_000_000, "big@x.com", old_date)
    rule = {"name": "large", "larger_than_mb": 10, "older_than_days": 730, "action": "trash"}
    assert matches_rule(msg, rule) is True


def test_rule_matches_sender():
    from gmail_cleanup import matches_rule

    old_date = int((datetime.now() - timedelta(days=100)).timestamp() * 1000)
    msg = _make_msg("m4", ["INBOX"], 100, "noreply@linkedin.com", old_date)
    rule = {"name": "linkedin", "from": ["noreply@linkedin.com"], "older_than_days": 90, "action": "trash"}
    assert matches_rule(msg, rule) is True


def test_protected_message_never_matched():
    from gmail_cleanup import is_protected

    msg = _make_msg("m5", ["STARRED", "INBOX"], 100, "x@x.com", 0)
    protect = [{"starred": True}]
    assert is_protected(msg, protect) is True


def test_unstarred_not_protected():
    from gmail_cleanup import is_protected

    msg = _make_msg("m6", ["INBOX"], 100, "x@x.com", 0)
    protect = [{"starred": True}]
    assert is_protected(msg, protect) is False


def test_protected_by_label():
    from gmail_cleanup import is_protected

    msg = _make_msg("m7", ["IMPORTANT", "INBOX"], 100, "x@x.com", 0)
    protect = [{"label": "IMPORTANT"}]
    assert is_protected(msg, protect) is True
