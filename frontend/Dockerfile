FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL
ARG VITE_SITE_URL
ARG VITE_APP_ENV=production
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_SITE_URL=${VITE_SITE_URL} \
    VITE_APP_ENV=${VITE_APP_ENV}
RUN npm run build

FROM node:22-bookworm-slim AS runtime
ENV NODE_ENV=production \
    PORT=3000
WORKDIR /app
RUN groupadd --system mayabu && useradd --system --gid mayabu mayabu
COPY --from=build /app/package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build --chown=mayabu:mayabu /app/build ./build
USER mayabu
EXPOSE 3000
CMD ["npm", "run", "start"]
