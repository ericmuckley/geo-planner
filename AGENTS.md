# Project Guidelines

Prioritize **simplicity, DRY, maintainability, and readability**. Choose the smallest clear solution; share repeated logic without premature abstractions. Keep changes focused and follow existing patterns.

Routing rules must apply generically to arbitrary supported locations and queries. Selected routes/places belong in validation only; never add city-name, coordinate or region-specific exceptions to make examples pass. Regional validation does not establish nationwide accuracy.

- **TanStack Start + React + TypeScript:** Use file-based routes in `src/routes`, typed code, and server functions or server routes for backend logic. Never edit `src/routeTree.gen.ts` manually.
- **Tailwind CSS v4:** Prefer utilities and existing theme tokens in `src/styles.css`; use `cn()` from `src/lib/utils.ts` to combine classes.
- **shadcn/ui + Lucide:** Reuse components in `src/components/ui` and Lucide icons. Add components with `npx shadcn@latest add <component>`; preserve accessibility.
- **Drizzle + PostgreSQL:** Keep schemas in `src/db/schema.ts` and reuse `src/db/index.ts`. Keep database access and `DATABASE_URL` server-only. Generate migrations with `npm run db:generate`; review them before applying.
- **Zod:** Validate untrusted input at server boundaries; reuse schemas and inferred types.
- **Vercel:** Keep deployments compatible with the existing TanStack Start setup; use environment variables for secrets and never commit them.
- **npm + Biome:** Use npm and maintain `package-lock.json`. Run relevant checks with `npm run check` and `npm run build` for code changes; test meaningful behavior when needed.

Use clear names and small, focused functions and components. Avoid unnecessary dependencies, configuration, and clever code. Add comments only when the reasoning is not obvious.

## Reading the documentation

Before starting or resuming development:

1. Read [the docs index](docs/README.md) and [agent handoff](docs/agent-handoff.md) for the current baseline, recovery checks, local assets and unfinished work.
2. Read [implementation status](docs/implementation-status.md) and the relevant parts of [local development](docs/local-development.md) before changing code, services or configuration.
3. Read [next steps](docs/next-steps.md) for the current scope and acceptance criteria, then the relevant baseline/report linked from the index.

Consult [the initial plan](docs/initial-project-plan.md) for long-term architecture and query semantics. Historical reports in [the archive](docs/archive/README.md) describe their named runs; their old “current,” “next” and admission-hold statements do not override current instructions. Read archived reports only when their model, recipe or evidence is relevant. Explicit user instructions take precedence over recorded plans.

## Maintaining the documentation

Update affected documentation as part of each meaningful change, before handing work back or ending a session:

- **`docs/agent-handoff.md`:** Keep the resume state, recovery commands, asset locations, completed verification, remaining limitations/blockers and next action accurate. A new agent must be able to continue without the chat. Distinguish local-only/uncommitted work from what a fresh clone contains; rediscover process owners instead of relying on old PIDs or tool-session IDs.
- **`docs/implementation-status.md`:** Update shipped behavior, current model/coverage limits, code locations and actual validation results. Separate measured results from forecasts/proposals; preserve timing scopes rather than calling HTTP round trip graph-search time.
- **`docs/local-development.md`:** Maintain exact setup/run/verification commands, prerequisites and environment-variable names when they change. Never include secret values, and preserve existing local configuration.
- **`docs/next-steps.md`:** Keep an ordered, actionable next task with acceptance criteria and explicit deferred scope. Remove completed or superseded instructions from the active queue.
- **`docs/progress.md` and `docs/README.md`:** Refresh the plain-language summary after milestones and update navigation whenever documents are added, moved or superseded. Keep the root README consistent with these entry points.

Prefer updating existing current pages over adding another status, handoff or session-summary document. Link to detailed reports instead of duplicating long measurements. Add dated reports only for substantive experiments or decisions; put superseded/historical material in `docs/archive/`, mark its scope clearly and maintain the archive index. Keep `AGENTS.md` focused on durable rules and reading pointers, not changing graph statistics.

Preserve measured evidence at `docs/evidence/` paths used by frozen recipes. Do not overwrite checksum-bound records, sealed producers or failed-attempt evidence to make checks pass; use a separately versioned run for new results. Keep required forwarding pages when moving a report would break links from checksum-bound indexes. Original measurements must remain distinguishable from later interpretation.

After documentation changes, check relative links and referenced anchors, inspect `git diff --check`, and verify any affected command examples or checksum bindings using safe checks. Do not rerun completed graph producers, overwrite evidence or spend hosted routing quota merely to validate documentation. For documentation-only edits, link/diff checks and applicable existing proof checks are sufficient; run the normal code checks when implementation changes.
