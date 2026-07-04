"""
Daily Current Affairs Generator
--------------------------------
Fetches Indian news from GNews API + RSS feeds, filters it down to exam-relevant
categories (Schemes, Sports, Appointments, Science) using the Gemini API, and
writes a bilingual (Hindi + English) Markdown digest.

Run manually:   python main.py
Run in CI:      triggered daily by .github/workflows/automate.yml
"""

import os
import sys
import json
import datetime
import requests
import feedparser
from google import genai

# ---------------------------------------------------------------------------
# 1. CONFIG — reads secrets from environment variables ONLY.
#    Never hardcode keys here. GitHub blocks commits that contain raw keys,
#    and it's a security risk even if it didn't.
# ---------------------------------------------------------------------------
GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GNEWS_API_KEY or not GEMINI_API_KEY:
    print("ERROR: GNEWS_API_KEY or GEMINI_API_KEY is missing from the environment.")
    print("Set them as GitHub Secrets — see the setup guide.")
    sys.exit(1)

RSS_FEEDS = {
    "The Hindu (National)": "https://www.thehindu.com/news/national/feeder/default.rss",
    "NDTV India (Hindi)": "https://feeds.feedburner.com/ndtv/ndtvkhabar",
}

OUTPUT_DIR = "affairs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# 2. FETCH — GNews API (India, English top headlines)
# ---------------------------------------------------------------------------
def fetch_gnews():
    """Fetch top India headlines from GNews API."""
    url = (
        "https://gnews.io/api/v4/top-headlines"
        f"?category=general&lang=en&country=in&max=10&apikey={GNEWS_API_KEY}"
    )
    items = []
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for article in data.get("articles", []):
            items.append(
                {
                    "source": f"GNews / {article.get('source', {}).get('name', 'Unknown')}",
                    "title": article.get("title", ""),
                    "description": article.get("description", ""),
                }
            )
    except requests.RequestException as e:
        print(f"WARNING: GNews fetch failed: {e}")
    return items


# ---------------------------------------------------------------------------
# 3. FETCH — RSS feeds via feedparser
# ---------------------------------------------------------------------------
def fetch_rss():
    """Fetch headlines from configured RSS feeds."""
    items = []
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                items.append(
                    {
                        "source": name,
                        "title": entry.get("title", ""),
                        "description": entry.get("summary", ""),
                    }
                )
        except Exception as e:
            print(f"WARNING: RSS fetch failed for {name}: {e}")
    return items


# ---------------------------------------------------------------------------
# 4. AI PROCESSING — Gemini filters + summarizes + translates
# ---------------------------------------------------------------------------
def build_prompt(news_items):
    raw_text = "\n\n".join(
        f"Source: {item['source']}\nTitle: {item['title']}\nDetails: {item['description']}"
        for item in news_items
        if item["title"]
    )

    prompt = f"""You are creating a "Daily Current Affairs" digest for Indian students
preparing for SSC, Railway (RRB), and one-day competitive exams.

From the raw news items below, select ONLY items relevant to exam preparation:
- Government Schemes & Policies
- Sports (achievements, tournaments, records)
- Appointments & Awards (new officials, resignations, honors)
- Science & Technology (ISRO, defence tech, research breakthroughs)

STRICTLY EXCLUDE: politics, crime, accidents, opinion pieces, and anything not
useful for a general knowledge exam.

OUTPUT FORMAT (follow exactly):
- Bulleted list, one news item per bullet.
- Each bullet: the Hindi summary FIRST, immediately followed by the English
  translation on the same bullet, separated by " / ".
- Keep each language version to 1–2 concise sentences focused on exam-relevant
  facts (names, numbers, dates, places).
- Group bullets under bold category headings: **योजनाएं / Schemes**,
  **खेल / Sports**, **नियुक्तियां / Appointments**, **विज्ञान / Science**.
- If a category has no relevant news today, omit that heading entirely.
- Do not add any preamble, disclaimer, or closing remarks — output only the
  bulleted digest.

RAW NEWS ITEMS:
{raw_text}
"""
    return prompt


def get_ai_summary(news_items):
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = build_prompt(news_items)

    # मॉडल का नाम बदलकर gemini-pro कर दिया है ताकि 404 एरर ना आए
    response = client.models.generate_content(
        model="gemini-pro",
        contents=prompt,
    )
    return response.text.strip()


# ---------------------------------------------------------------------------
# 5. SAVE — dated Markdown file + a JSON feed the frontend can read
# ---------------------------------------------------------------------------
def save_output(summary_text):
    today = datetime.datetime.now()
    date_str = today.strftime("%d-%m-%Y")
    filename = f"Current_Affairs_{date_str}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    display_date = today.strftime("%d %B %Y")
    md_content = f"# GK Parchi — Daily Current Affairs — {display_date}\n\n{summary_text}\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Update latest.json — a small manifest the static frontend fetches
    # instead of trying to guess today's filename.
    manifest_path = os.path.join(OUTPUT_DIR, "latest.json")
    archive = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                archive = existing.get("archive", [])
        except (json.JSONDecodeError, OSError):
            archive = []

    archive = [a for a in archive if a["file"] != filename]
    archive.insert(0, {"date": date_str, "file": filename})
    archive = archive[:30]  # keep last 30 days

    manifest = {
        "latest_date": date_str,
        "latest_file": filename,
        "latest_content": md_content,
        "archive": archive,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Saved: {filepath}")
    print(f"Updated manifest: {manifest_path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("Fetching GNews headlines...")
    gnews_items = fetch_gnews()
    print(f"  → {len(gnews_items)} items")

    print("Fetching RSS feeds...")
    rss_items = fetch_rss()
    print(f"  → {len(rss_items)} items")

    all_items = gnews_items + rss_items
    if not all_items:
        print("ERROR: No news items fetched from any source. Aborting.")
        sys.exit(1)

    print("Sending to Gemini for filtering + bilingual summary...")
    summary = get_ai_summary(all_items)

    if not summary:
        print("ERROR: Gemini returned an empty response.")
        sys.exit(1)

    save_output(summary)
    print("Done.")


if __name__ == "__main__":
    main()
