import json
import logging
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_BATCH_SIZE = 10
DEFAULT_RATE_LIMIT_SECONDS = 1.0
DEFAULT_BASE_TWITTER_URL = "https://x.com"

DEFAULT_TWEETS_ARCHIVE_PATH = "data/tweets/tweets.json"
DEFAULT_TRANSFORMED_TWEETS_PATH = "data/tweets/transformed/tweets.csv"
DEFAULT_CHECKPOINT_PATH = "data/checkpoint.txt"
DEFAULT_PROCESSED_RESULTS_PATH = "data/tweets/processed/results.csv"

CRITERIA_CONFIG_PATH = "config.json"


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


@dataclass
class Criteria:
    additional_instructions: str = ""
    forbidden_words: list[str] = field(default_factory=list)
    topics_to_exclude: list[str] = field(default_factory=list)
    tone_requirements: list[str] = field(default_factory=list)


@dataclass
class Settings:
    x_username: str
    gemini_api_key: str = ""
    tweets_archive_path: str = DEFAULT_TWEETS_ARCHIVE_PATH
    transformed_tweets_path: str = DEFAULT_TRANSFORMED_TWEETS_PATH
    checkpoint_path: str = DEFAULT_CHECKPOINT_PATH
    processed_results_path: str = DEFAULT_PROCESSED_RESULTS_PATH
    base_twitter_url: str = DEFAULT_BASE_TWITTER_URL
    gemini_model: str = DEFAULT_GEMINI_MODEL
    batch_size: int = DEFAULT_BATCH_SIZE
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS
    criteria: Criteria = field(default_factory=Criteria)

    def tweet_url(self, tweet_id: str) -> str:
        return f"{self.base_twitter_url}/{self.x_username}/{tweet_id}"


def _default_criteria() -> Criteria:
    return Criteria(
        forbidden_words=[],
        topics_to_exclude=[
            "Profanity or unprofessional language",
            "Personal attacks or insults",
            "Outdated political opinions",
        ],
        tone_requirements=[
            "Professional language only",
            "Respectful communication",
        ],
        additional_instructions="Flag any content that could harm professional reputation",
    )


def _load_criteria_from_file(path: str) -> Criteria | None:
    config_path = Path(path)
    if not config_path.exists():
        return None

    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        logging.getLogger(__name__).warning(f"Could not read {path}, using default criteria")
        return None

    criteria_data = data.get("criteria", {})
    return Criteria(
        additional_instructions=criteria_data.get("additional_instructions", ""),
        forbidden_words=criteria_data.get("forbidden_words", []),
        topics_to_exclude=criteria_data.get("topics_to_exclude", []),
        tone_requirements=criteria_data.get("tone_requirements", []),
    )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required. Set it via environment variable or .env file")
    return value


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    configure_logging()

    criteria = _load_criteria_from_file(CRITERIA_CONFIG_PATH) or _default_criteria()

    return Settings(
        x_username=_require_env("X_USERNAME"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        tweets_archive_path=os.getenv("TWEETS_ARCHIVE_PATH", DEFAULT_TWEETS_ARCHIVE_PATH),
        transformed_tweets_path=os.getenv(
            "TRANSFORMED_TWEETS_PATH", DEFAULT_TRANSFORMED_TWEETS_PATH
        ),
        checkpoint_path=os.getenv("CHECKPOINT_PATH", DEFAULT_CHECKPOINT_PATH),
        processed_results_path=os.getenv(
            "PROCESSED_RESULTS_PATH", DEFAULT_PROCESSED_RESULTS_PATH
        ),
        rate_limit_seconds=float(os.getenv("RATE_LIMIT_SECONDS", str(DEFAULT_RATE_LIMIT_SECONDS))),
        criteria=criteria,
    )


settings: Settings = load_settings()