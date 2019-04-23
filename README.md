# kodiak [![CircleCI](https://circleci.com/gh/chdsbd/kodiak.svg?style=svg&circle-token=4879604a0cca6fa815c4d22936350f5bdf455905)](https://circleci.com/gh/chdsbd/kodiak)
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
