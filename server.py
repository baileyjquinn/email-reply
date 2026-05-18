#!/usr/bin/env python3
"""
server.py — Local server for email_reply.html.
Run with: python server.py
Then open: http://localhost:5000
"""

import os
import json
from flask import Flask, request, jsonify, send_from_directory, session, redirect
import anthropic
from pydantic import BaseModel
from typing import Literal

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-dev-secret")

PASSWORD = os.environ.get("APP_PASSWORD", "")

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

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Sign In</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f4f6f8;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }}
    .card {{
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08), 0 4px 16px rgba(0,0,0,0.06);
      padding: 40px 36px;
      width: 100%;
      max-width: 400px;
      text-align: center;
    }}
    .badge {{
      display: inline-block;
      background: #e8f4fd;
      color: #1a6fb5;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.5px;
      padding: 4px 14px;
      border-radius: 20px;
      margin-bottom: 16px;
      text-transform: uppercase;
    }}
    h1 {{ font-size: 22px; font-weight: 700; color: #111827; margin-bottom: 8px; }}
    p {{ font-size: 14px; color: #6b7280; margin-bottom: 28px; }}
    input[type="password"] {{
      width: 100%;
      padding: 12px 14px;
      border: 1.5px solid #d1d5db;
      border-radius: 8px;
      font-size: 15px;
      margin-bottom: 14px;
      transition: border-color 0.2s;
      font-family: inherit;
    }}
    input[type="password"]:focus {{ outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }}
    button {{
      width: 100%;
      padding: 13px;
      background: #2563eb;
      color: #fff;
      border: none;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
    }}
    button:hover {{ background: #1d4ed8; }}
    .error {{
      background: #fee2e2;
      color: #991b1b;
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 14px;
      margin-bottom: 14px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">Powered by Claude AI</div>
    <h1>Email Reply Generator</h1>
    <p>Enter your password to continue</p>
    {error_block}
    <form method="POST" action="/login">
      <input type="password" name="password" placeholder="Password" autofocus/>
      <button type="submit">Sign In</button>
    </form>
  </div>
</body>
</html>"""


def is_logged_in():
    if not PASSWORD:
        return True
    return session.get("authenticated") is True


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["authenticated"] = True
            return redirect("/")
        error_block = '<div class="error">Incorrect password. Please try again.</div>'
    else:
        error_block = ""
    return LOGIN_PAGE.format(error_block=error_block)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
def index():
    if not is_logged_in():
        return redirect("/login")
    return send_from_directory(".", "email_reply.html")


@app.route("/triage", methods=["POST"])
def triage():
    if not is_logged_in():
        return jsonify({"error": "Not authenticated."}), 401

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
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
