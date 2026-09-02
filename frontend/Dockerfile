# syntax=docker/dockerfile:1.7
# ---- Stage 1: builder ----
# Install the frontend dependencies via pnpm (corepack-managed) and produce
# the static frontend bundle in `dist/`. The `prebuild` script
# regenerates OpenAPI types from `docs/api/openapi.json`, so that file is
# copied before the build step.
FROM node:20-slim AS builder

WORKDIR /app/frontend

# corepack ships with node:20-slim and provisions pnpm 9.12 from
# packageManager in frontend/package.json — no global npm install needed.
RUN corepack enable

# Copy frontend package metadata first so dependency installation remains
# cached independently of source changes.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/.npmrc ./

# Install all deps (including devDependencies: tsc, vite, eslint, vitest)
# so the build can run. `--frozen-lockfile` ensures the lockfile is never
# mutated by the build.
RUN pnpm install --frozen-lockfile

# Keep the repository-relative path expected by the OpenAPI generator.
COPY docs/api/openapi.json /app/docs/api/openapi.json

# Now copy the rest of the frontend source.
COPY frontend/ ./

# Build (triggers `prebuild` -> openapi:gen, then `tsc -b && vite build`).
RUN pnpm build

# ---- Stage 2: runtime ----
# Minimal runtime: node + the workspace tree (so `pnpm preview` can resolve
# vite through the workspace's node_modules). pnpm symlinks survive the
# cross-stage COPY because every symlink target is also copied in the same
# layer.
FROM node:20-slim AS runtime

ENV NODE_ENV=production

WORKDIR /app/frontend

# corepack so `pnpm` is available at runtime.
RUN corepack enable

# Copy the standalone frontend package. All pnpm symlink targets live under
# the package's own node_modules directory.
COPY --from=builder --chown=node:node /app/frontend /app/frontend

EXPOSE 5173
USER node

# `vite preview` reads vite.config.ts but respects the CLI flags below,
# which override the default `host: 127.0.0.1` / `port: 4173` baked into
# the config so the container can be reached from the host.
CMD ["pnpm", "preview", "--host", "0.0.0.0", "--port", "5173"]
