import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

export async function expectNoAxeViolations(page: Page, context?: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  if (results.violations.length > 0) {
    const summary = results.violations
      .map((v) => `${v.id} (${v.impact}): ${v.description}\n  nodes: ${v.nodes.length}`)
      .join("\n");
    throw new Error(`Axe violations${context ? ` on ${context}` : ""}:\n${summary}`);
  }
  expect(results.violations).toEqual([]);
}
