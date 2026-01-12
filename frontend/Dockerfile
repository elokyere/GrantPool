FROM node:18-alpine as build

WORKDIR /app

# Accept VITE environment variables as build arguments
# These are needed at build time for Vite to embed them in the bundle
ARG VITE_API_URL
ARG VITE_PAYSTACK_PUBLIC_KEY
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_PAYSTACK_PUBLIC_KEY=$VITE_PAYSTACK_PUBLIC_KEY

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ .
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
