FROM node:12.4.0 as builder

RUN mkdir -p /var/app

WORKDIR /var/app

COPY package.json yarn.lock /var/app/

RUN yarn install

COPY . /var/app

RUN node /var/app/scripts/build.js


FROM node:12.4.0
RUN mkdir -p /var/app/build
RUN yarn add --no-lockfile serve
COPY --from=builder /var/app/build /var/app/build
WORKDIR /var/app

CMD serve --single --no-clipboard --listen tcp://0.0.0.0:4444 /var/app/build
