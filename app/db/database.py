import hashlib
import json
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from app.schemas import (
    AuthUserResponse,
    PostsResponse,
    TopicsResponse,
    TranscriptResponse,
    TranscriptSegment,
    VideoResponse,
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    google_sub TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    name TEXT,
    picture TEXT,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS search_queries (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    broad_topic TEXT,
    search_query TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS found_videos (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    search_query_id BIGINT REFERENCES search_queries(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    title TEXT,
    channel_title TEXT,
    published_at TEXT,
    metadata_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS selected_videos (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    title TEXT,
    metadata_json TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcripts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    status TEXT NOT NULL,
    error_reason TEXT,
    text TEXT,
    segments_json TEXT,
    segments_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suggested_topics (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    transcript_hash TEXT NOT NULL,
    transcript_preview TEXT NOT NULL,
    topic TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS selected_topics (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    transcript_hash TEXT NOT NULL,
    transcript_preview TEXT NOT NULL,
    topic TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generated_posts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    selected_topic_id BIGINT REFERENCES selected_topics(id) ON DELETE CASCADE,
    post_text TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_action_history_user_created
ON action_history(user_id, created_at);
"""


class Database:
    def __init__(self, url: str) -> None:
        self.url = url

    def connect(self) -> Connection:
        return psycopg.connect(self.url, row_factory=dict_row)

    def init(self) -> None:
        with self.connect() as connection:
            for statement in SCHEMA_SQL.split(";"):
                if statement.strip():
                    connection.execute(statement)
            self._ensure_schema_columns(connection)

    def _ensure_schema_columns(self, connection: Connection) -> None:
        connection.execute("ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS segments_json TEXT")


class DatabaseRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert_user(self, user: AuthUserResponse) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO users (google_sub, email, name, picture, email_verified)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (google_sub) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    picture = EXCLUDED.picture,
                    email_verified = EXCLUDED.email_verified,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (
                    user.google_sub,
                    user.email,
                    user.name,
                    user.picture,
                    user.email_verified,
                ),
            ).fetchone()
            return int(row["id"])

    def create_search_query(
        self,
        user_id: int | None,
        search_query: str,
        broad_topic: str | None = None,
    ) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO search_queries (user_id, broad_topic, search_query)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (user_id, broad_topic, search_query),
            ).fetchone()
            search_query_id = int(row["id"])
            self._log_action(
                connection,
                user_id,
                "search_query_created",
                {
                    "searchQuery": search_query,
                    "broadTopic": broad_topic,
                },
            )
            return search_query_id

    def add_found_videos(
        self,
        user_id: int | None,
        search_query_id: int,
        videos: list[VideoResponse],
    ) -> None:
        with self.database.connect() as connection:
            for position, video in enumerate(videos, start=1):
                connection.execute(
                    """
                    INSERT INTO found_videos (
                        user_id,
                        search_query_id,
                        video_id,
                        title,
                        channel_title,
                        published_at,
                        metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        search_query_id,
                        video.video_id,
                        video.title,
                        video.channel_title,
                        video.published_at,
                        self._to_json(video.model_dump(by_alias=True)),
                    ),
                )
                self._log_action(
                    connection,
                    user_id,
                    "video_found",
                    {
                        "position": position,
                        "videoId": video.video_id,
                        "title": video.title,
                    },
                )

    def save_selected_video(self, user_id: int | None, video: VideoResponse) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO selected_videos (user_id, video_id, title, metadata_json)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    user_id,
                    video.video_id,
                    video.title,
                    self._to_json(video.model_dump(by_alias=True)),
                ),
            )
            self._log_action(
                connection,
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
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO transcripts (
                    user_id,
                    video_id,
                    status,
                    text,
                    segments_json,
                    segments_count
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    transcript.video_id,
                    "success",
                    transcript.text,
                    segments_json,
                    transcript.segments_count,
                ),
            )
            self._log_action(
                connection,
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
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT text, segments_json, segments_count
                FROM transcripts
                WHERE user_id = %s
                    AND video_id = %s
                    AND status = 'success'
                    AND text IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, video_id),
            ).fetchone()

        if not row:
            return None

        text = str(row["text"])
        segments = self._transcript_segments_from_json(row["segments_json"])
        return TranscriptResponse(
            video_id=video_id,
            text=text,
            segments=segments,
            segments_count=int(row["segments_count"]),
        )

    def save_transcript_error(
        self,
        user_id: int | None,
        video_id: str,
        error_reason: str,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO transcripts (user_id, video_id, status, error_reason)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, video_id, "error", error_reason),
            )
            self._log_action(
                connection,
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
        with self.database.connect() as connection:
            for position, topic in enumerate(response.topics, start=1):
                connection.execute(
                    """
                    INSERT INTO suggested_topics (
                        user_id,
                        transcript_hash,
                        transcript_preview,
                        topic,
                        position
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, transcript_hash, transcript_preview, topic, position),
                )
            self._log_action(
                connection,
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
        with self.database.connect() as connection:
            selected_topic_id = self._get_or_create_selected_topic(
                connection=connection,
                user_id=user_id,
                transcript_hash=transcript_hash,
                transcript_preview=transcript_preview,
                selected_topic=selected_topic,
            )
            for position, post in enumerate(response.posts, start=1):
                connection.execute(
                    """
                    INSERT INTO generated_posts (
                        user_id,
                        selected_topic_id,
                        post_text,
                        position
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, selected_topic_id, post, position),
                )
            self._log_action(
                connection,
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
        with self.database.connect() as connection:
            selected_topic_id = self._get_or_create_selected_topic(
                connection=connection,
                user_id=user_id,
                transcript_hash=transcript_hash,
                transcript_preview=transcript_preview,
                selected_topic=selected_topic,
            )
            self._log_action(
                connection,
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
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT action, details_json, created_at::text AS created_at
                FROM action_history
                WHERE user_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (user_id, limit),
            ).fetchall()
        return [
            {
                "action": row["action"],
                "details": json.loads(row["details_json"]),
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def _log_action(
        self,
        connection: Connection,
        user_id: int | None,
        action: str,
        details: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO action_history (user_id, action, details_json)
            VALUES (%s, %s, %s)
            """,
            (user_id, action, self._to_json(details)),
        )

    def _get_or_create_selected_topic(
        self,
        connection: Connection,
        user_id: int | None,
        transcript_hash: str,
        transcript_preview: str,
        selected_topic: str,
    ) -> int:
        row = connection.execute(
            """
            SELECT id
            FROM selected_topics
            WHERE user_id IS NOT DISTINCT FROM %s
                AND transcript_hash = %s
                AND topic = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, transcript_hash, selected_topic),
        ).fetchone()
        if row:
            return int(row["id"])

        row = connection.execute(
            """
            INSERT INTO selected_topics (
                user_id,
                transcript_hash,
                transcript_preview,
                topic
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, transcript_hash, transcript_preview, selected_topic),
        ).fetchone()
        return int(row["id"])

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
