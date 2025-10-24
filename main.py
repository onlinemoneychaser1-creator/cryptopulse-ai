"""
CryptoPulse.AI v4.5 — Scheduled, Bluesky, LinkedIn, Substack, Tweets, Shorts script
Author: Manuel (omcdigest.bsky.social)
"""

import os
import re
import requests
import feedparser
from datetime import datetime, timezone
from dotenv import load_dotenv

# === CONFIG ===============================================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CRYPTOPANIC_TOKEN = os.getenv("CRYPTOPANIC_TOKEN", "")
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE", "")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD", "")
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

OUT_DIR = "out"
os.makedirs(OUT_DIR, exist_ok=True)


# === HELPERS =============================================================================
def clean_text(text):
    """Remove URLs e lixo visual para posts curtos."""
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)
    text = text.replace("—", "-").strip()
    return text


def timestamp():
    # Ex: 2025-10-25_08h12
    return datetime.now().strftime("%Y-%m-%d_%Hh%M")


# === 1) FETCH NEWS =======================================================================
def fetch_news(limit=8):
    print("📰 A buscar notícias de crypto...")
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        "auth_token": CRYPTOPANIC_TOKEN,
        "filter": "hot",
        "public": "true"
    }
    headlines = []
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json().get("results", [])
        for item in data[:limit]:
            title = clean_text(item.get("title", ""))
            source = (item.get("source") or {}).get("title", "")
            if source:
                headlines.append(f"{title} ({source})")
            else:
                headlines.append(title)
        print(f"✅ {len(headlines)} notícias obtidas do CryptoPanic.")
    except Exception as e:
        print("⚠️ Falha no CryptoPanic, fallback Google News:", e)
        rss = "https://news.google.com/rss/search?q=cryptocurrency&hl=en&gl=US&ceid=US:en"
        feed = feedparser.parse(rss)
        for entry in feed.entries[:limit]:
            headlines.append(clean_text(entry.title))
        print(f"✅ {len(headlines)} notícias obtidas via Google News fallback.")
    return headlines


# === 2) AI CALL ==========================================================================
def call_openai(prompt, max_tokens=1000, temperature=0.6):
    """Faz uma chamada simples ao modelo de texto."""
    if not OPENAI_API_KEY:
        print("⚠️ Falta OPENAI_API_KEY, devolvo prompt.")
        return f"[NO_AI_KEY]\n{prompt}"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# === 3) CONTENT GENERATORS ===============================================================
def build_summary(news_items):
    print("📌 A gerar summary bullets...")
    prompt = f"""
Summarize today's cryptocurrency landscape in 8 concise bullet points.
Each bullet: start with a short bold-style title (like **ETF Surge:**) and then 1 sentence.
Keep it neutral, informative, English.
Base it ONLY on these headlines:
{chr(10).join(news_items)}
"""
    return call_openai(prompt, max_tokens=1000, temperature=0.5)


def build_linkedin(news_items):
    print("💼 A gerar LinkedIn post...")
    prompt = f"""
Write a professional English LinkedIn-style crypto analysis post based on these headlines:
{chr(10).join(news_items)}

Format:
1. Strong intro (market mood / why today matters).
2. 3-4 short paragraphs tying events together (not bullet points; flowing analysis).
3. Closing inviting discussion.

Tone: calm, informed, credible. No emojis.
"""
    return call_openai(prompt, max_tokens=1000, temperature=0.6)


def build_substack(news_items):
    print("📰 A gerar Substack newsletter...")
    prompt = f"""
Write a conversational daily crypto newsletter in English.
Audience: curious investors who don't have time.
Style:
- Warm intro "Good morning..."
- Then walk through 3-4 key stories in plain language
- Last line is a forward-looking teaser ("watch this next")

Use short paragraphs. No emojis.
Base ONLY on:
{chr(10).join(news_items)}
"""
    return call_openai(prompt, max_tokens=1000, temperature=0.7)


def build_youtube_script(news_items):
    print("🎬 A gerar guião YouTube Shorts...")
    prompt = f"""
Write a 60-second YouTube Shorts script in English.
Goal: fast, hype, but still factual.
Rules:
- Hook in first 2 seconds.
- Then 3 biggest crypto stories today, 1-2 punchy sentences each.
- End with "Follow for daily crypto in 60 seconds."

Keep sentences short, like spoken voice.
Base ONLY on:
{chr(10).join(news_items[:3])}
"""
    return call_openai(prompt, max_tokens=700, temperature=0.7)


