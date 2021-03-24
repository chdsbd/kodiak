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

### Who runs Kodiak?

Kodiak is built and maintained by the Kodiak Team: Christopher Dignam ([@chdsbd](https://github.com/chdsbd)) and Steve Dignam ([@sbdchd](https://github.com/sbdchd)).

### What third party services does Kodiak use?

| name                | purpose         | country       | website                  |
| ------------------- | --------------- | ------------- | ------------------------ |
| Digital Ocean       | Server Hosting  | United States | https://digitalocean.com |
| Amazon Web Services | Data storage    | United States | https://aws.amazon.com   |
| Sentry              | Error reporting | United States | https://sentry.io        |
| Stripe              | Payments        | United States | https://stripe.com       |

Access to these third party services is restricted to the Kodiak Team ([@chdsbd](https://github.com/chdsbd) and [@sbdchd](https://github.com/sbdchd)).

### Does Kodiak `git clone` my repository?

Kodiak does not clone any repository and does not use `git` at all.

Kodiak uses the GitHub API to perform actions on repositories and pull requests, so repository content stays within GitHub.

## Terms and Conditions

## Privacy Policy

KodiakHQ.com (“Kodiak”) operates multiple websites and services including kodiakhq.com, app.kodiakhq.com, and the KodiakHQ GitHub App. It is Kodiak’s policy to respect your privacy regarding any information we may collect while operating our services.

### Gathering of Personally-Identifying Information

Certain visitors to Kodiak’s services choose to interact with Kodiak in ways that require Kodiak to gather personally-identifying information. The amount and type of information that Kodiak gathers depends on the nature of the interaction. For example, we record the GitHub usernames of individuals that merge pull requests or login to the [Kodiak dashboard](./dashbobard.md). Those who engage in transactions with Kodiak – by purchasing seat licenses, for example – are asked to provide additional information, including as necessary the personal and financial information required to process those transactions. In each case, Kodiak collects such information only insofar as is necessary or appropriate to fulfill the purpose of the visitor’s interaction with Kodiak. Kodiak does not disclose personally-identifying information other than as described below. And visitors can always refuse to supply personally-identifying information, with the caveat that it may prevent them from engaging in certain product-related activities.

### Protection of Certain Personally-Identifying Information

Kodiak discloses potentially personally-identifying and personally-identifying information only to those of its employees and affiliated organizations that (i) need to know that information in order to process it on Kodiak’s behalf or to provide services available at Kodiak’s services and applications, and (ii) that have agreed not to disclose it to others. Kodiak will not rent or sell potentially personally-identifying and personally-identifying information to anyone. Other than to its employees and affiliated organizations, as described above, Kodiak discloses potentially personally-identifying and personally-identifying information only when required to do so by law, or when Kodiak believes in good faith that disclosure is reasonably necessary to protect the property or rights of Kodiak, third parties or the public at large. Kodiak takes all measures reasonably necessary to protect against the unauthorized access, use, alteration or destruction of potentially personally-identifying and personally-identifying information.

### Privacy Policy Changes

Although most changes are likely to be minor, Kodiak may change its Privacy Policy from time to time, and in Kodiak’s sole discretion. Kodiak encourages visitors to frequently check this page for any changes to its Privacy Policy. Your continued use of this product after any change in this Privacy Policy will constitute your acceptance of such change.

This privacy policy is modified from [Automattic's](http://web.archive.org/web/20101121173137/http://automattic.com/privacy/) under the "Creative Commons Sharealike" license.
