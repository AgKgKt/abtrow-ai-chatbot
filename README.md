# Abtrow AI Chatbot

Study-abroad assistant for Abtrow Education Consultancy (Flask + OpenAI).

## Features
- Chat remembers the conversation (last 12 messages are sent with each question).
- **University finder**: the AI calls `search_universities` and only shares links from Abtrow's own list, so it never invents URLs. There is also a filter panel (country / intake / subject / level) that works without using the AI.
- Clickable links and formatted answers (Markdown, sanitised).
- Rate limiting (20 chat messages per minute, 200 per day per IP) to protect the OpenAI bill.
- Friendly error messages; technical details only go to the server logs.

## Updating the university list
Columns: `university, country, city, level, subjects, intakes, ielts_min, tuition_per_year, scholarship, url, notes`

- Separate multiple values with `;` (e.g. `Business;Computer Science`, `Sep;Jan`, `UG;PG`).
- `url` must start with `http` (rows without a link are ignored). Use the exact course page where possible.
- `notes` is internal only and never shown to students.

Two ways to manage it:
1. Edit `universities.csv` and redeploy, **or**
2. Keep the list in a Google Sheet with the same columns → File → Share → Publish to web → CSV, then set `UNIVERSITIES_CSV_URL` on Render. Changes appear within 10 minutes without redeploying.

The rows currently in `universities.csv` are **samples** (homepage links, no fees/IELTS). Replace them with your real list before going live.

## Environment variables (Render → Environment)
| Name | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | OpenAI key |
| `OPENAI_MODEL` | no | defaults to `gpt-5-mini` |
| `UNIVERSITIES_CSV_URL` | no | published Google Sheet CSV link |
| `LOGO_URL` | no | logo image URL for the header |

Start command: `gunicorn main:app`
