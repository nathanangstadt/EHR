FROM node:20-alpine

WORKDIR /web

COPY package.json package-lock.json* /web/
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . /web

EXPOSE 5173
CMD ["npm","run","dev","--","--host","0.0.0.0","--port","5173"]

