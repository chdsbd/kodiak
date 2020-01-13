---
id: permissions
title: Permissions
---

Kodiak needs read/write access to PRs as well as your repository to update and merge PRs. This means that Kodiak
can see **all** the code in your repository. Below is a table of all the required permissions and the reasons they are necessary.

| name                      | level      | reason                                                                 |
| ------------------------- | ---------- | ---------------------------------------------------------------------- |
| repository administration | read-only  | branch protection info                                                 |
| checks                    | read/write | PR mergeability and status report                                      |
| repository contents       | read/write | update PRs, read configuration                                         |
| issues                    | read/write | support [closing issues using keywords][issue-keywords]                |
| pull requests             | read/write | PR mergeability, merge PR                                              |
| commit statuses           | read-only  | PR mergeability                                                        |
| organization members      | read-only  | view review requests for users/teams of a PR to calculate mergeability |

[issue-keywords]: https://help.github.com/en/articles/closing-issues-using-keywords
