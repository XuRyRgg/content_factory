import secrets

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas import (
    GeneratePostsRequest,
    AuthUserResponse,
    HistoryResponse,
    PostsResponse,
    SearchQueryRequest,
    SearchQueryResponse,
    SearchRequest,
    SearchResponse,
    SelectTopicRequest,
    SelectTopicResponse,
    TranscriptResponse,
    TopicsRequest,
    TopicsResponse,
    VideoResponse,
)
from app.services.ai import AIService
from app.db.database import Database, DatabaseRepository
from app.services.google_auth import GoogleAuthService
from app.services.transcripts import TranscriptService
from app.services.youtube import YouTubeService


router = APIRouter()


def get_youtube_service() -> YouTubeService:
    settings = get_settings()
    return YouTubeService(api_key=settings.require_youtube_api_key())


def get_transcript_service() -> TranscriptService:
    return TranscriptService()


def get_ai_service() -> AIService:
    settings = get_settings()
    return AIService(
        base_url=settings.lmstudio_base_url,
        model=settings.lmstudio_model,
        max_tokens=settings.lmstudio_max_tokens,
    )


def get_database_repository() -> DatabaseRepository:
    settings = get_settings()
    return DatabaseRepository(Database(settings.require_database_url()))


def get_google_auth_service() -> GoogleAuthService:
    settings = get_settings()
    client_id, client_secret, redirect_uri = settings.require_google_oauth_credentials()
    return GoogleAuthService(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )


def get_session_user(request: Request) -> AuthUserResponse:
    user = request.session.get("user")
    if not user:
        raise AppError(
            status_code=401,
            code="not_authenticated",
            message="User is not authenticated.",
        )
    return AuthUserResponse.model_validate(user)


def get_optional_user_id(request: Request) -> int | None:
    user = request.session.get("user")
    if not user:
        return None

    db_user_id = user.get("dbUserId")
    if db_user_id:
        return int(db_user_id)

    auth_user = AuthUserResponse.model_validate(user)
    db_user_id = get_database_repository().upsert_user(auth_user)
    request.session["user"] = {**user, "dbUserId": db_user_id}
    return db_user_id


def get_required_user_id(request: Request) -> int:
    user_id = get_optional_user_id(request)
    if user_id is None:
        raise AppError(
            status_code=401,
            code="not_authenticated",
            message="User is not authenticated.",
        )
    return user_id


@router.get("/auth/google/login")
def google_login(request: Request) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    authorization_url = get_google_auth_service().build_authorization_url(state)
    return RedirectResponse(authorization_url)


@router.get("/auth/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        raise AppError(
            status_code=400,
            code="google_oauth_denied",
            message=f"Google OAuth was denied: {error}.",
        )

    expected_state = request.session.pop("google_oauth_state", None)
    if not code or not state or state != expected_state:
        raise AppError(
            status_code=400,
            code="invalid_oauth_state",
            message="Invalid Google OAuth callback state.",
        )

    auth = get_google_auth_service()
    token_data = auth.exchange_code(code)
    access_token = token_data.get("access_token")
    if not access_token:
        raise AppError(
            status_code=502,
            code="google_access_token_missing",
            message="Google did not return an access token.",
        )

    user = auth.get_user_info(access_token)
    db_user_id = get_database_repository().upsert_user(user)
    request.session["user"] = {
        **user.model_dump(by_alias=True),
        "dbUserId": db_user_id,
    }
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/auth/me", response_model=AuthUserResponse)
def auth_me(request: Request) -> AuthUserResponse:
    return get_session_user(request)


@router.post("/auth/logout")
def auth_logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/history", response_model=HistoryResponse)
def get_history(request: Request) -> HistoryResponse:
    user_id = get_required_user_id(request)
    history = get_database_repository().list_user_history(user_id)
    return HistoryResponse(history=history)


