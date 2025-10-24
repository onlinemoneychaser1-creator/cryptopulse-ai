"""
CryptoPulse.AI v4.3 — Clean, no links, improved LinkedIn/Substack + tweet generation
Author: Manuel (omcdigest.bsky.social)
"""

import os
import re
import requests
import feedparser
from datetime import datetime, timezone
from dotenv import load_dotenv

# === CONFIGURAÇÕES ===
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CRYPTOPANIC_TOKEN = os.getenv("CRYPTOPANIC_TOKEN", "")
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE", "")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD", "")
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

OUT_DIR = "out"
os.makedirs(OUT_DIR, exist_ok=True)

# === Funções utilitárias ===
def clean_text(text):
    # Remove URLs e símbolos estranhos
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)
    text = text.replace("—", "-").strip()
    return text

# === 1️⃣ Buscar notícias ===
def fetch_news(limit=8):
    print("📰 A buscar notícias de crypto...")
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {"auth_token": CRYPTOPANIC_TOKEN, "filter": "hot", "public": "true"}
    items = []
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json().get("results", [])
        for i in data[:limit]:
            title = clean_text(i.get("title", ""))
            source = (i.get("source") or {}).get("title", "")
            items.append(f"{title} ({source})")
        print(f"✅ {len(items)} notícias obtidas.")
    except Exception as e:
        print("⚠️ Falha no CryptoPanic, a usar fallback do Google News...", e)
        rss = "https://news.google.com/rss/search?q=cryptocurrency&hl=en&gl=US&ceid=US:en"
        feed = feedparser.parse(rss)
        items = [clean_text(e.title) for e in feed.entries[:limit]]
    return items

# === 2️⃣ Resumo IA ===
def summarize(news_items):
    print("🤖 A resumir notícias...")
    if not OPENAI_API_KEY:
        return "\n".join(news_items)

    prompt = f"""
Write 8-10 concise bullet points summarizing today's cryptocurrency news headlines.
Neutral tone, professional, in English. Each bullet should have a short title in bold.
Headlines:
{chr(10).join(news_items)}
"""
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 1000,
    }
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# === 3️⃣ LinkedIn/Substack ===
def long_form_post(news_items):
    print("✍️ A criar artigo para LinkedIn/Substack...")
    prompt = f"""
Write a coherent daily crypto analysis post based on these headlines:
{chr(10).join(news_items)}

Structure:
- Engaging intro paragraph summarizing the market mood.
- 3-4 key insights explained in full sentences.
- Closing paragraph with a future outlook or reflection.
Tone: editorial, informative, calm.
Output in English.
"""
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "max_tokens": 1200}
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# === 4️⃣ Tweets ===
def generate_tweets(news_items):
    print("🐦 A criar tweets individuais...")
    prompt = f"""
Write one short, punchy English tweet (max 250 characters each) for every headline below.
No hashtags, no links, no emojis.
Headlines:
{chr(10).join(news_items)}
"""
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "max_tokens": 700}
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# === 5️⃣ Postar no Bluesky ===
def post_to_bluesky(text):
    if DRY_RUN:
        print("🚫 DRY_RUN ativo — simulação:", text[:120], "...")
        return
    print("🌐 A publicar no Bluesky...")
    try:
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
        record = {"$type": "app.bsky.feed.post", "text": text.strip(), "createdAt": datetime.now(timezone.utc).isoformat()}
        data = {"collection": "app.bsky.feed.post", "repo": BLUESKY_HANDLE, "record": record}
        post = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord", headers=headers, json=data, timeout=20)
        post.raise_for_status()
        print("✅ Publicado no Bluesky!")
    except Exception as e:
        print("⚠️ Erro ao publicar no Bluesky:", e)

# === 6️⃣ MAIN ===
def main():
    print("\n=== CryptoPulse.AI — Run", datetime.now(timezone.utc), "===\n")
    news = fetch_news(10)
    if not news:
        print("❌ Nenhuma notícia encontrada.")
        return

    summary = summarize(news)
    long_post = long_form_post(news)
    tweets = generate_tweets(news)

    date = datetime.now().strftime("%Y-%m-%d_%Hh%M")

    # Guardar ficheiros com timestamp
    with open(os.path.join(OUT_DIR, f"{date}_summary.md"), "w", encoding="utf-8") as f:
        f.write(summary)
    with open(os.path.join(OUT_DIR, f"{date}_linkedin.txt"), "w", encoding="utf-8") as f:
        f.write(long_post)
    with open(os.path.join(OUT_DIR, f"{date}_tweets.txt"), "w", encoding="utf-8") as f:
        f.write(tweets)

    # Publicar no Bluesky — sem links
    print("\n🌐 A publicar posts no Bluesky...")
    for n in news[:5]:
        title = clean_text(n.split("(")[0]).strip()
        post_to_bluesky(title[:280])

    print("\n💾 Guardado:")
    print(f"• out/{date}_summary.md — resumo IA")
    print(f"• out/{date}_linkedin.txt — artigo completo")
    print(f"• out/{date}_tweets.txt — tweets sugeridos")

    if DRY_RUN:
        print("\n🚫 DRY_RUN ativo — Nenhum post foi publicado.")
    else:
        print("\n✨ Concluído com sucesso!")


if __name__ == "__main__":
    main()
