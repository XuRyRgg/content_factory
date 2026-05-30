const state = {
  searchQuery: "",
  selectedVideo: null,
  transcript: "",
  topics: [],
  selectedTopic: "",
};

const actionLabels = {
  search_query_created: "Поисковый запрос",
  video_found: "Видео найдено",
  video_selected: "Видео выбрано",
  transcript_fetched: "Транскрипция получена",
  transcript_failed: "Транскрипция недоступна",
  topics_suggested: "Темы предложены",
  topic_selected: "Тема выбрана",
  posts_generated: "Посты сгенерированы",
};

document.addEventListener("DOMContentLoaded", () => {
  const topicForm = document.querySelector("#topicForm");
  const backToTopicsButton = document.querySelector("#backToTopicsButton");

  topicForm.addEventListener("submit", handleTopicSubmit);
  backToTopicsButton.addEventListener("click", () => {
    show("#postsPanel", false);
    setStatus("Можно выбрать другую тему.");
  });

  refreshHistory();
});

async function handleTopicSubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const input = form.querySelector("#broadTopic");
  const button = form.querySelector("button[type='submit']");
  const broadTopic = input.value.trim();
  if (!broadTopic) {
    return;
  }

  resetWorkflow();
  setLoading(button, true, "Ищем...");
  setStatus("Готовим поисковый запрос.");

  try {
    const queryResponse = await apiJson("/api/ai/search-query", {
      method: "POST",
      body: { broadTopic },
    });
    state.searchQuery = queryResponse.searchQuery || broadTopic;
    renderSearchQuery(state.searchQuery);

    setStatus("Ищем свежие видео.");
    const searchResponse = await apiJson("/api/youtube/search", {
      method: "POST",
      body: { query: state.searchQuery, limit: 5 },
    });
    renderVideos(searchResponse.videos || []);
    show("#videosPanel", true);
    setStatus("Видео загружены.");
    await refreshHistory();
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setLoading(button, false, "Найти видео");
  }
}

async function handleVideoSelect(video, button) {
  setLoading(button, true, "Проверяем...");
  setStatus("Проверяем транскрипцию.");
  show("#topicsPanel", false);
  show("#postsPanel", false);

  try {
    const checkedVideo = await apiJson(`/api/youtube/videos/${encodeURIComponent(video.videoId)}`);
    if (!checkedVideo.mvpUsable) {
      const reason = checkedVideo.transcriptReason || "транскрипция недоступна";
      throw new Error(`Видео нельзя использовать: ${reason}`);
    }

    setStatus("Получаем транскрипцию.");
    const transcript = await apiJson(`/api/transcripts/${encodeURIComponent(video.videoId)}`);
    state.selectedVideo = checkedVideo;
    state.transcript = transcript.text;
    renderSelectedVideo(checkedVideo, transcript);

    setStatus("Выделяем темы.");
    const topicsResponse = await apiJson("/api/ai/topics", {
      method: "POST",
      body: { transcript: transcript.text },
    });
    state.topics = topicsResponse.topics || [];
    renderTopics(state.topics);
    show("#topicsPanel", true);
    setStatus("Темы готовы.");
    await refreshHistory();
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setLoading(button, false, "Выбрать");
  }
}

async function handleTopicSelect(topic, button) {
  if (!state.transcript) {
    setStatus("Сначала выберите видео.", "error");
    return;
  }

  state.selectedTopic = topic;
  setActiveTopic(button);
  setLoading(button, true, "Генерируем...");
  setStatus("Сохраняем выбранную тему.");
  show("#postsPanel", false);

  try {
    await apiJson("/api/topics/select", {
      method: "POST",
      body: {
        transcript: state.transcript,
        selectedTopic: topic,
      },
    });

    setStatus("Генерируем варианты постов.");
    const postsResponse = await apiJson("/api/ai/posts", {
      method: "POST",
      body: {
        transcript: state.transcript,
        selectedTopic: topic,
      },
    });

    renderPosts(postsResponse.posts || []);
    show("#postsPanel", true);
    setStatus("Посты готовы.");
    await refreshHistory();
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setLoading(button, false, topic);
  }
}

async function refreshHistory() {
  const container = document.querySelector("#historyList");
  try {
    const response = await apiJson("/api/history");
    renderHistory(response.history || []);
  } catch (error) {
    container.replaceChildren(emptyState("История недоступна."));
  }
}

