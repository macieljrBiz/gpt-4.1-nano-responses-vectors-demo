# HR Assistant — GPT-4.1-nano CLI Chatbot

A simple Python command-line tool that answers Human Resources questions using the **GPT-4.1-nano** model deployed on **Microsoft Foundry**. The script uploads HR policy documents to a **Vector Store** so the model can ground its answers on real company content.

## Features

- Authenticates via **Azure Managed Identity** (no API keys)
- Uploads HR documents from the `docs/` folder to a **File Vector Store**
- Uses the **Responses API** with `file_search` tool for retrieval-augmented answers
- Simple interactive Q&A loop in the terminal

## Prerequisites

- Python 3.14.3
- Azure Managed Identity configured (e.g., running on an Azure VM, Container Instance, or using `az login` locally)
- A Microsoft Foundry project with the **GPT-4.1-nano** model deployed

## Setup

1. **Clone the repository**

   ```bash
   git clone <repo-url>
   cd stefanin-gpt-4.1-nano
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**

   | Variable | Required | Description |
   |---|---|---|
   | `AZURE_FOUNDRY_ENDPOINT` | Yes | Your Foundry endpoint URL (e.g., `https://<project>.services.ai.azure.com`) |
   | `AZURE_FOUNDRY_MODEL` | No | Model deployment name (defaults to `gpt-4.1-nano`) |

   **Option A — `.env` file (recommended)**

   Edit the `.env` file at the project root and fill in your values:

   ```dotenv
   AZURE_FOUNDRY_ENDPOINT=https://your-project.services.ai.azure.com
   # AZURE_FOUNDRY_MODEL=gpt-4.1-nano
   ```

   **Option B — Shell environment variables**

   ```bash
   # Linux / macOS
   export AZURE_FOUNDRY_ENDPOINT="https://your-project.services.ai.azure.com"

   # Windows PowerShell
   $env:AZURE_FOUNDRY_ENDPOINT = "https://your-project.services.ai.azure.com"
   ```

## Usage

```bash
python main.py
```

The script will:

1. Authenticate using Managed Identity
2. Upload HR documents from `docs/` to a Vector Store
3. Display a welcome message explaining its purpose
4. Prompt you to type HR-related questions
5. Return grounded answers from the model

Type `exit` or `quit` to end the session. The script will clean up the Vector Store and uploaded files on exit.

### Example

```
===================================================
  HR Assistant — Powered by GPT-4.1-nano
===================================================

This tool answers Human Resources questions using
company HR policy documents as context.

Initializing... Uploading documents and creating vector store.
Ready!

Type your question below or type "exit" to quit.

You: How many PTO days do I get after 3 years?
```

## Azure Services & API Status

| Resource / Feature | Status | Reference |
|---|---|---|
| **Azure AI Foundry** (platform) | GA | [Azure AI Foundry Models](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models) |
| **GPT-4.1-nano** (model) | GA | [GPT-4.1 series](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models#gpt-41-series) |
| **Responses API** | GA | [v1 API — Responses](https://learn.microsoft.com/azure/ai-foundry/openai/api-version-lifecycle) |
| **Vector Store API** | GA | [v1 API — Vector Stores](https://learn.microsoft.com/azure/ai-foundry/openai/api-version-lifecycle) |
| **Files API** | GA | [v1 API — Files](https://learn.microsoft.com/azure/ai-foundry/openai/api-version-lifecycle) |
| **File Search tool** | GA | [Responses API — file_search](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/responses) |
| **Azure Managed Identity** | GA | [DefaultAzureCredential](https://learn.microsoft.com/python/api/azure-identity/azure.identity.defaultazurecredential) |
| **azure-identity** (Python SDK) | GA | [azure-identity on PyPI](https://pypi.org/project/azure-identity/) |

> **Note:** All APIs used by this project (Responses, Vector Stores, Files, File Search) are **Generally Available** under the [v1 API](https://learn.microsoft.com/azure/ai-foundry/openai/api-version-lifecycle). The older versioned API (`api-version=2025-04-01-preview`) still labels some of these as Preview, but the v1 surface — which this project uses — is GA.