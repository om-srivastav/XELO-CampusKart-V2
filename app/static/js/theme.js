(() => {
  const media = matchMedia("(prefers-color-scheme: dark)");
  let choice = "system";
  try {
    choice = localStorage.getItem("xelo-theme") || "system";
  } catch {}
  function apply(value) {
    choice = ["light", "dark", "system"].includes(value) ? value : "system";
    document.documentElement.dataset.theme =
      choice === "system" ? (media.matches ? "dark" : "light") : choice;
    try {
      localStorage.setItem("xelo-theme", choice);
    } catch {}
  }
  apply(choice);
  media.addEventListener("change", () => apply(choice));
  document.addEventListener("DOMContentLoaded", () => {
    const select = document.querySelector("#theme");
    if (select) {
      select.value = choice;
      select.addEventListener("change", () => apply(select.value));
    }
  });
})();
