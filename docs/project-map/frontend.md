---
module: web
purpose: SvelteKit 2 + Svelte 5 + TypeScript frontend
key_files:
  - web/package.json — scripts + deps (svelte, sveltekit, biome, vitest, knip, tailwind)
  - web/svelte.config.js — adapter-node + vitePreprocess
  - web/vite.config.ts — sveltekit plugin + proxy /api → localhost:8000
  - web/vitest.config.ts — jsdom + @testing-library/svelte + coverage v8
  - web/biome.json — linter/formatter config (noExplicitAny=error, 2-space, double quotes)
  - web/knip.json — dead code detection entry points
  - web/tsconfig.json — TS config
  - web/src/routes/+layout.svelte — Tailwind wrapper
  - web/src/routes/+page.svelte — root page (placeholder)
  - web/Dockerfile.web — multi-stage build → adapter-node runtime
dependencies: []
last_updated: 2026-07-20
---

# frontend — web/

## Structure

```
web/
├── package.json          # telesoft-web: dev/build/preview/lint/format/check/typecheck/test/test:watch/knip
├── package-lock.json     # 428 пакетов
├── svelte.config.js      # adapter-node + vitePreprocess
├── vite.config.ts        # sveltekit plugin + proxy /api → localhost:8000 (ws:true)
├── vitest.config.ts      # jsdom + @testing-library/svelte/vite + coverage v8
├── tsconfig.json         # TS config (extends svelte-kit)
├── biome.json            # recommended, noExplicitAny=error, 2-space, double quotes, semicolons, lineWidth 100
├── knip.json             # entry: src/**/*.svelte, src/tests/**/*.ts
├── postcss.config.js     # tailwindcss + autoprefixer
├── tailwind.config.js    # минимальный config
├── Dockerfile.web        # multi-stage build → runtime (adapter-node, PORT=3000)
├── .env.example          # VITE_API_BASE=http://localhost:8000
├── .gitignore
└── src/
    ├── app.html          # HTML shell (%sveltekit.head% + %sveltekit.body%)
    ├── app.css           # @tailwind base/components/utilities
    ├── app.d.ts          # App.Locals (пустой), App.Error
    ├── routes/
    │   ├── +layout.svelte  # Tailwind wrapper, <slot />
    │   └── +page.svelte    # <h1>telesoft</h1><p>Under construction</p>
    └── tests/
        ├── setup.ts        # afterEach restoreAllMocks
        └── smoke.test.ts   # expect(1+1).toBe(2) — гарантирует vitest зелёный
```

## Patterns

- **SvelteKit 2 + Svelte 5 runes**
- **adapter-node** для SSR в Docker (PORT=3000)
- **Vite proxy** `/api` → backend (localhost:8000) для dev
- **Biome** вместо ESLint+Prettier (единый linter/formatter)
- **Knip** для dead code detection
- **Vitest + @testing-library/svelte** для unit-тестов (jsdom)
- **TailwindCSS** через PostCSS