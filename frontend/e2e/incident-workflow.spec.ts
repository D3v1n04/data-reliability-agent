import { expect, test } from "@playwright/test";

import {
  diagnosis,
  incident,
  pipeline,
  pipelineRun,
} from "../src/test/fixtures";

test("failure to diagnosis to lifecycle workflow", async ({ page }) => {
  let currentIncident = { ...incident };
  let storedDiagnosis = false;

  await page.route("http://127.0.0.1:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    let status = 200;
    let body: unknown = { detail: "Not found" };

    if (path === "/health") {
      body = { status: "ok" };
    } else if (
      path === `/api/pipelines/${pipeline.id}/runs`
    ) {
      body = [pipelineRun];
    } else if (path === `/api/pipelines/${pipeline.id}`) {
      body = pipeline;
    } else if (path === `/api/pipeline-runs/${pipelineRun.id}`) {
      body = pipelineRun;
    } else if (path === "/api/incidents") {
      body = [currentIncident];
    } else if (
      path === `/api/incidents/${incident.id}/diagnosis` &&
      method === "POST"
    ) {
      storedDiagnosis = true;
      status = 201;
      body = diagnosis;
    } else if (
      path === `/api/incidents/${incident.id}/diagnosis`
    ) {
      if (storedDiagnosis) {
        body = diagnosis;
      } else {
        status = 404;
        body = { detail: "Incident diagnosis not found" };
      }
    } else if (
      path === `/api/incidents/${incident.id}/status` &&
      method === "PATCH"
    ) {
      const requestBody = request.postDataJSON() as {
        status: "investigating" | "resolved";
      };
      currentIncident = {
        ...currentIncident,
        status: requestBody.status,
        resolved_at:
          requestBody.status === "resolved"
            ? "2026-07-28T12:45:00Z"
            : null,
      };
      body = currentIncident;
    } else if (path === `/api/incidents/${incident.id}`) {
      body = currentIncident;
    } else {
      status = 404;
    }

    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });

  await page.goto(`/pipelines/${pipeline.id}`);
  await expect(
    page.getByRole("heading", { name: pipeline.name }),
  ).toBeVisible();

  await page.getByRole("link", {
    name: pipelineRun.external_run_id,
    exact: true,
  }).click();
  await expect(
    page.getByRole("heading", {
      name: pipelineRun.external_run_id,
    }),
  ).toBeVisible();

  await page
    .getByRole("link", {
      name: new RegExp("Incident created from this run"),
    })
    .click();
  await expect(
    page.getByRole("heading", { name: incident.title }),
  ).toBeVisible();
  await expect(page.getByText("RUN_FAILED")).toBeVisible();

  await page
    .getByRole("button", { name: "Generate diagnosis" })
    .click();
  await expect(page.getByText(diagnosis.explanation)).toBeVisible();
  await expect(
    page.getByText("Customer import validation failure"),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Start investigation" })
    .click();
  await expect(
    page.getByRole("button", { name: "Resolve incident" }),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Resolve incident" })
    .click();
  await expect(page.getByText("Terminal audit record")).toBeVisible();
});
