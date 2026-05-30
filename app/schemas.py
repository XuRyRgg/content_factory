from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    limit: int = Field(default=5, ge=1, le=10)


class TranscriptPreview(BaseModel):
    available: bool
    reason: str | None = None
    preview: str = ""
    segments: int = 0


class VideoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    video_id: str = Field(alias="videoId")
    title: str | None = None
    description: str | None = None
    channel_title: str | None = Field(default=None, alias="channelTitle")
    published_at: str | None = Field(default=None, alias="publishedAt")
    thumbnails: dict[str, Any] | None = None
    duration: str | None = None
    view_count: int | None = Field(default=None, alias="viewCount")
    like_count: int | None = Field(default=None, alias="likeCount")
    comment_count: int | None = Field(default=None, alias="commentCount")
    tags: list[str] | None = None
    category_id: str | None = Field(default=None, alias="categoryId")
    default_audio_language: str | None = Field(default=None, alias="defaultAudioLanguage")
    transcript_available: bool = Field(default=False, alias="transcriptAvailable")
    captions_likely: bool = Field(default=False, alias="captionsLikely")
    transcript_reason: str | None = Field(default=None, alias="transcriptReason")
    transcript_segments: int = Field(default=0, alias="transcriptSegments")
    transcript_preview: str = Field(default="", alias="transcriptPreview")
    mvp_usable: bool = Field(default=False, alias="mvpUsable")


class SearchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str
    videos: list[VideoResponse]
    skipped_without_transcript: int = Field(alias="skippedWithoutTranscript")


class TranscriptSegment(BaseModel):
    text: str
    start: float | None = None
    duration: float | None = None


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    video_id: str = Field(alias="videoId")
    text: str
    segments: list[TranscriptSegment]
    segments_count: int = Field(alias="segmentsCount")


class SearchQueryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    broad_topic: str = Field(alias="broadTopic", min_length=2, max_length=200)


class SearchQueryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    search_query: str = Field(alias="searchQuery")


class TopicsRequest(BaseModel):
    transcript: str = Field(min_length=1)


class TopicsResponse(BaseModel):
    topics: list[str]


class SelectTopicRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    transcript: str = Field(min_length=1)
    selected_topic: str = Field(alias="selectedTopic", min_length=1)


class SelectTopicResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    selected_topic_id: int = Field(alias="selectedTopicId")
    selected_topic: str = Field(alias="selectedTopic")


class GeneratePostsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    transcript: str = Field(min_length=1)
    selected_topic: str = Field(alias="selectedTopic", min_length=1)


class PostsResponse(BaseModel):
    posts: list[str]


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    google_sub: str = Field(alias="googleSub")
    email: str
    name: str | None = None
    picture: str | None = None
    email_verified: bool = Field(default=False, alias="emailVerified")


class HistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: str
    details: dict[str, Any]
    created_at: str = Field(alias="createdAt")


class HistoryResponse(BaseModel):
    history: list[HistoryItem]
