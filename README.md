# 📰 GK Parchi — Daily Current Affairs Automation

GK Parchi is a fully automated, zero-cost daily current affairs generator built for Indian competitive exam aspirants (SSC CGL, Railway, and similar exams). It fetches the latest news from multiple sources, summarizes it into a detailed, exam-focused bilingual digest using Google's Gemini API, and publishes it automatically — every day, without manual effort.

## ✨ Features

- **Automated daily runs** via GitHub Actions (no server, no manual trigger needed)
- **Wide multi-source news aggregation** — GNews API across 6 categories (general, nation, world, business, sports, science) + curated RSS feeds (The Hindu, NDTV Hindi, PIB)
- **Duplicate detection** — near-identical headlines reported by multiple sources are automatically merged instead of appearing twice
- **AI-powered, detailed summarization** using the Gemini API, with each news point written as a ~10–25 line explanation (background, key numbers, people/places involved, and exam relevance) rather than a one-line headline
- **Categorized digest**, in order:
  - PIB & Government Schemes
  - Polity & Governance (includes major political developments, protests/movements with policy significance, court rulings, and elections — only routine crime/accident reports are excluded)
  - Economy
  - International Relations
  - Sports
  - Appointments & Awards
  - Science & Technology
- **Top Headlines section** — every distinct headline fetched that day, raw and uncapped, so nothing gets filtered out even if it doesn't fit a fixed category
- **Bilingual output** — Hindi first, English translation alongside, tailored for competitive exam prep
- **Section-wise voice mode** — a 🔊 icon next to every heading reads just that section aloud (Hindi/English, adjustable speed), instead of loading the whole digest as audio at once
- **Self-healing model selection** — automatically detects which Gemini model is available for the configured API key, so the workflow doesn't break if a model gets deprecated
- **Auto-archiving** — each day's digest is saved as a dated Markdown file, with a `latest.json` manifest tracking the most recent 30 entries

## 🗂️ Project Structure

```
GK-Parchi/
├── .github/workflows/
│   └── automate.yml        # Daily GitHub Actions workflow
├── affairs/
│   ├── Current_Affairs_DD-MM-YYYY.md
│   └── latest.json         # Manifest of recent digests
├── data/
├── index.html               # Web UI (archive, quick-nav, voice mode)
├── main.py                  # Fetch → dedupe → summarize → save
├── requirements.txt
└── README.md
```

## ⚙️ How It Works

1. **Fetch** — Pulls headlines from GNews API (6 categories) and RSS feeds (The Hindu, NDTV Hindi, PIB)
2. **Deduplicate** — Merges near-identical headlines reported by multiple sources
3. **Summarize** — Sends the deduplicated news to the Gemini API with a prompt tailored for detailed, categorized, bilingual exam-style output, plus a raw Top Headlines list
4. **Save** — Writes the digest as a Markdown file inside `affairs/` and updates `latest.json`
5. **Publish** — Commits and pushes the generated files back to the repository automatically

## 🔧 Setup

1. Fork or clone this repository
2. **Add repository secrets** — go to Settings → Secrets and variables → Actions and add:

   | Secret Name | Description |
   |---|---|
   | `GNEWS_API_KEY` | API key from gnews.io |
   | `GEMINI_API_KEY` | API key from Google AI Studio |

3. **Enable Actions** — the workflow (`automate.yml`) runs automatically every day (~7:00 AM IST) and can also be triggered manually from the Actions tab
4. **Install dependencies** (for local testing):
   ```bash
   pip install -r requirements.txt
   python main.py
   ```

## 📦 Requirements

- Python 3.11+
- requests
- feedparser

## 📄 Output Format

Each digest is saved as:
```
affairs/Current_Affairs_DD-MM-YYYY.md
```

And indexed in `affairs/latest.json`:
```json
{
  "latest_date": "20-07-2026",
  "latest_file": "Current_Affairs_20-07-2026.md",
  "archive": [ { "date": "20-07-2026", "file": "Current_Affairs_20-07-2026.md" } ],
  "headline_count": 63
}
```

## 🙋 Why GK Parchi?

Most current affairs resources are either paid, cluttered with irrelevant noise, or not tailored for exam prep. GK Parchi solves this by generating a detailed, categorized, bilingual digest every single day — with wide news coverage, duplicate-free reporting, and a listen-along mode — completely free and automated.

## 📌 Roadmap

- [ ] Who's Who tracker (appointments, resignations, awards as a dedicated section)
- [ ] Bookmark feature for important news
- [ ] Weekly/monthly PDF compilation for revision
- [ ] Search/filter on the site

## 📜 License

This project is for personal and educational use.
