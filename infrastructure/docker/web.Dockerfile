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
# Utilisateur non-root (audit sécurité 25/11) : le serveur ne tourne jamais
# en root ; l'utilisateur `node` (uid 1000) existe dans l'image de base.
COPY --from=builder --chown=node:node /app/.next ./.next
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/package.json ./package.json
COPY --from=builder --chown=node:node /app/next.config.mjs ./next.config.mjs
EXPOSE 3000
USER node
CMD ["npm", "run", "start"]
