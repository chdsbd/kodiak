FROM node:12.4.0 as builder

RUN mkdir -p /var/app

WORKDIR /var/app

COPY package.json yarn.lock /var/app/

RUN yarn install

COPY . /var/app

RUN node /var/app/scripts/build.js


FROM nginx:1.13.8-alpine@sha256:c8ff0187cc75e1f5002c7ca9841cb191d33c4080f38140b9d6f07902ababbe66
RUN mkdir -p /var/app/build
COPY --from=builder /var/app/build /var/app/build
COPY general_headers.conf /etc/nginx/headers.d/
COPY nginx.conf /etc/nginx/conf.d/
RUN rm /etc/nginx/conf.d/default.conf
WORKDIR /var/app
