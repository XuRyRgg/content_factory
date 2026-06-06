# Content Factory

MVP backend for automatic Telegram post generation from fresh YouTube videos.

## Current Stage

Stage 8: Simple HTML/CSS/JS frontend.

Implemented:

- FastAPI application.
- Configuration through `.env`.
- YouTube API service.
- Transcript service.
- Local LM Studio AI service through the OpenAI-compatible API.
- Google OAuth login.
- Signed cookie session.
- Simple account page.
- PostgreSQL storage through SQLAlchemy.
- User action history in the account page.
- Auth-required workflow endpoints.
- Per-user transcript cache.
- Simple HTML/CSS/JS frontend.
- Basic API endpoints.
- Basic error handling.

Not implemented yet:

- Telegram publishing.

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
```

Install dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Create `.env` from the example:

```bash
cp .env.example .env
```

Set your real YouTube API key and local LM Studio settings in `.env`:

```env
SESSION_SECRET_KEY=generate_a_random_session_secret_here
SESSION_HTTPS_ONLY=false
DATABASE_URL=postgresql:///content_factory
YOUTUBE_API_KEY=your_real_youtube_key_here
GOOGLE_CLIENT_ID=your_google_oauth_client_id_here
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret_here
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/auth/google/callback
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=auto
LMSTUDIO_MAX_TOKENS=4096
```

Generate a session secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

`SESSION_SECRET_KEY` is required. The app will not start without it.

PostgreSQL setup:

1. Install and start PostgreSQL.
2. If PostgreSQL was installed through Homebrew, start it:

```bash
brew services start postgresql@16
```

3. Create the database:

```bash
/opt/homebrew/opt/postgresql@16/bin/createdb content_factory
```

If `createdb` returns `command not found`, PostgreSQL is installed but its `bin`
folder is not in the terminal `PATH`. Use the full command above, or add this
line to your shell profile later:

```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
```

4. Put the real connection URL into `.env`:

```env
DATABASE_URL=postgresql:///content_factory
```

Google OAuth setup:

1. Create OAuth credentials in Google Cloud Console.
2. Application type: Web application.
3. Add this authorized redirect URI:

```text
http://127.0.0.1:8000/api/auth/google/callback
```

4. Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` into `.env`.

In LM Studio:

1. Download and load a chat/instruct model.
2. Open the Developer tab.
3. Start the local server on port `1234`.
4. Keep `LMSTUDIO_MODEL=auto`, or set the exact loaded model id shown by LM Studio.

## Run

```bash
.venv/bin/uvicorn app.main:app --reload
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Open the simple account page:

```text
http://127.0.0.1:8000/dashboard
```

Most workflow API endpoints require a signed session cookie.
For manual browser checks, log in through `/dashboard`; browser requests will include the cookie automatically.
For `curl` checks, copy the `session` cookie from the browser after Google login and export it:

```bash
export SESSION_COOKIE='paste_session_cookie_value_here'
```

## Check

Health:

```bash
curl http://127.0.0.1:8000/health
```

Current auth user:

```bash
curl -b "session=$SESSION_COOKIE" http://127.0.0.1:8000/api/auth/me
```

Google login starts in the browser:

```text
http://127.0.0.1:8000/api/auth/google/login
```

User history:

```bash
curl -b "session=$SESSION_COOKIE" http://127.0.0.1:8000/api/history
```

## PostgreSQL Schema

The app creates these tables automatically:

```text
users
search_queries
found_videos
selected_videos
transcripts
suggested_topics
selected_topics
generated_posts
action_history
```

History is stored in PostgreSQL, but AI generation still receives only the current request payload:

```text
transcript + selectedTopic
```

Old topics, old posts, and saved history are not passed into the AI prompt.

Search fresh YouTube videos filtered by closed captions:

```bash
curl -X POST http://127.0.0.1:8000/api/youtube/search \
  -b "session=$SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"query":"маркетинг в Telegram","limit":5}'
```

Search results are filtered by YouTube closed captions, but the transcript is marked as not checked until the user selects a video:

```text
captionsLikely: true
transcriptAvailable: false
```

The workflow API endpoints require Google login. Without a session they return:

```json
{"error":{"code":"not_authenticated","message":"User is not authenticated."}}
```

Fetch a transcript:

```bash
curl -b "session=$SESSION_COOKIE" http://127.0.0.1:8000/api/transcripts/VIDEO_ID
```

Successful transcripts are cached in PostgreSQL per user, including text and segments, and reused before calling YouTube again.

Transcript checks depend on YouTube and `youtube-transcript-api`. If a video
returns `ConnectionError`, `NoTranscriptFound`, `TranscriptsDisabled`,
`RequestBlocked`, or `IpBlocked`, the MVP treats that video as unavailable and
the user should choose another video.

Prepare a YouTube search query from a broad topic:

```bash
curl -X POST http://127.0.0.1:8000/api/ai/search-query \
  -b "session=$SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"broadTopic":"маркетинг в Telegram"}'
```

Extract narrow topics:

```bash
curl -X POST http://127.0.0.1:8000/api/ai/topics \
  -b "session=$SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"transcript":"текст транскрипта"}'
```

Save the selected topic before generating posts:

```bash
curl -X POST http://127.0.0.1:8000/api/topics/select \
  -b "session=$SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"transcript":"текст транскрипта","selectedTopic":"выбранная тема"}'
```

Generate Telegram posts:

```bash
curl -X POST http://127.0.0.1:8000/api/ai/posts \
  -b "session=$SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{"transcript":"текст транскрипта","selectedTopic":"выбранная тема"}'
```
