FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV API_PROXY_URL=http://api:8000
RUN cp node_modules/pdfjs-dist/build/pdf.worker.min.mjs public/pdf.worker.min.mjs
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
