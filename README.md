<p align=center><img src="https://github.com/chdsbd/kodiak/raw/master/assets/logo.png" alt="" width="200" height="200"></p>

# kodiak [![CircleCI](https://circleci.com/gh/chdsbd/kodiak.svg?style=svg&circle-token=4879604a0cca6fa815c4d22936350f5bdf455905)](https://circleci.com/gh/chdsbd/kodiak)

> A GitHub bot to automatically update and merge GitHub PRs

[install app](https://github.com/marketplace/kodiakhq) | [documentation](https://kodiakhq.com/docs/quickstart) | [web dashboard](https://app.kodiakhq.com)

Kodiak automates your GitHub workflow:

- Simple & Configurable — a simple configuration file with smart defaults will get you started in minutes
- Update — update your branches automatically
- Merge — use Kodiak's simple configuration with GitHub Branch Protection to merge pull requests automatically
- Delete — remove your old branches automatically

Configure Kodiak to automate your workflow in minutes!

## Installation

Kodiak is available through the GitHub Marketplace.

[![install](https://3c7446e0-cd7f-4e98-a123-1875fcbf3182.s3.amazonaws.com/button-small.svg?v=123)](https://github.com/marketplace/kodiakhq)

_If you'd rather run Kodiak yourself, check out the [self hosting page](https://kodiakhq.com/docs/self-hosting) in our docs._

View activity via the dashboard at <https://app.kodiakhq.com>.

## [Documentation](https://kodiakhq.com)

Helpful Links:

- [Getting Started](https://kodiakhq.com/docs/quickstart)
- [Configuration Guide](https://kodiakhq.com/docs/config-reference)
- [Why and How](https://kodiakhq.com/docs/why-and-how)
- [Troubleshooting](https://kodiakhq.com/docs/troubleshooting)
- [Help](https://kodiakhq.com/help)
- [Prior Art / Alternatives](https://kodiakhq.com/docs/prior-art-and-alternatives)

## Sponsors

<a href="https://www.complex-it.de/jobs/offene-stellen?utm_source=oss-referal&utm_medium=logo&utm_campaign=growwithus">![complex-grow-with-us](https://user-images.githubusercontent.com/47448731/76313751-d3408b00-62d5-11ea-8f0f-a99e78b55a42.png)</a>

## :money_with_wings: Sponsoring

Using Kodiak for your commercial project?

[Support Kodiak with GitHub Sponsors](https://github.com/sponsors/chdsbd) to help cover server costs and support development.

## Contributing

Feel free to file feature requests, bug reports, help requests through the issue tracker.

If you'd like to add a feature, fix a big, update the docs, etc, take a peek at our [contributing guide](https://kodiakhq.com/docs/contributing).

## Project Layout

This repository contains multiple services that make up Kodiak. The GitHub App which receives webhook events from GitHub and operates of pull requests is stored at `bot/`. The web API powering the Kodiak dashboard (WIP) is stored at `web_api/` and the Kodiak dashboard frontend (WIP) that talks to the web api is stored at `web_ui/`.
