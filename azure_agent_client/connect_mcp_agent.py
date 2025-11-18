# azure_agent_client/connect_mcp_agent.py

import os
import time
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

# -----------------------------
# 1) Load environment variables
# -----------------------------
load_dotenv()

PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"].strip()
MODEL_DEPLOYMENT_NAME = os.environ["MODEL_DEPLOYMENT_NAME"].strip()
MCP_SERVER_URL = os.environ["MCP_SERVER_URL"].strip()
MCP_SERVER_LABEL = os.environ.get("MCP_SERVER_LABEL", "corp_secure_mcp").strip()

# DEBUG: print exactly what label Azure is getting
print("DEBUG MCP_SERVER_LABEL:", repr(MCP_SERVER_LABEL))


def main() -> None:
    # -----------------------------
    # 2) Define MCP tool (points to your MCP server)
    # -----------------------------
    mcp_tool = McpTool(
        server_label=MCP_SERVER_LABEL,
        server_url=MCP_SERVER_URL,
        allowed_tools=[],  # [] => allow all tools exposed by the MCP server
    )

    # extra debug: ensure label is clean
    import re
    print("DEBUG regex_ok:",
          bool(re.fullmatch(r"^[A-Za-z0-9_]+$", MCP_SERVER_LABEL)))

    # -----------------------------
    # 3) Create Azure AI Agents client (direct)
    # -----------------------------
    agents_client = AgentsClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )

    with agents_client:
        # -----------------------------
        # 4) Create a new MCP-enabled agent
        # -----------------------------
        agent = agents_client.create_agent(
            model=MODEL_DEPLOYMENT_NAME,
            name="corp_supervisor_mcp",   # NOTE: name also uses only _ now
            instructions=(
                "You are a secure supervisor agent. "
                "Use the MCP tools to:\n"
                "- Check calendar availability\n"
                "- Schedule meetings\n"
                "- Draft emails\n"
                "- Send emails only after RBAC + PII checks\n"
                "Always respect role-based permissions and mask PII where needed."
            ),
            tools=mcp_tool.definitions,
        )
        print(f"Created agent, ID: {agent.id}")
        print(f"MCP Server: {mcp_tool.server_label} at {mcp_tool.server_url}")

        # -----------------------------
        # 5) Create a thread + user message
        # -----------------------------
        thread = agents_client.threads.create()
        print(f"Created thread, ID: {thread.id}")

        message = agents_client.messages.create(
            thread_id=thread.id,
            role="user",
            content=(
                "I am a manager. "
                "Check availability for a meeting tomorrow from 3 PM to 4 PM with the team, "
                "schedule it if slots are free, and draft a formal email to inform everyone. "
                "Use RBAC to ensure only managers can send emails, "
                "and scan the email for PII before sending."
            ),
        )
        print(f"Created message, ID: {message.id}")

        # -----------------------------
        # 6) Start a run with MCP tool resources
        # -----------------------------
        run = agents_client.runs.create(
            thread_id=thread.id,
            agent_id=agent.id,
            tool_resources=mcp_tool.resources,
        )
        print(f"Created run, ID: {run.id}")

        # -----------------------------
        # 7) Poll run status + handle MCP tool approvals
        # -----------------------------
        while run.status in ["queued", "in_progress", "requires_action"]:
            time.sleep(1)
            run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)
            print(f"Current run status: {run.status}")

            if (
                run.status == "requires_action"
                and isinstance(run.required_action, SubmitToolApprovalAction)
            ):
                tool_calls = run.required_action.submit_tool_approval.tool_calls

                if not tool_calls:
                    print("No tool calls provided - cancelling run.")
                    agents_client.runs.cancel(thread_id=thread.id, run_id=run.id)
                    break

                tool_approvals = []
                for tool_call in tool_calls:
                    if isinstance(tool_call, RequiredMcpToolCall):
                        print(
                            f"Approving MCP tool call: {tool_call.name}, "
                            f"arguments={tool_call.arguments}"
                        )
                        tool_approvals.append(
                            ToolApproval(
                                tool_call_id=tool_call.id,
                                approve=True,
                                headers=mcp_tool.headers,
                            )
                        )

                if tool_approvals:
                    agents_client.runs.submit_tool_outputs(
                        thread_id=thread.id,
                        run_id=run.id,
                        tool_approvals=tool_approvals,
                    )

        print(f"\nRun completed with status: {run.status}")
        if run.status == "failed":
            print(f"Run failed: {run.last_error}")

        # -----------------------------
        # 8) Print conversation
        # -----------------------------
        messages = agents_client.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING,
        )

        print("\n--- Conversation ---")
        print("-" * 50)
        for msg in messages:
            if getattr(msg, "text_messages", None):
                last_text = msg.text_messages[-1]
                print(f"{msg.role.upper()}: {last_text.text.value}")
                print("-" * 50)


if __name__ == "__main__":
    main()
