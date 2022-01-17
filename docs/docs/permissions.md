---
id: permissions
title: Permissions and Privacy
---

Kodiak only accesses the information necessary for its operation (pull request approval, update, merge). Information is stored temporarily in Redis, which acts as a message queue for the application.

If you have any questions or concerns, please [contact us](/help).

## GitHub App Permissions

Kodiak only requests [GitHub App permissions](https://developer.github.com/apps/building-github-apps/creating-github-apps-using-url-parameters/#github-app-permissions) necessary to operate.

Below is a table of all the required permissions and the reasons they are necessary.

| name            | type         | level        | reason                                                                                                   |
| --------------- | ------------ | ------------ | -------------------------------------------------------------------------------------------------------- |
| administration  | repository   | read         | Access GitHub branch protection settings to determine pull request merge eligibility.                    |
| checks          | repository   | write        | Set status checks to display Kodiak's activity on a pull request.                                        |
| contents        | repository   | write        | Merge and update pull requests. Read Kodiak's configuration from `.kodiak.toml`, `.github/.kodiak.toml`. |
| issues          | repository   | write        | Support [closing issues using keywords][issue-keywords].                                                 |
| pull requests   | repository   | write        | Comment on pull requests. View pull request information to determine merge eligibility.                  |
| commit statuses | repository   | read         | View passing/failing status checks to determine pull request merge eligibility.                          |
| workflows       | repository   | read & write | Merge pull requests that modify GitHub Workflow files.                                                   |
| members         | organization | read         | View review requests for users/teams of a pull request to determine merge eligibility.                   |

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

The following terms and conditions govern all use of the Kodiak services, including, but not limited to, the kodiakhq.com documentation website, the app.kodiakhq.com dashboard website ("The Dashboard"), and the KodiakHQ GitHub Marketplace App, (taken together, the App). The App is owned and operated by the Kodiak Team, Christopher Dignam ([@chdsbd](https://github.com/chdsbd)) and Steve Dignam [@sbdchd](https://github.com/sbdchd) ("Kodiak Team"). The App is offered subject to your acceptance without modification of all of the terms and conditions contained herein and all other operating rules, policies (including, without limitation, Kodiak's Privacy Policy) and procedures that may be published from time to time on this Site by the Kodiak Team (collectively, the “Agreement”).

Please read this Agreement carefully before accessing or using the App. By accessing or using any part of the web sites or bot, you agree to become bound by the terms and conditions of this agreement. If you do not agree to all the terms and conditions of this agreement, then you may not access the App or use any services. If these terms and conditions are considered an offer by Kodiak, acceptance is expressly limited to these terms.

1. **Using the Kodiak Bot.** If you use Kodiak to merge pull requests, you are fully responsible for all commit activities that are made in connection with your use of the bot.

2. **Fees and Payment.** Optional paid services such as Kodiak seat license subscriptions are available on the Dashboard. By selecting a seat license subscription you agree to pay Kodiak the monthly or annual subscription fees indicated for that license. Payments will be charged on the day you add a seat license service and will cover the use of that service for a monthly or annual period as indicated. Subscription fees are not refundable.

3. **Intellectual Property.** This Agreement does not transfer from Kodiak to you any Kodiak or third party intellectual property, and all right, title and interest in and to such property will remain (as between the parties) solely with Kodiak. Kodiak, the Kodiak logo, and all other trademarks, service marks, graphics and logos used in connection with the App are trademarks or registered trademarks of Kodiak or Kodiak’s licensors. Other trademarks, service marks, graphics and logos used in connection with the App may be the trademarks of other third parties. Your use of the App grants you no right or license to reproduce or otherwise use any Kodiak or third-party trademarks.

4. **Changes.** Kodiak reserves the right, at its sole discretion, to modify or replace any part of this Agreement. It is your responsibility to check this Agreement periodically for changes. Your continued use of or access to the App following the posting of any changes to this Agreement constitutes acceptance of those changes. Kodiak may also, in the future, offer new services and/or features through the App (including, the release of new tools and resources). Such new features and/or services shall be subject to the terms and conditions of this Agreement.

5. **Termination.** Kodiak may terminate your access to all or any part of the App at any time, with or without cause, with or without notice, effective immediately. If you wish to terminate this Agreement or your Kodiak account (if you have one), you may simply discontinue using the App. Notwithstanding the foregoing, if you have purchase a seat license susbcription, such account can only be terminated by Kodiak if you materially breach this Agreement and fail to cure such breach within thirty (30) days from Kodiak’s notice to you thereof; provided that, Kodiak can terminate the App immediately as part of a general shut down of our service. All provisions of this Agreement which by their nature should survive termination shall survive termination, including, without limitation, ownership provisions, warranty disclaimers, indemnity and limitations of liability.

6. **Disclaimer of Warranties.** The App is provided “as is”. Kodiak and its suppliers and licensors hereby disclaim all warranties of any kind, express or implied, including, without limitation, the warranties of merchantability, fitness for a particular purpose and non-infringement. Neither Kodiak nor its suppliers and licensors, makes any warranty that the App will be error free or that access thereto will be continuous or uninterrupted. If you’re actually reading this, here’s a treat. You understand that you download from, or otherwise obtain content or services through, the App at your own discretion and risk.

7. **Limitation of Liability.** In no event will Kodiak, or its suppliers or licensors, be liable with respect to any subject matter of this agreement under any contract, negligence, strict liability or other legal or equitable theory for: (i) any special, incidental or consequential damages; (ii) the cost of procurement or substitute products or services; (iii) for interruption of use or loss or corruption of data; or (iv) for any amounts that exceed the fees paid by you to Kodiak under this agreement during the twelve (12) month period prior to the cause of action. Kodiak shall have no liability for any failure or delay due to matters beyond their reasonable control. The foregoing shall not apply to the extent prohibited by applicable law.

8. **General Representation and Warranty.** You represent and warrant that (i) your use of the App will be in strict accordance with the Kodiak Privacy Policy, with this Agreement and with all applicable laws and regulations (including without limitation any local laws or regulations in your country, state, city, or other governmental area, regarding online conduct and acceptable content, and including all applicable laws regarding the transmission of technical data exported from the United States or the country in which you reside) and (ii) your use of the App will not infringe or misappropriate the intellectual property rights of any third party.

9. **Indemnification.** You agree to indemnify and hold harmless Kodiak, its contractors, and its licensors, and their respective directors, officers, employees and agents from and against any and all claims and expenses, including attorneys’ fees, arising out of your use of the App, including but not limited to your violation of this Agreement.

10. **Miscellaneous.** This Agreement constitutes the entire agreement between Kodiak and you concerning the subject matter hereof, and they may only be modified by a written amendment signed by an authorized executive of Kodiak, or by the posting by Kodiak of a revised version. Except to the extent applicable law, if any, provides otherwise, this Agreement, any access to or use of the App will be governed by the laws of the state of Massachusetts, U.S.A., excluding its conflict of law provisions, and the proper venue for any disputes arising out of or relating to any of the same will be the state and federal courts located in Essex County, Massachusetts. If any part of this Agreement is held invalid or unenforceable, that part will be construed to reflect the parties’ original intent, and the remaining portions will remain in full force and effect. A waiver by either party of any term or condition of this Agreement or any breach thereof, in any one instance, will not waive such term or condition or any subsequent breach thereof. You may assign your rights under this Agreement to any party that consents to, and agrees to be bound by, its terms and conditions; Kodiak may assign its rights under this Agreement without condition. This Agreement will be binding upon and will inure to the benefit of the parties, their successors and permitted assigns.

This terms of service is modified from [Automattic's](http://web.archive.org/web/20101124073443/http://en.wordpress.com/tos/) under the "Creative Commons Sharealike" license.

## Privacy Policy

KodiakHQ.com (“Kodiak”) operates multiple websites and services including kodiakhq.com, app.kodiakhq.com, and the KodiakHQ GitHub App. It is Kodiak’s policy to respect your privacy regarding any information we may collect while operating our services.

### Gathering of Personally-Identifying Information

Certain visitors to Kodiak’s services choose to interact with Kodiak in ways that require Kodiak to gather personally-identifying information. The amount and type of information that Kodiak gathers depends on the nature of the interaction. For example, we record the GitHub usernames of individuals that merge pull requests or login to the [Kodiak dashboard](./dashboard.md). Those who engage in transactions with Kodiak – by purchasing seat licenses, for example – are asked to provide additional information, including as necessary the personal and financial information required to process those transactions. In each case, Kodiak collects such information only insofar as is necessary or appropriate to fulfill the purpose of the visitor’s interaction with Kodiak. Kodiak does not disclose personally-identifying information other than as described below. And visitors can always refuse to supply personally-identifying information, with the caveat that it may prevent them from engaging in certain product-related activities.

### Protection of Certain Personally-Identifying Information

Kodiak discloses potentially personally-identifying and personally-identifying information only to those of its employees and affiliated organizations that (i) need to know that information in order to process it on Kodiak’s behalf or to provide services available at Kodiak’s services and applications, and (ii) that have agreed not to disclose it to others. Kodiak will not rent or sell potentially personally-identifying and personally-identifying information to anyone. Other than to its employees and affiliated organizations, as described above, Kodiak discloses potentially personally-identifying and personally-identifying information only when required to do so by law, or when Kodiak believes in good faith that disclosure is reasonably necessary to protect the property or rights of Kodiak, third parties or the public at large. Kodiak takes all measures reasonably necessary to protect against the unauthorized access, use, alteration or destruction of potentially personally-identifying and personally-identifying information.

### Privacy Policy Changes

Although most changes are likely to be minor, Kodiak may change its Privacy Policy from time to time, and in Kodiak’s sole discretion. Kodiak encourages visitors to frequently check this page for any changes to its Privacy Policy. Your continued use of this product after any change in this Privacy Policy will constitute your acceptance of such change.

This privacy policy is modified from [Automattic's](http://web.archive.org/web/20101121173137/http://automattic.com/privacy/) under the "Creative Commons Sharealike" license.
