---
id: permissions
title: Permissions and Privacy
---

Kodiak only accesses the information necessary for its operation (pull request approval, update, merge). Information is stored temporarily in Redis, which acts as a message queue for the application.

If you have any questions or concerns, please [contact us](/help).

## GitHub App Permissions

Kodiak only requests [GitHub App permissions](https://developer.github.com/apps/building-github-apps/creating-github-apps-using-url-parameters/#github-app-permissions) necessary to operate.

Below is a table of all the required permissions and the reasons they are necessary.

| name            | type         | level | reason                                                                                                   |
| --------------- | ------------ | ----- | -------------------------------------------------------------------------------------------------------- |
| administration  | repository   | read  | Access GitHub branch protection settings to determine pull request merge eligibility.                    |
| checks          | repository   | write | Set status checks to display Kodiak's activity on a pull request.                                        |
| contents        | repository   | write | Merge and update pull requests. Read Kodiak's configuration from `.kodiak.toml`, `.github/.kodiak.toml`. |
| issues          | repository   | write | Support [closing issues using keywords][issue-keywords].                                                 |
| pull requests   | repository   | write | Comment on pull requests. View pull request information to determine merge eligibility.                  |
| commit statuses | repository   | read  | View passing/failing status checks to determine pull request merge eligibility.                          |
| members         | organization | read  | View review requests for users/teams of a pull request to determine merge eligibility.                   |

[issue-keywords]: https://help.github.com/en/articles/closing-issues-using-keywords

## Questions and Answers

### What data is read by Kodiak?

Kodiak reads files from repositories at `.kodiak.toml` and `.github/.kodiak.toml` to retrieve its configuration. Kodiak reads pull request titles and bodies to create merge commit messages. Kodiak reads pull request labels, status checks and GitHub API fields to determine merge eligibility.

### What 3rd party services or infrastructure does Kodiak use?

Kodiak uses Digital Ocean for infrastructure hosting, Cloudflare for API protection, Google Cloud for API uptime monitoring, and Sentry for error monitoring. All accounts are only accessible by Kodiak's administrators ([@chdsbd](https://github.com/chdsbd), [@sbdchd](https://github.com/sbdchd)).

### Does Kodiak `git clone` my repository?

Kodiak does not clone any repository and does not use `git` at all.

Kodiak uses the GitHub API to perform actions on repositories and pull requests, so repository contents stays within GitHub.