@router.post("/youtube/search", response_model=SearchResponse)
def search_youtube_videos(payload: SearchRequest, request: Request) -> SearchResponse:
    youtube = get_youtube_service()
    user_id = get_required_user_id(request)

    video_ids = youtube.search_video_ids(query=payload.query, limit=payload.limit)
    metadata_items = youtube.get_video_metadata(video_ids)

    videos: list[VideoResponse] = []

    for item in metadata_items:
        video = youtube.to_video_response(item)
        video.captions_likely = True
        video.transcript_available = False
        video.transcript_reason = "Not checked yet. YouTube search was filtered by closed captions."
        video.mvp_usable = False
        videos.append(video)

    response = SearchResponse(
        query=payload.query,
        videos=videos,
        skipped_without_transcript=0,
    )
    repository = get_database_repository()
    search_query_id = repository.create_search_query(
        user_id=user_id,
        search_query=payload.query,
    )
    repository.add_found_videos(user_id, search_query_id, videos)
    return response


@router.get("/youtube/videos/{video_id}", response_model=VideoResponse)
def get_youtube_video(video_id: str, request: Request) -> VideoResponse:
    youtube = get_youtube_service()
    transcripts = get_transcript_service()
    user_id = get_required_user_id(request)

    metadata_items = youtube.get_video_metadata([video_id])
    if not metadata_items:
        raise AppError(
            status_code=404,
            code="video_not_found",
            message="Video was not found by YouTube API.",
        )

    video = youtube.to_video_response(metadata_items[0])
    transcript = transcripts.preview(video.video_id)
    video.transcript_available = transcript.available
    video.transcript_reason = transcript.reason
    video.transcript_segments = transcript.segments
    video.transcript_preview = transcript.preview
    video.mvp_usable = transcript.available
    get_database_repository().save_selected_video(user_id, video)
    return video


@router.get("/transcripts/{video_id}", response_model=TranscriptResponse)
def get_video_transcript(video_id: str, request: Request) -> TranscriptResponse:
    transcripts = get_transcript_service()
    user_id = get_required_user_id(request)
    repository = get_database_repository()
    cached_transcript = repository.get_cached_transcript(user_id, video_id)
    if cached_transcript:
        return cached_transcript

    try:
        transcript = transcripts.fetch(video_id)
    except AppError as exc:
        repository.save_transcript_error(user_id, video_id, exc.code)
        raise
    repository.save_transcript_success(user_id, transcript)
    return transcript


@router.post("/ai/search-query", response_model=SearchQueryResponse)
def prepare_search_query(payload: SearchQueryRequest, request: Request) -> SearchQueryResponse:
    user_id = get_required_user_id(request)
    response = get_ai_service().prepare_search_query(payload.broad_topic)
    get_database_repository().create_search_query(
        user_id=user_id,
        broad_topic=payload.broad_topic,
        search_query=response.search_query,
    )
    return response


@router.post("/ai/topics", response_model=TopicsResponse)
def extract_topics(payload: TopicsRequest, request: Request) -> TopicsResponse:
    user_id = get_required_user_id(request)
    response = get_ai_service().extract_topics(payload.transcript)
    get_database_repository().save_suggested_topics(
        user_id=user_id,
        transcript=payload.transcript,
        response=response,
    )
    return response


@router.post("/topics/select", response_model=SelectTopicResponse)
def select_topic(payload: SelectTopicRequest, request: Request) -> SelectTopicResponse:
    user_id = get_required_user_id(request)
    selected_topic_id = get_database_repository().save_selected_topic(
        user_id=user_id,
        transcript=payload.transcript,
        selected_topic=payload.selected_topic,
    )
    return SelectTopicResponse(
        selectedTopicId=selected_topic_id,
        selectedTopic=payload.selected_topic,
    )


@router.post("/ai/posts", response_model=PostsResponse)
def generate_posts(payload: GeneratePostsRequest, request: Request) -> PostsResponse:
    user_id = get_required_user_id(request)
    response = get_ai_service().generate_posts(
        transcript=payload.transcript,
        selected_topic=payload.selected_topic,
    )
    get_database_repository().save_generated_posts(
        user_id=user_id,
        transcript=payload.transcript,
        selected_topic=payload.selected_topic,
        response=response,
    )
    return response
