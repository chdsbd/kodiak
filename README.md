# kodiak
A bot to automatically merge GitHub PRs

## Development

```shell
# install dependencies
poetry install

# start dev server
poetry run uvicorn kodiak.main:app --reload

# format code
poetry run black .
# type check code
poetry run mypy .
# test code
poetry run pytest
```
