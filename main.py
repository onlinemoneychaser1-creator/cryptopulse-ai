"""
CryptoPulse.AI v3.0 — Multi-platform Daily Bot
Author: Manuel (omcdigest.bsky.social)
"""

import os
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

OUT_DIR = "out"
os.makedirs(OUT_DIR, exist_ok=True)

# === 1️⃣ Buscar notícias ===
def fetch_news(limit=10):
    print("📰 A buscar notícias de crypto...")
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {"auth_token": CRYPTOPANIC_TOKEN, "filter": "hot", "public": "true"}
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json().get("results", [])
        if data:
            print(f"✅ {len(data[:limit])} notícias obtidas do CryptoPanic.")
            return [
                f"- {i.get('title')} ({(i.get('source') or {}).get('title','')}) — {i.get('url')}"
                for i in data[:limit]
            ]
    except Exception as e:
        print("⚠️ Falha no CryptoPanic, a usar fallback do Google News...", e)
        rss = "https://news.google.com/rss/search?q=cryptocurrency&hl=en&gl=US&ceid=US:en"
        feed = feedparser.parse(rss)
        items = [f"- {e.title} ({e.link})" for e in feed.entries[:limit]]
        return items
    return []

# === 2️⃣ Resumo IA ===
def summarize(news_items):
    print("🤖 A resumir notícias...")
    if not OPENAI_API_KEY:
        print("⚠️ Falta OpenAI API key.")
        return "\n".join(news_items)

    prompt = f"""
Summarize the following {len(news_items)} cryptocurrency news headlines.
Output:
- 8 to 10 concise bullet points, neutral tone, English.
- Include short, catchy titles per bullet.
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

# === 3️⃣ Gerar guião para Shorts ===
def make_youtube_script(news_items):
    print("🎬 A criar guião para YouTube Short...")
    if not OPENAI_API_KEY:
        return "⚠️ Missing OpenAI key. Cannot generate script."

    prompt = f"""
Write a 60-second YouTube Short script summarizing today's top 3 cryptocurrency stories.
Tone: futuristic, informative, fast-paced.
Include an engaging intro and outro.
Headlines:
{chr(10).join(news_items[:3])}
"""

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 600,
    }
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# === 4️⃣ Postar no Bluesky ===
def post_to_bluesky(text):
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
        data = {
            "collection": "app.bsky.feed.post",
            "repo": BLUESKY_HANDLE,
            "record": {
                "$type": "app.bsky.feed.post",
                "text": text[:300],
                "createdAt": datetime.now(timezone.utc).isoformat(),
            },
        }

        post = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers=headers,
            json=data,
            timeout=20,
        )
        post.raise_for_status()
        print("✅ Publicado no Bluesky com sucesso!")
    except Exception as e:
        print("⚠️ Erro ao publicar no Bluesky:", e)

# === 5️⃣ MAIN ===
def main():
    print("\n=== CryptoPulse.AI — Run", datetime.now(timezone.utc), "===\n")
    news = fetch_news(6)
    if not news:
        print("❌ Nenhuma notícia encontrada.")
        return

    summary = summarize(news)
    short_script = make_youtube_script(news)

    date = datetime.now().strftime("%Y-%m-%d")

    # Criar versão longa para LinkedIn/Substack
    long_post_prompt = f"""
Write a professional English LinkedIn/Substack-style crypto update based on these news:
{chr(10).join(news)}
Include short intro paragraph, bullet points, and closing line inviting engagement.
"""
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": long_post_prompt}],
        "temperature": 0.6,
        "max_tokens": 1000,
    }
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body, timeout=90)
    long_post = r.json()["choices"][0]["message"]["content"]

    # Guardar ficheiros
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"{date}_summary.md"), "w", encoding="utf-8") as f:
        f.write(summary)
    with open(os.path.join(OUT_DIR, f"{date}_short.txt"), "w", encoding="utf-8") as f:
        f.write(short_script)
    with open(os.path.join(OUT_DIR, f"{date}_linkedin.txt"), "w", encoding="utf-8") as f:
        f.write(long_post)

    # Bluesky: cria posts separados
    print("\n🌐 A publicar múltiplos posts no Bluesky...")
    for n in news[:5]:
        text = n.split(" — ")[0][:280]  # texto curto
        post_to_bluesky(text)

    print("\n💾 Guardado:")
    print(f"• out/{date}_summary.md — resumo IA")
    print(f"• out/{date}_linkedin.txt — texto longo")
    print(f"• out/{date}_short.txt — guião YouTube")

    print("\n✨ Concluído com sucesso!")
from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

def generate_cover_image(title):
    print("🖼️ A gerar imagem de capa...")
    prompt = f"Futuristic crypto market background, bitcoin, ethereum, neon data charts, for article titled '{title}'"
    image = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1024")
    url = image.data[0].url
    print("🖼️ Imagem gerada:", url)
    return url
if __name__ == "__main__":
    main()

