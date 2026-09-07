import pytest

from app.services.integrations import run_email_integration


@pytest.mark.asyncio
async def test_email_without_smtp_does_not_leak_payload():
    secret_body = "super-secret-memory-content"
    result = await run_email_integration(
        {"to": "ops@example.com"},
        "Secret subject line",
        secret_body,
        {"input": {}, "steps": {}, "last_output": "", "memory": {}},
        "",
    )
    assert result == "Email queued (SMTP not configured)"
    assert secret_body not in result
    assert "Secret subject line" not in result


@pytest.mark.asyncio
async def test_email_single_recipient_succeeds_without_smtp():
    result = await run_email_integration(
        {"to": "ops@example.com"},
        "Status",
        "All good",
        {"input": {}, "steps": {}, "last_output": "", "memory": {}},
        "",
    )
    assert result == "Email queued (SMTP not configured)"


@pytest.mark.asyncio
async def test_email_rejects_multiple_recipients():
    recipients = ", ".join(f"user{i}@example.com" for i in range(10))
    result = await run_email_integration(
        {"to": recipients},
        "Bulk",
        "Hello",
        {"input": {}, "steps": {}, "last_output": "", "memory": {}},
        "",
    )
    assert result == "Email error: multiple recipients not allowed"


@pytest.mark.asyncio
async def test_email_missing_to_after_render():
    result = await run_email_integration(
        {"to": "   "},
        "Subject",
        "Body",
        {"input": {}, "steps": {}, "last_output": "", "memory": {}},
        "",
    )
    assert result == "Email error: missing 'to' address in credential config"