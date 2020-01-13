---
id: recipes
title: Recipes
sidebar_label: Recipes
---

## Better Merge Messages

In the config below we setup merge messages to use the PR title and body with
an included PR number. Additionally we strip html comments from the body
which can be useful if your GitHub repo has PR templates.

```toml
# .kodiak.toml
version = 1

[merge]
method = "squash"
delete_branch_on_merge = true
# Skip jobs that will never finish, like the WIP GitHub app
dont_wait_on_status_checks = ["WIP"] # handle github.com/apps/wip

[merge.message]
title = "pull_request_title"
body = "pull_request_body"
include_pr_number = true
body_type = "markdown"
strip_html_comments = true # remove html comments to auto remove PR templates
```
