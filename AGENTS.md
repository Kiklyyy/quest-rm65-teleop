# Collaboration Rules for Humans and Agents

Before doing project work, read:

1. `STATUS.md`
2. `docs/INTERFACE.md`
3. `COLLABORATION.md`
4. the relevant `docs/progress/*.md`

Repository state and current Git history take precedence over stale chat context.

## Mandatory development workflow

- One task = one feature branch + one independent worktree.
- Never let two humans/agents edit the same working directory.
- Start new work from current `origin/main`.
- After each meaningful checkpoint: **commit + push** so collaborators can see the actual Ubuntu progress.
- Larger tasks should open a Draft PR early; later pushes update that PR automatically.
- Small tasks may open a normal PR when ready.
- `main` is the reviewed/runnable baseline, not a scratch branch.
- Do not force push shared branches.
- Interface changes must update `docs/INTERFACE.md` before consumers are changed.
- Record real hardware facts in `STATUS.md` / `docs/progress/*.md`; do not leave them only in chat.
- Report branch, SHA, pushed state, PR, tests, hardware actions, and dirty files at handoff.

Full workflow: see `COLLABORATION.md`.

## Scope and safety

- Do not casually modify `/home/lh/robot`.
- Push is source synchronization, not deployment.
- Never start a duplicate RM driver.
- Never mix simulated input into live hardware command paths.
- Real hardware output requires the existing explicit gates and onsite operator authorization.
- Do not run broad `pkill`, change shared network/Conda/system configuration, or terminate unknown processes without explicit task scope.
- Do not commit SSH keys, tokens, `.env`, robot credentials, or personal configuration.
- Temporary robot tuning must not silently replace committed safe/default profiles.

## Current ownership guidance

- A / Quest side: Quest/TCP, VR mapping, operator interaction, integration UX.
- B / RM65 side: RM driver/runtime interface, adapter, robot feedback, hardware validation.

Ownership can change, but cross-boundary work must be coordinated through the shared interface contract.
