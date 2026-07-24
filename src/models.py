from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Decision(str, Enum):
    DELETE = "DELETE"
    KEEP = "KEEP"

@dataclass(frozen=True)
class Tweet:
    id: str
    content: str

@dataclass(frozen=True)
class AnalysisResult:
    tweet_url: str
    decision: Decision = Decision.KEEP
    reason: str = ""

    def __repr__(self) -> str:
        return f"AnalysisResult(tweet_url={self.tweet_url}, decision={self.decision.value})"

@dataclass(frozen=True)
class Result:
    success: bool
    count: int = 0
    error_type: str = ""
    error_message: str = ""

    def __repr__(self) -> str:
        if self.success:
            return f"Result(success={self.success}, count={self.count})"
        return (
            f"Result(success={self.success}, count={self.count}, "
            f"error_type={self.error_type!r}, error_message={self.error_message!r})"
        )