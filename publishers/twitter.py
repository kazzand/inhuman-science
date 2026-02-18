from __future__ import annotations

import logging
from pathlib import Path

import config
from publishers.telegram import send_error

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    if config.TWITTER_API_KEY.startswith("placeholder"):
        logger.warning("Twitter API not configured (placeholder keys), skipping")
        return None

    try:
        import tweepy

        auth = tweepy.OAuth1UserHandler(
            config.TWITTER_API_KEY,
            config.TWITTER_API_SECRET,
            config.TWITTER_ACCESS_TOKEN,
            config.TWITTER_ACCESS_SECRET,
        )
        _api_v1 = tweepy.API(auth)

        _client = tweepy.Client(
            consumer_key=config.TWITTER_API_KEY,
            consumer_secret=config.TWITTER_API_SECRET,
            access_token=config.TWITTER_ACCESS_TOKEN,
            access_token_secret=config.TWITTER_ACCESS_SECRET,
        )
        _client._api_v1 = _api_v1
        return _client
    except Exception as e:
        logger.exception("Failed to initialize Twitter client")
        send_error(f"Twitter init failed: {e}")
        return None


def post_tweet(
    text: str,
    image_path: Path | None = None,
    link: str = "",
) -> str | None:
    """Post a tweet with optional image. Returns tweet_id or None."""
    client = _get_client()
    if client is None:
        return None

    TCO_LEN = 24  # Twitter shortens all URLs to ~23 chars via t.co
    tweet_text = text
    if link:
        max_text = 280 - TCO_LEN - 1  # 1 for newline
        if len(tweet_text) > max_text:
            tweet_text = tweet_text[:max_text - 1] + "…"
        tweet_text += f"\n{link}"
    elif len(tweet_text) > 280:
        tweet_text = tweet_text[:279] + "…"

    media_ids = None
    if image_path and image_path.exists():
        try:
            media = client._api_v1.media_upload(str(image_path))
            media_ids = [media.media_id]
        except Exception as e:
            logger.exception("Failed to upload media to Twitter")
            send_error(f"Twitter media upload failed: {e}")

    try:
        response = client.create_tweet(text=tweet_text, media_ids=media_ids)
        tweet_id = response.data.get("id", "")
        logger.info("Tweet posted, id=%s", tweet_id)
        return str(tweet_id)
    except Exception as e:
        logger.exception("Failed to post tweet")
        send_error(f"Twitter post failed: {e}")
        return None


def retweet(tweet_url: str) -> str | None:
    """Retweet a tweet by URL. Returns our retweet id or None."""
    client = _get_client()
    if client is None:
        return None

    import re
    match = re.search(r"/status/(\d+)", tweet_url)
    if not match:
        logger.warning("Could not extract tweet ID from URL: %s", tweet_url)
        return None

    source_tweet_id = match.group(1)

    try:
        response = client.retweet(source_tweet_id)
        logger.info("Retweeted %s", source_tweet_id)
        return source_tweet_id
    except Exception as e:
        logger.exception("Failed to retweet %s", source_tweet_id)
        send_error(f"Retweet failed for {tweet_url}: {e}")
        return None
