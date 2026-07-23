FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.ts tsconfig.json ./
COPY public ./public
COPY src ./src
ARG VITE_API_BASE=https://paper-api-production-8e2c.up.railway.app
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM node:22-alpine
WORKDIR /app
RUN npm i -g serve@14
COPY --from=build /app/dist ./dist
ENV PORT=3000
EXPOSE 3000
CMD ["sh", "-c", "serve -s dist -l ${PORT}"]
