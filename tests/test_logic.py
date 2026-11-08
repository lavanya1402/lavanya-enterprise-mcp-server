from mcp_server.corp_mcp_server import (
    check_role_permission_logic,
    scan_pii_logic,
    schedule_meeting_secure,
)


def test_manager_can_send_email():
    assert check_role_permission_logic("manager", "send_email", "mailbox")["allowed"]


def test_employee_cannot_send_email():
    result = check_role_permission_logic("employee", "send_email", "mailbox")
    assert result["allowed"] is False
    assert "cannot perform" in result["reason"]


def test_unknown_role_is_denied():
    assert not check_role_permission_logic("intern", "generate_draft", "doc")["allowed"]


def test_scheduling_is_blocked_for_unknown_role():
    out = schedule_meeting_secure(
        role="guest",
        title="Review",
        organizer_email="a@corp.com",
        participant_emails=["b@corp.com"],
        start_time="2026-12-01T10:00",
        end_time="2026-12-01T11:00",
    )
    assert out["status"] == "forbidden"


def test_pii_masks_email_and_phone():
    out = scan_pii_logic("Contact priya@corp.com or +91 9876543210 today.")
    assert "priya@corp.com" not in out["masked_text"]
    assert "9876543210" not in out["masked_text"]
    assert {f["type"] for f in out["findings"]} == {"email", "phone"}
    assert out["risk_score"] == 0.35


def test_pii_detects_pan_and_aadhaar():
    out = scan_pii_logic("PAN ABCDE1234F, Aadhaar 1234 5678 9012")
    types = {f["type"] for f in out["findings"]}
    assert {"pan", "aadhaar"} <= types
    assert "[PAN]" in out["masked_text"] and "[AADHAAR]" in out["masked_text"]


def test_clean_text_has_zero_risk():
    out = scan_pii_logic("Team meeting moved to Friday.")
    assert out == {"risk_score": 0.0, "masked_text": "Team meeting moved to Friday.", "findings": []}


def test_contact_details_alone_do_not_block_sending():
    many = " ".join(f"user{i}@corp.com" for i in range(8))
    assert scan_pii_logic(many)["risk_score"] <= 0.8


def test_card_number_blocks_sending():
    assert scan_pii_logic("Card 4111 1111 1111 1111")["risk_score"] > 0.8
