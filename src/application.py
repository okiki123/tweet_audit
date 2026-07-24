import logging

from analyzer import Gemini
from config import settings
from models import Decision, Result
from storage import Checkpoint, CSVParser, CSVWriter, JSONParser

logger = logging.getLogger(__name__)


def _is_retweet(tweet) -> bool:
    return tweet.content.startswith("RT @")


class Application:
    def __init__(self):
        self._analyzer = None

    @property
    def analyzer(self) -> Gemini:
        """Lazily create the Gemini client so `extract_tweets` never pays its setup cost."""
        if self._analyzer is None:
            self._analyzer = Gemini()
            logger.info("Gemini analyzer initialized")
        return self._analyzer

    def extract_tweets(self) -> Result:
        """Convert the raw X archive export into a flat CSV for later analysis."""
        try:
            logger.info(f"Reading tweets from {settings.tweets_archive_path}")
            tweets = JSONParser(settings.tweets_archive_path).parse()

            logger.info(f"Extracted {len(tweets)} tweets, writing to CSV")
            with CSVWriter(settings.transformed_tweets_path) as writer:
                writer.write_tweets(tweets)

            logger.info(f"Wrote {len(tweets)} tweets to {settings.transformed_tweets_path}")
            return Result(success=True, count=len(tweets))
        except Exception as e:
            return self._build_error_result(e, context="extraction")

    def analyze_tweets(self) -> Result:
        """Evaluate each tweet against the configured criteria, resuming from the last checkpoint."""
        try:
            tweets = self._load_transformed_tweets()
            if not tweets:
                logger.warning("No tweets found to analyze")
                return Result(success=True, count=0)

            return self._analyze_with_checkpoint(tweets)
        except Exception as e:
            return self._build_error_result(e, context="analysis")

    def _load_transformed_tweets(self) -> list:
        logger.info(f"Loading tweets from {settings.transformed_tweets_path}")
        tweets = CSVParser(settings.transformed_tweets_path).parse()
        logger.info(f"Loaded {len(tweets)} tweets for analysis")
        return tweets

    def _analyze_with_checkpoint(self, tweets: list) -> Result:
        analyzed_count = 0

        with Checkpoint(settings.checkpoint_path) as checkpoint:
            start_index = checkpoint.load()
            logger.info(f"Resuming from tweet index {start_index}")

            with CSVWriter(settings.processed_results_path, append=True) as writer:
                batch_size = settings.batch_size
                total_batches = (len(tweets) + batch_size - 1) // batch_size

                for i in range(start_index, len(tweets), batch_size):
                    batch = tweets[i: i + batch_size]
                    batch_num = (i // batch_size) + 1

                    logger.info(
                        f"Processing batch {batch_num}/{total_batches} "
                        f"(tweets {i + 1}-{min(i + len(batch), len(tweets))} of {len(tweets)})"
                    )

                    batch_analyzed, failure = self._analyze_batch(batch, writer, analyzed_count)
                    analyzed_count += batch_analyzed
                    if failure is not None:
                        return failure

                    checkpoint.save(i + len(batch))
                    logger.info(f"Checkpoint saved at index {i + len(batch)}")

        logger.info(f"Analysis complete. Results written to {settings.processed_results_path}")
        return Result(success=True, count=analyzed_count)

    def _analyze_batch(
        self, batch: list, writer: CSVWriter, analyzed_before_batch: int
    ) -> tuple[int, Result | None]:
        """Analyze one batch of tweets.

        Returns (count_analyzed_in_this_batch, failure_result). failure_result is
        None on success, or a failed Result (with the correct running count) if a
        tweet's analysis raised an error partway through the batch.
        """
        analyzed_in_batch = 0

        for tweet in batch:
            if _is_retweet(tweet):
                continue

            try:
                result = self.analyzer.analyze(tweet)
                logger.debug(f"Tweet {tweet.id}: {result.decision.value}")
                analyzed_in_batch += 1

                if result.decision == Decision.DELETE:
                    writer.write_result(result)
            except Exception as e:
                logger.error(f"Failed to analyze tweet {tweet.id}: {e}", exc_info=True)
                failure = Result(
                    success=False,
                    count=analyzed_before_batch + analyzed_in_batch,
                    error_type="analysis_failed",
                    error_message=str(e),
                )
                return analyzed_in_batch, failure

        return analyzed_in_batch, None

    @staticmethod
    def _build_error_result(e: Exception, context: str = "") -> Result:
        where = f" during {context}" if context else ""

        if isinstance(e, FileNotFoundError):
            logger.error(f"Required file not found{where}: {e}")
            return Result(success=False, error_type="file_not_found", error_message=str(e))

        if isinstance(e, ValueError):
            logger.error(f"Invalid data format{where}: {e}")
            return Result(success=False, error_type="invalid_format", error_message=str(e))

        if isinstance(e, PermissionError):
            logger.error(f"Permission denied{where}: {e}")
            return Result(success=False, error_type="permission_denied", error_message=str(e))

        logger.error(f"Unexpected error{where}: {e}", exc_info=True)
        return Result(
            success=False,
            error_type="unexpected_error",
            error_message="An unexpected error occurred.",
        )