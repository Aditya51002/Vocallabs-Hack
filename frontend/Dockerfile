# Stage 1: Build production assets
FROM node:20-alpine AS build-stage

WORKDIR /app

ARG VITE_API_BASE_URL=
ARG VITE_API_KEY=
ARG VITE_DEMO_MODE=true

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_API_KEY=$VITE_API_KEY
ENV VITE_DEMO_MODE=$VITE_DEMO_MODE

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve static assets with Nginx
FROM nginx:alpine AS production-stage

COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
