import feedparser
import json
import os
import hashlib
import requests
import praw
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

HEADERS = {
    "User-Agent": "LevelFeed-IndieRadar/1.0 (gaming news aggregator)"
}

# ─────────────────────────────────────────
#  REDDIT — PRAW (free API)
# ─────────────────────────────────────────
def get_reddit():
    return praw.Reddit(
        client_id     = os.environ["REDDIT_CLIENT_ID"],
        client_secret = os.environ["REDDIT_CLIENT_SECRET"],
        user_agent    = "LevelFeed-IndieRadar/1.0",
    )

SUBREDDITS = ["indiegaming", "gamedev", "Steam", "IndieGames", "indiegamedev"]

def fetch_reddit_hot(reddit) -> list:
    items = []
    title_tracker = defaultdict(list)  # title keyword → subreddits seen on

    for sub_name in SUBREDDITS:
        try:
            subreddit = reddit.subreddit(sub_name)
            for post in subreddit.hot(limit=25):
                if post.score < 50:
                    continue
                title_lower = post.title.lower()
                title_tracker[title_lower].append(sub_name)
                items.append({
                    "title":      post.title,
                    "link":       f"https://reddit.com{post.permalink}",
                    "subreddit":  sub_name,
                    "score":      post.score,
                    "comments":   post.num_comments,
                    "flair":      post.link_flair_text or "",
                    "fetched":    datetime.now(timezone.utc).isoformat(),
                })
            print(f"    Reddit r/{sub_name}: ok")
        except Exception as e:
            print(f"    [WARN] Reddit r/{sub_name}: {e}")

    # Boost items that appeared in multiple subreddits (cross-subreddit signal)
    cross_posts = {t for t, subs in title_tracker.items() if len(subs) > 1}
    for item in items:
        item["cross_subreddit"] = item["title"].lower() in cross_posts

    return items

# ─────────────────────────────────────────
#  STEAM — new & trending + upcoming
# ─────────────────────────────────────────
def fetch_steam_trending() -> list:
    items = []
    urls = [
        "https://store.steampowered.com/feeds/newreleases.xml",
        "https://store.steampowered.com/feeds/upcoming.xml",
    ]
    for url in urls:
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
            for entry in feed.entries[:20]:
                title = getattr(entry, "title", "").strip()
                link  = getattr(entry, "link", "").strip()
                if title and link:
                    items.append({
                        "title":   title,
                        "link":    link,
                        "source":  "Steam",
                        "fetched": datetime.now(timezone.utc).isoformat(),
                    })
            print(f"    Steam RSS {url.split('/')[-1]}: ok")
        except Exception as e:
            print(f"    [WARN] Steam RSS: {e}")
    return items

def fetch_steamspy_trending() -> list:
    """SteamSpy API — free, no key required. Returns trending indie games."""
    items = []
    try:
        # genre=indie, sorted by recent players growth
        r = requests.get(
            "https://steamspy.com/api.php",
            params={"request": "genre", "genre": "Indie"},
            headers=HEADERS,
            timeout=15
        )
        data = r.json()
        # Sort by players_2weeks descending (recent momentum)
        sorted_games = sorted(
            data.items(),
            key=lambda x: x[1].get("players_2weeks", 0),
            reverse=True
        )[:20]

        for appid, info in sorted_games:
            name = info.get("name", "")
            if name:
                items.append({
                    "title":          name,
                    "link":           f"https://store.steampowered.com/app/{appid}",
                    "appid":          appid,
                    "players_2weeks": info.get("players_2weeks", 0),
                    "positive":       info.get("positive", 0),
                    "negative":       info.get("negative", 0),
                    "price":          info.get("price", 0),
                    "source":         "SteamSpy",
                    "fetched":        datetime.now(timezone.utc).isoformat(),
                })
        print(f"    SteamSpy: {len(items)} indie games")
    except Exception as e:
        print(f"    [WARN] SteamSpy: {e}")
    return items

# ─────────────────────────────────────────
#  ITCH.IO — hot section
# ─────────────────────────────────────────
def fetch_itchio_hot() -> list:
    items = []
    try:
        r = requests.get(
            "https://itch.io/games/new-and-popular",
            headers=HEADERS,
            timeout=15
        )
        soup = BeautifulSoup(r.text, "html.parser")
        for game_cell in soup.select(".game_cell")[:20]:
            title_el = game_cell.select_one(".game_title")
            link_el  = game_cell.select_one("a.game_link")
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            link  = link_el.get("href", "")
            desc_el = game_cell.select_one(".game_text")
            desc  = desc_el.get_text(strip=True) if desc_el else ""

            # Rating signal
            rating_el = game_cell.select_one(".aggregate_rating")
            rating = float(rating_el.get_text(strip=True)) if rating_el else 0.0

            items.append({
                "title":   title,
                "link":    link,
                "desc":    desc[:200],
                "rating":  rating,
                "source":  "itch.io",
                "fetched": datetime.now(timezone.utc).isoformat(),
            })
        print(f"    itch.io: {len(items)} games")
    except Exception as e:
        print(f"    [WARN] itch.io: {e}")
    return items

