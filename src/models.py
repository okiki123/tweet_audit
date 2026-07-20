from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True)
class Tweet:
    id: str
    text: str
    created_at: datetime
    language: str
    is_retweeted: bool
