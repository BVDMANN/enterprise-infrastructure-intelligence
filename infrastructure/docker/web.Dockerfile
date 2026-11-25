FROM node:20-alpine AS deps
WORKDIR /app
# Contexte de build = racine du dépôt (docker-compose.yml) : chemins relatifs à la racine.
# npm ci (et non npm install) : installation reproductible à partir du
# package-lock.json — le lockfile est donc obligatoire (sans glob *).
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web/. ./
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.mjs ./next.config.mjs
EXPOSE 3000
CMD ["npm", "run", "start"]
