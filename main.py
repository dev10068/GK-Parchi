import os
import sys
import json
import datetime
import requests
import feedparser
from difflib import SequenceMatcher

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

# Pulling only "general" was missing big chunks of news every day (sports,
# science, world, business etc never got fetched at all). Now we pull
# multiple GNews categories so far fewer stories slip through.
GNEWS_CATEGORIES = ["general", "nation", "world", "business", "sports", "science"]

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

# Two headlines this similar (0-1 scale) are treated as the same story
# reported by different sources, and get merged instead of duplicated.
DUPLICATE_SIMILARITY_THRESHOLD = 0.75


def fetch_gnews():
    items = []
    for category in GNEWS_CATEGORIES:
        url = (
            f"https://gnews.io/api/v4/top-headlines?category={category}"
            f"&lang=en&country=in&max=10&apikey={GNEWS_API_KEY}"
        )
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
                print(f"GNews [{category}] HTTP {resp.status_code}: {resp.text[:300]}")
        except Exception as e:
            print(f"GNews [{category}] Error: {e}")
    return items


def fetch_rss():
    items = []
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                items.append({
                    "source": name,
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", "")
                })
        except Exception as e:
            print(f"RSS Error ({name}): {e}")
    return items


def dedupe_items(items):
    """Merge near-duplicate headlines that show up across multiple sources
    (e.g. GNews and The Hindu covering the same story). Keeps the first
    occurrence, folds the other sources' names into it, and drops the
    repeat so neither the digest nor Top Headlines double-counts it."""
    deduped = []
    for item in items:
        if not item["title"]:
            continue
        matched = False
        for existing in deduped:
            similarity = SequenceMatcher(
                None, item["title"].lower(), existing["title"].lower()
            ).ratio()
            if similarity >= DUPLICATE_SIMILARITY_THRESHOLD:
                if item["source"] not in existing["sources"]:
                    existing["sources"].append(item["source"])
                matched = True
                break
        if not matched:
            deduped.append({
                "title": item["title"],
                "description": item["description"],
                "sources": [item["source"]],
            })
    return deduped


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


def get_ai_summary(deduped_items):
    raw_text = "\n\n".join(
        f"Title: {i['title']}\nDetails: {i['description']}" for i in deduped_items if i["title"]
    )
    prompt = (
        "Create a detailed daily current affairs digest for Indian competitive exams "
        "(SSC CGL, Railway). Group into these categories, in this order: "
        "PIB & Government Schemes, Polity & Governance, Economy, International Relations, "
        "Sports, Appointments & Awards, Science & Technology. Under 'PIB & Government "
        "Schemes', prioritize official government announcements, new scheme launches, "
        "policy updates, and ministry initiatives. Under 'Polity & Governance', include "
        "major political developments, protests or movements with policy significance, "
        "court rulings, and elections — exclude only routine crime/accident reports with "
        "no exam relevance.\n\n"
        "IMPORTANT: Include every distinct news item from the list below under its most "
        "relevant category — do not skip, shorten the list, or pick only one headline per "
        "topic. Only merge two items together if they clearly describe the exact same "
        "event — different events must stay as separate points even if from the same "
        "broad topic. It is fine and expected for a category to have many points.\n\n"
        "For EACH news item, write a detailed point of approximately 10 to 25 lines "
        "covering: what happened, key background/context, relevant numbers or stats, "
        "names of people/places/organizations involved, and why it matters for exams. "
        "Do not just give a one-line headline — go into real detail. At the start of "
        "each point, add a short tag in [Square Brackets] with 1-3 keywords for quick "
        "topic identification, e.g. [Ladakh, Statehood, Protest].\n\n"
        "Use bilingual format (Hindi first / English translation) for each point.\n\n"
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


def build_headlines_section(deduped_items):
    """Raw Top Headlines — every distinct headline fetched today, no
    summarizing, no fixed cap (just whatever came in after dedup). This
    exists so nothing gets silently filtered out even if it doesn't fit
    one of the digest's fixed categories."""
    lines = ["## Top Headlines\n"]
    for i, item in enumerate(deduped_items, start=1):
        sources = ", ".join(item["sources"])
        lines.append(f"{i}. {item['title']} _(Source: {sources})_")
    return "\n".join(lines)


def save_output(summary_text, deduped_items):
    today = datetime.datetime.now()
    date_str = today.strftime("%d-%m-%Y")
    filename = f"Current_Affairs_{date_str}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    headlines_section = build_headlines_section(deduped_items)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(
            f"# GK Parchi — Daily Current Affairs — {today.strftime('%d %B %Y')}\n\n"
            f"{summary_text}\n\n{headlines_section}\n"
        )

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
            "archive": archive[:30],
            "headline_count": len(deduped_items),
        }, f, indent=2)
    print(f"Saved: {filepath}")


def main():
    gnews_items = fetch_gnews()
    rss_items = fetch_rss()
    raw_items = gnews_items + rss_items

    print(f"GNews items fetched: {len(gnews_items)}")
    print(f"RSS items fetched: {len(rss_items)}")
    print(f"Total raw items fetched: {len(raw_items)}")

    deduped_items = dedupe_items(raw_items)
    print(f"Total distinct items after dedup: {len(deduped_items)}")
    for i, item in enumerate(deduped_items):
        print(f"  [{i+1}] ({', '.join(item['sources'])}) {item['title'][:80]}")

    if not deduped_items:
        print("No news fetched.")
        sys.exit(1)

    summary = get_ai_summary(deduped_items)
    if summary:
        save_output(summary, deduped_items)
        print("Done successfully!")


if __name__ == "__main__":
    main()