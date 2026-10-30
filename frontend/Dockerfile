# Contexto de construcción: frontend/ de la versión que se desplegará.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV VITE_API_URL=/api
RUN npm run build

FROM nginx:stable-alpine
ENV NGINX_ENVSUBST_FILTER=GATEWAY_UPSTREAM
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
