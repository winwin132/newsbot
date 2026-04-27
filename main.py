import os
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from google import genai


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

client = genai.Client(api_key=GEMINI_API_KEY)


def fetch_news():
    queries = [
        "top world news",
        "global economy news",
        "war geopolitics news",
        "climate disaster technology world news",
    ]

    all_articles = []

    for query in queries:
        rss_url = (
            "https://news.google.com/rss/search?"
            f"q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
        )

        try:
            response = requests.get(
                rss_url,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)

            for item in root.findall(".//item"):
                title = item.findtext("title")
                link = item.findtext("link")
                pub_date = item.findtext("pubDate")
                source = item.findtext("source")

                if title and link:
                    all_articles.append({
                        "title": title,
                        "url": link,
                        "source": source or "Google News",
                        "seen_date": pub_date,
                    })

        except Exception as e:
            print(f"Failed to fetch RSS for query '{query}': {e}")

    seen_titles = set()
    unique_articles = []

    for article in all_articles:
        clean_title = article["title"].lower().strip()

        if clean_title not in seen_titles:
            unique_articles.append(article)
            seen_titles.add(clean_title)

    return unique_articles[:50]


def summarize_news(articles):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""
You are a serious world-news editor.

Today is {today} UTC.

From the article list, choose exactly 3 globally important news stories.

Each story must include:
- headline
- content
- source

Rules:
- Return valid JSON only.
- Do not include markdown.
- Do not invent facts.
- Only use the provided article list.
- Avoid duplicate stories.
- Each story must be less than 500 words.
- Be concise, direct, and useful.
- Focus on global impact: war, geopolitics, elections, economy, climate, technology, public safety, diplomacy, major disasters.
- Use the article URL as the source.

JSON format:
[
  {{
    "headline": "headline here",
    "content": "summary here",
    "source": "source URL here"
  }},
  {{
    "headline": "headline here",
    "content": "summary here",
    "source": "source URL here"
  }},
  {{
    "headline": "headline here",
    "content": "summary here",
    "source": "source URL here"
  }}
]

Articles:
{json.dumps(articles, ensure_ascii=False, indent=2)}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    raw_text = response.text.strip()

    try:
        stories = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw_text, re.DOTALL)
        if not match:
            raise ValueError(f"Gemini response was not valid JSON:\n{raw_text}")
        stories = json.loads(match.group(0))

    if not isinstance(stories, list):
        raise ValueError("Gemini response is not a list.")

    return stories[:3]


def send_discord_message(story, index):
    headline = story.get("headline", "No headline")
    content = story.get("content", "No content")
    source = story.get("source", "No source")

    message = f"""🌍 **World News {index}/3**

**{headline}**

{content}

Source: {source}"""

    if len(message) > 1900:
        message = message[:1850] + "\n\n[Message shortened for Discord limit.]"

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": message},
        timeout=30,
    )

    response.raise_for_status()


def save_log(stories):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
    filename = log_dir / f"news_{timestamp}.txt"

    lines = [
        "AI World News Log",
        f"Generated at: {timestamp}",
        "AI model: Gemini 2.5 Flash",
        "=" * 60,
        "",
    ]

    for i, story in enumerate(stories, start=1):
        lines.append(f"{i}. {story.get('headline', 'No headline')}")
        lines.append("")
        lines.append(story.get("content", "No content"))
        lines.append("")
        lines.append(f"Source: {story.get('source', 'No source')}")
        lines.append("")
        lines.append("-" * 60)
        lines.append("")

    filename.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved log to {filename}")


def main():
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY")

    if not DISCORD_WEBHOOK_URL:
        raise ValueError("Missing DISCORD_WEBHOOK_URL")

    articles = fetch_news()

    if not articles:
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": "No recent world news found."},
            timeout=30,
        )
        return

    stories = summarize_news(articles)

    if len(stories) < 3:
        raise ValueError("Gemini returned fewer than 3 stories.")

    for i, story in enumerate(stories[:3], start=1):
        send_discord_message(story, i)

    save_log(stories[:3])


if __name__ == "__main__":
    main()

