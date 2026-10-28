import { describe, expect, it } from "vitest";
import { stageForPhase, statusTone } from "./stages";

describe("stage helpers", () => {
  it("maps AgoneTest phase names to dashboard stages", () => {
    expect(stageForPhase("evosuite_generate")).toBe("generation");
    expect(stageForPhase("jacoco_coverage")).toBe("jacoco");
    expect(stageForPhase("pit_mutation")).toBe("pit");
  });

  it("maps status values to tones", () => {
    expect(statusTone("START")).toBe("running");
    expect(statusTone("PASS")).toBe("success");
    expect(statusTone("ERROR")).toBe("danger");
  });
});

