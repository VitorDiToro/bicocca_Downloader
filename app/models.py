from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


@dataclass
class DownloadItem:
    url: str
    custom_name: Optional[str] = None

    @property
    def use_custom_name(self) -> bool:
        return self.custom_name is not None


class DownloadStatus(Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class DownloadResult:
    item: DownloadItem
    status: DownloadStatus
    message: str = ""


@dataclass
class DownloadSummary:
    results: List[DownloadResult] = field(default_factory=list)
    subtitle_success: int = 0
    subtitle_skipped: int = 0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.status == DownloadStatus.SUCCESS)

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == DownloadStatus.SKIPPED)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == DownloadStatus.ERROR)
