const canvas = document.querySelector("#scene");
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
if (
  canvas &&
  !reduced.matches &&
  !navigator.connection?.saveData &&
  (navigator.hardwareConcurrency || 4) >= 4
) {
  const observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      import("./scene.js").then((m) => m.mount(canvas)).catch(() => {});
      observer.disconnect();
    }
  });
  observer.observe(canvas);
}
