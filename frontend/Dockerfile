# Use Node 18
FROM node:18-slim

# Set working directory
WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the frontend source
COPY . .

# Expose Vite's default port
EXPOSE 5173

# Run Vite in dev mode
# The "-- --host" flag is critical so Docker can map the port
CMD ["npm", "run", "dev", "--", "--host"]