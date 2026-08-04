# syntax=docker/dockerfile:1

FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1

# `NEXT_PUBLIC_*` values are inlined into the client bundle at BUILD time, so
# they have to be present here — passing them to the runtime container has no
# effect on an already-built bundle.
#
# This was the bug that would have broken every deployment: the build received
# nothing, `client.ts` fell back to its `http://localhost:8000` default, and the
# published site told each visitor's browser to call *its own* machine on port
# 8000. The site would load and every request would fail.
#
# Empty = same origin, which is the compose topology: the reverse proxy serves
# the app and proxies /api/ to the backend. Override only when the API lives on a
# different host.
ARG NEXT_PUBLIC_API_BASE_URL=""
ARG NEXT_PUBLIC_SITE_URL=""
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL

RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN useradd --create-home nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
