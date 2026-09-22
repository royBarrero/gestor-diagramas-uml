FROM node:24-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite resuelve import.meta.env en BUILD-TIME, no en runtime: si cambiás la
# URL del backend hay que volver a buildear esta imagen con un nuevo
# --build-arg VITE_API_URL, no alcanza con cambiar una variable del contenedor.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
