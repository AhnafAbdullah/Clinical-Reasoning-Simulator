# Build context is the repo root so the @crs/sdk package source is available.
# The monorepo layout is mirrored under /app so the "../../packages/sdk" path
# alias resolves during the Next build (experimental.externalDir).
FROM node:22-alpine AS deps
WORKDIR /app/apps/frontend
COPY apps/frontend/package.json apps/frontend/package-lock.json* ./
RUN npm ci || npm install

FROM node:22-alpine AS build
WORKDIR /app/apps/frontend
COPY --from=deps /app/apps/frontend/node_modules ./node_modules
COPY apps/frontend /app/apps/frontend
COPY packages/sdk /app/packages/sdk
# Same-origin in the container (served behind nginx); "/" -> empty base -> relative URLs.
ARG NEXT_PUBLIC_API_BASE=/
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app/apps/frontend
ENV NODE_ENV=production
COPY --from=build /app/apps/frontend/.next ./.next
COPY --from=build /app/apps/frontend/node_modules ./node_modules
COPY --from=build /app/apps/frontend/package.json ./package.json
EXPOSE 3000
CMD ["npm", "start"]
