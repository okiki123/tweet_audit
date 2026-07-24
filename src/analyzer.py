import json
import time
from functools import wraps

import google.generativeai as genai

from config import settings
from models import AnalysisResult, Decision, Tweet

RETRYABLE_ERROR_KEYWORDS = (
    "timeout",
    "max_retries",
    "connection",
    "rate limit",
    "quota",
    "503",
    "429",
    "temporarily unavailable",
)


def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0):
    """Retry a function with exponential backoff, but only for transient errors."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()
                    is_retryable = any(keyword in error_str for keyword in RETRYABLE_ERROR_KEYWORDS)
                    is_last_attempt = attempt == max_retries - 1

                    if not is_retryable or is_last_attempt:
                        raise

                    wait_seconds = initial_delay * (2 ** attempt) + (time.time() % 1)
                    time.sleep(wait_seconds)

            raise last_exception

        return wrapper

    return decorator


class Gemini:
    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required. Set it via environment variable or .env file"
            )

        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self._last_request_time = 0.0
        self._min_request_interval = settings.rate_limit_seconds

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        remaining = self._min_request_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_time = time.time()

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    def analyze(self, tweet: Tweet) -> AnalysisResult:
        self._wait_for_rate_limit()

        response = self.model.generate_content(
            self._build_prompt(tweet),
            generation_config=genai.GenerationConfig(response_mime_type="application/json"),
        )

        return self._parse_response(tweet, response.text)

    def _parse_response(self, tweet: Tweet, raw_text: str) -> AnalysisResult:
        if not raw_text:
            raise ValueError(f"Empty response from Gemini for tweet {tweet.id}")

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Non-JSON response from Gemini for tweet {tweet.id}: {e} (response: {raw_text})"
            ) from e

        try:
            decision = Decision(data["decision"].upper())
        except KeyError as e:
            raise ValueError(
                f"Gemini response missing 'decision' for tweet {tweet.id} (response: {raw_text})"
            ) from e
        except ValueError as e:
            raise ValueError(
                f"Gemini returned an unrecognized decision for tweet {tweet.id}: "
                f"{data.get('decision')!r} (response: {raw_text})"
            ) from e

        return AnalysisResult(
            tweet_url=settings.tweet_url(tweet.id),
            decision=decision,
            reason=data.get("reason", ""),
        )

    def _build_prompt(self, tweet: Tweet) -> str:
        criteria = settings.criteria
        rules = [*criteria.topics_to_exclude, *criteria.tone_requirements]

        if criteria.forbidden_words:
            rules.append(f"Contains any of these words: {', '.join(criteria.forbidden_words)}")

        numbered_rules = "\n".join(f"{i}. {rule}" for i, rule in enumerate(rules, start=1))

        guidance = ""
        if criteria.additional_instructions:
            guidance = f"\n\nAdditional guidance: {criteria.additional_instructions}"

        return f"""You are evaluating tweets for a professional's Twitter cleanup.

Tweet ID: {tweet.id}
Tweet: "{tweet.content}"

Mark for deletion if it violates any of these criteria:
{numbered_rules}{guidance}

Respond in JSON format:
{{
  "decision": "DELETE" or "KEEP",
  "reason": "brief explanation"
}}"""