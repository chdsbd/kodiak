---
id: contributing
title: Contributing
sidebar_label: Contributing
---


## Dev Scripts




```shell
# install dependencies
poetry install

# start dev server
poetry run uvicorn kodiak.main:app --reload

# type check and lint
s/lint

# format code
s/fmt

# test code
s/test
```

## Testing on a Live Repo

Due to the nature of a GitHub bot, testing relies largely on mocks.
For testing to see if a given feature will work it is recommended to create a
GitHub App and a testing GitHub repo.

### Create a Test GitHub App

1.  Configure the app as described in the [heroku setup instructions](self-hosting#heroku) above.
1.  Setup the webhook URL

    You probably want to use something like [`ngrok`](https://ngrok.com) for
    this. If you do use `ngrok`, you may also want to signup for an account
    via the [`ngrok` website](https://ngrok.com) so that your `ngrok` url
    for the webhook doesn't expire.

    With `ngrok` installed, we can run it with the Kodiak's dev port.

    ```
    ngrok http 8000
    ```

    Now we can copy the **Forwarding** url into the GitHub app form.
    Don't forget to append the path: `/api/github/hook` and make sure to copy the
    `https`.

    Then hit create.

1.  Now install the GitHub App

    Use the **Install** option in the sidebar for the GitHub App.

    You will want to create a testing GitHub repo with a Kodiak config file
    with the `app_id` option set to your GitHub app's id.

    You will also need to setup branch protection in `settings > branches`.
    Make sure the **Branch name pattern** matches `master`. Then check
    **Require status checks to pass before merging** and the sub-option
    **Require branches to be up to date before merging**.

    This allows for the production version of Kodiak to be setup on all repos,
    while allowing the testing version to run on the configured repo. If the
    production version of Kodiak finds a non-matching app_id, it will ignore
    the repository, leaving your local version to handle it.

1.  Setup secrets

    After creating we need to add a **Webhook secret**. The field is labeled **(optional)** but it is necessary for Kodiak to work.

    You can fill it in with a UUID -- be sure to hold onto it, we'll need it
    later.

    Now you need to generate a private key via the generate private key button under the **Private keys** section.

    Move the secret key to directory where you are running Kodiak.

### Run the Dev Server

Note: you need to replace the `$SHARE_SECRET`, `$GH_PRIVATE_KEY_PATH` and `$GITHUB_APP_ID` with your own values.

The GitHub App ID can be found in the **About** sections of your GitHub App.

```
SECRET_KEY=$SHARED_SECRET GITHUB_PRIVATE_KEY_PATH=$GH_PRIVATE_KEY_PATH GITHUB_APP_ID=$GITHUB_APP_ID poetry run uvicorn kodiak.main:app
```

You can create a test PR via the following shell function.

Note: you need to have [`hub`](https://github.com/github/hub) installed.

```sh
create_mock_pr() {
  git pull &&
  uuidgen >> "$(uuidgen).txt" &&
  git checkout -b $(uuidgen) &&
  git add . &&
  git commit -am $(uuidgen) &&
  git push --set-upstream origin $(git symbolic-ref --short HEAD) &&
  hub pull-request -l automerge -m "$(uuidgen)" &&
  git checkout master
}
```

### Integration Testing with Docker

The following steps will set your test-app up with little effort:

- Copy the private key that you generated on github for the app to your repository root and name it `kodiaktest.private-key.pem`,
- Create a file `.env` that sets the following environment variables: `GITHUB_APP_ID`, `SECRET_KEY`.
- By using the `docker-compose.yml` file in conjunction with the `Dockerfile` in the repository
  doing integration tests with WIP code is as easy as running these commands from the root of the repository:
  ```bash
  docker-compose build
  docker-compose up
  ```
- In a separate terminal you have to open up a tunnel to make your machine reachable from outside your local network:
  ```bash
  ngrok http 3000
  ```
- Copy the address from the `ngrok` output to the webhook settings of your github app and it should work.

## Releasing a New Version

```bash
GIT_SHA='62fcc1870b609f43b95de41b8be41a2858eb56bd'
APP_NAME='kodiak-prod'
docker pull cdignam/kodiak:$GIT_SHA
docker tag cdignam/kodiak:$GIT_SHA registry.heroku.com/$APP_NAME/web
docker push registry.heroku.com/$APP_NAME/web
heroku container:release -a $APP_NAME web
```
