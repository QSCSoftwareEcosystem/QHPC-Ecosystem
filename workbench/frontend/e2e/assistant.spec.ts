import { expect, test } from "@playwright/test";


test("asks ChatQEC through the Workbench gateway and renders cited text safely", async ({
  page,
}) => {
  let submitted: Record<string, unknown> | undefined;

  await page.route("**/api/v1/assistant/chatqec/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        available: true,
        service: "chatqec",
        mode: "canonical-extractive-development",
        source_revision: "4c017510511f835001bfe5901a9d59e86cc130cd",
        corpus_revision: `sha256:${"a".repeat(64)}`,
        pages: 60,
        tool_execution: false,
      }),
    });
  });
  await page.route("**/api/v1/assistant/chatqec/answers", async (route) => {
    submitted = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "req-browser-test",
        correlation_id: "corr-browser-test",
        conversation_id: submitted.conversation_id,
        answer:
          "Surface-code decoding maps syndrome changes to likely errors.\n\n<img src=x onerror=alert(1)>",
        citations: [
          {
            id: "canonical:surface-code",
            title: "Surface Code",
            source_uri:
              "https://github.com/QSCSoftwareThrust/ChatQEC/blob/4c017510511f835001bfe5901a9d59e86cc130cd/pages/surface-code.md",
            source_revision: `sha256:${"b".repeat(64)}`,
            locator: "Decoding",
          },
          {
            id: "unsafe:test",
            title: "Unsafe source",
            source_uri: "javascript:alert(1)",
            source_revision: `sha256:${"c".repeat(64)}`,
          },
        ],
        confidence: 0.86,
        provider: "chatqec-local",
        model: "canonical-extractive-v1",
        corpus_revision: `sha256:${"a".repeat(64)}`,
        usage: {
          input_tokens: 12,
          output_tokens: 18,
          total_tokens: 30,
        },
        latency_ms: {
          retrieval: 1.2,
          rerank: 0,
          generation: 0,
          total: 1.3,
        },
      }),
    });
  });

  await page.goto("/?view=assistant");

  await expect(page.locator("#view-title")).toHaveText("ChatQEC");
  await expect(
    page.getByRole("heading", { name: "QEC research assistant" }),
  ).toBeVisible();
  await expect(page.getByText("60 canonical pages")).toBeVisible();
  await expect(page.getByText("disabled", { exact: true })).toBeVisible();

  await page
    .getByLabel("Question for ChatQEC")
    .fill("How is the surface code decoded?");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  await expect(
    page.getByText(/Surface-code decoding maps syndrome changes/),
  ).toBeVisible();
  await expect(page.locator(".assistant-message.assistant img")).toHaveCount(0);
  await expect(
    page.getByText("<img src=x onerror=alert(1)>", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Surface Code", exact: true }),
  ).toHaveAttribute("href", /^https:\/\/github\.com\//);
  await expect(
    page.getByRole("link", { name: "Unsafe source", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("Unsafe source", { exact: true })).toBeVisible();

  expect(submitted).toBeDefined();
  expect(Object.keys(submitted!).sort()).toEqual([
    "conversation_id",
    "history",
    "question",
  ]);
  expect(submitted).toMatchObject({
    question: "How is the surface code decoded?",
    history: [],
  });
  expect(submitted).not.toHaveProperty("authorized_subject");
  expect(submitted).not.toHaveProperty("identity_token");
});


test("opens ChatQEC contextually and can continue into the full workspace", async ({
  page,
}) => {
  await page.route("**/api/v1/assistant/chatqec/status", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        available: true,
        service: "chatqec",
        mode: "canonical-extractive-development",
        source_revision: "4c017510511f835001bfe5901a9d59e86cc130cd",
        corpus_revision: `sha256:${"a".repeat(64)}`,
        pages: 60,
        tool_execution: false,
      }),
    });
  });

  await page.goto("/");
  const toggle = page.getByRole("button", { name: "ChatQEC", exact: true });
  await toggle.click();

  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(
    page.getByRole("dialog", { name: "ChatQEC contextual assistant" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Keep the workflow in view." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "How is the surface code decoded?" })
    .click();
  await expect(
    page.getByLabel("Question for contextual ChatQEC"),
  ).toHaveValue("How is the surface code decoded?");

  const close = page.getByRole("button", { name: "Close ChatQEC" });
  const openFull = page.getByRole("button", {
    name: /Open the full research workspace/,
  });
  await openFull.focus();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();
  await close.focus();
  await page.keyboard.press("Shift+Tab");
  await expect(openFull).toBeFocused();

  await openFull.click();
  await expect(page.locator("#view-title")).toHaveText("ChatQEC");
  await expect(toggle).toBeHidden();
});
