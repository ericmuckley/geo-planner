# Project Guidelines

Prioritize **simplicity, DRY, maintainability, and readability**. Choose the smallest clear solution; share repeated logic without premature abstractions. Keep changes focused and follow existing patterns.

- **TanStack Start + React + TypeScript:** Use file-based routes in `src/routes`, typed code, and server functions or server routes for backend logic. Never edit `src/routeTree.gen.ts` manually.
- **Tailwind CSS v4:** Prefer utilities and existing theme tokens in `src/styles.css`; use `cn()` from `src/lib/utils.ts` to combine classes.
- **shadcn/ui + Lucide:** Reuse components in `src/components/ui` and Lucide icons. Add components with `npx shadcn@latest add <component>`; preserve accessibility.
- **Drizzle + PostgreSQL:** Keep schemas in `src/db/schema.ts` and reuse `src/db/index.ts`. Keep database access and `DATABASE_URL` server-only. Generate migrations with `npm run db:generate`; review them before applying.
- **Zod:** Validate untrusted input at server boundaries; reuse schemas and inferred types.
- **Vercel:** Keep deployments compatible with the existing TanStack Start setup; use environment variables for secrets and never commit them.
- **npm + Biome:** Use npm and maintain `package-lock.json`. Run relevant checks with `npm run check` and `npm run build` for code changes; test meaningful behavior when needed.

Use clear names and small, focused functions and components. Avoid unnecessary dependencies, configuration, and clever code. Add comments only when the reasoning is not obvious.