# ─────────────────────────────────────────
#  KICKSTARTER — games RSS
# ─────────────────────────────────────────
def fetch_kickstarter_games() -> list:
    items = []
    try:
        feed = feedparser.parse(
            "https://www.kickstarter.com/discover/advanced.atom?category_id=35&sort=newest",
            request_headers=HEADERS
        )
        for entry in feed.entries[:15]:
            title = getattr(entry, "title", "").strip()
            link  = getattr(entry, "link", "").strip()
            if title and link:
                items.append({
                    "title":   title,
                    "link":    link,
                    "source":  "Kickstarter",
                    "fetched": datetime.now(timezone.utc).isoformat(),
                })
        print(f"    Kickstarter: {len(items)} projects")
    except Exception as e:
        print(f"    [WARN] Kickstarter: {e}")
    return items

# ─────────────────────────────────────────
#  HYPE SCORE ALGORITHM
# ─────────────────────────────────────────
def calculate_hype_score(game_title: str, reddit_items: list,
                          steam_items: list, itch_items: list) -> dict:
    """
    Score 1–10 based on signals:
      - Reddit mentions across multiple subreddits (+3)
      - Reddit post score > 500             (+2)
      - Reddit post score > 200             (+1)
      - SteamSpy players_2weeks growth      (+2)
      - itch.io high rating (> 4.0)         (+1)
      - Cross-subreddit appearance          (+1)
    """
    score = 0
    signals = []
    title_lower = game_title.lower()

    # Reddit signals
    reddit_mentions = [r for r in reddit_items if title_lower in r["title"].lower()]
    if reddit_mentions:
        max_score = max(r["score"] for r in reddit_mentions)
        subs_seen = list({r["subreddit"] for r in reddit_mentions})
        if len(subs_seen) > 1:
            score += 3
            signals.append(f"trending in {len(subs_seen)} subreddits: {', '.join(subs_seen)}")
        if max_score > 500:
            score += 2
            signals.append(f"Reddit score {max_score}")
        elif max_score > 200:
            score += 1
            signals.append(f"Reddit score {max_score}")
        if any(r.get("cross_subreddit") for r in reddit_mentions):
            score += 1
            signals.append("cross-subreddit signal")

    # Steam signals
    steam_match = next((s for s in steam_items if title_lower in s["title"].lower()), None)
    if steam_match and steam_match.get("players_2weeks", 0) > 1000:
        score += 2
        signals.append(f"Steam: {steam_match['players_2weeks']:,} players (2 weeks)")

    # itch.io signal
    itch_match = next((i for i in itch_items if title_lower in i["title"].lower()), None)
    if itch_match and itch_match.get("rating", 0) >= 4.0:
        score += 1
        signals.append(f"itch.io rating {itch_match['rating']}")

    score = min(score, 10)  # cap at 10
    return {"score": score, "signals": signals}

# ─────────────────────────────────────────
#  BUILD RADAR ITEMS
# ─────────────────────────────────────────
def build_radar_items(reddit_items, steam_items, itch_items, ks_items) -> list:
    seen_titles = set()
    radar = []

    # Combine all game titles as candidates
    candidates = (
        [(i["title"], i["link"], "Reddit") for i in reddit_items] +
        [(i["title"], i["link"], "Steam")  for i in steam_items]  +
        [(i["title"], i["link"], "itch.io")for i in itch_items]   +
        [(i["title"], i["link"], "Kickstarter") for i in ks_items]
    )

    for title, link, source in candidates:
        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        hype = calculate_hype_score(title, reddit_items, steam_items, itch_items)

        radar.append({
            "id":       hashlib.md5(f"{title}{link}".encode()).hexdigest()[:12],
            "title":    title,
            "link":     link,
            "source":   source,
            "hype_score": hype["score"],
            "signals":    hype["signals"],
            "category": "indie",
            "fetched":  datetime.now(timezone.utc).isoformat(),
        })

    # Sort by hype score descending
    radar.sort(key=lambda x: x["hype_score"], reverse=True)
    return radar[:100]  # top 100

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
def run():
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    print("  Fetching Reddit...")
    reddit       = get_reddit()
    reddit_items = fetch_reddit_hot(reddit)

    print("  Fetching Steam...")
    steam_items  = fetch_steam_trending() + fetch_steamspy_trending()

    print("  Fetching itch.io...")
    itch_items   = fetch_itchio_hot()

    print("  Fetching Kickstarter...")
    ks_items     = fetch_kickstarter_games()

    print("  Calculating hype scores...")
    radar_items  = build_radar_items(reddit_items, steam_items, itch_items, ks_items)

    hot = [i for i in radar_items if i["hype_score"] >= 6]
    print(f"  Hot games (score ≥ 6): {len(hot)}")

    output = {
        "last_updated":  datetime.now(timezone.utc).isoformat(),
        "total":         len(radar_items),
        "hot_count":     len(hot),
        "items":         radar_items,
    }

    path = output_dir / "news_bot2.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"  Saved {len(radar_items)} items to {path}")

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  LevelFeed Bot 2 — Indie Radar")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}\n")
    run()
    print("\n  Done.\n")
