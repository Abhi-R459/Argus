# Build stage
FROM node:20-slim AS build

WORKDIR /app

ARG VITE_CLERK_PUBLISHABLE_KEY
ARG VITE_API_URL=/api
# This Clerk key is designed to be public and is embedded in browser assets.
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}
ENV VITE_API_URL=${VITE_API_URL}

COPY package*.json ./
RUN npm ci

COPY . .
RUN test -n "$VITE_CLERK_PUBLISHABLE_KEY"
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
