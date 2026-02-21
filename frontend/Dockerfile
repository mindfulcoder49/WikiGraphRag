FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Vite dev server – reads VITE_* env vars at serve time
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
