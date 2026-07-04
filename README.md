📰 GK Parchi — Daily Current Affairs Automation
GK Parchi is a fully automated, zero-cost daily current affairs generator built for Indian competitive exam aspirants (SSC CGL, Railway, and similar exams). It fetches the latest news, summarizes it into an exam-focused bilingual digest using Google's Gemini API, and publishes it automatically — every day, without manual effort.
✨ Features
Automated daily runs via GitHub Actions (no server, no manual trigger needed)
Multi-source news aggregation — GNews API + curated RSS feeds (The Hindu, NDTV Hindi)
AI-powered summarization using the Gemini API, categorized into:
Schemes
Sports
Appointments
Science
Bilingual output — Hindi first, English translation alongside, tailored for competitive exam prep
Politics/crime excluded — keeps focus strictly on exam-relevant GK
Self-healing model selection — automatically detects which Gemini model is available for the configured API key, so the workflow doesn't break if a model gets deprecated
Auto-archiving — each day's digest is saved as a dated Markdown file, with a latest.json manifest tracking the most recent 30 entries
🗂️ Project Structure
Code
⚙️ How It Works
Fetch — Pulls top headlines from GNews API and RSS feeds (The Hindu, NDTV Hindi)
Summarize — Sends aggregated news to the Gemini API with a prompt tailored for exam-style, categorized, bilingual output
Save — Writes the digest as a Markdown file inside affairs/ and updates latest.json
Publish — Commits and pushes the generated files back to the repository automatically
🔧 Setup
1. Fork or clone this repository
2. Add repository secrets
Go to Settings → Secrets and variables → Actions and add:
Secret Name
Description
GNEWS_API_KEY
API key from gnews.io
GEMINI_API_KEY
API key from Google AI Studio
3. Enable Actions
The workflow (automate.yml) runs automatically every day (~7:00 AM IST) and can also be triggered manually from the Actions tab.
4. Install dependencies (for local testing)
Bash
📦 Requirements
Python 3.11+
requests
feedparser
📄 Output Format
Each digest is saved as:
Code
And indexed in affairs/latest.json:
Json
🙋 Why GK Parchi?
Most current affairs resources are either paid, cluttered with politics/crime, or not tailored for exam prep. GK Parchi solves this by generating a clean, categorized, bilingual digest every single day — completely free and automated.
📌 Roadmap
[ ] Webpage to browse and search past digests
[ ] PDF export of monthly compilations
[ ] Topic-wise filtering (Schemes / Sports / Appointments / Science)
📜 License
This project is for personal and educational use.# GK-Parchi
