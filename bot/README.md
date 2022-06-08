# Kodiak GitHub App

The Kodiak GitHub App receives webhook requests from GitHub and acts on GitHub pull requests.

## Dev

The follow shows how to run commands for testing and development. For information on creating an GitHub App for testing, please see <https://kodiakhq.com/docs/contributing>.

```shell
# bot/

# install dependencies
poetry config virtualenvs.in-project true
poetry install

# format and lint using black, isort, mypy, flake8, pylint
s/lint

# run tests using pytest
# pytest flags can be passed like `s/test -s --pdb`
s/test

# create a .env file for local testing by copying the example and adding your
# settings
cp example.env .env

# in a seperate terminal, start ngrok and configure your GitHub app settings to
# route to the ngrok url
ngrok http 3000

# start development webserver. The Redis server specified in `.env` must be
# running
s/dev --reload
```
