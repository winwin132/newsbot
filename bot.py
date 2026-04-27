import os
import requests
import discord
from discord.ext import commands

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")
    print("Slash commands synced")


@bot.tree.command(name="news", description="Get 3 AI summarized world news")
async def news(interaction: discord.Interaction):
    await interaction.response.send_message(
        "⏳ Fetching news... wait 10–30 seconds",
        ephemeral=True
    )

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/dispatches"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "discord-news-bot",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"event_type": "discord_news"},
        timeout=20,
    )

    if response.status_code == 204:
        await interaction.followup.send("✅ News workflow started!", ephemeral=True)
    else:
        await interaction.followup.send(
            f"❌ Failed: {response.status_code} {response.text}",
            ephemeral=True
        )


bot.run(DISCORD_BOT_TOKEN)
