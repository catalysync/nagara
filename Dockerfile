# ─── Build stage ───
FROM node:22-bookworm-slim AS build
WORKDIR /app

ARG KEYSTATIC_GITHUB_CLIENT_ID
ARG KEYSTATIC_GITHUB_CLIENT_SECRET
ARG KEYSTATIC_SECRET
ARG NEXT_PUBLIC_KEYSTATIC_GITHUB_APP_SLUG
ENV KEYSTATIC_GITHUB_CLIENT_ID=$KEYSTATIC_GITHUB_CLIENT_ID \
    KEYSTATIC_GITHUB_CLIENT_SECRET=$KEYSTATIC_GITHUB_CLIENT_SECRET \
    KEYSTATIC_SECRET=$KEYSTATIC_SECRET \
    NEXT_PUBLIC_KEYSTATIC_GITHUB_APP_SLUG=$NEXT_PUBLIC_KEYSTATIC_GITHUB_APP_SLUG \
    NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# ─── Runtime stage ───
FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0

COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
COPY --from=build /app/content ./content

EXPOSE 3000
CMD ["node", "server.js"]
