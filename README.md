# Tweet Audit Checker

A command-line tool that processes your X (Twitter) archive, evaluates every tweet against a configurable set of personal/professional criteria using Google's Gemini API, and produces a CSV of tweets flagged for deletion — with the AI's reasoning for each flag.

## How it works

1. **Extract** — parses your raw X archive export (`tweet.js`/`tweets.json`) and converts it into a flat, easy-to-work-with CSV.
2. **Analyze** — sends each tweet to Gemini in batches, evaluated against criteria you define (banned topics, tone requirements, forbidden words, or freeform guidance). Tweets flagged `DELETE` are written to a results CSV along with Gemini's stated reason.

The analysis step is resumable: progress is checkpointed after every batch, so if it's interrupted (network issue, API rate limit, closing your laptop), re-running `analyze-tweets` picks up exactly where it left off instead of starting over or re-spending API calls.

## Getting started

### Prerequisites

- Python 3.11+
- A [Gemini API key](https://ai.google.dev/gemini-api/docs)
- Your X archive export ([how to request one](https://help.x.com/en/managing-your-account/how-to-download-your-x-archive))

### Installation

```bash
git clone https://github.com/okiki123/tweet_audit.git
cd tweet_audit
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```
X_USERNAME=your_x_username
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

### Usage

Place your X archive's tweet data at `data/tweets/tweets.json`, then run:

```bash
python main.py extract-tweets
python main.py analyze-tweets
```

Results are written to `data/tweets/processed/results.csv`, containing each flagged tweet's URL, Gemini's decision, its reasoning, and a `deleted` column you can update as you work through and manually delete tweets.

## Configuration reference

| Environment variable      | Required | Default                              | Description                          |
|----------------------------|----------|---------------------------------------|---------------------------------------|
| `X_USERNAME`               | Yes      | —                                      | Your X handle, used to build tweet URLs |
| `GEMINI_API_KEY`           | Yes*     | —                                      | Required only for `analyze-tweets`   |
| `GEMINI_MODEL`              | No       | `gemini-2.5-flash`                    | Gemini model to use                   |

## Project structure

```
.
├── main.py         # CLI entry point
├── application.py  # Orchestrates extraction and analysis
├── analyzer.py      # Gemini client, prompt construction, retry logic
├── storage.py       # File parsing, CSV writing, checkpointing
├── models.py         # Core data types (Tweet, Decision, Result, etc.)
├── config.py         # Settings and criteria loading
└── requirements.txt
```

## Design notes

- **Resumable by design** — batch-level checkpointing means large archives (thousands of tweets) can be processed incrementally across multiple runs without losing progress or reprocessing tweets.
- **Retries with backoff** — transient API errors (rate limits, timeouts, temporary unavailability) are automatically retried with exponential backoff and jitter; permanent errors fail fast.
- **Locked-down file permissions** — since this data includes your tweet content and analysis results, output files are written with owner-only read/write permissions.
- **Configurable criteria** — evaluation rules live in `config.json`, not hardcoded, so the same tool can be reused with different personal standards.

## Tech stack

Python · Google Gemini API · `python-dotenv`

## Disclaimer

This tool flags tweets for review — it does not delete anything automatically. Always review the output CSV before manually deleting tweets on X.
