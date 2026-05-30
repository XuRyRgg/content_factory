from typing import Any

import requests

from app.core.errors import AppError
from app.schemas import VideoResponse


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search_video_ids(self, query: str, limit: int) -> list[str]:
        data = self._request(
            YOUTUBE_SEARCH_URL,
            {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": "date",
                "maxResults": min(limit, 50),
                "safeSearch": "none",
                "videoCaption": "closedCaption",
            },
        )

        video_ids: list[str] = []
        for item in data.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)
        return video_ids

    def get_video_metadata(self, video_ids: list[str]) -> list[dict[str, Any]]:
        if not video_ids:
            return []

        data = self._request(
            YOUTUBE_VIDEOS_URL,
            {
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(video_ids),
            },
        )
        return data.get("items", [])

    def to_video_response(self, item: dict[str, Any]) -> VideoResponse:
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})

        return VideoResponse(
            video_id=item.get("id", ""),
            title=snippet.get("title"),
            description=snippet.get("description"),
            channel_title=snippet.get("channelTitle"),
            published_at=snippet.get("publishedAt"),
            thumbnails=snippet.get("thumbnails"),
            duration=content_details.get("duration"),
            view_count=self._optional_int(statistics.get("viewCount")),
            like_count=self._optional_int(statistics.get("likeCount")),
            comment_count=self._optional_int(statistics.get("commentCount")),
            tags=snippet.get("tags"),
            category_id=snippet.get("categoryId"),
            default_audio_language=snippet.get("defaultAudioLanguage"),
        )

    def _request(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        safe_params = {**params, "key": self.api_key}
        try:
            response = requests.get(url, params=safe_params, timeout=20)
        except requests.RequestException as exc:
            raise AppError(
                status_code=502,
                code="youtube_request_failed",
                message="YouTube API request failed. Check internet connection, DNS, or API access.",
            ) from None

        if response.status_code != 200:
            raise AppError(
                status_code=response.status_code,
                code="youtube_api_error",
                message=self._extract_error_message(response),
            )
        return response.json()

    def _extract_error_message(self, response: requests.Response) -> str:
        try:
            error = response.json().get("error", {})
            return error.get("message", "Unknown YouTube API error.")
        except ValueError:
            return "Unknown YouTube API error."

    def _optional_int(self, value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None
