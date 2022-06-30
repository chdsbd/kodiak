FROM python:3.10.5@sha256:850b7f7626e5ca9822cc9ac36ce1f712930d8c87eb31b5937dba4037fe204034

RUN set -ex && mkdir -p /var/app

RUN apt-get update && apt-get install -y supervisor

RUN mkdir -p /var/log/supervisor

RUN python3 -m pip install poetry===1.1.13

RUN poetry config virtualenvs.in-project true

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /var/app

COPY pyproject.toml poetry.lock /var/app/

# install deps
RUN poetry install

COPY . /var/app

# workaround for: https://github.com/sdispater/poetry/issues/1123
RUN rm -rf /var/app/pip-wheel-metadata/

# install cli
RUN poetry install

CMD ["/usr/bin/supervisord"]
