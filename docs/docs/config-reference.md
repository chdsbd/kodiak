---
id: config-reference
title: Configuration Reference
---

Kodiak's configuration file is a TOML file and should be placed at `.kodiak.toml` (repository root) or `.github/.kodiak.toml`.

For Kodiak to run on a pull request:

1. Kodiak must be installed on the repository.
2. A configuration file must exist in the repository.
3. GitHub branch protection must exist on the target branch.

## configuration fields

### `version`

- **type:** `number`
- **required:** `true`

`1` is the only valid setting for this field.

### `merge.automerge_label`

- **type:** `string`
- **default:** `"automerge"`

Label to enable Kodiak to merge a PR.

By default, Kodiak will only act on PRs that have this label. You can disable this requirement via `merge.require_automerge_label`.

```toml
merge.automerge_label = "🚀 merge it!"
```

### `merge.require_automerge_label`

- **type:** `boolean`
- **default:** `true`

Require that the automerge label (`merge.automerge_label`) be set for Kodiak to merge a PR.

When disabled, Kodiak will immediately attempt to merge any PR that passes all GitHub branch protection requirements.

### `merge.blacklist_title_regex`

- **type:** `string`
- **default:** `"^WIP:.*"`
- **options:** Regex pattern or `""`

If a PR's title matches this regex, Kodiak will not merge the PR. This is useful
to prevent merging work-in-progress PRs.

Setting `merge.blacklist_title_regex = ""` disables this option.

#### example

```
merge.blacklist_title_regex = ".*DONT\s*MERGE.*"
```

### `merge.blacklist_labels`

- **type:** `string[]`
- **default:** `[]`
- **options:** List of label names

Kodiak will not merge a PR with any of these labels.

#### example

```
merge.blacklist_labels = ["wip"]
```

### `merge.method`

- **type:** `string`
- **default:** `"merge"`
- **options:** `"merge"`, `"squash"`, `"rebase"`

Choose merge method for Kodiak to use.

Kodiak will report a configuration error if the selected merge method is disabled for a repository.

If you're using the "Require signed commits" GitHub Branch Protection setting to require commit signatures, _`"merge"` is the only compatible option_. Any other option will cause Kodiak to raise a configuration error.

### `merge.delete_branch_on_merge`

- **type:** `boolean`
- **default:** `false`

Once a PR is merged, delete the branch.

This option behaves like the GitHub repository setting "Automatically delete head branches", which automatically deletes head branches after pull requests are merged.

### `merge.block_on_reviews_requested`

- **type:** `boolean`
- **default:** `false`

