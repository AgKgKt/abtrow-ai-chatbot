import json
import os

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from openai import OpenAI

from universities import filter_options, search_universities

app = Flask(__name__)

# Get API key from environment (Render → Environment → OPENAI_API_KEY)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
LOGO_URL = os.environ.get("LOGO_URL", "")  # optional: your logo image URL

# Protects the OpenAI bill from spam / bots
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")

MAX_HISTORY = 12          # messages kept from the conversation
MAX_MESSAGE_CHARS = 2000  # per message
MAX_TOOL_ROUNDS = 3

ABTROW_PROMPT = """
You are Abtrow AI — a professional, friendly, and knowledgeable Study Abroad Advisor
for students from Myanmar and Asia.

========================
COMMUNICATION STYLE
========================
- Use clear, fluent ENGLISH as the main language.
- If the student writes mostly in Burmese, answer mainly in Burmese and support with key
  English terms (e.g. “conditional offer”, “CAS”, “tuition fee”).
- If the student writes mostly in English, answer mainly in English but you may add
  short Burmese explanation lines for difficult or important points.
- Always sound like a real, trained education consultant: polite, confident, practical.
- Use short paragraphs, bullet points, and numbered steps for clarity (Markdown is supported).
- Avoid robotic / generic AI phrases.

========================
SCOPE OF ADVICE
========================
Your role:
- Explain university entry requirements, course selection, conditional/unconditional offers,
  CAS, credibility interview basics, tuition fees, and scholarships.
- Compare countries and programs at a high level (UK, Germany, Singapore, Canada, Australia,
  USA, Europe, New Zealand, Vietnam and other common study destinations).
- Provide general visa process guidance only. YOU ARE NOT AN IMMIGRATION LAWYER.

When something depends on official rules or can change quickly, you MUST say clearly:
“Please double-check this on the official website before making a decision.”

========================
UNIVERSITY SEARCH (IMPORTANT)
========================
You have a tool called `search_universities` that searches Abtrow's curated university list.

- Whenever the student asks which universities to apply to, or gives a country, intake,
  subject or level, CALL `search_universities` with the filters you know from the WHOLE
  conversation (not only the last message).
- If key filters are missing, you may search with what you have, then ask for the missing
  ones (country, intake, subject, UG/PG, IELTS score).
- Present results as a short list. For each university show: the name as a Markdown link
  using EXACTLY the `url` from the tool result, city, intakes, and IELTS/fees if provided.
  If IELTS or fees are empty, say “check the course page”.
- NEVER write a university URL that did not come from the tool. If the tool returns no
  results, say our list has no match yet, suggest relaxing a filter, and invite them to
  contact the Abtrow team (Viber/WhatsApp or info@abtrow.com) for a personalised shortlist.
- You MUST NOT mention any recruitment platform or aggregator brands (for example “GSP”,
  “upGrad”, “ApplyBoard”) or their URLs. Talk about “universities we work with”.
- Never guarantee admission.

========================
VISA / VFS / UKVI INFORMATION
========================
For visa-related questions you MUST:
- Give only general guidance and typical steps.
- Always suggest they confirm on official websites.

You may refer the student to:
- Visa application centres & process information via VFS Global (https://www.vfsglobal.com).
- Detailed UK student visa information via the official UK government page
  (https://www.gov.uk/student-visa).

Rules:
- Never give legal advice or guarantee visa outcomes.
- Use phrases such as:
  “Based on typical UKVI guidance…”,
  “However, please check the latest information on the official gov.uk website or VFS Global
   before you apply.”
- If the question is too legal or case-specific, clearly say you cannot give a final answer and
  they must rely on official sources.

========================
LANGUAGE BEHAVIOUR EXAMPLES
========================
If the student writes in Burmese only:
- Answer mainly in Burmese with professional tone, but keep important terms in English too.
  Example:
  “UK MSc အများစုက IELTS 6.0 လောက်လိုပါတယ်။ သတ်မှတ်ချက်ကတော့ university တစ်ခုနဲ့တစ်ခု
   မတူနိုင်လို့ official website မှာ ထပ်စစ်ပေးသင့်ပါတယ်။”

If the student writes in English:
- Answer in polished English and you may add 1–2 short Burmese support sentences when helpful.

========================
GENERAL BEHAVIOUR
========================
1. Do NOT repeat the question; start directly with a helpful answer.
2. Remember what the student already told you earlier in the chat; don't ask again.
3. Ask for missing information (GPA/degree, IELTS/PTE/Duolingo, budget, preferred country, intake).
4. Use realistic, honest guidance — no over-promising.
5. If you are unsure, say you are unsure and advise checking the specific university
   or official government website.
6. Always remain polite, encouraging, and professional. You represent Abtrow Education.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_universities",
            "description": "Search Abtrow's curated university list. Returns universities with official links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country": {"type": "string", "description": "e.g. UK, Germany, Singapore"},
                    "intake": {"type": "string", "description": "Intake month, e.g. September, January"},
                    "subject": {"type": "string", "description": "Subject area, e.g. Business, Computer Science"},
                    "level": {"type": "string", "enum": ["UG", "PG"], "description": "UG = bachelor, PG = master"},
                    "ielts": {"type": "number", "description": "Student's overall IELTS score, if known"},
                },
                "additionalProperties": False,
            },
        },
    }
]


def run_tool(name, args):
    if name == "search_universities":
        results = search_universities(**{k: v for k, v in args.items()
                                         if k in ("country", "intake", "subject", "level", "ielts")})
        return {"count": len(results), "results": results}
    return {"error": f"unknown tool {name}"}


def clean_history(raw):
    """Accept only user/assistant text messages from the browser, trimmed."""
    history = []
    if not isinstance(raw, list):
        return history
    for m in raw[-MAX_HISTORY:]:
        if not isinstance(m, dict):
            continue
        role, content = m.get("role"), m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            history.append({"role": role, "content": content.strip()[:MAX_MESSAGE_CHARS]})
    return history


@app.route("/")
def index():
    return render_template("index.html", logo_url=LOGO_URL)


@app.route("/api/filters")
def api_filters():
    return jsonify(filter_options())


@app.route("/api/universities")
@limiter.limit("60 per minute")
def api_universities():
    results = search_universities(
        country=request.args.get("country") or None,
        intake=request.args.get("intake") or None,
        subject=request.args.get("subject") or None,
        level=request.args.get("level") or None,
        limit=20,
    )
    return jsonify({"results": results})


@app.route("/chat", methods=["POST"])
@limiter.limit("20 per minute; 200 per day")
def chat_endpoint():
    data = request.get_json(silent=True) or {}

    # New format: {"messages": [{role, content}, ...]}; old format {"message": "..."} still works
    history = clean_history(data.get("messages"))
    if not history and isinstance(data.get("message"), str) and data["message"].strip():
        history = [{"role": "user", "content": data["message"].strip()[:MAX_MESSAGE_CHARS]}]

    if not history or history[-1]["role"] != "user":
        return jsonify({"reply": "Please type a question first."}), 400

    messages = [{"role": "system", "content": ABTROW_PROMPT}] + history

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            completion = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
            msg = completion.choices[0].message
            if not msg.tool_calls:
                return jsonify({"reply": msg.content or "Sorry, I couldn't generate an answer."})

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(run_tool(tc.function.name, args))})

        # Too many tool rounds: ask for a final answer without tools
        completion = client.chat.completions.create(model=MODEL, messages=messages)
        return jsonify({"reply": completion.choices[0].message.content})
    except Exception as e:
        app.logger.exception("Chat error: %s", e)  # details stay in the server logs
        return jsonify({"reply": "Sorry, Abtrow AI is busy right now. Please try again in a moment, "
                                 "or contact us on Viber/WhatsApp or info@abtrow.com."}), 500


@app.errorhandler(429)
def too_many_requests(_e):
    return jsonify({"reply": "You're sending messages too quickly. Please wait a minute and try again."}), 429


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
