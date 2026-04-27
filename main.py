import os
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from google import genai


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

client = genai.Client(api_key=GEMINI_API_KEY)


def fetch_news():
    url = "https://api.gdeltproject.org/api/v2/doc/doc"

    params = {
        "query": (
            "world OR global OR war OR economy OR election OR climate "
            "OR technology OR security OR diplomacy OR market OR disaster"
        ),
        "mode": "artlist",
        "format": "json",
        "maxrecords": 50,
        "sort": "hybridrel",
        "timespan": "24h",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    articles = data.get("articles", [])

    cleaned = []

    for article in articles:
        title = article.get("title")
        article_url = article.get("url")
        domain = article.get("domain")
        source_country = article.get("sourceCountry")
        seen_date = article.get("seendate")

        if title and article_url:
            cleaned.append({
                "title": title,
                "url": article_url,
                "domain": domain,
                "source_country": source_country,
                "seen_date": seen_date,
            })

    return cleaned[:50]


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
        return json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw_text, re.DOTALL)
        if not match:
            raise ValueError(f"Gemini response was not valid JSON:\n{raw_text}")
        return json.loads(match.group(0))


def send_discord_message(story, index):
    message = f"""🌍 **World News {index}/3**

**{story["headline"]}**

{story["content"]}

Source: {story["source"]}"""

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

    lines = []
    lines.append("AI World News Log")
    lines.append(f"Generated at: {timestamp}")
    lines.append("AI model: Gemini 2.5 Flash")
    lines.append("=" * 60)
    lines.append("")

    for i, story in enumerate(stories, start=1):
        lines.append(f"{i}. {story['headline']}")
        lines.append("")
        lines.append(story["content"])
        lines.append("")
        lines.append(f"Source: {story['source']}")
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

    if len(stories) != 3:
        raise ValueError("Gemini did not return exactly 3 stories.")

    for i, story in enumerate(stories, start=1):
        send_discord_message(story, i)

    save_log(stories)


if __name__ == "__main__":
    main()
