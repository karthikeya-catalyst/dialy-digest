import os, re, time, smtplib, ssl, html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import feedparser, requests

FEEDS = {
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Google News (AI)": "https://news.google.com/rss/search?q=Artificial+Intelligence+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
    "Hacker News": "https://news.ycombinator.com/rss",
}
PER_FEED = 10
MODEL = "gemini-2.5-flash"

PROMPT = """You are a Daily Tech Digest Assistant.

Create a clean HTML email briefing from the provided news items. Do NOT use markdown symbols like ### or **. Use HTML tags instead. Output only the HTML, no code fences.

Format the output strictly as:

<h1>🚀 Daily Tech Briefing</h1>
<br>

<div>
  <h2 style="color: #1a73e8; margin-bottom: 4px;">1. [Title of News]</h2>
  <p style="margin: 2px 0;"><b>Category:</b> [e.g., AI / Cybersecurity]</p>
  <p style="margin: 2px 0;"><b>Summary:</b> [1 crisp sentence summary]</p>
  <p style="margin: 2px 0;"><b>Why it Matters:</b> [1 short sentence for CS/AI student]</p>
  <p style="margin: 2px 0;"><a href="[article link]">Read more</a></p>
</div>
<br><hr><br>

Repeat this for all 5 updates. Pick the 5 most important, varied items.

Articles Data:
"""

def collect():
    items = []
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:PER_FEED]:
                summary = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:300]
                items.append({"source": source, "title": e.get("title", ""),
                              "link": e.get("link", ""), "summary": html.unescape(summary)})
        except Exception as ex:
            print(f"Feed failed ({source}): {ex}")
    return items

def ask_gemini(items):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body = {"contents": [{"parts": [{"text": PROMPT + str(items)}]}]}
    headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"}
    for attempt in range(4):
        r = requests.post(url, json=body, headers=headers, timeout=90)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return re.sub(r"^```(?:html)?\s*|\s*```$", "", text.strip())
        print(f"Gemini {r.status_code}, retrying...")
        time.sleep(15 * (attempt + 1))
    r.raise_for_status()

def send(html_body):
    user, pwd = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    to = [x.strip() for x in os.environ["TO_EMAILS"].split(",")]
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = "Daily Tech Digest Summary", user, ", ".join(to)
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pwd)
        s.sendmail(user, to, msg.as_string())

if __name__ == "__main__":
    items = collect()
    if not items:
        raise SystemExit("No articles fetched")
    send(ask_gemini(items))
    print("Sent.")
