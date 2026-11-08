### **Corp Secure Supervisor — Azure Agents × MCP × RBAC × PII**

**Built by Lavanya Srivastava, Lavanya AI Consultancy**

---

## 🌟 **Overview**

**Corp Secure Supervisor** is a working prototype that demonstrates how modern companies use **Agentic AI** to automate secure internal workflows.

A manager gives **one natural-language request**, and the system:

* Checks calendar availability
* Schedules meetings
* Drafts formal internal emails
* Applies RBAC (Role-Based Access Control)
* Sanitizes PII before communication
* Sends the final output safely

It shows the pattern many organisations are adopting for internal AI assistants: an agent that can act through tools, but only within each user's permissions and without leaking personal data.

---

## 🧠 **What Makes This Project Different**

Most demos show simple Q&A chatbots.
This is a **full enterprise workflow orchestration system**.

It combines:

### ✔ Azure Supervisor Agents

Understands the manager’s request and decides which secure tools to call.

### ✔ MCP (Model Context Protocol) Custom Tooling

Your own tools for availability check, scheduling, email drafting, and secure communication.

### ✔ RBAC Enforcement

Agent checks **who is allowed to do what**.

### ✔ PII Sanitization

Sensitive information is removed before any email is sent.

### ✔ Streamlit Business UI

A clean interface that simulates how business managers interact with internal AI systems.

### ✔ Hybrid Cloud via ngrok

Your MCP tools run locally but securely connect to Azure through HTTPS.

---

## 🏗 **Architecture (High-Level)**



```
Manager Request →
  Azure Supervisor Agent →
    MCP Secure Tools →
      RBAC + PII Guardrails →
        Safe Automated Output →
          Streamlit UI
```

This architecture reflects **real enterprise AI production systems**.

---

## 🏢 **Real Corporate Use Cases**

This system can automate:

* Emergency escalation workflows
* Incident management & scheduling
* HR communications
* Compliance-safe email generation
* Customer issue triaging
* Shift planning & internal coordination

---

## 📁 **Project Structure**

```
lavanya-enterprise-mcp-server/
│
├── mcp_server/
│   └── corp_mcp_server.py             # Custom MCP tools (FastMCP)
│
├── azure_agent_client/
│   └── connect_mcp_agent.py           # Connect MCP to Azure Supervisor Agent
│
├── streamlit_azure_mcp_app.py         # Streamlit front-end (Manager UI)
│
├── .env.example                       # Copy to .env (never commit .env)
├── tests/                             # Unit tests (pytest)
├── requirements.txt
├── .gitignore
└── LICENSE
```

---

## 🚀 **Run Locally**

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # fill in your Azure and MCP values

# 1. Start the MCP tool server (streamable HTTP)
python mcp_server/corp_mcp_server.py

# 2. Expose it over HTTPS so Azure can reach it
ngrok http 8000                    # put the URL in MCP_SERVER_URL

# 3. Start the manager UI
streamlit run streamlit_azure_mcp_app.py
```

Sign in to Azure first (`az login`) so `DefaultAzureCredential` can reach your Foundry project.

## 🔐 **How PII protection works**

Before an email is drafted or sent, `scan_pii_logic` finds and masks emails, phone numbers, PAN, Aadhaar and card numbers, and returns a 0–1 risk score based on the most sensitive item found. Contact details score low; government IDs and card numbers score above 0.8, and `send_email_secure` refuses to send above that threshold.

## 🧪 **Tests**

```bash
pip install pytest
python -m pytest -q tests
```

The tests cover role permissions, the blocked-role path and PII detection. They stub the MCP SDK, so no server or Azure account is needed.

## 🌍 **ngrok Integration**

MCP server runs locally and is securely exposed to Azure through **ngrok**, showcasing:

* Hybrid on-prem + cloud integration
* Real networked tool calling
* Production-style architecture

Recruiters immediately understand this as **practical enterprise engineering**.

---

## 🎯 **Skills Demonstrated**

This project showcases:

* Agentic AI Systems
* Azure AI Foundry
* MCP Tooling
* Enterprise RBAC + PII Guardrails
* Workflow Automation
* Streamlit Engineering
* Cloud + Local Hybrid AI
* Secure System Design

---

## 🏆 **More About This Project**

* Build **real enterprise systems**, not demos
* Automate complex workflows end-to-end
* Architect **secure, scalable, multi-agent systems**
* **enterprise AI solutions architecture**
* **production-style prototypes**

---

## 📜 **Footer**

**Designed & Orchestrated by Lavanya Srivastava**
*Enterprise Agentic AI Architect (Azure + MCP + Cloud Automations)*

---









<img width="959" height="502" alt="image" src="https://github.com/user-attachments/assets/fb681e9e-2c86-47c5-8be9-e7cec0bf63d2" />
