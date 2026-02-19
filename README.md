# Inhuman Science

Automated AI/ML content curation and publishing pipeline. Aggregates papers, blog posts, and tweets from the AI world, evaluates them with LLMs, and publishes the best finds to Telegram and Twitter/X.

## How It Works

The system runs three independent pipelines on a configurable cron schedule:

**Papers** — scrapes trending papers from [AlphaXiv](https://www.alphaxiv.org), scores them with an LLM oracle, downloads PDFs, extracts the most representative figure using a vision model, generates bilingual posts (Russian for Telegram, English for Twitter), and publishes.

**Blogs** — fetches RSS feeds from OpenAI, Anthropic, and Google Gemini blogs, scores and fact-checks each post, generates summaries, and publishes.

**Twitter** — monitors tweets from configurable AI leaders (e.g. Sam Altman, Yann LeCun), scores them, generates Russian summaries for Telegram, and retweets on Twitter.

Every pipeline checks for duplicates against recently published content, tracks all decisions in SQLite, and sends error notifications to a dedicated Telegram chat.

## Architecture

```
Sources                 Processing              Publishing
┌─────────────┐        ┌──────────────┐        ┌───────────┐
│  AlphaXiv   │───┐    │  Oracle      │        │ Telegram  │
│  (papers)   │   │    │  (scoring,   │   ┌───▶│ (RU post) │
├─────────────┤   │    │  fact-check, │   │    ├───────────┤
│  RSS Feeds  │───┼───▶│  dedup)      │───┤    │ Twitter   │
│  (blogs)    │   │    ├──────────────┤   └───▶│ (EN post) │
├─────────────┤   │    │  Processors  │        └───────────┘
│  Twitter    │───┘    │  (PDF, image,│              │
│  (tweets)   │        │  post gen)   │              ▼
└─────────────┘        └──────────────┘        ┌───────────┐
                                               │  SQLite   │
                                               │  (state)  │
                                               └───────────┘
```

## Project Structure

```
├── main.py                 # Entry point, scheduler, pipeline orchestration
├── config.py               # Configuration and environment variables
├── requirements.txt        # Python dependencies
├── Dockerfile
├── docker-compose.yml
│
├── sources/
│   ├── base.py             # ContentItem dataclass
│   ├── alphaxiv.py         # AlphaXiv trending papers scraper
│   ├── blogs.py            # RSS feed parser (OpenAI, Anthropic, Google)
│   └── twitter_feed.py     # Twitter API v2 feed reader
│
├── oracle/
│   └── oracle.py           # LLM-based scoring, fact-checking, deduplication
│
├── processors/
│   ├── pdf.py              # PDF download and text extraction
│   ├── images.py           # Best figure extraction via vision model
│   └── post_generator.py   # Bilingual post generation (RU/EN)
│
├── publishers/
│   ├── telegram.py         # Telegram channel publisher
│   └── twitter.py          # Twitter/X publisher
│
├── storage/
│   └── state.py            # SQLite state tracking
│
└── llm/
    └── client.py           # OpenRouter API client
```

## Setup

### Prerequisites

- Python 3.11+
- API keys: [OpenRouter](https://openrouter.ai/), Telegram Bot, Twitter/X

### Installation

```bash
git clone <repo-url>
cd inhuman-science
pip install -r requirements.txt
```

### Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

#### Required variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM calls |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHANNEL_ID` | Target Telegram channel ID |
| `TELEGRAM_ERROR_CHAT_ID` | Chat ID for error notifications |
| `TWITTER_API_KEY` | Twitter API key |
| `TWITTER_API_SECRET` | Twitter API secret |
| `TWITTER_ACCESS_TOKEN` | Twitter access token |
| `TWITTER_ACCESS_SECRET` | Twitter access secret |

#### Optional variables

| Variable | Default | Description |
|---|---|---|
| `SCHEDULE_PAPERS_CRON` | `0 10 * * *` | Papers pipeline schedule |
| `SCHEDULE_BLOGS_CRON` | `0 12 * * *` | Blogs pipeline schedule |
| `SCHEDULE_TWITTER_CRON` | `0 14 * * *` | Twitter pipeline schedule |
| `TWITTER_MONITOR_USERS` | `sama,ylecun,kaborov` | Comma-separated Twitter usernames to monitor |
| `ORACLE_MIN_SCORE` | `7` | Minimum LLM score (1-10) to publish |
| `ORACLE_MAX_PAPERS_PER_RUN` | `5` | Max papers published per run |
| `ORACLE_MAX_BLOGS_PER_RUN` | `3` | Max blog posts published per run |
| `TIMEZONE` | `Europe/Moscow` | Timezone for scheduling |
| `DB_PATH` | `state.db` | SQLite database path |
| `PDF_DIR` | `pdfs` | Directory for downloaded PDFs |
| `IMG_DIR` | `images` | Directory for extracted images |

## Usage

### Run a single pipeline

```bash
python main.py papers     # Papers pipeline
python main.py blogs      # Blogs pipeline
python main.py twitter    # Twitter pipeline
python main.py all        # All pipelines sequentially
```

### Run the scheduler

```bash
python main.py
```

Without arguments the app starts a background scheduler that triggers each pipeline at its configured cron time and keeps running indefinitely.

### Docker

```bash
docker-compose up -d
```

The compose file mounts `state.db`, `pdfs/`, and `images/` as volumes so state persists across container restarts.

## LLM Models

All LLM calls go through [OpenRouter](https://openrouter.ai/). Models are configured in `config.py`:

| Task | Model |
|---|---|
| Content scoring | `deepseek/deepseek-chat-v3-0324` |
| Fact-checking | `deepseek/deepseek-chat-v3-0324` |
| Post generation (RU & EN) | `anthropic/claude-sonnet-4.6` |
| Figure extraction (vision) | `google/gemini-2.5-flash` |

## Data Storage

SQLite database (`state.db`) with four tables:

- **posted_papers** — published papers (arxiv ID, title, timestamp)
- **posted_blogs** — published blog posts (URL, title, timestamp)
- **posted_tweets** — published tweets (tweet ID, author, timestamp)
- **oracle_decisions** — all scoring decisions with scores and reasoning
