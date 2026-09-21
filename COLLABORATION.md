# Collaboration Workflow

This repository is the shared source of truth for the Quest ↔ RM65 teleoperation project.

The Ubuntu robot host is the development/test site. GitHub is the collaboration and review hub.  
**Local code may move faster than `main`, but meaningful progress must be committed and pushed so the other human/agent can see it.**

## 1. One task = one branch + one worktree

Never let two people/Codex sessions edit the same working directory.

For every new task:

```bash
git fetch origin
git worktree add .worktrees/<task> -b feat/<task> origin/main
```

Use a dedicated build/install/log for that worktree.

Do not casually modify:

```text
/home/lh/robot
```

The existing robot/competition project is read-only unless the task explicitly requires otherwise.

## 2. GitHub sync rule

`commit + push` is the normal progress-sync mechanism.

Do **not** wait until a feature is finished before pushing.

After a meaningful checkpoint:

```bash
git add <relevant-files>
git commit -m "<clear checkpoint message>"
git push -u origin <branch>
```

Good checkpoints include:

- a tested interface contract;
- a dry-run implementation;
- a passing test set;
- a verified hardware micro-test;
- a safety fix;
- a completed small feature.

Do not create meaningless "save" commits every few minutes; push when the state is useful for another collaborator to inspect or continue.

## 3. Pull requests

For a larger task, open a **Draft PR early** from the feature branch to `main`.

The Draft PR is the live collaboration page:

- subsequent `git push` automatically updates it;
- the other human/agent can inspect the latest diff without waiting for completion;
- interface conflicts can be found early.

For a small task, a normal PR at completion is fine.

When implementation and verification are complete:

1. update the relevant progress/status documentation;
2. mark the Draft PR ready for review;
3. merge only after review/acceptance.

## 4. Meaning of main

`main` is the most recent shared, reviewed, runnable baseline.

Do not use `main` as a scratch branch.

New work should normally start from the latest:

```bash
git fetch origin
git switch main
git pull --ff-only
```

or create a new worktree directly from `origin/main`.

After another feature is merged, an active feature branch should sync explicitly:

```bash
git fetch origin
git merge origin/main
```

Resolve conflicts deliberately. Do not use force push as a shortcut.

## 5. No force push on shared work

Do not use:

```bash
git push --force
git push -f
```

on shared project branches unless a human explicitly authorizes it for a specific reason.

If push is rejected because the remote moved, inspect/fetch first.

## 6. Interface changes

Before changing any interface consumed by the other side, update:

```text
docs/INTERFACE.md
```

This includes:

- topic names/types;
- frame semantics;
- coordinate mappings;
- units;
- enable/deadman semantics;
- watchdog/rearm behavior;
- command/stop interfaces.

Do not silently change a cross-team contract in code first.

## 7. Progress and hardware facts

Record verified facts in the repository, not only in chat.

Use:

- `STATUS.md` for overall project state;
- `docs/progress/*.md` for branch/side-specific progress;
- `CHANGELOG.md` for meaningful merged milestones.

Clearly distinguish:

- automated test result;
- dry-run/simulation result;
- isolated hardware micro-test;
- real Quest → real RM65 end-to-end validation.

Never describe an unrun test or unperformed hardware check as completed.

## 8. Local robot tuning

Repository YAML files represent reproducible defaults.

Do not leave a tracked config permanently dirty merely because the robot host needs temporary tuning.

If a temporary local override is required:

- keep the committed safe/default profile unchanged unless the team intentionally changes the baseline;
- record the actual temporary values in the progress log when they matter to a hardware result;
- use an ignored/local override mechanism when one is available;
- never silently publish local tuning as a new shared default.

Always check `git status` before branch switches, merges, cleanup, or handoff.

## 9. Robot safety boundaries

- Only one designated command chain may control one RM65 arm at a time.
- Never start a duplicate RM driver.
- SimulationInput must not publish into live hardware topics/domain during real-arm operation.
- Pushing code does not mean deploying, restarting, or enabling hardware.
- Real hardware output requires the existing explicit safety gates and onsite operator authorization.
- Do not run broad `pkill` or terminate unknown processes.
- Do not change shared network, Conda, driver, or system configuration unless the current task explicitly requires it.

## 10. Required handoff report from Codex/agent

At the end of a coding session or meaningful checkpoint, report:

1. branch name;
2. current commit SHA;
3. whether the commit was pushed;
4. PR URL/state if one exists;
5. files changed;
6. tests actually run and results;
7. hardware actions actually performed;
8. remaining local dirty/untracked files;
9. known limitations / next step.

If work is not complete, still commit and push a coherent checkpoint when practical so collaborators can inspect the current state.

## 11. Recommended parallel ownership

Ownership is flexible, but the current split is:

- A / Quest side: Quest/TCP, VR mapping, operator interaction, integration UX;
- B / RM65 side: RM driver/runtime interface, adapter, robot feedback, hardware validation.

Cross-boundary changes require `docs/INTERFACE.md` synchronization first.

## 12. Rule for agents

Before editing code, every Codex/agent should read:

1. `AGENTS.md`
2. `STATUS.md`
3. `docs/INTERFACE.md`
4. this file
5. the relevant `docs/progress/*.md`

Repository state and current Git history take precedence over stale chat summaries.