> **DEPRECATED**
>
> Due to limitations with the GitHub API this feature is fundamentally broken and cannot be fixed. Prefer the GitHub branch protection "required reviewers" setting instead.
>
> When a user leaves a comment on a PR, GitHub counts that as satisfying a review request, so the PR will be allowed to merge, even though a reviewer was likely just starting a review.
>
> See this issue comment for more information: [chdsbd/kodiak#153 (comment)](https://github.com/chdsbd/kodiak/issues/153#issuecomment-523057332)

If you request review from a user, don't merge until that user provides a review, even if the PR is passing all status checks.

### `merge.notify_on_conflict`

- **type:** `boolean`
- **default:** `true`

If there is a merge conflict, make a comment on the PR and remove the
automerge label.

This option only applies when `merge.require_automerge_label` is enabled.

### `merge.optimistic_updates`

- **type:** `boolean`
- **default:** `true`

Don't wait for in-progress status checks on a PR to finish before updating the branch.

This setting can speed up merges but increases chance of running extra CI jobs.

### `merge.dont_wait_on_status_checks`

- **type:** `string[]`
- **default:** `[]`
- **options:** List of check names

Don't wait for specified status checks when merging a PR. If a configured status check is incomplete when a PR is being merged, Kodiak will skip the PR.

Use this option for status checks that run indefinitely, like deploy jobs or the WIP GitHub App.

#### example

```
merge.dont_wait_on_status_checks = ["ci/circleci: deploy", "WIP"]
```

### `merge.update_branch_immediately`

- **type:** `boolean`
- **default:** `false`

> **DEPRECATED**
>
> Prefer [`update.always`](#updatealways), which will deliver better behavior in most use cases. `merge.update_branch_immediately` only affects PRs eligible for merging, while `update.always` will keep all PRs up-to-date.

Update PRs that are passing all branch requirements or are waiting for status checks to pass.

### `merge.prioritize_ready_to_merge`

- **type:** `boolean`
- **default:** `false`

If a PR is passing all checks and is able to be merged, merge it without
placing it in the merge queue.

This option adds some unfairness where PRs waiting in the queue the longest are not served first.

### `merge.do_not_merge`

- **type:** `boolean`
- **default:** `false`

Never merge a PR. This option can be used with `update.always` to automatically update a PR without merging.

### `merge.message.title`

- **type:** `enum`
- **default:** `"github_default"`
- **options:** `"github_default"`, `"pull_request_title"`

By default (`"github_default"`), GitHub uses the title of a PR's first commit for the merge commit title. `"pull_request_title"` uses the PR title for the merge commit.

### `merge.message.body`

- **type:** `enum`
- **default:** `"github_default"`
- **options:** `"github_default"`, `"pull_request_body"`, `"empty"`

By default (`"github_default"`), GitHub combines the titles of a PR's commits to create the body
text of a merge commit. `"pull_request_body"` uses the content of the PR to generate
the body content while `"empty"` sets an empty body.

### `merge.message.include_pr_number`

- **type:** `boolean`
- **default:** `true`

Add the PR number to the merge commit title.

This setting replicates GitHub's behavior of automatically adding the PR number to the title of merges created through the UI.

This option only applies when `merge.message.title` does not equal `"github_default"`.

### `merge.message.body_type`

- **type:** `enum`
- **default:** `"markdown"`
- **options:** `"markdown"`, `"plain_text"`, `"html"`

Control the text used in the merge commit. The GitHub default is markdown, but `"plain_text"` or `"html"` can be used to render the pull request body as text or HTML.

This option only applies when `merge.message.body = "pull_request_body"`.

### `merge.message.strip_html_comments`

- **type:** `boolean`
- **default:** `false`

Strip HTML comments (`<!-- some HTML comment -->`) from merge commit body.

This setting is useful for stripping HTML comments created by PR templates.

This option only applies when `merge.message.body_type = "markdown"`.

### `merge.message.include_pull_request_author`

- **type:** `boolean`
- **default:** `false`

Add the pull request author as a coauthor of the merge commit using `Co-authored-by: jdoe <828352+jdoe@users.noreply.github.com>` syntax.

This setting will override `merge.message.body = "github_default"` and `merge.message.body = "empty"`. In both cases the result will be an empty merge commit body with coauthor information at the end of the commit body.

This setting is useful when GitHub strips authorship information for squashes.

### `update.always`

- **type:** `boolean`
- **default:** `false`

Update a PR whenever out of date with the base branch. The PR will be
updated regardless of merge requirements (e.g. failing status
checks, missing reviews, blacklist labels).

Kodiak will only update PRs with the `merge.automerge_label` label or if `update.require_automerge_label = false`.

When enabled, _Kodiak will not be able to efficiently update PRs._ If you have multiple PRs against a target like `master`, any time a commit
is added to `master` _all_ of those PRs against `master` will update. For `N` PRs against a target you will see at least `N(N-1)/2` updates. If
this configuration option was disabled you would only see at least `N-1` updates.

### `update.require_automerge_label`

- **type:** `boolean`
- **default:** `true`

When enabled, Kodiak will only update PRs that have an automerge label (configured via `merge.automerge_label`).

When disable, Kodiak will update any PR.

This option only applies when `update.always = true`.

### `approve.auto_approve_usernames`

- **type:** `string[]`
- **default:** `[]`
- **options:** List of GitHub usernames

If a PR is opened by a user with a username in the `approve.auto_approve_usernames` list, Kodiak will automatically add an approval to the PR.

If Kodiak's review is dismissed, it will add a review again.

This setting is useful when the "Required approving reviews" GitHub Branch Protection setting is configured and dependency upgrade bots like dependabot, greenkeeper, etc, run on the repository. When these bots open a PR, Kodiak can automatically add a review so dependency upgrade PRs can be automatically merged.

See the "[Automated dependency updates with Dependabot](recipes.md#automated-dependency-updates-with-dependabot)" recipe for an example of this feature in action.

## full examples

### minimal

```toml
# .kodiak.toml
# docs: https://kodiakhq.com/docs/config-reference
version = 1
```

### all options

Below is a Kodiak config with all options set and commented.

```toml
# .kodiak.toml

# Kodiak's configuration file should be placed at `.kodiak.toml` (repository
# root) or `.github/.kodiak.toml`.
# docs: https://kodiakhq.com/docs/config-reference

# version is the only required setting in a kodiak config.
# `1` is the only valid setting for this field.
version = 1

[merge]
# Label to enable Kodiak to merge a PR.

# By default, Kodiak will only act on PRs that have this label. You can disable
# this requirement via `merge.require_automerge_label`.
automerge_label = "automerge" # default: "automerge"

# Require that the automerge label (`merge.automerge_label`) be set for Kodiak
# to merge a PR.
#
# When disabled, Kodiak will immediately attempt to merge any PR that passes all
# GitHub branch protection requirements.
require_automerge_label = true

# If a PR's title matches this regex, Kodiak will not merge the PR. This is
# useful to prevent merging work-in-progress PRs.
#
# Setting `merge.blacklist_title_regex = ""` disables this option.
blacklist_title_regex = "" # default: "^WIP:.*", options: "" (disables regex), a regex string (e.g. ".*DONT\s*MERGE.*")

# Kodiak will not merge a PR with any of these labels.
blacklist_labels = [] # default: [], options: list of label names (e.g. ["wip"])

# Choose merge method for Kodiak to use.
#
# Kodiak will report a configuration error if the selected merge method is
# disabled for a repository.
#
# If you're using the "Require signed commits" GitHub Branch Protection setting
# to require commit signatures, _`"merge"` is the only compatible option_. Any
# other option will cause Kodiak to raise a configuration error.
method = "merge" # default: "merge", options: "merge", "squash", "rebase"

# Once a PR is merged, delete the branch. This option behaves like the GitHub
# repository setting "Automatically delete head branches", which automatically
# deletes head branches after pull requests are merged.
delete_branch_on_merge = false # default: false

# DEPRECATED
#
# Due to limitations with the GitHub API this feature is fundamentally broken
# and cannot be fixed. Prefer the GitHub branch protection "required reviewers"
# setting instead.
#
# When a user leaves a comment on a PR, GitHub counts that as satisfying a
# review request, so the PR will be allowed to merge, even though a reviewer was
# likely just starting a review.
#
# See this issue comment for more information:
# https://github.com/chdsbd/kodiak/issues/153#issuecomment-523057332
#
# If you request review from a user, don't merge until that user provides a
# review, even if the PR is passing all status checks.
block_on_reviews_requested = false # default: false

# If there is a merge conflict, make a comment on the PR and remove the
# automerge label. This option only applies when `merge.require_automerge_label`
# is enabled.
notify_on_conflict = true # default: true

# Don't wait for in-progress status checks on a PR to finish before updating the
# branch.
optimistic_updates = false # default: true

# Don't wait for specified status checks when merging a PR. If a configured
# status check is incomplete when a PR is being merged, Kodiak will skip the PR.
# Use this option for status checks that run indefinitely, like deploy jobs or
# the WIP GitHub App.
dont_wait_on_status_checks = [] # default: [], options: list of check names (e.g. ["ci/circleci: lint_api"])

# DEPRECATED
#
# Prefer `update.always`, which will deliver better behavior in most use cases.
# `merge.update_branch_immediately` only affects PRs eligible for merging, while
# `update.always` will keep all PRs up-to-date.
#
# Update PRs that are passing all branch requirements or are waiting for status
# checks to pass.
update_branch_immediately = false # default: false

# If a PR is passing all checks and is able to be merged, merge it without
# placing it in the merge queue. This option adds some unfairness where PRs
# waiting in the queue the longest are not served first.
prioritize_ready_to_merge = false # default: false

# Never merge a PR. This option can be used with `update.always` to
# automatically update a PR without merging.
do_not_merge = false # default: false

[merge.message]
# By default (`"github_default"`), GitHub uses the title of a PR's first commit
# for the merge commit title. `"pull_request_title"` uses the PR title for the
# merge commit.
title = "github_default" # default: "github_default", options: "github_default", "pull_request_title"

# By default (`"github_default"`), GitHub combines the titles of a PR's commits
# to create the body text of a merge commit. `"pull_request_body"` uses the
# content of the PR to generate the body content while `"empty"` sets an empty
# body.
body = "github_default" # default: "github_default", options: "github_default", "pull_request_body", "empty"

# Add the PR number to the merge commit title. This setting replicates GitHub's
# behavior of automatically adding the PR number to the title of merges created
# through the UI. This option only applies when `merge.message.title` does not
# equal `"github_default"`.
include_pr_number = true # default: true

# Control the text used in the merge commit. The GitHub default is markdown, but
# `"plain_text"` or `"html"` can be used to render the pull request body as text
# or HTML. This option only applies when `merge.message.body = "pull_request_body"`.
body_type = "markdown" # default: "markdown", options: "plain_text", "markdown", "html"


# Strip HTML comments (`<!-- some HTML comment -->`) from merge commit body.
# This setting is useful for stripping HTML comments created by PR templates.
# This option only applies when `merge.message.body_type = "markdown"`.
strip_html_comments = false # default: false

[update]

# Update a PR whenever out of date with the base branch. The PR will be updated
# regardless of merge requirements (e.g. failing status checks, missing reviews,
# blacklist labels).
#
# Kodiak will only update PRs with the `merge.automerge_label` label or if
# `update.require_automerge_label = false`.
#
# When enabled, _Kodiak will not be able to efficiently update PRs._ If you have
# multiple PRs against a target like `master`, any time a commit is added to
# `master` _all_ of those PRs against `master` will update. For `N` PRs against
# a target you will see at least `N(N-1)/2` updates. If this configuration
# option was disabled you would only see at least `N-1` updates.
always = false # default: false

# When enabled, Kodiak will only update PRs that have an automerge label
# (configured via `merge.automerge_label`). When disable, Kodiak will update any
# PR. This option only applies when `update.always = true`.
require_automerge_label = true # default: true
```

## other resources

See [`kodiak/test/fixtures/config`](https://github.com/chdsbd/kodiak/tree/master/kodiak/test/fixtures/config) for more examples and [`kodiak/config.py`](https://github.com/chdsbd/kodiak/blob/master/kodiak/config.py) for the Python models that codify this configuration.
