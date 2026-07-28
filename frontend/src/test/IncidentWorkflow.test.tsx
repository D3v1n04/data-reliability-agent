import {
  cleanup,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import {
  diagnosis,
  incident,
  pipeline,
  pipelineRun,
} from "./fixtures";

function jsonResponse(
  body: unknown,
  status = 200,
): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("incident-to-diagnosis workflow", () => {
  it("loads evidence, generates a diagnosis, and advances status", async () => {
    let currentIncident = { ...incident };

    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url.endsWith("/health")) {
          return jsonResponse({ status: "ok" });
        }
        if (
          url.endsWith(`/api/incidents/${incident.id}`) &&
          method === "GET"
        ) {
          return jsonResponse(currentIncident);
        }
        if (
          url.endsWith(`/api/pipeline-runs/${pipelineRun.id}`)
        ) {
          return jsonResponse(pipelineRun);
        }
        if (url.endsWith(`/api/pipelines/${pipeline.id}`)) {
          return jsonResponse(pipeline);
        }
        if (
          url.endsWith(
            `/api/incidents/${incident.id}/diagnosis`,
          ) &&
          method === "GET"
        ) {
          return jsonResponse(
            { detail: "Incident diagnosis not found" },
            404,
          );
        }
        if (
          url.endsWith(
            `/api/incidents/${incident.id}/diagnosis`,
          ) &&
          method === "POST"
        ) {
          return jsonResponse(diagnosis, 201);
        }
        if (
          url.endsWith(`/api/incidents/${incident.id}/status`) &&
          method === "PATCH"
        ) {
          currentIncident = {
            ...currentIncident,
            status: "investigating",
          };
          return jsonResponse(currentIncident);
        }

        return jsonResponse({ detail: "Not found" }, 404);
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`/incidents/${incident.id}`]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", {
        name: incident.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("RUN_FAILED")).toBeInTheDocument();
    expect(
      screen.getByText("Source file validation failed"),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Generate diagnosis" }),
    );

    expect(
      await screen.findByText(diagnosis.explanation),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Customer import validation failure"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("88% confidence")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Start investigation" }),
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Resolve incident" }),
      ).toBeInTheDocument();
    });
    expect(currentIncident.status).toBe("investigating");
  });

  it("filters the incident list by search text", async () => {
    const secondIncident = {
      ...incident,
      id: "66666666-6666-6666-6666-666666666666",
      title: "Nightly orders quality warning",
      description: "Two order quality checks failed.",
      severity: "high" as const,
      status: "resolved" as const,
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string | URL | Request) => {
        const url = String(input);

        if (url.endsWith("/health")) {
          return jsonResponse({ status: "ok" });
        }
        if (url.includes("/api/incidents?")) {
          return jsonResponse([incident, secondIncident]);
        }

        return jsonResponse({ detail: "Not found" }, 404);
      }),
    );

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/incidents"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(incident.title),
    ).toBeInTheDocument();
    expect(screen.getByText(secondIncident.title)).toBeInTheDocument();

    await user.type(
      screen.getByRole("textbox", { name: "Search incidents" }),
      "orders",
    );

    expect(screen.queryByText(incident.title)).not.toBeInTheDocument();
    expect(screen.getByText(secondIncident.title)).toBeInTheDocument();
  });
});
