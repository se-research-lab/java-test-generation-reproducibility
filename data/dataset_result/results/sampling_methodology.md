# Data V3 sampling methodology

- Unit: one physical focal Java source file, identified by repository ID plus normalized focal path.
- Repository frame: first 30 final-qualified repositories in the deterministic seed-42 SHA-256 queue.
- Qualification: at least 12 unique structurally eligible classes in scopes compiled on the effective JDK 8 runtime.
- Declared Java 5/6/7/8 and unknown are all tested on JDK 8; only evidence of a >8 requirement is excluded.
- Selection: SHA-256 rank within repository; exactly 10 main and 2 backup classes per repository.
- Complexity is not an eligibility or selection variable. It is used only after selection for relative 150/150 halves.
- No source/build/dependency file may be edited to obtain a successful baseline build.
- Backups are for documented pre-experiment technical failures only, never for unfavorable GPT/EvoSuite outcomes.
- The operational physical-file unit is an explicit amendment to the proposal tuple-based reconstruction and must be disclosed.
