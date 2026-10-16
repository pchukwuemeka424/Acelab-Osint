import { expect, test } from "@playwright/test"

test("demonstration investigation reaches an evidence-backed report", async ({ page }) => {
  await page.setViewportSize({ width: 1373, height: 647 })
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Start an investigation" })).toBeVisible()
  await page.getByLabel("Investigate indicator").fill("portal.example.test")
  await page.getByLabel("Investigate indicator").press("Enter")
  await expect(page.getByRole("heading", { name: "Nodes details" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "1 Domains" })).toBeVisible()
  await expect(page.getByRole("button", { name: "portal.example.test" })).toBeVisible()
  await expect(page.locator("[data-graph-ready]")).toHaveAttribute("data-graph-ready", "1")
  await expect(page.getByText("Live collection off")).toBeVisible()
  await page.screenshot({ path: "../docs/reference/actual-1373x647.png" })

  await page.getByRole("button", { name: "Exp date" }).click()
  await page.getByRole("tab", { name: /Domains/ }).click()
  await page.getByRole("button", { name: /example\.test/ }).first().click()
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export records" }).click()
  expect((await download).suggestedFilename()).toContain(".csv")

  await page.getByRole("button", { name: "Account menu" }).click()
  await page.getByRole("link", { name: "Report" }).click()
  await expect(page.getByRole("heading", { name: "Investigation report" })).toBeVisible()
  await expect(page.getByText("heuristic baseline", { exact: false }).first()).toBeVisible()
  await expect(page.getByText("Live collection is off. Only the submitted indicator is stored.")).toBeVisible()

  await page.setViewportSize({ width: 1920, height: 1080 })
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Start an investigation" })).toBeVisible()
  await expect(page.getByLabel("Investigate indicator")).toHaveAttribute("placeholder", /domain/)
  await page.screenshot({ path: "../docs/reference/actual-1920x1080.png" })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByLabel("Investigate indicator")).toBeVisible()
  await page.screenshot({ path: "../docs/reference/actual-mobile.png" })
})
