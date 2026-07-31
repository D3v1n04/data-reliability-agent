import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Incident } from "../api/types";
import { incident, pipeline, pipelineRun } from "../test/fixtures";
import { RunDetailPage } from "./RunDetailPage";

function jsonResponse(body: unknown): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function renderRunDetail(incidents: Incident[]) {
  const fetchMock = vi.fn(
    async (input: string | URL | Request) => {
      const url = new URL(String(input));

      if (url.pathname === `/api/pipeline-runs/${pipelineRun.id}`) {
        return jsonResponse(pipelineRun);
      }
      if (url.pathname === `/api/pipelines/${pipeline.id}`) {
        return jsonResponse(pipeline);
      }
      if (url.pathname === "/api/incidents") {
        return jsonResponse(incidents);
      }

      return Promise.resolve(
        new Response(JSON.stringify({ detail: "Not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      );
    },
  );
  vi.stubGlobal("fetch", fetchMock);

  render(
    <MemoryRouter initialEntries={[`/runs/${pipelineRun.id}`]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RunDetailPage incident lookup", () => {
  it("requests the loaded run's incident and renders the match", async () => {
    const fetchMock = renderRunDetail([incident]);

    expect(
      await screen.findByRole("heading", {
        name: pipelineRun.external_run_id,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: /Incident created from this run/,
      }),
    ).toHaveAttribute("href", `/incidents/${incident.id}`);

    const incidentRequests = fetchMock.mock.calls
      .map(([input]) => new URL(String(input)))
      .filter((url) => url.pathname === "/api/incidents");

    expect(incidentRequests).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(
      incidentRequests[0].searchParams.get("pipeline_run_id"),
    ).toBe(pipelineRun.id);
    expect(incidentRequests[0].searchParams.get("limit")).toBe("100");
    expect(incidentRequests[0].searchParams.get("offset")).toBe("0");
  });

  it("preserves the empty-incident behavior", async () => {
    const fetchMock = renderRunDetail([]);

    expect(
      await screen.findByRole("heading", {
        name: pipelineRun.external_run_id,
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Incident created from this run"),
    ).not.toBeInTheDocument();

    await waitFor(() => {
      const incidentRequests = fetchMock.mock.calls
        .map(([input]) => new URL(String(input)))
        .filter((url) => url.pathname === "/api/incidents");

      expect(incidentRequests).toHaveLength(1);
      expect(
        incidentRequests[0].searchParams.get("pipeline_run_id"),
      ).toBe(pipelineRun.id);
    });
  });
});
