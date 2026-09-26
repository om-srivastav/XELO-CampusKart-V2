const { chromium } = require("playwright");
const assert = require("assert");
(async () => {
  const b = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_CHANNEL
      ? { channel: process.env.BROWSER_CHANNEL }
      : {}),
  });
  const p = await b.newPage();
  const errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  await p.goto("http://127.0.0.1:5001/auth/login");
  await p.locator("[name=email]").fill("buyer@qa.test");
  await p.locator("[name=password]").fill("QA-browser-password-123");
  await p.getByRole("button", { name: "Sign in", exact: false }).click();
  await p.waitForURL("**/profile/edit");
  for (const width of [320, 390, 768, 1440]) {
    await p.setViewportSize({ width, height: 900 });
    for (const path of [
      "/",
      "/market",
      "/profile/edit",
      "/messages",
      "/dashboard",
    ]) {
      await p.goto("http://127.0.0.1:5001" + path);
      assert.equal(
        await p.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
        width + " " + path,
      );
    }
  }
  await p.setViewportSize({ width: 390, height: 844 });
  await p.goto("http://127.0.0.1:5001/market");
  await p.getByRole("button", { name: "Filter & sort", exact: true }).click();
  assert(await p.locator("dialog").evaluate((e) => e.open));
  await p.keyboard.press("Escape");
  assert.equal(await p.locator("dialog").evaluate((e) => e.open), false);
  assert(
    await p
      .getByRole("button", { name: "Filter & sort", exact: true })
      .evaluate((e) => e === document.activeElement),
  );
  const fallback = await b.newContext();
  await fallback.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      if (kind === "webgl") return null;
      return original.call(this, kind, ...args);
    };
  });
  const f = await fallback.newPage();
  await f.goto("http://127.0.0.1:5001");
  await f.getByRole("heading", { name: /Good finds/ }).waitFor();
  assert(await f.locator(".orb").isVisible());
  await f.getByRole("link", { name: "Sign up", exact: true }).click();
  assert(f.url().includes("/auth/signup"));
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify({
      result: "PASS",
      widths: [320, 390, 768, 1440],
      pages: 5,
      mobileDialog: "Escape and focus restore pass",
      webglFallback: "visible and interactive",
      errors,
    }),
  );
  await b.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
