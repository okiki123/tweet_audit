import csv
import json
import os
from abc import ABC, abstractmethod

from models import AnalysisResult, Tweet

PRIVATE_FILE_MODE = 0o600
PRIVATE_DIR_MODE = 0o750

FILE_ENCODING = "utf-8"

TWITTER_ARCHIVE_ID_FIELD = "id_str"
TWITTER_ARCHIVE_TEXT_FIELD = "full_text"

TWEET_CSV_ID_COLUMN = "id"
TWEET_CSV_TEXT_COLUMN = "text"

RESULT_CSV_URL_COLUMN = "tweet_url"
RESULT_CSV_DECISION_COLUMN = "decision"
RESULT_CSV_REASON_COLUMN = "reason"
RESULT_CSV_DELETED_COLUMN = "deleted"

CSV_BOOL_FALSE = "false"


def _ensure_parent_dir(path: str) -> None:
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, mode=PRIVATE_DIR_MODE, exist_ok=True)


class Parser(ABC):
    @abstractmethod
    def parse(self) -> list[Tweet]:
        raise NotImplementedError


class JSONParser(Parser):
    """Reads tweets from a raw X/Twitter archive export."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def parse(self) -> list[Tweet]:
        try:
            with open(self.file_path, encoding=FILE_ENCODING) as file:
                data = json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Tweet archive not found: {self.file_path}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in archive: {self.file_path}") from e

        try:
            return [
                Tweet(
                    id=item["tweet"][TWITTER_ARCHIVE_ID_FIELD],
                    content=item["tweet"][TWITTER_ARCHIVE_TEXT_FIELD],
                )
                for item in data
            ]
        except KeyError as e:
            raise ValueError(f"Unexpected archive structure in {self.file_path}: missing {e}") from e


class CSVParser(Parser):
    """Reads tweets back from the flat CSV produced by CSVWriter.write_tweets."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def parse(self) -> list[Tweet]:
        try:
            with open(self.file_path, encoding=FILE_ENCODING) as file:
                reader = csv.DictReader(file)
                return [
                    Tweet(id=row[TWEET_CSV_ID_COLUMN], content=row[TWEET_CSV_TEXT_COLUMN])
                    for row in reader
                ]
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Transformed tweets file not found: {self.file_path}") from e
        except KeyError as e:
            raise ValueError(f"Missing expected column in {self.file_path}: {e}") from e
        except csv.Error as e:
            raise ValueError(f"Invalid CSV in {self.file_path}: {e}") from e


class Checkpoint:
    """Tracks the last successfully processed tweet index, so a run can resume after a crash."""

    def __init__(self, file_path: str) -> None:
        self.path = file_path
        self._file = None

    def __enter__(self) -> "Checkpoint":
        _ensure_parent_dir(self.path)
        self._file = open(self.path, "a+", encoding=FILE_ENCODING)
        os.chmod(self.path, PRIVATE_FILE_MODE)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if self._file:
            self._file.close()
            self._file = None
        return False

    def load(self) -> int:
        if not self._file:
            raise RuntimeError("Checkpoint file is not open")

        self._file.seek(0)
        content = self._file.read().strip()

        if not content:
            return 0

        try:
            return int(content)
        except ValueError as e:
            raise ValueError(f"Checkpoint file contains invalid data: {content!r}") from e

    def save(self, tweet_index: int) -> None:
        if not self._file:
            raise RuntimeError("Checkpoint file is not open")

        self._file.seek(0)
        self._file.truncate()
        self._file.write(str(tweet_index))
        self._file.flush()


class CSVWriter:
    """Writes tweets or analysis results to CSV, optionally resuming an in-progress file."""

    def __init__(self, file_path: str, append: bool = False) -> None:
        self.file_path = file_path
        self.append = append
        self._file = None
        self._writer = None
        self._header_written = False

    def __enter__(self) -> "CSVWriter":
        _ensure_parent_dir(self.file_path)

        file_exists = os.path.exists(self.file_path)
        self._header_written = self.append and file_exists

        mode = "a" if self.append and file_exists else "w"
        self._file = open(self.file_path, mode, encoding=FILE_ENCODING, newline="")
        self._writer = csv.writer(self._file)

        os.chmod(self.file_path, PRIVATE_FILE_MODE)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None
        return False

    def _require_open(self) -> None:
        if not self._writer:
            raise RuntimeError("CSVWriter file is not open")

    def write_tweets(self, tweets: list[Tweet]) -> None:
        self._require_open()

        if not self._header_written:
            self._writer.writerow([TWEET_CSV_ID_COLUMN, TWEET_CSV_TEXT_COLUMN])
            self._header_written = True

        for tweet in tweets:
            self._writer.writerow([tweet.id, tweet.content])

    def write_result(self, result: AnalysisResult) -> None:
        self._require_open()

        if not self._header_written:
            self._writer.writerow([
                RESULT_CSV_URL_COLUMN,
                RESULT_CSV_DECISION_COLUMN,
                RESULT_CSV_REASON_COLUMN,
                RESULT_CSV_DELETED_COLUMN,
            ])
            self._header_written = True

        self._writer.writerow([
            result.tweet_url,
            result.decision.value,
            result.reason,
            CSV_BOOL_FALSE,
        ])
        self._file.flush()