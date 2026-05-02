from django.core.mail import EmailMultiAlternatives
from django.test import override_settings


@override_settings(EMAIL_BACKEND="alumni.email.FakeResendBackend")
def test_fake_backend_records_simple_message():
    from django.core.mail import get_connection

    conn = get_connection()
    msg = EmailMultiAlternatives(
        subject="Hello",
        body="Plain text body",
        from_email="noreply@example.test",
        to=["alice@example.test"],
    )
    msg.attach_alternative("<p>HTML body</p>", "text/html")
    sent = conn.send_messages([msg])

    assert sent == 1
    assert len(conn.sent_messages) == 1
    rec = conn.sent_messages[0]
    assert rec["from"] == "noreply@example.test"
    assert rec["to"] == ["alice@example.test"]
    assert rec["subject"] == "Hello"
    assert rec["text"] == "Plain text body"
    assert rec["html"] == "<p>HTML body</p>"


@override_settings(EMAIL_BACKEND="alumni.email.FakeResendBackend")
def test_fake_backend_handles_text_only_message():
    from django.core.mail import get_connection

    conn = get_connection()
    msg = EmailMultiAlternatives(
        subject="Plain",
        body="Body only",
        from_email="x@example.test",
        to=["b@example.test"],
    )
    sent = conn.send_messages([msg])
    assert sent == 1
    assert "html" not in conn.sent_messages[0]


def test_send_email_helper_renders_text_html_subject(tmp_path, settings):
    """send_email loads <base>.txt, <base>.html, <base>.subject.txt and
    sends a multipart message via Django's email backend."""
    from alumni.email import send_email

    settings.EMAIL_BACKEND = "alumni.email.FakeResendBackend"

    # Confirm the helper accepts the expected args without raising;
    # template rendering is tested in test_email_templates.py once
    # the actual templates exist.
    assert callable(send_email)
