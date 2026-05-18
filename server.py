#!/usr/bin/env python3
"""
server.py — Local server for email_reply.html.
Run with: python server.py
Then open: http://localhost:5000
"""

import os
import json
from flask import Flask, request, jsonify, send_from_directory
import anthropic
from pydantic import BaseModel
from typing import Literal

app = Flask(__name__)

class EmailTriage(BaseModel):
    category: Literal["Urgent", "Follow-up needed", "FYI only", "Spam"]
    summary: str
    reply_draft: str

SYSTEM_PROMPT = """\
You are an expert assistant for a trades business (HVAC, plumbing, electrical, etc.).
A customer email has come in. Analyse it and provide:

1. CATEGORY — choose exactly one:
   • Urgent          — new job inquiry, complaint, or time-sensitive request
   • Follow-up needed — needs a response but not immediately
   • FYI only        — informational, no response needed
   • Spam            — promotional, irrelevant, or junk

2. SUMMARY — one sentence (max 100 characters) capturing the key point.

3. REPLY DRAFT — a warm, professional reply suitable for a trades business.
   - Sound like a real person, not a corporation
   - For new inquiries: thank them, confirm you received it, say you'll follow up shortly
   - For Spam: write exactly "No reply needed."
   - Keep it concise and ready to send
"""

@app.route("/")
def index():
    return send_from_directory(".", "email_reply.html")

@app.route("/triage", methods=["POST"])
def triage():
    data = request.get_json()
    email_text = (data or {}).get("email", "").strip()

    if not email_text:
        return jsonify({"error": "No email text provided."}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY is not set."}), 500

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.parse(
            model="claude-opus-4-7",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Triage this customer email:\n\n{email_text}",
                }
            ],
            output_format=EmailTriage,
        )

        result = response.parsed_output
        if result is None:
            return jsonify({"error": "Claude did not return a result."}), 500

        return jsonify({
            "category": result.category,
            "summary": result.summary,
            "reply_draft": result.reply_draft,
        })

    except anthropic.APIStatusError as e:
        return jsonify({"error": f"API error {e.status_code}: {e.message}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("Starting Email Reply server...")
    print("Open your browser and go to: http://localhost:5000")
    print("Press Ctrl+C to stop the server.\n")
    app.run(debug=False, port=5000)
