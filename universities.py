"""University list loading and filtering.

Data source (first one that works):
  1. UNIVERSITIES_CSV_URL env var - e.g. a Google Sheet "Publish to web" CSV link,
     so the team can edit the list without redeploying.
  2. universities.csv in this folder.
"""
import csv
import io
import os
import time
import urllib.request

LOCAL_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "universities.csv")
CACHE_SECONDS = 600

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

_cache = {"rows": None, "loaded_at": 0.0}


def _split(value):
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalise_intake(text):
    """'September 2026', 'Sept', 'sep' -> 'Sep'."""
    if not text:
        return None
    t = text.strip().lower()
    for m in MONTHS:
        if t.startswith(m) or f" {m}" in f" {t}":
            return m.capitalize()
    return None


def _parse(raw_text):
    rows = []
    for r in csv.DictReader(io.StringIO(raw_text)):
        name = (r.get("university") or "").strip()
        url = (r.get("url") or "").strip()
        if not name or not url.startswith("http"):
            continue  # never serve rows without a real link
        rows.append({
            "university": name,
            "country": (r.get("country") or "").strip(),
            "city": (r.get("city") or "").strip(),
            "level": _split(r.get("level")),
            "subjects": _split(r.get("subjects")),
            "intakes": [normalise_intake(i) or i for i in _split(r.get("intakes"))],
            "ielts_min": _to_float(r.get("ielts_min")),
            "tuition_per_year": (r.get("tuition_per_year") or "").strip(),
            "scholarship": (r.get("scholarship") or "").strip(),
            "url": url,
        })
    return rows


def load_universities(force=False):
    now = time.time()
    if not force and _cache["rows"] is not None and now - _cache["loaded_at"] < CACHE_SECONDS:
        return _cache["rows"]

    rows = None
    sheet_url = os.environ.get("UNIVERSITIES_CSV_URL")
    if sheet_url:
        try:
            with urllib.request.urlopen(sheet_url, timeout=10) as resp:
                rows = _parse(resp.read().decode("utf-8-sig"))
        except Exception as e:  # fall back to the local file
            print("WARN: could not load UNIVERSITIES_CSV_URL:", e)
    if rows is None:
        with open(LOCAL_CSV, encoding="utf-8-sig") as f:
            rows = _parse(f.read())

    _cache.update(rows=rows, loaded_at=now)
    return rows


def filter_options():
    rows = load_universities()
    countries = sorted({r["country"] for r in rows if r["country"]})
    subjects = sorted({s for r in rows for s in r["subjects"]})
    levels = sorted({l for r in rows for l in r["level"]})
    present = {i for r in rows for i in r["intakes"]}
    intakes = [m.capitalize() for m in MONTHS if m.capitalize() in present]
    return {"countries": countries, "subjects": subjects, "levels": levels, "intakes": intakes}


def search_universities(country=None, intake=None, subject=None, level=None, ielts=None, limit=7):
    rows = load_universities()
    intake_n = normalise_intake(intake) if intake else None
    ielts_f = _to_float(ielts)
    results = []
    for r in rows:
        if country and country.strip().lower() not in r["country"].lower():
            continue
        if intake_n and intake_n not in r["intakes"]:
            continue
        if level and level.strip().upper() not in [l.upper() for l in r["level"]]:
            continue
        if subject:
            s = subject.strip().lower()
            if not any(s in subj.lower() or subj.lower() in s for subj in r["subjects"]):
                continue
        if ielts_f is not None and r["ielts_min"] is not None and ielts_f < r["ielts_min"]:
            continue
        results.append(r)
    return results[: max(1, min(int(limit or 7), 20))]
