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
}

OUTPUT_DIR = "affairs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

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
            print(f"RSS Error: {e}")
    return items

def get_ai_summary(news_items):
    raw_text = "\n\n".join(f"Title: {i['title']}\nDetails: {i['description']}" for i in news_items if i["title"])
    prompt = f"Create a daily current affairs digest for Indian competitive exams. Group into: Schemes, Sports, Appointments, Science. Exclude politics/crime. Use bilingual format (Hindi first / English translation). Keep it concise.\n\nNews:\n{raw_text}"
    
    # ब्रह्मास्त्र: डायरेक्ट Google REST API (बिना किसी पैकेज के)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"API Error: {e}")
        if 'resp' in locals():
            print(resp.text)
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
        except:
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
    items = fetch_gnews() + fetch_rss()
    if not items:
        print("No news fetched.")
        sys.exit(1)
    
    summary = get_ai_summary(items)
    if summary:
        save_output(summary)
        print("Done successfully!")

if __name__ == "__main__":
    main()
