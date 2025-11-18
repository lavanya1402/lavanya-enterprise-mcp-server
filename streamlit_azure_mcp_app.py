# streamlit_azure_mcp_app.py

import os
import time
import json

import streamlit as st
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    ListSortOrder,
    McpTool,
    RequiredMcpToolCall,
    SubmitToolApprovalAction,
    ToolApproval,
)

# -------------------------------------------------
# Load environment
# -------------------------------------------------
load_dotenv()

PROJECT_ENDPOINT = (os.environ.get("PROJECT_ENDPOINT") or "").strip()
MODEL_DEPLOYMENT_NAME = (os.environ.get("MODEL_DEPLOYMENT_NAME") or "").strip()
MCP_SERVER_URL = (os.environ.get("MCP_SERVER_URL") or "").strip()
MCP_SERVER_LABEL = (os.environ.get("MCP_SERVER_LABEL") or "corp_secure_mcp").strip()

if not PROJECT_ENDPOINT:
    raise RuntimeError("PROJECT_ENDPOINT missing in environment.")
if not MODEL_DEPLOYMENT_NAME:
    raise RuntimeError("MODEL_DEPLOYMENT_NAME missing in environment.")
if not MCP_SERVER_URL:
    raise RuntimeError("MCP_SERVER_URL missing in environment.")
if not MCP_SERVER_LABEL:
    raise RuntimeError("MCP_SERVER_LABEL missing in environment.")

st.set_page_config(
    page_title="Corp Secure Supervisor – Azure Agents + MCP + RBAC + PII",
    layout="wide",
)

# -------------------------------------------------
# Scenarios for demo (all use same MCP tools)
# -------------------------------------------------
SCENARIOS = {
    "Emergency Escalation – Platform Reliability": {
        "role": "manager",
        "prompt": (
            "I am a senior engineering manager. Check availability for an emergency "
            "escalation call with the platform reliability team tomorrow from 11 AM "
            "to 12 PM, schedule it if free, draft an urgent email to all team leads, "
            "apply RBAC for confidential communication, and perform PII sanitization "
            "before sending."
        ),
    },
    "Security Audit Sync – CISO": {
        "role": "manager",
        "prompt": (
            "I am the CISO. Check availability for tomorrow from 9 AM to 10 AM for a "
            "security audit sync with the SOC team, schedule the meeting if free, "
            "draft a confidential security update email, apply RBAC so only security "
            "team members receive it, and sanitize PII before sending."
        ),
    },
    "Quarterly Planning – Product": {
        "role": "manager",
        "prompt": (
            "I am a product manager. Check availability for a quarterly planning sync "
            "with all PMs tomorrow from 2 PM to 3 PM, schedule the meeting if the slot "
            "is open, draft a formal invite email, apply RBAC for PM leaders, and run "
            "a PII scan before sending."
        ),
    },
    "HR Policy Announcement – Line Managers": {
        "role": "hr-admin",
        "prompt": (
            "I am the HR director. Check availability for an HR policy announcement "
            "meeting with all line managers tomorrow from 3 PM to 4 PM, schedule it if "
            "free, draft a formal announcement email, apply RBAC for HR + managers, "
            "and sanitize any PII before sending."
        ),
    },
}


# -------------------------------------------------
# Cached AgentsClient (no context manager)
# -------------------------------------------------
@st.cache_resource
def get_agents_client() -> AgentsClient:
    credential = DefaultAzureCredential()
    client = AgentsClient(endpoint=PROJECT_ENDPOINT, credential=credential)
    return client


