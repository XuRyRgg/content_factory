import json
import re
from typing import Any

from pydantic import ValidationError
import requests

from app.core.errors import AppError
from app.schemas import PostsResponse, SearchQueryResponse, TopicsResponse


SEARCH_QUERY_PROMPT = """
Ты помогаешь подготовить поисковый запрос для YouTube.

Задача:
- Получи широкую тему пользователя.
- Верни один короткий поисковый запрос на русском языке.
- Запрос должен помогать найти свежие видео, из которых можно сделать экспертный Telegram-пост.
- Не добавляй операторов поиска, кавычек, годы, даты и лишние пояснения.

Широкая тема:
{broad_topic}
"""


TOPICS_PROMPT = """
Ты редактор экспертного Telegram-канала.

Тебе дан только транскрипт одного YouTube-видео.
Выдели 5 узких тем для экспертных Telegram-постов.

Правила:
- Используй только факты, идеи и контекст из транскрипта.
- Не добавляй внешние факты.
- Не используй историю прошлых генераций.
- Темы должны быть конкретными, полезными и подходящими для Telegram-поста.
- Пиши на русском языке.

Транскрипт:
{transcript}
"""


POSTS_PROMPT = """
Ты пишешь экспертные Telegram-посты на русском языке.

Тебе даны только:
1. транскрипт выбранного YouTube-видео;
2. тема, выбранная пользователем.

Сгенерируй 4 разных варианта Telegram-поста по выбранной теме.

Правила:
- Используй только факты, идеи и контекст из транскрипта.
- Не добавляй внешние факты, цифры, имена, кейсы и выводы, которых нет в транскрипте.
- Не добавляй конкретные объекты, действия, инструменты или детали, которых нет в транскрипте.
- Не используй старые темы, старые посты и историю генераций.
- Выбранная тема задаёт только фокус поста, но не является источником новых фактов.
- Если фактов мало, делай пост короче и проще, но не выдумывай.
- Перед ответом проверь каждый пост и удали любые детали, которых нет в транскрипте.
- Каждый пост должен быть самостоятельным.
- Стиль: экспертно, понятно, без канцелярита.
- Без Markdown-заголовков.
- Без хэштегов.
- Не упоминай, что текст написан по транскрипту.

Выбранная тема:
{selected_topic}

Транскрипт:
{transcript}
"""


SEARCH_QUERY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "searchQuery": {
            "type": "string",
            "description": "Short YouTube search query in Russian.",
        }
    },
    "required": ["searchQuery"],
}


TOPICS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Five narrow Telegram post topics in Russian.",
        }
    },
    "required": ["topics"],
}


POSTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "posts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Four different expert Telegram post variants in Russian.",
        }
    },
    "required": ["posts"],
}


class AIService:
    def __init__(self, base_url: str, model: str, max_tokens: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens

    def prepare_search_query(self, broad_topic: str) -> SearchQueryResponse:
        payload = self._generate_json(
            prompt=SEARCH_QUERY_PROMPT.format(broad_topic=broad_topic),
            schema=SEARCH_QUERY_SCHEMA,
        )
        try:
            response = SearchQueryResponse.model_validate(payload)
        except ValidationError as exc:
            raise self._invalid_response_error() from exc
        response.search_query = self._clean_search_query(response.search_query)
        return response

    def extract_topics(self, transcript: str) -> TopicsResponse:
        payload = self._generate_json(
            prompt=TOPICS_PROMPT.format(transcript=transcript),
            schema=TOPICS_SCHEMA,
        )
        try:
            response = TopicsResponse.model_validate(payload)
        except ValidationError as exc:
            raise self._invalid_response_error() from exc

        response.topics = self._clean_items(response.topics, expected_count=5)
        return response

    def generate_posts(self, transcript: str, selected_topic: str) -> PostsResponse:
        payload = self._generate_json(
            prompt=POSTS_PROMPT.format(
                transcript=transcript,
                selected_topic=selected_topic,
            ),
            schema=POSTS_SCHEMA,
        )
        try:
            response = PostsResponse.model_validate(payload)
        except ValidationError as exc:
            raise self._invalid_response_error() from exc

        response.posts = self._clean_items(response.posts, expected_count=4)
        return response

    def _generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        no_think_prompt = f"/no_think\n{prompt}"
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self._resolve_model(),
                    "messages": [
                        {
                            "role": "system",
                            "content": "Отвечай только валидным JSON по заданной схеме.",
                        },
                        {"role": "user", "content": no_think_prompt},
                    ],
                    "stream": False,
                    "temperature": 0.3,
                    "max_tokens": self.max_tokens,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "content_factory_response",
                            "strict": True,
                            "schema": schema,
                        },
                    },
                },
                timeout=180,
            )
        except requests.RequestException as exc:
            raise AppError(
                status_code=502,
                code="lmstudio_unavailable",
                message="LM Studio local server is not available. Start the server in LM Studio Developer tab.",
            ) from exc

        if response.status_code != 200:
            raise AppError(
                status_code=502,
                code="lmstudio_request_failed",
                message=self._extract_lmstudio_error(response),
            )

        response_data = response.json()
        message = response_data.get("choices", [{}])[0].get("message", {})
        response_text = message.get("content") or message.get("reasoning_content")
        if not response_text:
            raise AppError(
                status_code=502,
                code="ai_empty_response",
                message="LM Studio returned an empty response.",
            )

        try:
            result = json.loads(response_text.strip())
        except json.JSONDecodeError as exc:
            raise AppError(
                status_code=502,
                code="ai_invalid_json",
                message="LM Studio returned invalid JSON.",
            ) from exc

        if not isinstance(result, dict):
            raise self._invalid_response_error()
        return result

    def _resolve_model(self) -> str:
        if self.model and self.model != "auto":
            return self.model

        try:
            response = requests.get(f"{self.base_url}/models", timeout=10)
            response.raise_for_status()
            models = response.json().get("data", [])
        except requests.RequestException as exc:
            raise AppError(
                status_code=502,
                code="lmstudio_unavailable",
                message="LM Studio local server is not available. Start the server in LM Studio Developer tab.",
            ) from exc

        if not models:
            raise AppError(
                status_code=502,
                code="lmstudio_model_missing",
                message="No model is loaded in LM Studio. Load a model or set LMSTUDIO_MODEL in .env.",
            )
        return models[0].get("id", "local-model")

    def _extract_lmstudio_error(self, response: requests.Response) -> str:
        try:
            error = response.json().get("error")
        except ValueError:
            error = None
        if isinstance(error, dict):
            return f"LM Studio request failed: {error.get('message', error)}"
        if error:
            return f"LM Studio request failed: {error}"
        return "LM Studio request failed."

    def _clean_items(self, items: list[str], expected_count: int) -> list[str]:
        cleaned = [item.strip() for item in items if item.strip()]
        if len(cleaned) < expected_count:
            raise self._invalid_response_error()
        return cleaned[:expected_count]

    def _clean_search_query(self, query: str) -> str:
        query = re.sub(r"\b[12][0-9]{3}\b", "", query)
        query = query.replace('"', "").replace("'", "")
        query = re.sub(r"\s+", " ", query)
        return query.strip()

    def _invalid_response_error(self) -> AppError:
        return AppError(
            status_code=502,
            code="ai_invalid_response",
            message="LM Studio returned an unexpected response structure.",
        )
