const token = document.querySelector('meta[name="csrf-token"]').content;
let toastTimer;
function toast(message) {
  const el = document.querySelector("#toast");
  el.textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.textContent = ""), 4000);
}
document.querySelectorAll("[data-confirm]").forEach((button) =>
  button.addEventListener("click", (e) => {
    if (!confirm(button.dataset.confirm)) e.preventDefault();
  }),
);
document.querySelectorAll("[data-gallery]").forEach((button) =>
  button.addEventListener("click", () => {
    document.querySelector("#gallery-main").src = button.dataset.gallery;
  }),
);
document.querySelector("[data-copy]")?.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(location.href);
    toast("Link copied.");
  } catch {
    toast("Copy the page address from your browser.");
  }
});
document.querySelector("[data-share]")?.addEventListener("click", async () => {
  try {
    if (navigator.share)
      await navigator.share({ title: document.title, url: location.href });
    else {
      await navigator.clipboard.writeText(location.href);
      toast("Link copied.");
    }
  } catch (e) {
    if (e.name !== "AbortError")
      toast("Copy the page address from your browser.");
  }
});
const filters = document.querySelector(".filters");
if (filters && matchMedia("(max-width: 800px)").matches) filters.open = false;
const input = document.querySelector("#images");
if (input) {
  let files = [],
    urls = [];
  const previews = document.querySelector("#previews");
  function render() {
    urls.forEach(URL.revokeObjectURL);
    urls = [];
    previews.replaceChildren();
    const dt = new DataTransfer();
    files.forEach((f) => dt.items.add(f));
    input.files = dt.files;
    files.forEach((file, index) => {
      const box = document.createElement("div"),
        image = document.createElement("img");
      const url = URL.createObjectURL(file);
      urls.push(url);
      image.src = url;
      image.alt = "Upload preview " + (index + 1);
      box.append(image);
      for (const [text, action] of [
        [
          "←",
          () => {
            if (index) {
              [files[index - 1], files[index]] = [
                files[index],
                files[index - 1],
              ];
              render();
            }
          },
        ],
        [
          "→",
          () => {
            if (index < files.length - 1) {
              [files[index + 1], files[index]] = [
                files[index],
                files[index + 1],
              ];
              render();
            }
          },
        ],
        [
          "Remove",
          () => {
            files.splice(index, 1);
            render();
          },
        ],
      ]) {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = text;
        b.setAttribute(
          "aria-label",
          text === "←"
            ? "Move photo earlier"
            : text === "→"
              ? "Move photo later"
              : "Remove photo",
        );
        b.addEventListener("click", action);
        box.append(b);
      }
      previews.append(box);
    });
  }
  function add(incoming) {
    const accepted = [...incoming];
    if (files.length + accepted.length > 6) {
      toast("Choose up to six images.");
      return;
    }
    if (
      accepted.some(
        (f) =>
          f.size > 5 * 1024 * 1024 ||
          !["image/jpeg", "image/png", "image/webp"].includes(f.type),
      )
    ) {
      toast("Use JPEG, PNG or WebP under 5 MB each.");
      return;
    }
    files.push(...accepted);
    render();
  }
  input.addEventListener("change", () => {
    const incoming = [...input.files];
    add(incoming);
    render();
  });
  const zone = document.querySelector("#drop-zone");
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("dragging");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragging"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragging");
    add(e.dataTransfer.files);
  });
}
const existing = document.querySelector("#existing-images");
if (existing) {
  function update() {
    document.querySelector("#reorder-form [name=order]").value = [
      ...existing.children,
    ]
      .map((e) => e.dataset.imageId)
      .join(",");
  }
  existing.addEventListener("click", (e) => {
    const box = e.target.closest("[data-image-id]");
    if (!box) return;
    if (e.target.hasAttribute("data-remove-image")) {
      if (existing.children.length === 1) {
        toast("Keep at least one photo.");
        return;
      }
      box.remove();
    } else if (e.target.dataset.move === "-1" && box.previousElementSibling) {
      existing.insertBefore(box, box.previousElementSibling);
    } else if (e.target.dataset.move === "1" && box.nextElementSibling) {
      existing.insertBefore(box.nextElementSibling, box);
    }
    update();
  });
}
const search = document.querySelector("#search"),
  suggestions = document.querySelector("#suggestions");
