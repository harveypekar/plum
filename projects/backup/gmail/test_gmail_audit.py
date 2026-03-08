def test_aggregate_messages():
    from gmail_audit import aggregate_messages

    messages = [
        {
            "id": "a1",
            "sizeEstimate": 5000,
            "labelIds": ["CATEGORY_PROMOTIONS", "INBOX"],
            "internalDate": "1704067200000",  # 2024-01-01
            "payload": {
                "headers": [{"name": "From", "value": "news@shop.com"}],
                "parts": [
                    {
                        "filename": "flyer.pdf",
                        "body": {"size": 3000},
                    }
                ],
            },
        },
        {
            "id": "a2",
            "sizeEstimate": 200,
            "labelIds": ["CATEGORY_SOCIAL"],
            "internalDate": "1709596800000",  # 2024-03-05
            "payload": {
                "headers": [{"name": "From", "value": "notif@twitter.com"}],
            },
        },
    ]

    report = aggregate_messages(messages)

    assert report["by_sender"]["news@shop.com"]["total_size"] == 5000
    assert report["by_sender"]["news@shop.com"]["count"] == 1
    assert report["by_category"]["promotions"]["total_size"] == 5000
    assert report["by_category"]["social"]["count"] == 1
    assert report["by_year"]["2024"]["total_size"] == 5200
    assert len(report["largest"]) == 2
    assert report["attachments"]["pdf"]["count"] == 1