# -------------------------------------------------
# Core run function
# -------------------------------------------------
def run_supervisor_with_mcp(user_request: str, role: str = "manager"):
    """
    One end-to-end run:
      - create MCP tool
      - create agent + thread + message
      - run, auto-approve tool calls
      - return summary dict for UI
    """
    client = get_agents_client()

    # MCP tool definition
    mcp_tool = McpTool(
        server_label=MCP_SERVER_LABEL,
        server_url=MCP_SERVER_URL,
        allowed_tools=[],  # [] => allow all tools exposed by MCP server
    )

    events = []
    approved_calls = []

    # 1) Agent (per-run agent, simple for demo)
    agent = client.create_agent(
        model=MODEL_DEPLOYMENT_NAME,
        name="corp_supervisor_mcp",
        instructions=(
            f"You are a secure supervisor agent serving a corporate user with role: {role}.\n"
            "Use the MCP tools to coordinate a secure calendar + email workflow:\n"
            "- Check calendar availability\n"
            "- Schedule meetings\n"
            "- Draft emails\n"
            "- Send emails only after RBAC + PII checks\n"
            "Always explain clearly what you did in the final answer."
        ),
        tools=mcp_tool.definitions,
    )
    events.append(f"✅ Agent created: {agent.id}")

    # 2) Thread
    thread = client.threads.create()
    events.append(f"✅ Thread created: {thread.id}")

    # 3) User message
    message = client.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_request,
    )
    events.append(f"✅ User message created: {message.id}")

    # 4) Run with MCP tool resources
    run = client.runs.create(
        thread_id=thread.id,
        agent_id=agent.id,
        tool_resources=mcp_tool.resources,
    )
    events.append(f"🚀 Run created: {run.id}")

    # 5) Poll + handle MCP tool approvals
    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(1)
        run = client.runs.get(thread_id=thread.id, run_id=run.id)
        status = run.status

        if status in ["queued", "in_progress"]:
            events.append(f"⏳ Run status: {status}")
            continue

        if (
            status == "requires_action"
            and isinstance(run.required_action, SubmitToolApprovalAction)
        ):
            tool_calls = run.required_action.submit_tool_approval.tool_calls or []
            events.append("⚠️ Run status: requires_action (tool approval)")

            approvals = []
            for tc in tool_calls:
                if isinstance(tc, RequiredMcpToolCall):
                    # Parse arguments for display
                    try:
                        args = json.loads(tc.arguments)
                    except Exception:
                        args = {"raw": tc.arguments}

                    approved_calls.append(
                        {
                            "name": tc.name,
                            "arguments": args,
                            "tool_call_id": tc.id,
                        }
                    )
                    events.append(
                        f"🛠 Approving MCP tool call: {tc.name} args={tc.arguments}"
                    )
                    approvals.append(
                        ToolApproval(
                            tool_call_id=tc.id,
                            approve=True,
                            headers=mcp_tool.headers,
                        )
                    )

            if approvals:
                client.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_approvals=approvals,
                )
                events.append("✅ Tool approvals submitted.")

    # 6) Run finished
    events.append(f"🏁 Run completed with status: {run.status}")
    last_error = run.last_error if run.status == "failed" else None

    # 7) Conversation
    messages = list(
        client.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING,
        )
    )

    convo = []
    assistant_answer = ""
    for msg in messages:
        if getattr(msg, "text_messages", None):
            text = msg.text_messages[-1].text.value
            convo.append({"role": msg.role, "text": text})
            if msg.role == "assistant":
                assistant_answer = text

    return {
        "agent_id": agent.id,
        "thread_id": thread.id,
        "run_id": run.id,
        "status": run.status,
        "error": last_error,
        "events": events,
        "conversation": convo,
        "tool_calls": approved_calls,
        "assistant_answer": assistant_answer,
    }


# -------------------------------------------------
# UI – Enterprise demo
# -------------------------------------------------

# Sidebar
st.sidebar.header("⚙️ Config (from .env)")
st.sidebar.text_area("PROJECT_ENDPOINT", PROJECT_ENDPOINT, height=70)
st.sidebar.text_input("MODEL_DEPLOYMENT_NAME", MODEL_DEPLOYMENT_NAME)
st.sidebar.text_input("MCP_SERVER_URL", MCP_SERVER_URL)
st.sidebar.text_input("MCP_SERVER_LABEL", MCP_SERVER_LABEL)

st.sidebar.info(
    "1️⃣ Start your MCP server (FastMCP)\n"
    "2️⃣ Expose it via ngrok: https://.../mcp\n"
    "3️⃣ Put that URL in MCP_SERVER_URL\n"
    "4️⃣ Then click *Run Supervisor* below."
)

