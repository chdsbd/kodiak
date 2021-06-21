FROM python:3.7@sha256:6eaf19442c358afc24834a6b17a3728a45c129de7703d8583392a138ecbdb092

RUN set -ex && mkdir -p /var/app

RUN python3 -m pip install poetry===0.12.11

RUN poetry config settings.virtualenvs.in-project true

WORKDIR /var/app

COPY pyproject.toml poetry.lock /var/app/

# install deps
RUN poetry install

COPY . /var/app

# workaround for: https://github.com/sdispater/poetry/issues/1123
RUN rm -rf /var/app/pip-wheel-metadata/

# install cli
RUN poetry install

CMD ["/var/app/.venv/bin/python", "-m", "kodiak.main"]
