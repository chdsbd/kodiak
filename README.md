# kodiak [![CircleCI](https://circleci.com/gh/chdsbd/kodiak.svg?style=svg&circle-token=4879604a0cca6fa815c4d22936350f5bdf455905)](https://circleci.com/gh/chdsbd/kodiak)

A bot to automatically merge GitHub PRs

## Why?

Enabling the "require branches be up to date" feature on GitHub repositories is
great because, when coupled with CI, master will always be green.

However, as the number of collaborators on a GitHub repo increases, a
repetitive behavior emerges where contributors are updating their branches
manually hoping to merge their branch before others.

Kodiak fixes this wasteful behavior by automatically updating
and merging branches. Contributors simply mark their
PR with a configurable label that indicates the PR is ready to merge and Kodiak
will do the rest, handling branch updates and merging, using the _minimal_
number of branch updates to land the code on master.

This means that contributors don't have to worry about keeping their PRs up
to date with the latest on master or even pressing the merge button. Kodiak
does this for them.

### Minimal updates
Kodiak ensures that branches are always updated before merging, but does so
efficiently by only updating a PR when it's being prepared to merge. This
prevents spurious CI jobs from being created as they would if all PRs were
updated when their targets were updated.

## How does it work?

1. Kodiak receives a webhook event from GitHub and adds it to a queue for processing
2. Kodiak processes these webhook events and extracts the associated pull
   requests for further processing
3. The following pull request information is requested:

   - the `.kodiak.toml` configuration file is fetched from default repository branch
   - branch protection rules are found for the target branch
   - reviews, status checks and labels are located for the pull request

4. Pull request mergeability is evaluated using PR data

   - configuration whitelists/blacklists for labels are checked
   - configuration merge method is checked against enabled repo merge methods
   - pull request merge states are evaluated
   - the branch is updated if necessary and this process restarts
   - branch protection rules are evaluated

5. The pull request is merged 🎉

## Setup

**Warning:** Kodiak requires branch protection to be enabled to function,
Kodiak won't merge PRs if branch protection is disabled.

1. Create a `.kodiak.toml` file in the root of your repository on the default
   branch with the following contents:

   ```toml
   # version is the only required field
   version = 1
   
   # the following default settings can be omitted
   block_on_reviews_requested = false
   [merge]
   method = "merge" # or "squash", "rebase"
   whitelist = ["automerge"] # labels to trigger bot 
   blacklist = [] # labels to block bot
   ```

2. Setup Kodiak

   Kodiak can be run either through the GitHub App or by self hosting.
   In order to merge pull requests (PRs) Kodiak needs read write access to
   PRs as well as additional permissions to the repository. This means that Kodiak
   can see **all** the code in your repository.

   The current [permissions](https://developer.github.com/v3/apps/permissions/) that are required to use the GitHub App are:

   | name                       | level       | reason                          |
   | -------------------------- | ----------- | ------------------------------- |
   | repository administration  | read-only   | branch protection info          |
   | checks                     | read-only   | PR mergeability                 |
   | repository contents        | read/write  | update PRs, read configuration  |
   | pull requests              | read/write  | PR mergeability, merge PR       |
   | commit statuses            | read-only   | PR mergeability                 |

   **Via GitHub App**

   Follow the steps at: <https://github.com/apps/kodiakhq>

   **Self Hosted**

   You can run the `Dockerfile` provided in the repo on your platform of choice
   or you could use the Heroku app configuration below:

   ```shell
   # a unique name for the heroku app
   export APP_NAME='kodiak-prod'

   # create app with container stack
   heroku apps:create $APP_NAME
   heroku stack:set container -a $APP_NAME

   # login to registry
   heroku container:login

   # download latest release from docker hub and tag for push to heroku
   docker pull cdignam/kodiak
   docker tag cdignam/kodiak registry.heroku.com/$APP_NAME/web

   # push tagged image to Heroku
   docker push registry.heroku.com/$APP_NAME/web

   # create gihub app at https://developer.github.com/apps/building-github-apps/creating-a-github-app/
   # The APP_ID and PRIVATE_KEY are needed to run the app. You must also set a SECRET_KEY to pass to the app.

   # configure app environment (this can also be done through the Heroku web ui)
   heroku config:set -a $APP_NAME GITHUB_APP_ID='<GH_APP_ID>' SECRET_KEY='<GH_APP_SECRET>' GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nsome/private/key\nbits\n-----END RSA PRIVATE KEY-----\n"

   # release app
   heroku container:release web -a $APP_NAME
   ```

## Prior Art

| Name                                                                  | Works With GitHub Integrations | Auto Merging | Auto Update Branches | Update Branches Efficiently | Open Source | Practice [Dogfooding](https://en.wikipedia.org/wiki/Eating_your_own_dog_food) | Language   |
| --------------------------------------------------------------------- | ------------------------------ | ------------ | -------------------- | --------------------------- | ----------- | ----------------------------------------------------------------------------- | ---------- |
| [Kodiak](https://github.com/chdsbd/kodiak)                            | ✅                             | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Python     |
| [Bors](https://github.com/graydon/bors)                               | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| [Highfive](https://github.com/servo/highfive)                         | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Python     |
| [Homu](https://github.com/barosl/homu)                                | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| [Gullintanni](https://github.com/gullintanni/gullintanni)             | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Elixir     |
| [Popuko](https://github.com/voyagegroup/popuko)                       | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Go         |
| [Bors-ng](https://bors.tech)                                          | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Elixir     |
| [Marge-bot](https://github.com/smarkets/marge-bot)                    | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| [Bulldozer](https://github.com/palantir/bulldozer)                    | ✅                             | ✅           | ✅                   | ❌                          | ✅          | ❌                                                                            | Go         |
| [Autorebase](https://github.com/tibdex/autorebase)                    | ✅                             | ✅           | ✅                   | ❌                          | ✅          | ✅                                                                            | TypeScript |
| [Auto Merge](https://github.com/SvanBoxel/auto-merge)                 | ❌                             | ✅           | ❌                   | ❌                          | ✅          | ❌                                                                            | JavaScript |
| [Always Be Closing](https://github.com/marketplace/always-be-closing) | 🤷‍                            | ✅           | ✅                   | 🤷‍                         | ❌          | 🤷‍                                                                           | 🤷‍        |

Works With GitHub Integration:

- doesn't require changing CI
- follows commit statuses & GitHub checks
- works with PRs — some services create separate test branches for merging
  that circumvent the simpler PR workflow

Auto Merging:

- automatically merges PR once up to date with master and all required statuses and checks pass.

Auto Update Branches:

- ensures branches are automatically updated to the latest version of master

Update Branches Efficiently:

- a improvement of Auto Update Branches where branches are only updated when necessary, as opposed to updating all branches any time their target branch (usually master) updates.

## Development

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