if (search && suggestions) {
  let timer, controller;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    controller?.abort();
    suggestions.replaceChildren();
    if (search.value.trim().length < 2) return;
    timer = setTimeout(async () => {
      controller = new AbortController();
      try {
        const r = await fetch(
          "/market/suggest?q=" + encodeURIComponent(search.value),
          { signal: controller.signal },
        );
        if (!r.ok) return;
        const data = await r.json();
        suggestions.replaceChildren();
        for (const item of data) {
          const a = document.createElement("a");
          a.href = item.url;
          a.textContent = item.title;
          suggestions.append(a);
        }
      } catch {}
    }, 250);
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-form")) suggestions.replaceChildren();
  });
  search.addEventListener("keydown", (e) => {
    if (e.key === "Escape") suggestions.replaceChildren();
  });
}
const messages = document.querySelector("#messages");
if (messages && messages.dataset.historical !== "true") {
  let after = Number(messages.dataset.after),
    delay = 5000,
    running = false,
    stopped = false,
    timer;
  async function mark() {
    if (!after) return;
    await fetch("/messages/" + messages.dataset.conversation + "/read", {
      method: "POST",
      headers: {
        "X-CSRFToken": token,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: "through=" + after,
    });
  }
  async function poll() {
    if (stopped || running || document.hidden) return;
    running = true;
    try {
      const r = await fetch(
        "/messages/" + messages.dataset.conversation + "/poll?after=" + after,
      );
      if ([401, 403, 404].includes(r.status) || r.redirected) {
        stopped = true;
        return;
      }
      if (!r.ok) throw Error();
      const data = await r.json();
      for (const m of data.messages) {
        if (document.querySelector('[data-message-id="' + m.id + '"]'))
          continue;
        messages.querySelector(".message-empty")?.remove();
        const article = document.createElement("article");
        article.className = "message" + (m.mine ? " mine" : "");
        article.dataset.messageId = m.id;
        const name = document.createElement("strong"),
          body = document.createElement("p"),
          time = document.createElement("small"),
          report = document.createElement("a");
        name.textContent = m.sender;
        body.textContent = m.body;
        time.textContent =
          new Date(m.created_at).toLocaleString() +
          " · " +
          (m.read ? "Read" : "Sent");
        report.href = "/reports/new?kind=message&target=" + m.id;
        report.textContent = "Report";
        article.append(name, body, time, report);
        messages.append(article);
        after = m.id;
      }
      await mark();
      delay = data.messages.length === 100 ? 500 : 5000;
    } catch {
      delay = Math.min(delay * 2, 60000);
    } finally {
      running = false;
      if (!stopped && !document.hidden) timer = setTimeout(poll, delay);
    }
  }
  mark().catch(() => {});
  timer = setTimeout(poll, delay);
  document.addEventListener("visibilitychange", () => {
    clearTimeout(timer);
    if (!document.hidden) poll();
  });
  window.addEventListener(
    "pagehide",
    () => {
      stopped = true;
      clearTimeout(timer);
    },
    { once: true },
  );
}
if (document.querySelector("[data-unread]")) {
  let timer;
  async function counts() {
    if (document.hidden) return;
    try {
      const r = await fetch("/notifications/counts");
      if (!r.ok || r.redirected) return;
      const values = await r.json();
      document
        .querySelectorAll("[data-unread]")
        .forEach((el) => (el.textContent = values[el.dataset.unread] || ""));
    } catch {}
    timer = setTimeout(counts, 30000);
  }
  counts();
  document.addEventListener("visibilitychange", () => {
    clearTimeout(timer);
    if (!document.hidden) counts();
  });
}
