---
id: config-reference
title: Configuration Reference
---

Kodiak's configuration file is a TOML file and should be placed at `.kodiak.toml` (repository root) or `.github/.kodiak.toml`.

For Kodiak to run on a pull request:

1. Kodiak must be installed on the repository.
2. A configuration file must exist in the repository.
3. GitHub branch protection must exist on the target branch.

## fields

### `version`
- __type:__ `number`
- __required:__ `true`

`1` is the only valid setting for this field.

```toml
version = 1
```

### `merge.automerge_label`
- __type:__ `string`
- __default:__ `"automerge"`

Label to enable Kodiak to merge a PR.

By default, Kodiak will only act on PRs that have this label. You can disable this requirement via `merge.require_automerge_label`.

```toml
merge.automerge_label = "🚀 merge it!"
```

### `merge.require_automerge_label`
- __type:__ `boolean`
- __default:__ `true`

Require that the automerge label (`merge.automerge_label`) be set for Kodiak to merge a PR.

When disabled, Kodiak will immediately attempt to merge any PR that passes all GitHub branch protection requirements.

### `merge.blacklist_title_regex`
- __type:__ `string`
- __default:__ `"^WIP:.*"`
- __options:__ Regex pattern or `""`

If this title regex matches, Kodiak will not merge the PR. This is useful
to prevent merging work in progress PRs.

Setting `merge.blacklist_title_regex = ""` disables this option.


#### example
```
merge.blacklist_title_regex = ".*DONT\s*MERGE.*"
```

### `merge.blacklist_labels`
- __type:__ `string[]`
- __default:__ `[]`
- __options:__ List of label names

If these labels are set Kodiak will not merge the PR.

#### example
```
merge.blacklist_labels = ["wip"]
```

### `merge.method`
- __type:__ `string`
- __default:__ `"merge"`
- __options:__ `"merge"`, `"squash"`, `"rebase"`

Choose merge method for Kodiak to use.

Kodiak will report a configuration error if the selected merge method is disabled for a repository.

### `merge.delete_branch_on_merge`
- __type:__ `boolean`
- __default:__ `false`

Once a PR is merged, delete the branch.

### `merge.block_on_reviews_requested`
- __type:__ `boolean`
- __default:__ `false`

> __DEPRECATED__
> 
> Due to limitations with the GitHub API this feature is fundamentally broken and cannot be fixed. Prefer the GitHub branch protection "required reviewers" setting instead.
>
> When a user leaves a comment on a PR, GitHub counts that as satisfying a review request, so the PR will be allowed to merge, even though a reviewer was likely just starting a review. 
>
> See this issue comment for more information about why this feature is not fixable: https://github.com/chdsbd/kodiak/issues/153#issuecomment-523057332.

If you request review from a user, don't merge until that user provides a review, even if the PR is passing all checks.

### `merge.notify_on_conflict`
- __type:__ `boolean`
- __default:__ `true`

> Only applies when `merge.require_automerge_label` is enabled.

If there is a merge conflict, make a comment on the PR and remove the
automerge label.

### `merge.optimistic_updates`
- __type:__ `boolean`
- __default:__ `true`

Don't wait for in-progress status checks on a PR to finish before updating the branch.

### `merge.dont_wait_on_status_checks`
- __type:__ `string[]`
- __default:__ `[]`
- __options:__ List of check names

Don't wait for specified status checks when merging a PR. If a configured status check is incomplete when a PR is being merged, Kodiak will skip the PR.

Use this option for status checks that run indefinitely, like deploy jobs or the WIP GitHub App.

#### example

```
merge.dont_wait_on_status_checks = ["ci/circleci: deploy", "WIP"]
```

### `merge.update_branch_immediately`
- __type:__ `boolean`
- __default:__ `false`

