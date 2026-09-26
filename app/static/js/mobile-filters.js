const filters = document.querySelector(".filters");
if (filters && typeof HTMLDialogElement !== "undefined") {
  const media = matchMedia("(max-width: 800px)");
  const anchor = document.createComment("filter home");
  filters.before(anchor);
  const open = document.createElement("button");
  open.type = "button";
  open.textContent = "Filter & sort";
  open.className = "filter-open";
  anchor.before(open);
  const dialog = document.createElement("dialog");
  dialog.className = "filter-dialog";
  dialog.setAttribute("aria-label", "Filter and sort listings");
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "Close filters ×";
  dialog.append(close);
  document.body.append(dialog);
  function reset() {
    if (dialog.open) dialog.close();
    anchor.after(filters);
    open.hidden = !media.matches;
    filters.hidden = media.matches;
  }
  open.addEventListener("click", () => {
    filters.hidden = false;
    filters.open = true;
    dialog.append(filters);
    dialog.showModal();
  });
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    anchor.after(filters);
    filters.hidden = media.matches;
    open.focus();
  });
  media.addEventListener("change", reset);
  reset();
}
