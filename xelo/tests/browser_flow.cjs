const { chromium } = require("playwright");
const fs = require("fs");
const assert = require("assert");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_CHANNEL
      ? { channel: process.env.BROWSER_CHANNEL }
      : {}),
  });
  fs.mkdirSync("tests/artifacts", { recursive: true });
  const errors = [],
    failures = [];
  async function session(name, mobile = false) {
    const c = await browser.newContext({
      viewport: mobile
        ? { width: 390, height: 844 }
        : { width: 1440, height: 1000 },
    });
    const p = await c.newPage();
    p.on("pageerror", (e) => errors.push(e.message));
    p.on("response", (r) => {
      if (r.status() >= 500) failures.push(r.url() + ":" + r.status());
    });
    await p.goto("http://127.0.0.1:5001/auth/login");
    await p.getByLabel("Email", { exact: true }).fill(name + "@qa.test");
    await p
      .getByLabel("Password", { exact: true })
      .fill("QA-browser-password-123");
    await p.getByRole("button", { name: "Sign in", exact: false }).click();
    await p.waitForURL("**/profile/edit");
    return p;
  }
  const seller = await session("seller");
  await seller
    .getByLabel("Department", { exact: true })
    .fill("Computer Science");
  await seller.getByLabel("Year", { exact: true }).fill("Second year");
  await seller
    .getByLabel("WhatsApp number", { exact: true })
    .fill("919000000000");
  await seller.getByLabel("Enable WhatsApp contact", { exact: true }).check();
  await seller
    .getByLabel("Show my full profile to campus members", { exact: true })
    .check();
  const profileSaved = seller.waitForResponse(r => r.url().endsWith("/profile/edit") && r.request().method() === "POST");
  await seller
    .getByRole("button", { name: "Save profile", exact: true })
    .click();
  await profileSaved;
  await seller.waitForLoadState("networkidle");
  await seller.goto("http://127.0.0.1:5001/market/new");
  const title = "QA textbook " + Date.now();
  await seller.getByLabel("What are you selling?").fill(title);
  await seller
    .locator("select[name=category_id]")
    .selectOption({ label: "Books" });
  await seller.locator("select[name=condition]").selectOption("good");
  await seller.getByLabel("Price (₹)", { exact: true }).fill("450");
  await seller.getByLabel("Brand (optional)").fill("QA Test");
  await seller
    .getByLabel("Tell your campus about it")
    .fill(
      "QA fixture listing for end-to-end browser verification. Not a real sale.",
    );
  await seller
    .locator("#images")
    .setInputFiles("tests/fixtures/qa-product.png");
  await seller.getByRole("button", { name: "Publish listing" }).click();
  await seller.waitForURL(/\/market\/\d+$/);
  const productURL = seller.url(),
    pid = productURL.split("/").pop();
  await seller.screenshot({
    path: "tests/artifacts/xelo-qa-listing-desktop.png",
    fullPage: true,
  });
  const buyer = await session("buyer", true);
  await buyer.goto("http://127.0.0.1:5001/market");
  await buyer.locator("#search").fill(title);
  await buyer.getByRole("button", { name: "Search ↗", exact: true }).click();
  await buyer.getByRole("heading", { name: title }).getByRole("link").click();
  await buyer.getByRole("button", { name: "Save for later" }).click();
  let whatsappReached = false;
  await buyer.context().route("https://wa.me/**", async (route) => {
    whatsappReached = true;
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "QA intercepted WhatsApp link",
    });
  });
  await buyer.getByRole("button", { name: "Message on WhatsApp" }).click();
  await buyer.waitForURL(/wa\.me|whatsapp\.com/, {
    timeout: 15000,
    waitUntil: "commit",
  });
  assert(/wa\.me|whatsapp\.com/.test(buyer.url()));
  await buyer.goto(productURL);
  await buyer.getByRole("button", { name: "Message seller" }).click();
  await buyer
    .getByLabel("Your message")
    .fill("QA buyer: is this still available?");
  await buyer.getByRole("button", { name: "Send message" }).click();
  await buyer
    .getByText("QA buyer: is this still available?", { exact: true })
    .waitFor();
  const conversationURL = buyer.url();
  await seller.goto(conversationURL);
  await seller
    .getByLabel("Your message")
    .fill("QA seller: yes, meet at the library.");
  await seller.getByRole("button", { name: "Send message" }).click();
  await buyer
    .getByText("QA seller: yes, meet at the library.", { exact: true })
    .waitFor({ timeout: 15000 });
  await buyer.screenshot({
    path: "tests/artifacts/xelo-qa-messages-mobile.png",
    fullPage: true,
  });
  await seller.goto(productURL);
  await seller.locator("select[name=status]").selectOption("reserved");
  await Promise.all([seller.waitForNavigation(), seller.getByRole("button", { name: "Update status" }).click()]);
  await seller.locator("select[name=status]").selectOption("sold");
  await seller
    .locator("select[name=buyer_id]")
    .selectOption({ label: "QA Buyer" });
  await Promise.all([seller.waitForNavigation(), seller.getByRole("button", { name: "Update status" }).click()]);
  await buyer.goto(productURL);
  await buyer
    .getByRole("button", { name: "Confirm exchange received" })
    .click();
  await buyer
    .getByLabel("Your experience")
    .fill("QA exchange completed correctly. " + title);
  await buyer.getByRole("button", { name: "Publish review" }).click();
  await buyer
    .getByText("QA exchange completed correctly. " + title, { exact: true })
    .waitFor();
  await buyer.goto(productURL);
  await buyer.getByRole("link", { name: "Report listing" }).click();
  await buyer.locator("select[name=reason]").selectOption("other");
  await buyer
    .getByLabel("Tell us what happened")
    .fill("QA moderation workflow test. " + title);
  await buyer.getByRole("button", { name: "Submit report" }).click();
  const admin = await session("moderator");
  await admin.goto("http://127.0.0.1:5001/admin");
  await admin
    .getByText("QA moderation workflow test. " + title, { exact: true })
    .waitFor();
  await admin.goto("http://127.0.0.1:5001/admin?section=products");
  const row = admin
    .locator(".admin-row")
    .filter({ has: admin.getByRole("heading", { name: title, exact: true }) });
  await row
    .getByLabel("Private audit reason")
    .fill("QA moderation test complete");
  await Promise.all([admin.waitForNavigation(), row.getByRole("button", { name: "Apply action" }).click()]);
  const hidden = await buyer.goto(productURL);
  assert.equal(hidden.status(), 404);
  await buyer.goto("http://127.0.0.1:5001/market");
  await buyer.getByLabel("Color theme").selectOption("dark");
  await buyer.reload();
  assert.equal(await buyer.locator("html").getAttribute("data-theme"), "dark");
  assert.equal(
    await buyer.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await buyer.screenshot({
    path: "tests/artifacts/xelo-qa-market-mobile-dark.png",
    fullPage: true,
  });
  const reduced = await browser.newContext({
    reducedMotion: "reduce",
    viewport: { width: 390, height: 844 },
  });
  const rp = await reduced.newPage();
  let sceneRequested = false;
  rp.on("request", (r) => {
    if (r.url().endsWith("/scene.js")) sceneRequested = true;
  });
  await rp.goto("http://127.0.0.1:5001");
  await rp.getByRole("heading", { name: /Good finds/ }).waitFor();
  assert.equal(sceneRequested, false);
  const nojs = await browser.newContext({ javaScriptEnabled: false });
  const np = await nojs.newPage();
  await np.goto("http://127.0.0.1:5001/auth/login");
  await np.getByLabel("Email", { exact: true }).fill("buyer@qa.test");
  await np
    .getByLabel("Password", { exact: true })
    .fill("QA-browser-password-123");
  await np.getByRole("button", { name: "Sign in", exact: false }).click();
  assert(np.url().includes("/profile/edit"));
  assert.deepEqual(errors, []);
  assert.deepEqual(failures, []);
  console.log(
    JSON.stringify({
      result: "PASS",
      flows: [
        "profile",
        "publish with image",
        "search",
        "wishlist",
        "buyer message",
        "seller reply polled",
        "reserve",
        "sell",
        "confirm exchange",
        "review",
        "report",
        "moderation removal",
        "dark theme persistence",
        "mobile no overflow",
        "reduced motion no renderer",
        "login without JavaScript",
      ],
      product: pid,
      pageErrors: errors,
      serverErrors: failures,
    }),
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
