---
id: recipes
title: Recipes
sidebar_label: Recipes
---

## Sync with Master

A config to keep every PR up-to-date with master. Whenever the target branch of a PR updates, the PR will update.

```toml
# .kodiak.toml
version = 1

[update]
always = true # default: false
require_automerge_label = false # default: true
```

## Automated dependency updates with Dependabot

While Dependabot can [automerge dependency updates](https://dependabot.com/docs/config-file/#automerged_updates), this functionality will not work when "Required approving reviews" is configured via GitHub Branch Protection because the PR needs an approving review.

Kodiak can help us here by automatically adding an approval to all Dependabot PRs, which will allow Dependabot PRs to be automatically merged without human intervention.

> **NOTE:** Remove the `[bot]` suffix from GitHub Bot usernames. Instead of `"dependabot-preview[bot]"` use `"dependabot-preview"`.

```
# .kodiak.toml
version = 1

[approve]
# note: remove the "[bot]" suffix from GitHub Bot usernames.
# Instead of "dependabot-preview[bot]" use "dependabot-preview".
auto_approve_usernames = ["dependabot-preview"]
```

## The Favourite

This is the config use by the [Kodiak repository](https://github.com/chdsbd/kodiak/blob/master/.kodiak.toml).

We squash all PR commits and use the PR title and body for the merge commit. Once merged, we delete the PR's branch.

```
# .kodiak.toml
version = 1

[merge]
method = "squash" # default: "merge"
delete_branch_on_merge = true # default: false

[merge.message]
title = "pull_request_title" # default: "github_default"
body = "pull_request_body" # default: "github_default"
```

## Efficiency and Speed

This config prioritizes resource conservation by only updating a PR when it is ready to merge and favors speed by immediately merging any PR that is ready to merge.

Disabling `merge.prioritize_ready_to_merge` would improve fairness by ensuring a first-come-first-served policy for the merge queue.

```toml
# .kodiak.toml
version = 1

[merge]
# don't wait for running status checks when a PR needs update.
optimistic_updates = true # default: true

# if a PR is ready, merge it, don't place it in the merge queue.
prioritize_ready_to_merge = true # default: false
```

## Better Merge Messages

GitHub's default merge commits are _ugly_. GitHub uses the title of the first commit for the merge title and combines all of the other commit titles and bodies for the merge body.

Using the pull request title and body give a cleaner, more useful merge commit.

This config uses the PR title and body, along with the PR number to create a nice merge commit. Additionally we strip HTML comments from the PR markdown body which can be useful if your GitHub repo has PR templates.

```toml
# .kodiak.toml
version = 1

[merge.message]
# use title of PR for merge commit.
title = "pull_request_title" # default: "github_default"

# use body of PR for merge commit.
body = "pull_request_body" # default: "github_default"

# add the PR number to the merge commit title, like GitHub.
include_pr_number = true # default: true

# use the default markdown content of the PR for the merge commit.
body_type = "markdown" # default: "markdown"

# remove html comments to auto remove PR templates.
strip_html_comments = true # default: false
```
