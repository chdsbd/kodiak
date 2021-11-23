FROM python:3.8@sha256:cb03bb011e5dca2d0d48f842187fd789062e234e829e96f417542e7ffcaf41cf

RUN set -ex && mkdir -p /var/app

RUN apt-get update && apt-get install -y supervisor

RUN mkdir -p /var/log/supervisor

RUN python3 -m pip install poetry===1.1.8

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
