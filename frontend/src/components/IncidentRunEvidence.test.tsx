import {
  cleanup,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { PipelineRun } from "../api/types";
import { pipelineRun } from "../test/fixtures";
import { IncidentRunEvidence } from "./IncidentRunEvidence";

afterEach(cleanup);

function renderRun(overrides: Partial<PipelineRun> = {}) {
  render(
    <IncidentRunEvidence
      run={{
        ...pipelineRun,
        ...overrides,
      }}
    />,
  );
}

describe("IncidentRunEvidence", () => {
  it("renders the run summary and error evidence", () => {
    renderRun();

    expect(
      within(screen.getByText("Run status").parentElement!).getByText(
        "Failed",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByText("Duration").parentElement!).getByText(
        "22m",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByText("Rows processed").parentElement!).getByText(
        "450",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByText("Quality failures").parentElement!).getByText(
        "2",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Run error")).toBeInTheDocument();
    expect(
      screen.getByText("Source file validation failed"),
    ).toBeInTheDocument();
  });

  it("does not render a log disclosure when there are no logs", () => {
    renderRun({ logs: [] });

    expect(screen.queryByText(/View \d+ log entr/)).not.toBeInTheDocument();
  });

  it("renders one log entry with singular text", () => {
    renderRun({ logs: ["Only log entry"] });

    expect(screen.getByText("View 1 log entry")).toBeInTheDocument();
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText("Only log entry")).toBeInTheDocument();
  });

  it("renders multiple log entries in their original order", () => {
    renderRun({ logs: ["First log entry", "Second log entry"] });

    expect(screen.getByText("View 2 log entries")).toBeInTheDocument();
    const entries = screen.getAllByRole("listitem");
    expect(entries).toHaveLength(2);
    expect(within(entries[0]).getByText("01")).toBeInTheDocument();
    expect(
      within(entries[0]).getByText("First log entry"),
    ).toBeInTheDocument();
    expect(within(entries[1]).getByText("02")).toBeInTheDocument();
    expect(
      within(entries[1]).getByText("Second log entry"),
    ).toBeInTheDocument();
  });
});
