# Kodiak GitHub App

The Kodiak GitHub App receives webhook requests from GitHub and acts on GitHub pull requests.

## Dev

The following shows how to run commands for testing and development. For information on creating a GitHub App for testing, please see <https://kodiakhq.com/docs/contributing>.

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

# start development webserver. The Redis server specified in `.env` must be
# running
s/dev-ingest --reload
# in another terminal start the workers
s/dev-workers
```

### Tunnelmole
[Tunnelmole](https://github.com/robbie-cahill/tunnelmole-client) is an open source tunnelling tool that will create a Public URL that forwards traffic to your local machine through a secure tunnel. Here is how to set it up:

First, you need to install Tunnelmole. For Linux, Mac and Windows Subsystem for Linux, copy and paste the following into a terminal:
```
curl -O https://tunnelmole.com/sh/install.sh && sudo bash install.sh
```

*For Windows without WSL, [Download tmole.exe](https://tunnelmole.com/downloads/tmole.exe) and put it somewhere in your [PATH](https://www.wikihow.com/Change-the-PATH-Environment-Variable-on-Windows).*

Then run `tmole 3000` in a separate terminal and configure your GitHub app settings to route to the Tunnelmole URL.
```shell
tmole 3000
http://bvdo5f-ip-49-183-170-144.tunnelmole.net is forwarding to localhost:3000
https://bvdo5f-ip-49-183-170-144.tunnelmole.net is forwarding to localhost:3000
```

### ngrok
[ngrok](https://ngrok.com) is a popular closed source tunnelling tool. You can also use it for this project. Start ngrok in a separate terminal and configure your GitHub app settings to route to the ngrok URL.
```shell
ngrok http 3000
```

If you made any changes concerning the config, run the following command to update the schema:

```shell
poetry run kodiak gen-conf-json-schema > kodiak/test/fixtures/config/config-schema.json
```
