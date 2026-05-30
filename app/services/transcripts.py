from youtube_transcript_api import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from app.core.errors import AppError
from app.schemas import TranscriptPreview, TranscriptResponse, TranscriptSegment


class TranscriptService:
    def __init__(self) -> None:
        self.client = YouTubeTranscriptApi()

    def preview(self, video_id: str) -> TranscriptPreview:
        try:
            segments = self._fetch_raw(video_id)
        except (NoTranscriptFound, TranscriptsDisabled) as exc:
            return TranscriptPreview(
                available=False,
                reason=exc.__class__.__name__,
            )
        except Exception as exc:
            return TranscriptPreview(
                available=False,
                reason=exc.__class__.__name__,
            )

        text = self._join_text(segments)
        return TranscriptPreview(
            available=True,
            preview=text[:300],
            segments=len(segments),
        )

    def fetch(self, video_id: str) -> TranscriptResponse:
        try:
            raw_segments = self._fetch_raw(video_id)
        except (NoTranscriptFound, TranscriptsDisabled) as exc:
            raise AppError(
                status_code=404,
                code="transcript_not_available",
                message=f"Transcript is not available for this video: {exc.__class__.__name__}.",
            ) from exc
        except (RequestBlocked, IpBlocked) as exc:
            raise AppError(
                status_code=502,
                code="transcript_request_blocked",
                message="YouTube blocked transcript requests. Try again later or use a proxy later in production.",
            ) from exc
        except Exception as exc:
            raise AppError(
                status_code=502,
                code="transcript_fetch_failed",
                message="Failed to fetch transcript for this video.",
            ) from exc

        segments = [
            TranscriptSegment(
                text=segment.get("text", ""),
                start=segment.get("start"),
                duration=segment.get("duration"),
            )
            for segment in raw_segments
        ]
        return TranscriptResponse(
            video_id=video_id,
            text=self._join_text(raw_segments),
            segments=segments,
            segments_count=len(segments),
        )

    def _fetch_raw(self, video_id: str) -> list[dict[str, str | float]]:
        return self.client.fetch(
            video_id,
            languages=["ru", "en"],
        ).to_raw_data()

    def _join_text(self, segments: list[dict[str, str | float]]) -> str:
        return " ".join(str(segment.get("text", "")).strip() for segment in segments).strip()