# Title
st.title("🛡️ Corp Secure Supervisor — Azure Agents + MCP + RBAC + PII")

# Flow explainer
with st.expander("🔁 Architecture flow (Manager → Supervisor → MCP → Secure Tools)", expanded=True):
    st.markdown(
        """
**Step 1 – Business user (you)**  
➡️ Sends a natural-language request from this Streamlit UI  

**Step 2 – Azure Supervisor Agent (in your AI Project)**  
➡️ Reads the request  
➡️ Decides which MCP tools to call (availability, scheduling, email, RBAC, PII check)  

**Step 3 – MCP Server (FastMCP, running in VS Code)**  
➡️ Exposes secure tools:
- `check_availability`
- `schedule_meeting_secure`
- `generate_email_draft_secure`
- `send_email_secure`

**Step 4 – Guarded Execution**  
➡️ RBAC decides **who is allowed** to do what  
➡️ PII scan masks risky information  
➡️ Agent only sends the email if everything is safe  

All of this is triggered by **one enterprise-style query** from the manager.
"""
    )

st.markdown(
    """
This demo shows a **Supervisor Agent in Azure AI** calling a **custom MCP server**
for secure calendar + email workflows:

- ✅ Check calendar availability  
- 📅 Schedule meetings with RBAC  
- ✉️ Draft emails  
- 🔐 Scan for PII before sending  

Everything runs end-to-end from **Streamlit → Azure Agent → MCP → your tools**.
"""
)

# Scenario selector
st.markdown("### 🏢 Choose an enterprise scenario")

scenario_name = st.selectbox("Scenario", list(SCENARIOS.keys()))
scenario = SCENARIOS[scenario_name]

role = scenario["role"]
default_prompt = scenario["prompt"]

user_request = st.text_area(
    "💬 Enterprise request to the Supervisor Agent",
    value=default_prompt,
    height=110,
)

st.caption(f"Effective user role for RBAC in this scenario: **{role}**")

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None

run_button = st.button("🚀 Run Supervisor with MCP", type="primary")

if run_button:
    with st.spinner("Running Azure Agent with MCP tools (RBAC + PII)..."):
        try:
            result = run_supervisor_with_mcp(user_request=user_request, role=role)
            st.session_state["last_result"] = result
            st.balloons()
        except Exception as e:
            st.error(f"Run failed: {e}")
            st.stop()

result = st.session_state["last_result"]

# -------------------------------------------------
# Show results
# -------------------------------------------------
st.markdown("## 🗣️ Conversation")

if not result:
    st.info("No runs yet. Select a scenario and click **Run Supervisor with MCP**.")
else:
    # 1) Chat-style conversation
    for msg in result["conversation"]:
        role = msg["role"]
        text = msg["text"]
        with st.chat_message("user" if role == "user" else "assistant"):
            st.markdown(text)

    # 2) High-level summary
    st.markdown("## 📌 What did the Supervisor do?")

    if result["assistant_answer"]:
        st.success(result["assistant_answer"])

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Run status", str(result["status"]))

    with col2:
        st.caption("Agent ID")
        st.code(result["agent_id"])

    with col3:
        st.caption("Run ID")
        st.code(result["run_id"])

    # 3) MCP tool calls
    st.markdown("## 🔍 Behind the scenes – MCP tool calls")

    if not result["tool_calls"]:
        st.write("No MCP tool calls recorded for this run.")
    else:
        for i, tc in enumerate(result["tool_calls"], start=1):
            title = f"{i}. 🛠 **{tc['name']}**"
            with st.expander(title, expanded=True if i == 1 else False):
                st.markdown("**Arguments passed to tool:**")
                st.json(tc["arguments"])
                st.caption(f"Tool call ID: `{tc['tool_call_id']}`")

    # 4) Raw event log
    with st.expander("📜 Detailed run log"):
        for ev in result["events"]:
            st.write(ev)
        if result["error"]:
            st.error(f"Run error from Azure: {result['error']}")

# Signature/footer
st.markdown("---")
st.markdown(
    "👩‍💻 **Designed & orchestrated by _Lavanya Srivastava_ – Enterprise Agentic AI Architect (Azure + MCP, 2026)**"
)