> DEPRECATED: See [`update.always`](#updatealways), which will deliver better behavior in most use cases.

Update PRs that are passing all branch requirements or are waiting for status checks to pass.

### `merge.prioritize_ready_to_merge`
- __type:__ `boolean`
- __default:__ `false`

If a PR is passing all checks and is able to be merged, merge it without
placing it in the merge queue.

This option adds some unfairness where PRs waiting in the queue the longest are not served first.

### `merge.do_not_merge`
- __type:__ `boolean`
- __default:__ `false`

Never merge a PR. This option can be used with `update.always` to automatically update a PR without merging.

### `merge.message.title`
- __type:__ `enum`
- __default:__ `"github_default"`
- __options:__ `"github_default"`, `"pull_request_title"`

By default (`"github_default"`), GitHub uses the title of a PR's first commit for the merge commit title. `"pull_request_title"` uses the PR title for the merge commit.

### `merge.message.body`
- __type:__ `enum`
- __default:__ `"github_default"`
- __options:__ `"github_default"`, `"pull_request_body"`, `"empty"`

By default (`"github_default"`), GitHub combines the titles of a PR's commits to create the body
text of a merge commit. `"pull_request_body"` uses the content of the PR to generate
the body content while `"empty"` simply gives an empty string.

### `merge.message.include_pr_number`
- __type:__ `boolean`
- __default:__ `true`

> Only applies when `merge.message.title` does not equal `"github_default"`.

Add the PR number to the merge commit title.

This setting replicates GitHub's behavior of automatically adding the PR number to the title of merges created through the UI.

### `merge.message.body_type`
- __type:__ `enum`
- __default:__ `"markdown"`
- __options:__ `"markdown"`, `"plain_text"`, `"html"`

> Only applies when `merge.message.body = "pull_request_body"`.

Control the text used in the merge commit. The GitHub default is markdown, but `"plain_text"` or `"html"` can be used to render the pull request body as text or HTML.

### `merge.message.strip_html_comments`
- __type:__ `boolean`
- __default:__ `false`

> Only applies when `merge.message.body_type = "markdown"`.

Strip HTML comments (`<!-- some HTML comment -->`) from merge commit body.

This setting is useful for stripping HTML comments created by PR templates.

### `update.always`
- __type:__ `boolean`
- __default:__ `false`

> Kodiak will only update PRs with the `merge.automerge_label` label or if `update.require_automerge_label = false`.

Update a PR whenever out of date with the base branch. The PR will be
updated regardless of failing merge requirements (e.g. failing status
checks, missing reviews, blacklist labels).

When enabled, _Kodiak will not be able to efficiently update PRs._ If you have multiple PRs against a target like `master`, any time a commit
is added to `master` _all_ of those PRs against `master` will update. For `N` PRs against a target you will potentially see `N(N-1)/2` updates. If
this configuration option was disabled you would only see `N-1` updates.


### `update.require_automerge_label`
- __type:__ `boolean`
- __default:__ `true`

> This option only applies when `update.always = true`.

When `true`, Kodiak will only update PRs that have an automerge label (configured via [`merge.automerge_label`](#mergeautomerge_label)).

When `false`, Kodiak will update any PR.


## full examples

### minimal

```toml
version = 1
```

### all options
Below is a Kodiak config with all options set and commented.

```toml
# .kodiak.toml
# version is the only required setting in a kodiak config.
# it must be set to 1
version = 1

[merge]
# label to use to enable Kodiak to merge a PR
automerge_label = "automerge" # default: "automerge"

# require that the automerge label be set for Kodiak to merge a PR. if you
# disable this Kodiak will immediately attempt to merge every PR you create
require_automerge_label = true

# if this title regex matches, Kodiak will not merge the PR. this is useful
# to prevent merging work in progress PRs
blacklist_title_regex = "" # default: "^WIP:.*", options: "" (disables regex), a regex string (e.g. ".*DONT\s*MERGE.*")

# if these labels are set Kodiak will not merge the PR
blacklist_labels = [] # default: [], options: list of label names (e.g. ["wip"])

# choose a merge method. If the configured merge method is disabled for a
# repository, Kodiak will report an error in a status message.
method = "merge" # default: "merge", options: "merge", "squash", "rebase"

# once a PR is merged, delete the branch
delete_branch_on_merge = false # default: false

# DEPRECATED
# Due to limitations with the GitHub API this feature is
# fundamentally broken and cannot be fixed. Please use the GitHub branch
# protection "required reviewers" setting instead. See this issue/comment
# for more information about why this feature is not fixable
# see: https://github.com/chdsbd/kodiak/issues/153#issuecomment-523057332.
#
# if you request review from a user, don't merge until that user provides a
# review, even if the PR is passing all checks
block_on_reviews_requested = false # default: false

# if there is a merge conflict, make a comment on the PR and remove the
# automerge label. this is disabled when require_automerge_label is enabled
notify_on_conflict = true # default: true

# if there are running status checks on a PR when it's up for merge, don't
# wait for those to finish before updating the branch
optimistic_updates = false # default: true

# use this for status checks that run indefinitely, like deploy jobs or the
# WIP GitHub App
dont_wait_on_status_checks = [] # default: [], options: list of check names (e.g. ["ci/circleci: lint_api"])

# DEPRECATED
# This setting only updates PRs that are passing passing all requirements or
# waiting for status checks to pass. `update.always = True` will deliver
# better behavior in many use cases.
#
# immediately update a PR whenever the target updates. If enabled, Kodiak will
# not be able to efficiently update PRs. Any time the target of a PR updates,
# the PR will update.
#
# If you have multiple PRs against a target like "master", any time a commit
# is added to "master" _all_ of those PRs against "master" will update.
#
# For N PRs against a target you will potentially see N(N-1)/2 updates. If
# this configuration option was disabled you would only see N-1 updates.
#
# If you have continuous integration (CI) run on every commit, enabling this
# configuration option will likely increase your CI costs if you pay per
# minute. If you pay per build host, this will likely increase job queueing.
update_branch_immediately = false # default: false

# if a PR is passing all checks and is able to be merged, merge it without
# placing it in the queue. This will introduce some unfairness where those
# waiting in the queue the longest will not be served first.
prioritize_ready_to_merge = false # default: false

# never merge a PR. This can be used with merge.update_branch_immediately to
# automatically update a PR without merging.
do_not_merge = false # default: false

[merge.message]
# by default, github uses the first commit title for the PR of a merge.
# "pull_request_title" uses the PR title.
title = "github_default" # default: "github_default", options: "github_default", "pull_request_title"

# by default, GitHub combines the titles of a PR's commits to create the body
# text of a merge. "pull_request_body" uses the content of the PR to generate
# the body content while "empty" simply gives an empty string.
body = "github_default" # default: "github_default", options: "github_default", "pull_request_body", "empty"

# GitHub adds the PR number to the title of merges created through the UI.
# This setting replicates that feature.
include_pr_number = true # default: true

# markdown is the normal format for GitHub merges
body_type = "markdown" # default: "markdown", options: "plain_text", "markdown", "html"

# useful for stripping HTML comments created by PR templates when the `markdown` `body_type` is used.
strip_html_comments = false # default: false

[update]
# update PR whenever out of date with the base branch. PR will be
# updated regardless of failing requirements for merge (e.g. failing status
# checks, missing reviews, blacklist labels).
#
# Kodiak will only update the PR if the automerge label is enabled or
# `update.require_automerge_label` is false.
always = false # default: false
# enable updating PRs missing automerge label. automerge label is defined by `merge.automerge_label`.
require_automerge_label = true # default: true
```

## other resources

See [`kodiak/test/fixtures/config`](https://github.com/chdsbd/kodiak/tree/master/kodiak/test/fixtures/config) for more examples and [`kodiak/config.py`](https://github.com/chdsbd/kodiak/blob/master/kodiak/config.py) for the Python models.