def build_tweets(news_items):
    print("🐦 A gerar tweets...")
    prompt = f"""
For EACH headline below, write one tweet in English (max 250 characters).
No links, no hashtags, no emojis.
Tweets should sound confident and analytical, not hype.
Return them as a numbered list (1., 2., 3., ...).

Headlines:
{chr(10).join(news_items)}
"""
    return call_openai(prompt, max_tokens=800, temperature=0.6)


# === 4) BLUESKY POSTING ==================================================================
def post_to_bluesky(text):
    """Publica um post básico no Bluesky (ou simula se DRY_RUN=1)."""
    clean = text.strip()
    clean = clean_text(clean)
    clean = clean[:280]  # garantes limite

    if DRY_RUN:
        print("🚫 DRY_RUN ativo — simulação de Bluesky:", clean[:120], "...")
        return

    print("🌐 A publicar no Bluesky...")
    try:
        # login
        session = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": BLUESKY_HANDLE, "password": BLUESKY_PASSWORD},
            timeout=20,
        )
        session.raise_for_status()
        access_token = session.json().get("accessJwt")
        if not access_token:
            print("❌ Falha no login Bluesky.")
            return

        headers = {"Authorization": f"Bearer {access_token}"}
        record = {
            "$type": "app.bsky.feed.post",
            "text": clean,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        data = {
            "collection": "app.bsky.feed.post",
            "repo": BLUESKY_HANDLE,
            "record": record,
        }

        post = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers=headers,
            json=data,
            timeout=20,
        )
        post.raise_for_status()
        print("✅ Publicado no Bluesky!")
    except Exception as e:
        print("⚠️ Erro ao publicar no Bluesky:", e)


# === 5) MAIN =============================================================================
def main():
    print("\n=== CryptoPulse.AI — Run", datetime.now(timezone.utc), "===\n")

    # 1. Buscar notícias
    news = fetch_news(10)
    if not news:
        print("❌ Nenhuma notícia encontrada.")
        return

    # 2. Gerar conteúdo
    summary_md   = build_summary(news)
    linkedin_txt = build_linkedin(news)
    substack_txt = build_substack(news)
    shorts_txt   = build_youtube_script(news)
    tweets_txt   = build_tweets(news)

    # 3. Timestamp para ficheiros
    stamp = timestamp()

    summary_path   = os.path.join(OUT_DIR, f"{stamp}_summary.md")
    linkedin_path  = os.path.join(OUT_DIR, f"{stamp}_linkedin.txt")
    substack_path  = os.path.join(OUT_DIR, f"{stamp}_substack.txt")
    shorts_path    = os.path.join(OUT_DIR, f"{stamp}_shorts.txt")
    tweets_path    = os.path.join(OUT_DIR, f"{stamp}_tweets.txt")

    # 4. Guardar localmente (no runner da cloud OU no teu PC se correres local)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_md)

    with open(linkedin_path, "w", encoding="utf-8") as f:
        f.write(linkedin_txt)

    with open(substack_path, "w", encoding="utf-8") as f:
        f.write(substack_txt)

    with open(shorts_path, "w", encoding="utf-8") as f:
        f.write(shorts_txt)

    with open(tweets_path, "w", encoding="utf-8") as f:
        f.write(tweets_txt)

    # 5. Bluesky (publica só os títulos, sem links)
    print("\n🌐 A publicar posts no Bluesky...")
    for headline in news[:5]:
        # headline vem tipo "Bitcoin pumps after ETF approval (CoinDesk)"
        # queremos só a parte antes do '('
        title_only = headline.split("(")[0].strip()
        post_to_bluesky(title_only)

    print("\n💾 Ficheiros gerados:")
    print("•", summary_path,   "— resumo bullets")
    print("•", linkedin_path,  "— LinkedIn pro")
    print("•", substack_path,  "— Substack newsletter")
    print("•", shorts_path,    "— YouTube Shorts script")
    print("•", tweets_path,    "— tweets para X")

    if DRY_RUN:
        print("\n🚫 DRY_RUN ativo — Nenhum post real foi publicado.")
    else:
        print("\n✨ Concluído com sucesso!")


if __name__ == "__main__":
    main()
