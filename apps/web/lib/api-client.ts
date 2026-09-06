import {
  CompleteDashboardResponse,
  CaseSummary,
  RunStatusResponse,
} from "./contracts";
import completeDashboardFixture from "../fixtures/complete-dashboard.fixture.json";
import casesListFixture from "../fixtures/cases-list.fixture.json";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:3001/api/v1";
const USE_FIXTURES =
  process.env.NEXT_PUBLIC_USE_FIXTURES !== "false"; // Defaults to true for local dev/demo

export class ApiClient {
  /**
   * Fetches full dashboard data for a given case.
   * Seamlessly uses fixture fallback if backend is offline or USE_FIXTURES is true.
   */
  static async getCaseDashboard(caseId: string): Promise<CompleteDashboardResponse> {
    if (USE_FIXTURES) {
      console.log(`[VARUN-ASTRA API Client] Using local fixture fallback for case: ${caseId}`);
      return completeDashboardFixture as CompleteDashboardResponse;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/cases/${caseId}/dashboard`, {
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
      });

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}: ${res.statusText}`);
      }

      return await res.json();
    } catch (err) {
      console.warn(
        `[VARUN-ASTRA API Client] Real API request failed. Falling back to local fixture. Error:`,
        err
      );
      return completeDashboardFixture as CompleteDashboardResponse;
    }
  }

  /**
   * Fetches list of available cases.
   */
  static async getCases(): Promise<CaseSummary[]> {
    if (USE_FIXTURES) {
      return casesListFixture as CaseSummary[];
    }

    try {
      const res = await fetch(`${API_BASE_URL}/cases`, {
        cache: "no-store",
      });

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`);
      }

      return await res.json();
    } catch (err) {
      console.warn(`[VARUN-ASTRA API Client] Failed to fetch cases list. Falling back to fixture.`, err);
      return casesListFixture as CaseSummary[];
    }
  }

  /**
   * Triggers a pipeline execution run for a case/phase.
   */
  static async startPhaseRun(caseId: string, phase: string): Promise<{ runId: string; status: string }> {
    if (USE_FIXTURES) {
      return {
        runId: `RUN-${phase.toUpperCase()}-${Math.floor(Math.random() * 1000)}`,
        status: "RUNNING",
      };
    }

    const res = await fetch(`${API_BASE_URL}/cases/${caseId}/phase-run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phase }),
    });

    if (!res.ok) {
      throw new Error(`Failed to trigger phase run: ${res.statusText}`);
    }

    return await res.json();
  }

  /**
   * Polls run status for active scientific pipeline execution.
   */
  static async getRunStatus(runId: string): Promise<RunStatusResponse> {
    if (USE_FIXTURES) {
      return {
        runId,
        phase: "PHASE_2",
        status: "COMPLETED",
        progressPercentage: 100,
        message: "Simulation finished cleanly.",
      };
    }

    const res = await fetch(`${API_BASE_URL}/runs/${runId}/status`, {
      cache: "no-store",
    });

    if (!res.ok) {
      throw new Error(`Failed to fetch run status: ${res.statusText}`);
    }

    return await res.json();
  }
}
