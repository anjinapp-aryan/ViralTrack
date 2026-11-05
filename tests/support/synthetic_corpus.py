"""Deterministic synthetic YouTube-shaped corpus for offline discovery tests (no real data).

Ages are relative to the moment of seeding, always far from a window boundary (never 30.0 days, never
7.0 days), so a test run at any time of day gets the same membership. Ids pass ViralTrack's real-id
checks (11-character video ids, `UC` + 22-character channel ids) so the corpus can be mapped as
real-shaped data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SENTINEL_MAX = 2_147_483_647  # the largest 32-bit integer, used to probe "no upper bound"


def channel_id(n: int) -> str:
    return f"UCD1C{n:019d}"  # UC + 22 characters


def video_id(n: int) -> str:
    return f"D1V{n:08d}"  # 11 characters


@dataclass(frozen=True)
class Channel:
    key: str
    n: int
    subs: int | None  # None = hidden / unknown
    videos: int = 20

    @property
    def id(self) -> str:
        return channel_id(self.n)


@dataclass(frozen=True)
class Video:
    key: str
    n: int
    channel: str  # Channel.key
    age_days: float | None  # None = missing publication date
    views: int | None  # None = missing view count
    likes: int | None = 0
    comments: int | None = 0
    duration: int = 600  # seconds; <= 180 counts as a Short upstream
    snapshots: tuple = ()  # ((hours_ago, views), ...) oldest first

    @property
    def id(self) -> str:
        return video_id(self.n)


CHANNELS = {
    c.key: c
    for c in (
        Channel("SMALL", 1, 500),
        Channel("ZERO", 2, 0),
        Channel("HIDDEN", 3, None),
        Channel("EDGE", 4, 10_000),  # exactly the upstream default limit
        Channel("ABOVE", 5, 10_001),  # one over it
        Channel("BIG", 6, 250_000),
    )
}

VIDEOS = {
    v.key: v
    for v in (
        Video("s_recent_hi", 1, "SMALL", 1.9, 50_000, 1000, 100, snapshots=((40, 30_000), (1, 50_000))),
        Video("s_recent_lo", 2, "SMALL", 3, 2_000, 50, 5),
        Video("z_mid", 3, "ZERO", 20, 30_000, 600, 60),
        Video("h_recent", 4, "HIDDEN", 4, 15_000, 300, 30),
        Video("e_recent", 5, "EDGE", 5, 12_000, 240, 24, snapshots=((3, 11_800), (1, 12_000))),
        Video("a_recent", 6, "ABOVE", 6, 20_000, 400, 40, snapshots=((480, 18_000), (476, 18_100))),
        Video("b_recent", 7, "BIG", 8, 900_000, 9000, 900, snapshots=((2, 899_000),)),
        Video("b_old", 8, "BIG", 200, 5_000_000, 50_000, 5000),
        Video("s_old", 9, "SMALL", 90, 80_000, 800, 80),
        Video("s_nopub", 10, "SMALL", None, 40_000, 400, 40),
        Video("s_noviews", 11, "SMALL", 0.5, None, 0, 0),
        Video("s_hiddenlikes", 12, "SMALL", 2.5, 25_000, None, 250),
        Video("s_short", 13, "SMALL", 1.8, 70_000, 700, 70, duration=45),
    )
}

# Batch 5 shape: 70 videos, only 3 inside 30 days, all on channels well above 10,000 subscribers.
B5_CHANNELS = {
    c.key: c
    for c in (Channel("B5_A", 11, 154_000), Channel("B5_B", 12, 207_000), Channel("B5_C", 13, 2_000_000))
}


def b5_videos() -> dict[str, Video]:
    out = {}
    for i in range(70):
        ch = ("B5_A", "B5_B", "B5_C")[i % 3]
        age = (3, 12, 25)[i] if i < 3 else 400 + i * 10  # 3 recent, 67 old
        out[f"b5_{i}"] = Video(f"b5_{i}", 100 + i, ch, age, 20_000 + i * 1000, 500, 50)
    return out


def iso(moment: datetime) -> str:
    return moment.isoformat()


def seed(conn, schema: str, channels=CHANNELS, videos=None, now: datetime | None = None) -> datetime:
    """Insert the corpus into `schema` (which already holds the upstream DDL). Returns the seeding time."""
    videos = VIDEOS if videos is None else videos
    now = now or datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {schema}")
        for c in channels.values():
            cur.execute(
                "INSERT INTO channels (channel_id, title, subscriber_count, video_count, view_count, "
                "updated_at, first_seen_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (c.id, f"Synthetic channel {c.key}", c.subs, c.videos, 1_000_000, iso(now), iso(now)),
            )
        for v in videos.values():
            published = iso(now - timedelta(days=v.age_days)) if v.age_days is not None else None
            cur.execute(
                "INSERT INTO videos (video_id, channel_id, title, published_at, duration_seconds, "
                "view_count, like_count, comment_count, updated_at, first_seen_at, category_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    v.id,
                    channels[v.channel].id,
                    f"Synthetic video {v.key}",
                    published,
                    v.duration,
                    v.views,
                    v.likes,
                    v.comments,
                    iso(now),
                    iso(now),
                    "27",
                ),
            )
            for hours_ago, views in v.snapshots:
                cur.execute(
                    "INSERT INTO video_stats_history (video_id, captured_at, view_count, like_count, "
                    "comment_count, title, thumbnail) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        v.id,
                        iso(now - timedelta(hours=hours_ago)),
                        views,
                        v.likes,
                        v.comments,
                        f"Synthetic video {v.key}",
                        "https://i.ytimg.com/vi/synthetic/hq.jpg",
                    ),
                )
    conn.commit()
    return now


# ---- independent oracle: what each filter SHOULD leave, computed from the definitions above ----


def oracle(
    videos,
    channels,
    *,
    window_days: float | None,
    exclude_shorts: bool,
    max_subscribers: int | None,
    min_views: int,
) -> dict:
    """Candidate keys after each stage, in the order upstream applies them."""

    def short(v):
        return v.duration <= 180

    start = [
        v
        for v in videos.values()
        if (window_days is None or (v.age_days is not None and v.age_days <= window_days))
        and not (exclude_shorts and short(v))
    ]
    stages = {"window": [v.key for v in start]}
    cur = start
    if max_subscribers is not None:
        cur = [
            v for v in cur if channels[v.channel].subs is None or channels[v.channel].subs <= max_subscribers
        ]
        stages["subscribers"] = [v.key for v in cur]
    if min_views:
        cur = [v for v in cur if (v.views or 0) >= min_views]
        stages["views"] = [v.key for v in cur]
    stages["final"] = [v.key for v in cur]
    return stages
