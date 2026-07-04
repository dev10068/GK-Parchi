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
    "The Hindu (National)": "https://www.thehindu.com/news/national/feeder/default.rss",
    "NDTV India (Hindi)": "https://feeds.feedburner.com/ndtv/ndtvkhabar",
}

OUTPUT_DIR = "affairs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_gnews():
    url = f"https://gnews.io/api/v4/top-headlines?category=general&lang=en&country=in&max=10&apikey={GNEWS_API_KEY}"
    items = []
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for article in data.get("articles", []):
            items.append({
                "source": f"GNews / {article.get('source', {}).get('name', 'Unknown')}",
                "title": article.get("title", ""),
                "description": article.get("description", ""),
            })
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
                    "description": entry.get("summary", ""),
                })
        except Exception as e:
            print(f"RSS Error: {e}")
    return items

def build_prompt(news_items):
    raw_text = "\n\n".join(
        f"Source: {item['source']}\nTitle: {item['title']}\nDetails: {item['description']}"
        for item in news_items if item["title"]
    )
    return f"""You are creating a "Daily Current Affairs" digest for Indian students preparing for SSC, Railway (RRB), and one-day exams.
From the raw news items below, select ONLY items relevant to exam preparation:
- Government Schemes & Policies
- Sports
- Appointments & Awards
- Science & Technology

EXCLUDE: politics, crime, accidents.

OUTPUT FORMAT:
- Bulleted list.
- Each bullet: the Hindi summary FIRST, immediately followed by the English translation on the same bullet, separated by " / ".
- Group bullets under bold category headings: **योजनाएं / Schemes**, **खेल / Sports**, **नियुक्तियां / Appointments**, **विज्ञान / Science**.

RAW NEWS:
{raw_text}"""

def get_ai_summary(news_items):
    # ब्रह्मास्त्र: बिना पैकेज के सीधा गूगल के सर्वर से बात करना
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = build_prompt(news_items)
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except requests.exceptions.HTTPError as e:
        print(f"Gemini API ERROR (Direct): {resp.status_code}")
        print(resp.text)  # अगर अब भी फेल हुआ, तो गूगल खुद बताएगा कि वो ऐसा क्यों कर रहा है!
        sys.exit(1)
    except Exception as e:
        print(f"Connection Error: {e}")
        sys.exit(1)

def save_output(summary_text):
    today = datetime.datetime.now()
    date_str = today.strftime("%d-%m-%Y")
    filename = f"Current_Affairs_{date_str}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    display_date = today.strftime("%d %B %Y")
    md_content = f"# GK Parchi — Daily Current Affairs — {display_date}\n\n{summary_text}\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    manifest_path = os.path.join(OUTPUT_DIR, "latest.json")
    archive = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                archive = json.load(f).get("archive", [])
        except:
            pass

    archive = [a for a in archive if a["file"] != filename]
    archive.insert(0, {"date": date_str, "file": filename})
    archive = archive[:30]

    manifest = {
        "latest_date": date_str,
        "latest_file": filename,
        "latest_content": md_content,
        "archive": archive,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")

def main():
    items = fetch_gnews() + fetch_rss()
    if not items:
        sys.exit(1)
    summary = get_ai_summary(items)
    if summary:
        save_output(summary)

if __name__ == "__main__":
    main()
