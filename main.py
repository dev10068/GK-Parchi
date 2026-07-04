import os
import sys
import json
import datetime
import requests
import feedparser

GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GNEWS_API_KEY or not GEMINI_API_KEY:
    print("ERROR: API Keys missing.")
    sys.exit(1)

RSS_FEEDS = {
    "The Hindu": "https://www.thehindu.com/news/national/feeder/default.rss",
    "NDTV Hindi": "https://feeds.feedburner.com/ndtv/ndtvkhabar",
    "PIB": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
}

OUTPUT_DIR = "affairs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Models to try, in order of preference. If one is retired/unavailable for
# the API key, the code automatically falls through to the next one instead
# of crashing the whole workflow.
MODEL_CANDIDATES = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


def fetch_gnews():
    url = f"https://gnews.io/api/v4/top-headlines?category=general&lang=en&country=in&max=10&apikey={GNEWS_API_KEY}"
    items = []
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            for article in resp.json().get("articles", []):
                items.append({
                    "source": "GNews",
                    "title": article.get("title", ""),
                    "description": article.get("description", "")
                })
        else:
            print(f"GNews HTTP {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        print(f"GNews Error: {e}")
    return items


def fetch_rss():
    items = []
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                items.append({
                    "source": name,
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", "")
                })
        except Exception as e:
            print(f"RSS Error ({name}): {e}")
    return items


def get_available_models():
    """Ask Google which models this API key can actually use for
    generateContent, so we never hardcode a name that might get retired."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        usable = []
        for m in data.get("models", []):
            name = m.get("name", "").replace("models/", "")
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods:
                usable.append(name)
        return usable
    except Exception as e:
        print(f"ListModels Error: {e}")
        return []


def call_gemini(model_name, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def get_ai_summary(news_items):
    raw_text = "\n\n".join(
        f"Title: {i['title']}\nDetails: {i['description']}" for i in news_items if i["title"]
    )
    prompt = (
        "Create a daily current affairs digest for Indian competitive exams. "
        "Group into these categories, in this order: PIB & Government Schemes, Sports, "
        "Appointments, Science. Under 'PIB & Government Schemes', prioritize official "
        "government announcements, new scheme launches, policy updates, and ministry "
        "initiatives. Exclude politics/crime. "
        "IMPORTANT: Include every distinct news item from the list below under its "
        "relevant category — do not skip, shorten the list, or pick only one headline "
        "per topic. Only merge two items together if they clearly describe the exact "
        "same event (e.g. the same appointment or the same scheme reported by two "
        "sources) — different events must stay as separate points even if from the "
        "same broad topic. It is fine and expected for a category to have many points. "
        "Use bilingual format (Hindi first / English translation). Keep each point "
        "concise, but do not drop items for the sake of brevity.\n\n"
        f"News:\n{raw_text}"
    )

    # Build the list of models to try: whatever this key actually supports
    # (from ListModels), falling back to our known-good candidate list.
    live_models = get_available_models()
    ordered_candidates = live_models if live_models else []
    for m in MODEL_CANDIDATES:
        if m not in ordered_candidates:
            ordered_candidates.append(m)

    last_error = None
    for model_name in ordered_candidates:
        try:
            print(f"Trying model: {model_name}")
            return call_gemini(model_name, prompt)
        except requests.HTTPError as e:
            last_error = e
            body = e.response.text if e.response is not None else str(e)
            print(f"Model '{model_name}' failed: {body[:300]}")
            continue
        except Exception as e:
            last_error = e
            print(f"Model '{model_name}' failed: {e}")
            continue

    print(f"ERROR: All models failed. Last error: {last_error}")
    sys.exit(1)


def save_output(summary_text):
    today = datetime.datetime.now()
    date_str = today.strftime("%d-%m-%Y")
    filename = f"Current_Affairs_{date_str}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# GK Parchi — Daily Current Affairs — {today.strftime('%d %B %Y')}\n\n{summary_text}\n")

    manifest_path = os.path.join(OUTPUT_DIR, "latest.json")
    archive = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                archive = json.load(f).get("archive", [])
        except Exception:
            pass

    archive = [a for a in archive if a.get("file") != filename]
    archive.insert(0, {"date": date_str, "file": filename})

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "latest_date": date_str,
            "latest_file": filename,
            "archive": archive[:30]
        }, f, indent=2)
    print(f"Saved: {filepath}")


def main():
    gnews_items = fetch_gnews()
    rss_items = fetch_rss()
    items = gnews_items + rss_items

    print(f"GNews items fetched: {len(gnews_items)}")
    print(f"RSS items fetched: {len(rss_items)}")
    print(f"Total items fetched: {len(items)}")
    for i, item in enumerate(items):
        print(f"  [{i+1}] ({item['source']}) {item['title'][:80]}")

    if not items:
        print("No news fetched.")
        sys.exit(1)

    summary = get_ai_summary(items)
    if summary:
        save_output(summary)
        print("Done successfully!")


if __name__ == "__main__":
    main()