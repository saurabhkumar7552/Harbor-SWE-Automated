You are M1, the task author. Your proposal was reviewed by R1. This is your one and only revision. Apply every hardening item, unless one is factually wrong about the repository; in that case, show why in `revision_notes`. Re-check the repository (`{{REPO_DIR}}`, read-only) for anything the hardening changes: the defect must still exist, the tests must still be hermetic, and the instruction must still have one correct interpretation.

## Your proposal (v1)
```json
{{PROPOSAL}}
```

## R1 review
```json
{{REVIEW}}
```

References: `{{PAINPOINTS}}`, `{{INTEL}}`.

If R1 has a `needs_new_defect` finding, or its first hardening item is "Replace the defect", don't patch the old proposal with more tests. Pick a different defect in this repository that avoids AP-10..AP-13 (no correct sibling path to copy, defects return silent wrong values instead of crashing, the minimal local patch falls into a trap, no single greppable token covering every site). Verify it in the code as carefully as a new scout would. Keep the same `task_id` (the factory pins it), and update the title, instruction outline, tests and traps for the new defect. Say in `revision_notes` why the old defect couldn't be saved.

Return the revised proposal as JSON matching the provided schema. Keep the same `task_id`. `revision_notes` lists, for each hardening item, what you changed.
