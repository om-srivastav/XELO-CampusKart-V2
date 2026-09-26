// Refresh open forms without clearing text or selected photos.
const ready = new WeakSet();
const pending = new WeakSet();
document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== "post") return;
  const input = form.querySelector('input[name="csrf_token"]');
  if (!input || new URL(form.action, location.href).origin !== location.origin) return;
  if (ready.has(form)) { ready.delete(form); return; }
  event.preventDefault();
  event.stopImmediatePropagation();
  if (pending.has(form)) return;
  pending.add(form);
  const button = event.submitter;
  let error = form.querySelector("[data-form-error]");
  if (error) error.remove();
  try {
    const response = await fetch("/auth/form-token", {
      credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}
    });
    if (!response.ok) throw new Error("refresh");
    const data = await response.json();
    if (!data.token) throw new Error("token");
    input.value = data.token;
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) meta.content = data.token;
    ready.add(form);
    form.requestSubmit(button || undefined);
  } catch {
    ready.delete(form);
    error = document.createElement("p");
    error.dataset.formError = "";
    error.className = "flash";
    error.setAttribute("role", "alert");
    error.textContent = "Couldn't connect. Your entries are still here. Please try again.";
    form.append(error);
  } finally {
    pending.delete(form);
  }
}, true);
