import hashlib
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy import create_engine, func, select, text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.schemas import (
    AuthUserResponse,
    PostsResponse,
    TopicsResponse,
    TranscriptResponse,
    TranscriptSegment,
    VideoResponse,
)


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    google_sub: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    picture: Mapped[str | None] = mapped_column(Text)
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    broad_topic: Mapped[str | None] = mapped_column(Text)
    search_query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class FoundVideo(Base):
    __tablename__ = "found_videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    search_query_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("search_queries.id", ondelete="CASCADE"),
    )
    video_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    channel_title: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SelectedVideo(Base):
    __tablename__ = "selected_videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    video_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    video_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_reason: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    segments_json: Mapped[str | None] = mapped_column(Text)
    segments_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SuggestedTopic(Base):
    __tablename__ = "suggested_topics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    transcript_hash: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_preview: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SelectedTopic(Base):
    __tablename__ = "selected_topics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    transcript_hash: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_preview: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class GeneratedPost(Base):
    __tablename__ = "generated_posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    selected_topic_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("selected_topics.id", ondelete="CASCADE"),
    )
    post_text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ActionHistory(Base):
    __tablename__ = "action_history"
    __table_args__ = (
        Index("idx_action_history_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = create_engine(_normalize_database_url(url), future=True)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def init(self) -> None:
        Base.metadata.create_all(self.engine)
        self._ensure_schema_columns(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self.session_factory() as session:
            yield session

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with self.session_factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def _ensure_schema_columns(self, engine: Engine) -> None:
        with engine.begin() as connection:
            connection.execute(
                sql_text("ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS segments_json TEXT")
            )


class DatabaseRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_user(self, user: AuthUserResponse) -> int:
        with self.database.transaction() as session:
            statement = pg_insert(User).values(
                google_sub=user.google_sub,
                email=user.email,
                name=user.name,
                picture=user.picture,
                email_verified=user.email_verified,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[User.google_sub],
                set_={
                    "email": statement.excluded.email,
                    "name": statement.excluded.name,
                    "picture": statement.excluded.picture,
                    "email_verified": statement.excluded.email_verified,
                    "updated_at": func.now(),
                },
            ).returning(User.id)
            user_id = session.execute(statement).scalar_one()
            return int(user_id)

    def create_search_query(
        self,
        user_id: int | None,
        search_query: str,
        broad_topic: str | None = None,
    ) -> int:
        with self.database.transaction() as session:
            row = SearchQuery(
                user_id=user_id,
                broad_topic=broad_topic,
                search_query=search_query,
            )
            session.add(row)
            session.flush()
            self._log_action(
                session,
                user_id,
                "search_query_created",
                {
                    "searchQuery": search_query,
                    "broadTopic": broad_topic,
                },
            )
            return int(row.id)

    def add_found_videos(
        self,
        user_id: int | None,
        search_query_id: int,
        videos: list[VideoResponse],
    ) -> None:
        with self.database.transaction() as session:
            for position, video in enumerate(videos, start=1):
                session.add(
                    FoundVideo(
                        user_id=user_id,
                        search_query_id=search_query_id,
                        video_id=video.video_id,
                        title=video.title,
                        channel_title=video.channel_title,
                        published_at=video.published_at,
                        metadata_json=self._to_json(video.model_dump(by_alias=True)),
                    )
                )
                self._log_action(
                    session,
                    user_id,
                    "video_found",
                    {
                        "position": position,
                        "videoId": video.video_id,
                        "title": video.title,
                    },
                )

    def save_selected_video(self, user_id: int | None, video: VideoResponse) -> None:
        with self.database.transaction() as session:
            session.add(
                SelectedVideo(
                    user_id=user_id,
                    video_id=video.video_id,
                    title=video.title,
                    metadata_json=self._to_json(video.model_dump(by_alias=True)),
                )
            )
            self._log_action(
                session,
                user_id,
                "video_selected",
                {
                    "videoId": video.video_id,
                    "title": video.title,
                },
            )

    def save_transcript_success(
        self,
        user_id: int | None,
        transcript: TranscriptResponse,
    ) -> None:
        segments_json = self._to_json(
            [segment.model_dump() for segment in transcript.segments]
        )
        with self.database.transaction() as session:
            session.add(
                Transcript(
                    user_id=user_id,
                    video_id=transcript.video_id,
                    status="success",
                    text=transcript.text,
                    segments_json=segments_json,
                    segments_count=transcript.segments_count,
                )
            )
            self._log_action(
                session,
                user_id,
                "transcript_fetched",
                {
                    "videoId": transcript.video_id,
                    "segmentsCount": transcript.segments_count,
                },
            )

    def get_cached_transcript(
        self,
        user_id: int,
        video_id: str,
    ) -> TranscriptResponse | None:
        with self.database.session() as session:
            row = session.execute(
                select(
                    Transcript.text,
                    Transcript.segments_json,
                    Transcript.segments_count,
                )
                .where(
                    Transcript.user_id == user_id,
                    Transcript.video_id == video_id,
                    Transcript.status == "success",
                    Transcript.text.is_not(None),
                )
                .order_by(Transcript.id.desc())
                .limit(1)
            ).first()

        if not row:
            return None

        text = str(row.text)
        segments = self._transcript_segments_from_json(row.segments_json)
        return TranscriptResponse(
            video_id=video_id,
            text=text,
            segments=segments,
            segments_count=int(row.segments_count),
        )

    def save_transcript_error(
        self,
        user_id: int | None,
        video_id: str,
        error_reason: str,
    ) -> None:
        with self.database.transaction() as session:
            session.add(
                Transcript(
                    user_id=user_id,
                    video_id=video_id,
                    status="error",
                    error_reason=error_reason,
                )
            )
            self._log_action(
                session,
                user_id,
                "transcript_failed",
                {
                    "videoId": video_id,
                    "errorReason": error_reason,
                },
            )

    def save_suggested_topics(
        self,
        user_id: int | None,
        transcript: str,
        response: TopicsResponse,
    ) -> None:
        transcript_hash = self._hash_text(transcript)
        transcript_preview = transcript[:300]
        with self.database.transaction() as session:
            for position, topic in enumerate(response.topics, start=1):
                session.add(
                    SuggestedTopic(
                        user_id=user_id,
                        transcript_hash=transcript_hash,
                        transcript_preview=transcript_preview,
                        topic=topic,
                        position=position,
                    )
                )
            self._log_action(
                session,
                user_id,
                "topics_suggested",
                {
                    "transcriptHash": transcript_hash,
                    "topics": response.topics,
                },
            )

    def save_generated_posts(
        self,
        user_id: int | None,
        transcript: str,
        selected_topic: str,
        response: PostsResponse,
    ) -> None:
        transcript_hash = self._hash_text(transcript)
        transcript_preview = transcript[:300]
        with self.database.transaction() as session:
            selected_topic_id = self._get_or_create_selected_topic(
                session=session,
                user_id=user_id,
                transcript_hash=transcript_hash,
                transcript_preview=transcript_preview,
                selected_topic=selected_topic,
            )
            for position, post in enumerate(response.posts, start=1):
                session.add(
                    GeneratedPost(
                        user_id=user_id,
                        selected_topic_id=selected_topic_id,
                        post_text=post,
                        position=position,
                    )
                )
            self._log_action(
                session,
                user_id,
                "posts_generated",
                {
                    "transcriptHash": transcript_hash,
                    "selectedTopic": selected_topic,
                    "postsCount": len(response.posts),
                },
            )

    def save_selected_topic(
        self,
        user_id: int | None,
        transcript: str,
        selected_topic: str,
    ) -> int:
        transcript_hash = self._hash_text(transcript)
        transcript_preview = transcript[:300]
        with self.database.transaction() as session:
            selected_topic_id = self._get_or_create_selected_topic(
                session=session,
                user_id=user_id,
                transcript_hash=transcript_hash,
                transcript_preview=transcript_preview,
                selected_topic=selected_topic,
            )
            self._log_action(
                session,
                user_id,
                "topic_selected",
                {
                    "transcriptHash": transcript_hash,
                    "selectedTopic": selected_topic,
                    "selectedTopicId": selected_topic_id,
                },
            )
            return selected_topic_id

    def list_user_history(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with self.database.session() as session:
            rows = session.execute(
                select(
                    ActionHistory.action,
                    ActionHistory.details_json,
                    ActionHistory.created_at,
                )
                .where(ActionHistory.user_id == user_id)
                .order_by(ActionHistory.id.desc())
                .limit(limit)
            ).all()

        return [
            {
                "action": row.action,
                "details": json.loads(row.details_json),
                "createdAt": str(row.created_at),
            }
            for row in rows
        ]

    def _log_action(
        self,
        session: Session,
        user_id: int | None,
        action: str,
        details: dict[str, Any],
    ) -> None:
        session.add(
            ActionHistory(
                user_id=user_id,
                action=action,
                details_json=self._to_json(details),
            )
        )

    def _get_or_create_selected_topic(
        self,
        session: Session,
        user_id: int | None,
        transcript_hash: str,
        transcript_preview: str,
        selected_topic: str,
    ) -> int:
        user_filter = (
            SelectedTopic.user_id.is_(None)
            if user_id is None
            else SelectedTopic.user_id == user_id
        )
        row = session.execute(
            select(SelectedTopic)
            .where(
                user_filter,
                SelectedTopic.transcript_hash == transcript_hash,
                SelectedTopic.topic == selected_topic,
            )
            .order_by(SelectedTopic.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row:
            return int(row.id)

        row = SelectedTopic(
            user_id=user_id,
            transcript_hash=transcript_hash,
            transcript_preview=transcript_preview,
            topic=selected_topic,
        )
        session.add(row)
        session.flush()
        return int(row.id)

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _to_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _transcript_segments_from_json(self, value: str | None) -> list[TranscriptSegment]:
        if not value:
            return []

        try:
            raw_segments = json.loads(value)
        except json.JSONDecodeError:
            return []

        if not isinstance(raw_segments, list):
            return []

        segments: list[TranscriptSegment] = []
        for raw_segment in raw_segments:
            if isinstance(raw_segment, dict):
                try:
                    segments.append(TranscriptSegment.model_validate(raw_segment))
                except ValueError:
                    continue
        return segments
