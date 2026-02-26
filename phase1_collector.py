#!/usr/bin/env python3
"""Coletor de métricas (Fase 1) para YouTube, X e Instagram.

Fluxo:
1) Lê credenciais do ambiente (.env opcional).
2) Coleta métricas básicas de conta e posts recentes.
3) Salva tudo em SQLite local.
4) Gera relatório simples no terminal.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

try:
    from googleapiclient.discovery import build
except ImportError:  # dependency opcional em tempo de edição
    build = None


DEFAULT_DB_PATH = Path("social_metrics.db")
UTC_NOW = lambda: datetime.now(timezone.utc).isoformat()


@dataclass
class PlatformSnapshot:
    platform: str
    account_id: str
    followers: int
    engagement_rate: float | None
    raw_payload: dict[str, Any]


@dataclass
class PostSnapshot:
    platform: str
    account_id: str
    post_id: str
    published_at: str | None
    impressions: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    watch_time: float | None
    raw_payload: dict[str, Any]


class MetricsDB:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS account_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    followers INTEGER NOT NULL,
                    engagement_rate REAL,
                    raw_payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS post_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    post_id TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    published_at TEXT,
                    impressions INTEGER,
                    likes INTEGER,
                    comments INTEGER,
                    shares INTEGER,
                    watch_time REAL,
                    raw_payload TEXT NOT NULL
                );
                """
            )

    def insert_account_snapshot(self, item: PlatformSnapshot) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO account_metrics (
                    platform, account_id, collected_at, followers, engagement_rate, raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.platform,
                    item.account_id,
                    UTC_NOW(),
                    item.followers,
                    item.engagement_rate,
                    json.dumps(item.raw_payload, ensure_ascii=False),
                ),
            )

    def insert_post_snapshots(self, items: Iterable[PostSnapshot]) -> None:
        rows = [
            (
                i.platform,
                i.account_id,
                i.post_id,
                UTC_NOW(),
                i.published_at,
                i.impressions,
                i.likes,
                i.comments,
                i.shares,
                i.watch_time,
                json.dumps(i.raw_payload, ensure_ascii=False),
            )
            for i in items
        ]
        if not rows:
            return

        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO post_metrics (
                    platform, account_id, post_id, collected_at, published_at,
                    impressions, likes, comments, shares, watch_time, raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def top_posts(self, platform: str, limit: int = 5) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT platform, post_id, published_at, impressions, likes, comments, shares
                    FROM post_metrics
                    WHERE platform = ?
                    ORDER BY COALESCE(likes, 0) + COALESCE(comments, 0) + COALESCE(shares, 0) DESC
                    LIMIT ?
                    """,
                    (platform, limit),
                )
            )


class YouTubeCollector:
    def __init__(self, api_key: str, channel_id: str) -> None:
        if build is None:
            raise RuntimeError("google-api-python-client não está instalado.")
        self.client = build("youtube", "v3", developerKey=api_key)
        self.channel_id = channel_id

    def collect(self, max_videos: int = 10) -> tuple[PlatformSnapshot, list[PostSnapshot]]:
        channel_resp = (
            self.client.channels()
            .list(part="statistics,snippet", id=self.channel_id)
            .execute()
        )
        items = channel_resp.get("items", [])
        if not items:
            raise RuntimeError("Canal do YouTube não encontrado.")

        channel = items[0]
        stats = channel.get("statistics", {})
        followers = int(stats.get("subscriberCount", 0))
        account_snapshot = PlatformSnapshot(
            platform="youtube",
            account_id=self.channel_id,
            followers=followers,
            engagement_rate=None,
            raw_payload=channel,
        )

        search_resp = (
            self.client.search()
            .list(
                part="id,snippet",
                channelId=self.channel_id,
                maxResults=max_videos,
                order="date",
                type="video",
            )
            .execute()
        )
        video_ids = [it["id"]["videoId"] for it in search_resp.get("items", [])]
        if not video_ids:
            return account_snapshot, []

        videos_resp = (
            self.client.videos()
            .list(part="statistics,snippet", id=",".join(video_ids))
            .execute()
        )
        posts: list[PostSnapshot] = []
        for video in videos_resp.get("items", []):
            vstats = video.get("statistics", {})
            likes = int(vstats.get("likeCount", 0))
            comments = int(vstats.get("commentCount", 0))
            views = int(vstats.get("viewCount", 0))
            posts.append(
                PostSnapshot(
                    platform="youtube",
                    account_id=self.channel_id,
                    post_id=video.get("id", ""),
                    published_at=video.get("snippet", {}).get("publishedAt"),
                    impressions=views,
                    likes=likes,
                    comments=comments,
                    shares=None,
                    watch_time=None,
                    raw_payload=video,
                )
            )

        return account_snapshot, posts


class XCollector:
    def __init__(self, bearer_token: str, user_id: str) -> None:
        self.user_id = user_id
        if requests is None:
            raise RuntimeError("requests não está instalado.")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {bearer_token}"})

    def collect(self, max_posts: int = 10) -> tuple[PlatformSnapshot, list[PostSnapshot]]:
        user_resp = self.session.get(
            f"https://api.x.com/2/users/{self.user_id}",
            params={"user.fields": "public_metrics"},
            timeout=30,
        )
        user_resp.raise_for_status()
        user_data = user_resp.json().get("data", {})
        metrics = user_data.get("public_metrics", {})

        followers = int(metrics.get("followers_count", 0))
        account_snapshot = PlatformSnapshot(
            platform="x",
            account_id=self.user_id,
            followers=followers,
            engagement_rate=None,
            raw_payload=user_data,
        )

        tweets_resp = self.session.get(
            f"https://api.x.com/2/users/{self.user_id}/tweets",
            params={
                "max_results": max_posts,
                "tweet.fields": "public_metrics,created_at",
                "exclude": "replies",
            },
            timeout=30,
        )
        tweets_resp.raise_for_status()
        tweets = tweets_resp.json().get("data", [])

        posts: list[PostSnapshot] = []
        for tweet in tweets:
            pm = tweet.get("public_metrics", {})
            posts.append(
                PostSnapshot(
                    platform="x",
                    account_id=self.user_id,
                    post_id=tweet.get("id", ""),
                    published_at=tweet.get("created_at"),
                    impressions=pm.get("impression_count"),
                    likes=pm.get("like_count"),
                    comments=pm.get("reply_count"),
                    shares=pm.get("retweet_count"),
                    watch_time=None,
                    raw_payload=tweet,
                )
            )

        return account_snapshot, posts


class InstagramCollector:
    def __init__(self, access_token: str, ig_user_id: str) -> None:
        if requests is None:
            raise RuntimeError("requests não está instalado.")
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.base_url = "https://graph.facebook.com/v21.0"

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "access_token": self.access_token}
        resp = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def collect(self, max_posts: int = 10) -> tuple[PlatformSnapshot, list[PostSnapshot]]:
        account = self._get(
            self.ig_user_id,
            {"fields": "username,followers_count,media_count"},
        )

        account_snapshot = PlatformSnapshot(
            platform="instagram",
            account_id=self.ig_user_id,
            followers=int(account.get("followers_count", 0)),
            engagement_rate=None,
            raw_payload=account,
        )

        media_resp = self._get(
            f"{self.ig_user_id}/media",
            {"fields": "id,caption,like_count,comments_count,timestamp", "limit": max_posts},
        )
        media = media_resp.get("data", [])

        posts: list[PostSnapshot] = []
        for post in media:
            posts.append(
                PostSnapshot(
                    platform="instagram",
                    account_id=self.ig_user_id,
                    post_id=post.get("id", ""),
                    published_at=post.get("timestamp"),
                    impressions=None,
                    likes=post.get("like_count"),
                    comments=post.get("comments_count"),
                    shares=None,
                    watch_time=None,
                    raw_payload=post,
                )
            )

        return account_snapshot, posts


def run_collection(db: MetricsDB, max_posts: int) -> list[str]:
    logs: list[str] = []

    youtube_key = os.getenv("YOUTUBE_API_KEY")
    youtube_channel_id = os.getenv("YOUTUBE_CHANNEL_ID")
    if youtube_key and youtube_channel_id:
        yt = YouTubeCollector(youtube_key, youtube_channel_id)
        account, posts = yt.collect(max_posts)
        db.insert_account_snapshot(account)
        db.insert_post_snapshots(posts)
        logs.append(f"YouTube: {len(posts)} vídeos coletados.")
    else:
        logs.append("YouTube: pulado (faltam YOUTUBE_API_KEY/YOUTUBE_CHANNEL_ID).")

    x_token = os.getenv("X_BEARER_TOKEN")
    x_user_id = os.getenv("X_USER_ID")
    if x_token and x_user_id:
        xc = XCollector(x_token, x_user_id)
        account, posts = xc.collect(max_posts)
        db.insert_account_snapshot(account)
        db.insert_post_snapshots(posts)
        logs.append(f"X: {len(posts)} posts coletados.")
    else:
        logs.append("X: pulado (faltam X_BEARER_TOKEN/X_USER_ID).")

    ig_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    ig_user_id = os.getenv("INSTAGRAM_USER_ID")
    if ig_token and ig_user_id:
        ig = InstagramCollector(ig_token, ig_user_id)
        account, posts = ig.collect(max_posts)
        db.insert_account_snapshot(account)
        db.insert_post_snapshots(posts)
        logs.append(f"Instagram: {len(posts)} posts coletados.")
    else:
        logs.append("Instagram: pulado (faltam INSTAGRAM_ACCESS_TOKEN/INSTAGRAM_USER_ID).")

    return logs




def build_report_payload(db: MetricsDB, limit: int = 5) -> dict[str, list[dict[str, Any]]]:
    payload: dict[str, list[dict[str, Any]]] = {}
    for platform in ["youtube", "x", "instagram"]:
        rows = db.top_posts(platform, limit=limit)
        payload[platform] = [
            {
                "post_id": row["post_id"],
                "published_at": row["published_at"],
                "impressions": row["impressions"],
                "likes": row["likes"],
                "comments": row["comments"],
                "shares": row["shares"],
                "score": (row["likes"] or 0) + (row["comments"] or 0) + (row["shares"] or 0),
            }
            for row in rows
        ]
    return payload

def print_report(db: MetricsDB) -> None:
    platforms = ["youtube", "x", "instagram"]
    for platform in platforms:
        top = db.top_posts(platform)
        print(f"\n=== Top posts: {platform} ===")
        if not top:
            print("Sem dados ainda.")
            continue
        for row in top:
            score = (row["likes"] or 0) + (row["comments"] or 0) + (row["shares"] or 0)
            print(
                f"post={row['post_id']} likes={row['likes']} comments={row['comments']} "
                f"shares={row['shares']} score={score}"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fase 1 - Coletor de métricas sociais")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Caminho do SQLite")
    parser.add_argument("--max-posts", type=int, default=10, help="Quantidade de posts por rede")
    parser.add_argument(
        "--action",
        choices=["init-db", "collect", "report", "all"],
        default="all",
        help="Ação a executar",
    )
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    db = MetricsDB(args.db)

    if args.action in {"init-db", "all", "collect"}:
        db.initialize()

    if args.action in {"collect", "all"}:
        try:
            for line in run_collection(db, args.max_posts):
                print(line)
        except Exception as exc:
            if requests is not None and isinstance(exc, requests.HTTPError):
                print(f"Erro HTTP na coleta: {exc}")
            else:
                print(f"Erro na coleta: {exc}")
            raise SystemExit(1)

    if args.action in {"report", "all"}:
        print_report(db)


if __name__ == "__main__":
    main()
