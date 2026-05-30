from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="ru">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Content Factory</title>
            <link rel="stylesheet" href="/static/styles.css">
          </head>
          <body>
            <main class="login-shell">
              <section class="login-panel">
                <p class="eyebrow">Content Factory</p>
                <h1>Автоматический постинг в Telegram</h1>
                <a class="primary-link" href="/dashboard">Открыть кабинет</a>
              </section>
            </main>
          </body>
        </html>
        """
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    user = request.session.get("user")
    if not user:
        return HTMLResponse(
            """
            <!doctype html>
            <html lang="ru">
              <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Вход</title>
                <link rel="stylesheet" href="/static/styles.css">
              </head>
              <body>
                <main class="login-shell">
                  <section class="login-panel">
                    <p class="eyebrow">Content Factory</p>
                    <h1>Вход в личный кабинет</h1>
                    <a class="primary-link" href="/api/auth/google/login">Войти через Google</a>
                  </section>
                </main>
              </body>
            </html>
            """
        )

    name = escape(str(user.get("name") or "Пользователь"))
    email = escape(str(user.get("email") or ""))
    picture = escape(str(user.get("picture") or ""))
    avatar_html = (
        f'<img class="avatar" src="{picture}" alt="" width="40" height="40">'
        if picture
        else '<div class="avatar avatar-fallback" aria-hidden="true"></div>'
    )

    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="ru">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Content Factory</title>
            <link rel="stylesheet" href="/static/styles.css">
          </head>
          <body>
            <header class="app-header">
              <div>
                <p class="eyebrow">Content Factory</p>
                <h1>Telegram-посты из YouTube-видео</h1>
              </div>
              <div class="user-bar">
                {avatar_html}
                <div class="user-meta">
                  <strong>{name}</strong>
                  <span>{email}</span>
                </div>
                <form method="post" action="/api/auth/logout">
                  <button class="secondary-button" type="submit">Выйти</button>
                </form>
              </div>
            </header>

            <main class="app-layout">
              <section class="workspace" aria-label="Workflow генерации">
                <div class="status-line" id="statusLine" role="status"></div>

                <section class="panel">
                  <div class="panel-heading">
                    <span class="step-index">1</span>
                    <div>
                      <h2>Широкая тема</h2>
                    </div>
                  </div>
                  <form class="search-form" id="topicForm">
                    <label for="broadTopic">Тема</label>
                    <div class="input-row">
                      <input id="broadTopic" name="broadTopic" type="text" minlength="2" maxlength="200" required placeholder="Например: маркетинг в Telegram">
                      <button class="primary-button" type="submit">Найти видео</button>
                    </div>
                  </form>
                  <div class="query-box hidden" id="queryBox"></div>
                </section>

                <section class="panel hidden" id="videosPanel">
                  <div class="panel-heading">
                    <span class="step-index">2</span>
                    <div>
                      <h2>Видео</h2>
                    </div>
                  </div>
                  <div class="video-list" id="videoList"></div>
                </section>

                <section class="panel hidden" id="topicsPanel">
                  <div class="panel-heading">
                    <span class="step-index">3</span>
                    <div>
                      <h2>Узкие темы</h2>
                    </div>
                  </div>
                  <div class="selected-video" id="selectedVideo"></div>
                  <div class="topic-list" id="topicList"></div>
                </section>

                <section class="panel hidden" id="postsPanel">
                  <div class="panel-heading">
                    <span class="step-index">4</span>
                    <div>
                      <h2>Варианты постов</h2>
                    </div>
                  </div>
                  <div class="toolbar">
                    <button class="secondary-button" type="button" id="backToTopicsButton">Выбрать другую тему</button>
                  </div>
                  <div class="post-list" id="postList"></div>
                </section>
              </section>

              <aside class="history-panel" aria-label="История">
                <div class="panel-heading compact">
                  <div>
                    <h2>История</h2>
                  </div>
                </div>
                <div class="history-list" id="historyList"></div>
              </aside>
            </main>

            <script src="/static/app.js" defer></script>
          </body>
        </html>
        """
    )