async function apiJson(url, options = {}) {
  const init = {
    method: options.method || "GET",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
    },
  };

  if (options.body) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, init);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (response.status === 401) {
    window.location.href = "/dashboard";
    throw new Error("Нужен вход через Google.");
  }

  if (!response.ok) {
    const message = payload?.error?.message || payload?.detail || `Ошибка ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

function renderSearchQuery(query) {
  const box = document.querySelector("#queryBox");
  box.textContent = `Поисковый запрос: ${query}`;
  show("#queryBox", true);
}

function renderVideos(videos) {
  const list = document.querySelector("#videoList");
  list.replaceChildren();

  if (!videos.length) {
    list.append(emptyState("Видео не найдены."));
    return;
  }

  videos.forEach((video) => {
    const card = el("article", "video-card");
    const image = el("img", "video-thumb");
    image.alt = "";
    image.loading = "lazy";
    image.src = getThumbnail(video);

    const body = el("div");
    const title = el("h3", "video-title", video.title || "Без названия");
    const meta = el("div", "video-meta");
    meta.append(
      el("span", "", video.channelTitle || "Канал не указан"),
      el("span", "", formatDate(video.publishedAt)),
      el("span", "", formatViews(video.viewCount)),
      badge(video.captionsLikely ? "Субтитры вероятны" : "Субтитры не проверены", video.captionsLikely ? "good" : "warn")
    );
    body.append(title, meta);

    const button = el("button", "primary-button", "Выбрать");
    button.type = "button";
    button.addEventListener("click", () => handleVideoSelect(video, button));

    card.append(image, body, button);
    list.append(card);
  });
}

function renderSelectedVideo(video, transcript) {
  const box = document.querySelector("#selectedVideo");
  box.replaceChildren();
  const title = el("strong", "", video.title || "Выбранное видео");
  const details = el(
    "div",
    "video-meta",
    `${video.channelTitle || "Канал не указан"} · ${transcript.segmentsCount || 0} сегментов`
  );
  box.append(title, details);
}

function renderTopics(topics) {
  const list = document.querySelector("#topicList");
  list.replaceChildren();

  if (!topics.length) {
    list.append(emptyState("Темы не получены."));
    return;
  }

  topics.forEach((topic) => {
    const button = el("button", "topic-button", topic);
    button.type = "button";
    button.addEventListener("click", () => handleTopicSelect(topic, button));
    list.append(button);
  });
}

function renderPosts(posts) {
  const list = document.querySelector("#postList");
  list.replaceChildren();

  if (!posts.length) {
    list.append(emptyState("Посты не получены."));
    return;
  }

  posts.forEach((post, index) => {
    const card = el("article", "post-card");
    const title = el("h3", "", `Вариант ${index + 1}`);
    const text = el("p", "", post);
    const button = el("button", "ghost-button", "Скопировать");
    button.type = "button";
    button.addEventListener("click", async () => {
      await navigator.clipboard.writeText(post);
      setStatus(`Вариант ${index + 1} скопирован.`);
    });
    card.append(title, text, button);
    list.append(card);
  });
}

function renderHistory(history) {
  const list = document.querySelector("#historyList");
  list.replaceChildren();

  if (!history.length) {
    list.append(emptyState("История пока пуста."));
    return;
  }

  history.forEach((item) => {
    const row = el("div", "history-item");
    row.append(
      el("strong", "", actionLabels[item.action] || item.action),
      el("span", "", item.createdAt || ""),
      el("span", "", historyDetails(item.details || {}))
    );
    list.append(row);
  });
}

function historyDetails(details) {
  if (details.selectedTopic) {
    return details.selectedTopic;
  }
  if (details.title) {
    return details.title;
  }
  if (details.searchQuery) {
    return details.searchQuery;
  }
  if (details.errorReason) {
    return details.errorReason;
  }
  if (details.postsCount) {
    return `${details.postsCount} варианта`;
  }
  if (details.videoId) {
    return details.videoId;
  }
  return "";
}

function resetWorkflow() {
  state.searchQuery = "";
  state.selectedVideo = null;
  state.transcript = "";
  state.topics = [];
  state.selectedTopic = "";
  show("#queryBox", false);
  show("#videosPanel", false);
  show("#topicsPanel", false);
  show("#postsPanel", false);
  document.querySelector("#videoList").replaceChildren();
  document.querySelector("#topicList").replaceChildren();
  document.querySelector("#postList").replaceChildren();
}

function setActiveTopic(activeButton) {
  document.querySelectorAll(".topic-button").forEach((button) => {
    button.classList.toggle("active", button === activeButton);
  });
}

function setStatus(message, type = "") {
  const line = document.querySelector("#statusLine");
  line.textContent = message || "";
  line.classList.toggle("error", type === "error");
}

function setLoading(button, isLoading, label) {
  button.disabled = isLoading;
  button.textContent = label;
}

function show(selector, visible) {
  document.querySelector(selector).classList.toggle("hidden", !visible);
}

function emptyState(text) {
  return el("div", "empty", text);
}

function badge(text, kind) {
  return el("span", `badge ${kind}`, text);
}

function el(tagName, className = "", text = "") {
  const node = document.createElement(tagName);
  if (className) {
    node.className = className;
  }
  if (text) {
    node.textContent = text;
  }
  return node;
}

function getThumbnail(video) {
  return (
    video.thumbnails?.medium?.url ||
    video.thumbnails?.high?.url ||
    video.thumbnails?.default?.url ||
    ""
  );
}

function formatDate(value) {
  if (!value) {
    return "Дата не указана";
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function formatViews(value) {
  if (value === null || value === undefined) {
    return "Просмотры не указаны";
  }
  return `${Number(value).toLocaleString("ru-RU")} просмотров`;
}
