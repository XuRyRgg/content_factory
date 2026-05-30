import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def require_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY is missing. Add it to .env.")
    return api_key


def request_youtube(url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError(
            "YouTube API request failed. Check internet connection, DNS, or API access."
        ) from exc

    if response.status_code != 200:
        try:
            error = response.json().get("error", {})
            message = error.get("message", "Unknown YouTube API error")
        except ValueError:
            message = "Unknown YouTube API error"
        raise RuntimeError(f"YouTube API error {response.status_code}: {message}")
    return response.json()


def search_videos(api_key: str, query: str, limit: int) -> list[str]:
    data = request_youtube(
        YOUTUBE_SEARCH_URL,
        {
            "key": api_key,
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "date",
            "maxResults": min(limit, 10),
            "safeSearch": "none",
        },
    )

    video_ids: list[str] = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        if video_id:
            video_ids.append(video_id)
    return video_ids


def get_video_metadata(api_key: str, video_ids: list[str]) -> list[dict[str, Any]]:
    if not video_ids:
        return []

    data = request_youtube(
        YOUTUBE_VIDEOS_URL,
        {
            "key": api_key,
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(video_ids),
        },
    )
    return data.get("items", [])


def transcript_preview(video_id: str) -> dict[str, Any]:
    try:
        transcript = YouTubeTranscriptApi().fetch(
            video_id,
            languages=["ru", "en"],
        ).to_raw_data()
    except (NoTranscriptFound, TranscriptsDisabled) as exc:
        return {
            "available": False,
            "reason": exc.__class__.__name__,
            "preview": "",
            "segments": 0,
        }
    except Exception as exc:
        return {
            "available": False,
            "reason": exc.__class__.__name__,
            "preview": "",
            "segments": 0,
        }

    text = " ".join(segment.get("text", "") for segment in transcript)
    return {
        "available": True,
        "reason": "",
        "preview": text[:300],
        "segments": len(transcript),
    }


def simplify_video(item: dict[str, Any]) -> dict[str, Any]:
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})
    content_details = item.get("contentDetails", {})

    return {
        "videoId": item.get("id"),
        "title": snippet.get("title"),
        "description": snippet.get("description"),
        "channelTitle": snippet.get("channelTitle"),
        "publishedAt": snippet.get("publishedAt"),
        "thumbnails": snippet.get("thumbnails"),
        "duration": content_details.get("duration"),
        "viewCount": statistics.get("viewCount"),
        "likeCount": statistics.get("likeCount"),
        "commentCount": statistics.get("commentCount"),
        "tags": snippet.get("tags"),
        "categoryId": snippet.get("categoryId"),
        "defaultAudioLanguage": snippet.get("defaultAudioLanguage"),
    }


def print_video(video: dict[str, Any], transcript: dict[str, Any]) -> None:
    print("=" * 80)
    print(f"videoId: {video['videoId']}")
    print(f"mvpUsable: {transcript['available']}")
    print(f"title: {video['title']}")
    print(f"descriptionPreview: {(video['description'] or '')[:300]}")
    print(f"channelTitle: {video['channelTitle']}")
    print(f"publishedAt: {video['publishedAt']}")
    print(f"duration: {video['duration']}")
    print(f"viewCount: {video['viewCount']}")
    print(f"likeCount: {video['likeCount']}")
    print(f"commentCount: {video['commentCount']}")
    print(f"categoryId: {video['categoryId']}")
    print(f"defaultAudioLanguage: {video['defaultAudioLanguage']}")
    print(f"tags: {video['tags']}")
    print(f"thumbnail: {video['thumbnails'].get('high', {}).get('url') if video['thumbnails'] else None}")
    print(f"transcriptAvailable: {transcript['available']}")
    if transcript["available"]:
        print(f"transcriptSegments: {transcript['segments']}")
        print(f"transcriptPreview: {transcript['preview']}")
    else:
        print(f"transcriptReason: {transcript['reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check YouTube API and transcripts.")
    parser.add_argument("query", help="Search query, for example: 'маркетинг в Telegram'")
    parser.add_argument("--limit", type=int, default=5, help="How many fresh videos to check")
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc).isoformat()
    print(f"Started at: {started_at}")
    print(f"Query: {args.query}")

    api_key = require_api_key()
    video_ids = search_videos(api_key, args.query, args.limit)
    videos = get_video_metadata(api_key, video_ids)

    videos_with_transcripts = 0
    skipped_without_transcript = 0
    for item in videos:
        video = simplify_video(item)
        transcript = transcript_preview(video["videoId"])
        if transcript["available"]:
            videos_with_transcripts += 1
        else:
            skipped_without_transcript += 1
        print_video(video, transcript)

    print("=" * 80)
    print(f"Found videos: {len(videos)}")
    print(f"Videos with transcripts: {videos_with_transcripts}")
    print(f"Skipped without transcripts: {skipped_without_transcript}")
    print("MVP API methods: search.list, videos.list")
    print("Transcript source: youtube-transcript-api, skip video if transcript is unavailable")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
