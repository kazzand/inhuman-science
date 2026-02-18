from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import config
from sources.base import ContentItem

logger = logging.getLogger(__name__)

_client = None

MAX_RESULTS_PER_USER = 10


def _get_client():
    global _client
    if _client is not None:
        return _client

    if config.TWITTER_API_KEY.startswith("placeholder"):
        return None

    try:
        import tweepy
        _client = tweepy.Client(
            consumer_key=config.TWITTER_API_KEY,
            consumer_secret=config.TWITTER_API_SECRET,
            access_token=config.TWITTER_ACCESS_TOKEN,
            access_token_secret=config.TWITTER_ACCESS_SECRET,
        )
        return _client
    except Exception:
        logger.exception("Failed to init Twitter client for reading")
        return None


def fetch_ai_leader_tweets(max_age_days: int = 2) -> list[ContentItem]:
    """Fetch recent tweets from monitored AI leaders via X API v2."""
    client = _get_client()
    if client is None:
        logger.warning("Twitter client not available, skipping tweet monitoring")
        return []

    items: list[ContentItem] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    for username in config.TWITTER_MONITOR_USERS:
        try:
            tweets = _fetch_user_tweets(client, username, cutoff)
            items.extend(tweets)
            logger.info("Fetched %d tweets from @%s", len(tweets), username)
        except Exception:
            logger.exception("Failed to fetch tweets for @%s", username)

    return items


def _fetch_user_tweets(
    client, username: str, cutoff: datetime
) -> list[ContentItem]:
    try:
        user_resp = client.get_user(username=username, user_auth=True)
        if not user_resp.data:
            logger.warning("User @%s not found", username)
            return []
        user_id = user_resp.data.id
    except Exception:
        logger.exception("Failed to look up user @%s", username)
        return []

    try:
        tweets_resp = client.get_users_tweets(
            user_id,
            max_results=MAX_RESULTS_PER_USER,
            tweet_fields=["created_at", "text", "public_metrics"],
            exclude=["retweets", "replies"],
            user_auth=True,
        )
    except Exception:
        logger.exception("Failed to fetch timeline for @%s", username)
        return []

    if not tweets_resp.data:
        return []

    items: list[ContentItem] = []
    for tweet in tweets_resp.data:
        created = tweet.created_at
        if created and created < cutoff:
            continue

        text = tweet.text or ""
        if len(text) < 30:
            continue

        tweet_url = f"https://x.com/{username}/status/{tweet.id}"
        likes = 0
        if tweet.public_metrics:
            likes = tweet.public_metrics.get("like_count", 0)

        items.append(
            ContentItem(
                content_id=tweet_url,
                source_type="tweet",
                source_name=f"twitter:{username}",
                title=text[:200],
                summary=text,
                url=tweet_url,
                likes=likes,
                authors=[f"@{username}"],
                published_at=created.isoformat() if created else "",
            )
        )

    return items
