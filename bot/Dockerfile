FROM python:3.7-slim@sha256:f5f9129d24b29d1964639dac62e5e813c50aa9fe8d9ca83fd6f31d3d5e700f1a

RUN apt update && \
  apt-get install --no-install-recommends -y supervisor git && \
  python3 -m pip install --no-cache-dir poetry===1.1.8 && \
  poetry config virtualenvs.in-project true && \
  groupadd kodiak && \
  useradd --uid 1000 --gid kodiak kodiak && \
  mkdir -p /var/app && \
  chown -R kodiak:kodiak /var/app

WORKDIR /var/app

COPY --chown=kodiak pyproject.toml poetry.lock .

# install deps
RUN poetry install

COPY --chown=kodiak . .

USER kodiak

CMD ["/usr/bin/supervisord"]
