# mcp_server/corp_mcp_server.py

import re
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP

# -------------------------------------------------
# 1. Core business logic (tumhari original functions)
# -------------------------------------------------

def check_availability_logic(data: Dict[str, Any]) -> Dict[str, Any]:
    # Dummy availability logic for demo
    return {
        "status": "success",
        "organizer_email": data["organizer_email"],
        "participants": data["participant_emails"],
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "available": True,  # Always true in demo
    }


def schedule_meeting_logic(data: Dict[str, Any]) -> Dict[str, Any]:
    # Demo meeting creation
    return {
        "status": "meeting_created",
        "event": {
            "title": data["title"],
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "participants": data["participant_emails"],
            "location": data.get("location", "Online"),
        },
    }


def generate_draft_logic(data: Dict[str, Any]) -> Dict[str, Any]:
    draft_id = "draft_" + data["subject"].replace(" ", "_")

    body = (
        f"Dear team,\n\n"
        f"{data['purpose']}\n\n"
        f"Best regards,\nLavanya"
    )

    return {
        "draft_id": draft_id,
        "subject": data["subject"],
        "body": body,
        "tone": data.get("tone", "formal"),
        "to": data["to_emails"],
    }


def send_email_logic(data: Dict[str, Any]) -> Dict[str, Any]:
    # In real-life this would hit Gmail/Outlook API
    return {
        "status": "sent",
        "draft_id": data["draft_id"],
        "msg": "Email has been successfully sent (simulated)",
    }


ALLOWED_ACTIONS = {
    "employee": ["schedule_meeting", "generate_draft"],
    "manager": ["schedule_meeting", "generate_draft", "send_email"],
    "hr-admin": ["schedule_meeting", "generate_draft", "send_email", "access_sensitive_data"],
}


def check_role_permission_logic(role: str, action: str, resource: str) -> Dict[str, Any]:
    if action in ALLOWED_ACTIONS.get(role, []):
        return {"allowed": True, "role": role, "action": action, "resource": resource}
    else:
        return {
            "allowed": False,
            "role": role,
            "action": action,
            "resource": resource,
            "reason": f"Role '{role}' cannot perform '{action}'.",
        }


# Patterns for common personal data. Order matters: longer, more specific
# patterns run first so a card number is not also counted as a phone number.
PII_PATTERNS = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("card_number", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("aadhaar", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("pan", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("phone", re.compile(r"(?<!\w)(?:\+?\d{1,3}[ -]?)?\d{10}(?!\w)")),
]

# Sensitivity of each kind of data (0-1). Contact details are low; government
# IDs and card numbers are high, and push the score over the send-block
# threshold used in send_email_secure (0.8).
PII_WEIGHTS = {"email": 0.2, "phone": 0.3, "pan": 0.6, "aadhaar": 0.85, "card_number": 0.9}


def scan_pii_logic(text: str) -> Dict[str, Any]:
    """Find and mask personal data (emails, phone, PAN, Aadhaar, card numbers).

    Returns the masked text, the kinds of data found, and a risk score
    between 0 and 1 set by the most sensitive item found.
    """
    masked = text or ""
    findings: List[Dict[str, Any]] = []
    for kind, pattern in PII_PATTERNS:
        count = len(pattern.findall(masked))
        if count:
            findings.append({"type": kind, "count": count})
            masked = pattern.sub(f"[{kind.upper()}]", masked)

    # Score = most sensitive item found, plus 0.05 for each extra item.
    total = sum(f["count"] for f in findings)
    risk = max((PII_WEIGHTS[f["type"]] for f in findings), default=0.0)
    if total > 1:
        risk += 0.05 * (total - 1)
    return {
        "risk_score": round(min(risk, 1.0), 2),
        "masked_text": masked,
        "findings": findings,
    }


# -------------------------------------------------
# 2. MCP Server setup
# -------------------------------------------------

mcp = FastMCP("CorpSecureAssistant")


# -------------------------------
# 3. Exposed MCP tools
# -------------------------------

@mcp.tool()
def check_availability(
    organizer_email: str,
    participant_emails: List[str],
    start_time: str,
    end_time: str,
) -> Dict[str, Any]:
    """
    Check calendar availability for an organizer and participants.
    For demo: always returns available=True.
    """
    payload = {
        "organizer_email": organizer_email,
        "participant_emails": participant_emails,
        "start_time": start_time,
        "end_time": end_time,
    }
    return check_availability_logic(payload)


@mcp.tool()
def schedule_meeting_secure(
    role: str,
    title: str,
    organizer_email: str,
    participant_emails: List[str],
    start_time: str,
    end_time: str,
    location: str = "Online",
) -> Dict[str, Any]:
    """
    Schedule a meeting if the user's role is allowed.
    Uses RBAC to ensure only certain roles can perform 'schedule_meeting'.
    """
    perm = check_role_permission_logic(
        role=role,
        action="schedule_meeting",
        resource="calendar_event",
    )
    if not perm["allowed"]:
        return {
            "status": "forbidden",
            "reason": perm["reason"],
        }

    data = {
        "title": title,
        "organizer_email": organizer_email,
        "participant_emails": participant_emails,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
    }
    meeting = schedule_meeting_logic(data)
    return {
        "status": "ok",
        "rbac": perm,
        "meeting": meeting,
    }


@mcp.tool()
def generate_email_draft_secure(
    role: str,
    subject: str,
    purpose: str,
    to_emails: List[str],
    tone: str = "formal",
) -> Dict[str, Any]:
    """
    Generate an email draft if the role is allowed to create drafts.
    Also runs a PII scan on the email body.
    """
    perm = check_role_permission_logic(
        role=role,
        action="generate_draft",
        resource="email",
    )
    if not perm["allowed"]:
        return {
            "status": "forbidden",
            "reason": perm["reason"],
        }

    data = {
        "subject": subject,
        "purpose": purpose,
        "to_emails": to_emails,
        "tone": tone,
    }

    draft = generate_draft_logic(data)
    pii = scan_pii_logic(draft["body"])

    return {
        "status": "ok",
        "rbac": perm,
        "draft": draft,
        "pii_scan": pii,
    }


@mcp.tool()
def send_email_secure(
    role: str,
    draft_id: str,
    body: str,
) -> Dict[str, Any]:
    """
    Send an email if the role is allowed.
    Also runs a PII scan before sending.
    """
    perm = check_role_permission_logic(
        role=role,
        action="send_email",
        resource="email",
    )
    if not perm["allowed"]:
        return {
            "status": "forbidden",
            "reason": perm["reason"],
        }

    pii = scan_pii_logic(body)

    if pii["risk_score"] > 0.8:
        return {
            "status": "blocked",
            "reason": "High PII risk detected in email body.",
            "pii_scan": pii,
        }

    data = {"draft_id": draft_id, "body": body}
    result = send_email_logic(data)

    return {
        "status": "sent",
        "rbac": perm,
        "pii_scan": pii,
        "result": result,
    }


# -------------------------------
# 4. Entry point
# -------------------------------

if __name__ == "__main__":
    # STDIO mode (for local tools / Claude desktop)
    # mcp.run(transport="stdio")

    # HTTP MCP server for Azure + ngrok (defaults to localhost:8000, path /mcp)
    mcp.run(transport="streamable-http")
