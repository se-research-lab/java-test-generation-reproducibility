export type StageKey = "precheck" | "baseline" | "generation" | "compile" | "jacoco" | "pit" | "report";

export const STAGES: Array<{ key: StageKey; label: string; detail: string }> = [
  { key: "precheck", label: "Precheck", detail: "Source and buildable class gate" },
  { key: "baseline", label: "Baseline", detail: "Clean build before generation" },
  { key: "generation", label: "Generate", detail: "GPT and EvoSuite test classes" },
  { key: "compile", label: "Compile", detail: "Project test compilation" },
  { key: "jacoco", label: "JaCoCo", detail: "Branch, line, and method coverage" },
  { key: "pit", label: "PIT", detail: "Mutation score" },
  { key: "report", label: "Report", detail: "CSV and Excel artifacts" }
];

export function stageForPhase(phase: string): StageKey {
  const normalized = phase.toLowerCase();
  if (normalized.includes("precheck") || normalized.includes("stage")) return "precheck";
  if (normalized.includes("baseline")) return "baseline";
  if (normalized.includes("evosuite") || normalized.includes("generation") || normalized.includes("project_run")) {
    return "generation";
  }
  if (normalized.includes("compile") || normalized.includes("maven") || normalized.includes("gradle")) return "compile";
  if (normalized.includes("jacoco") || normalized.includes("coverage")) return "jacoco";
  if (normalized.includes("pit") || normalized.includes("mutation")) return "pit";
  return "report";
}

export function statusTone(status: string): "idle" | "running" | "success" | "warning" | "danger" {
  const normalized = status.toLowerCase();
  if (["start", "running", "queued"].includes(normalized)) return "running";
  if (["pass", "completed", "ok"].includes(normalized)) return "success";
  if (["skip", "warn", "warning"].includes(normalized)) return "warning";
  if (["fail", "failed", "error", "cancelled"].includes(normalized)) return "danger";
  return "idle";
}
