"""
Author: Vicente Maciel Jr. (vicentem@microsoft.com)
Created: 04 March, 2026
main.py — HR Assistant CLI powered by GPT-4.1-nano on Microsoft Foundry.

This script:
  1. Authenticates via Azure Managed Identity (DefaultAzureCredential).
  2. Uploads HR policy documents from the docs/ folder to the Files API.
  3. Creates a Vector Store and attaches the uploaded files.
  4. Polls until the Vector Store is ready.
  5. Starts an interactive Q&A loop using the Responses API with file_search.
  6. Cleans up the Vector Store and uploaded files on exit.

Dependencies: azure-identity, python-dotenv, requests (see requirements.txt).
"""

import os
import sys
import glob
import time
import json
import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Azure Cognitive Services token scope used by Managed Identity
TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

# Directory containing HR documents to upload
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

# Default model deployment name
DEFAULT_MODEL = "gpt-4.1-nano"

# Maximum seconds to wait for the vector store to finish processing files
VECTOR_STORE_POLL_TIMEOUT = 300  # 5 minutes

# Seconds between poll attempts
VECTOR_STORE_POLL_INTERVAL = 2


# ---------------------------------------------------------------------------
# Helper: obtain a Bearer token from Managed Identity
# ---------------------------------------------------------------------------
def get_access_token():
    """
    Obtain an access token using DefaultAzureCredential (Managed Identity).
    Returns the token string or exits on failure.
    """
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token(TOKEN_SCOPE)
        return token.token
    except Exception as exc:
        print(f"\n[ERROR] Authentication failed: {exc}")
        print("Make sure Managed Identity is configured or you are logged in via 'az login'.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helper: build common HTTP headers
# ---------------------------------------------------------------------------
def auth_headers(token, content_type="application/json"):
    """Return a headers dict with Authorization and optional Content-Type."""
    headers = {"Authorization": f"Bearer {token}"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


# ---------------------------------------------------------------------------
# Step 1 — Upload files from docs/ folder
# ---------------------------------------------------------------------------
def upload_files(endpoint, token):
    """
    Upload every .txt file found in the docs/ directory.
    Returns a list of uploaded file IDs.
    """
    # Gather all .txt files inside the docs directory
    pattern = os.path.join(DOCS_DIR, "*.txt")
    file_paths = sorted(glob.glob(pattern))

    if not file_paths:
        print(f"[WARNING] No .txt files found in '{DOCS_DIR}'. The assistant will have no context.")
        return []

    uploaded_ids = []
    url = f"{endpoint}/openai/v1/files"

    for path in file_paths:
        filename = os.path.basename(path)
        print(f"  Uploading {filename} ... ", end="", flush=True)
        try:
            with open(path, "rb") as f:
                # Multipart form upload — purpose must be "assistants" for file_search
                resp = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": (filename, f, "text/plain")},
                    data={"purpose": "assistants"},
                    timeout=60,
                )
            resp.raise_for_status()
            file_id = resp.json()["id"]
            uploaded_ids.append(file_id)
            print(f"OK (id={file_id})")
        except Exception as exc:
            # Log and continue — other files may still succeed
            print(f"FAILED ({exc})")

    return uploaded_ids


# ---------------------------------------------------------------------------
# Step 2 — Create a Vector Store with the uploaded files
# ---------------------------------------------------------------------------
def create_vector_store(endpoint, token, file_ids):
    """
    Create a Vector Store and attach the given file IDs.
    Returns the vector store ID.
    """
    url = f"{endpoint}/openai/v1/vector_stores"
    payload = {
        "name": "HR Policy Documents",
        "file_ids": file_ids,
    }

    try:
        resp = requests.post(
            url,
            headers=auth_headers(token),
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        vs = resp.json()
        vs_id = vs["id"]
        print(f"  Vector Store created (id={vs_id})")
        return vs_id
    except Exception as exc:
        print(f"\n[ERROR] Failed to create Vector Store: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 3 — Poll Vector Store until processing completes
# ---------------------------------------------------------------------------
def wait_for_vector_store(endpoint, token, vs_id):
    """
    Poll the Vector Store status until it reaches 'completed' or times out.
    """
    url = f"{endpoint}/openai/v1/vector_stores/{vs_id}"
    deadline = time.time() + VECTOR_STORE_POLL_TIMEOUT

    print("  Waiting for Vector Store processing ", end="", flush=True)
    while time.time() < deadline:
        try:
            resp = requests.get(url, headers=auth_headers(token), timeout=30)
            resp.raise_for_status()
            status = resp.json().get("status", "unknown")
        except Exception:
            status = "error"

        if status == "completed":
            print(" Done!")
            return
        elif status in ("failed", "cancelled"):
            print(f"\n[ERROR] Vector Store processing {status}.")
            sys.exit(1)

        # Still processing — show progress dot
        print(".", end="", flush=True)
        time.sleep(VECTOR_STORE_POLL_INTERVAL)

    print(f"\n[ERROR] Vector Store processing timed out after {VECTOR_STORE_POLL_TIMEOUT}s.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Step 4 — Call the Responses API with file_search tool
# ---------------------------------------------------------------------------
def ask_question(endpoint, token, model, vs_id, question):
    """
    Send a user question to the Responses API using the file_search tool
    backed by the given vector store. Returns the assistant's text answer.
    """
    url = f"{endpoint}/openai/v1/responses"
    payload = {
        "model": model,
        "input": question,
        "instructions": (
            "You are a helpful HR assistant. Answer questions about company "
            "Human Resources policies using the documents provided via file search. "
            "If the answer is not in the documents, say so clearly."
        ),
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": [vs_id],
            }
        ],
    }

    try:
        resp = requests.post(
            url,
            headers=auth_headers(token),
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        return "[ERROR] The request timed out. Please try again."
    except requests.exceptions.RequestException as exc:
        return f"[ERROR] API request failed: {exc}"

    # Parse the response output — extract text from the first message
    try:
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content.get("text", "(empty response)")
        # Fallback if the expected structure is different
        return data.get("output_text", "(no text returned)")
    except Exception:
        return "(could not parse the response)"


# ---------------------------------------------------------------------------
# Step 5 — Cleanup: delete vector store and uploaded files
# ---------------------------------------------------------------------------
def cleanup(endpoint, token, vs_id, file_ids):
    """
    Delete the vector store and all uploaded files.
    Errors are logged but do not halt the program.
    """
    print("\nCleaning up resources...")

    # Delete vector store
    if vs_id:
        try:
            url = f"{endpoint}/openai/v1/vector_stores/{vs_id}"
            resp = requests.delete(url, headers=auth_headers(token), timeout=30)
            resp.raise_for_status()
            print(f"  Deleted Vector Store {vs_id}")
        except Exception as exc:
            print(f"  [WARNING] Could not delete Vector Store {vs_id}: {exc}")

    # Delete uploaded files
    for fid in file_ids:
        try:
            url = f"{endpoint}/openai/v1/files/{fid}"
            resp = requests.delete(url, headers=auth_headers(token), timeout=30)
            resp.raise_for_status()
            print(f"  Deleted file {fid}")
        except Exception as exc:
            print(f"  [WARNING] Could not delete file {fid}: {exc}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main():
    """Main function — orchestrates the full workflow."""

    # --- Load .env file (if present) so environment variables are available ---
    load_dotenv()

    # --- Read configuration from environment variables ---
    endpoint = os.environ.get("AZURE_FOUNDRY_ENDPOINT", "").rstrip("/")
    model = os.environ.get("AZURE_FOUNDRY_MODEL", DEFAULT_MODEL)

    if not endpoint:
        print("[ERROR] The environment variable AZURE_FOUNDRY_ENDPOINT is not set.")
        print("Example: export AZURE_FOUNDRY_ENDPOINT=https://<project>.services.ai.azure.com")
        sys.exit(1)

    # --- Display the welcome banner (Step 2 of the UX flow) ---
    print("=" * 55)
    print("  HR Assistant — Powered by GPT-4.1-nano")
    print("=" * 55)
    print()
    print("This tool answers Human Resources questions using")
    print("company HR policy documents as context.")
    print()

    # --- Authenticate (Managed Identity) ---
    print("Authenticating via Managed Identity...")
    token = get_access_token()
    print("  Authentication successful.\n")

    # --- Upload documents and create vector store ---
    print("Initializing... Uploading documents and creating vector store.\n")

    file_ids = upload_files(endpoint, token)
    if not file_ids:
        print("[ERROR] No files were uploaded. Cannot proceed without documents.")
        sys.exit(1)

    vs_id = create_vector_store(endpoint, token, file_ids)
    wait_for_vector_store(endpoint, token, vs_id)

    print("\nReady!\n")
    print('Type your question below or type "exit" to quit.\n')

    # --- Interactive Q&A loop (Steps 3 and 4 of the UX flow) ---
    try:
        while True:
            # Step 3 — Prompt the user for input
            try:
                question = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                # Gracefully handle Ctrl+C or piped input ending
                print()
                break

            # Check for exit commands
            if not question:
                continue
            if question.lower() in ("exit", "quit"):
                break

            # Step 4 — Get and display the answer
            print("\nAssistant: ", end="", flush=True)
            answer = ask_question(endpoint, token, model, vs_id, question)
            print(answer)
            print()

    except (KeyboardInterrupt, EOFError):
        # Extra safety net for unexpected interrupts during the loop
        print()

    # --- Cleanup resources ---
    cleanup(endpoint, token, vs_id, file_ids)
    print("\nGoodbye!")


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
