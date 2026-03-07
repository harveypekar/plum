import email
from pathlib import Path


def _make_eml_with_attachment():
    """Create a minimal EML with a text attachment."""
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart()
    msg["From"] = "test@example.com"
    msg["To"] = "user@example.com"
    msg["Subject"] = "Test with attachment"
    msg["Date"] = "Mon, 15 Jan 2024 10:00:00 +0000"
    msg["Message-ID"] = "<test123@example.com>"

    body = MIMEText("Hello world")
    msg.attach(body)

    att = MIMEBase("application", "octet-stream")
    att.set_payload(b"fake pdf content")
    encoders.encode_base64(att)
    att.add_header("Content-Disposition", "attachment", filename="report.pdf")
    msg.attach(att)

    return msg.as_bytes()


def test_save_message_creates_eml_and_extracts_attachments(tmp_path):
    from gmail_backup import save_message

    raw = _make_eml_with_attachment()
    msg_id = "abc123"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    attachments_dir = data_dir / "attachments"
    attachments_dir.mkdir()

    result = save_message(msg_id, raw, data_dir)

    # EML saved in YYYY/MM structure
    eml_path = data_dir / "2024" / "01" / "abc123.eml"
    assert eml_path.exists()
    assert result["path"] == str(eml_path.relative_to(data_dir))

    # Attachment extracted
    att_path = attachments_dir / "abc123_report.pdf"
    assert att_path.exists()
    assert att_path.read_bytes() == b"fake pdf content"

    # Labels stored
    assert "labels" in result


def test_save_message_no_attachment(tmp_path):
    from email.mime.text import MIMEText

    msg = MIMEText("Plain email")
    msg["From"] = "test@example.com"
    msg["Date"] = "Tue, 05 Mar 2024 12:00:00 +0000"
    raw = msg.as_bytes()

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "attachments").mkdir()

    from gmail_backup import save_message
    result = save_message("def456", raw, data_dir)

    eml_path = data_dir / "2024" / "03" / "def456.eml"
    assert eml_path.exists()
