# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 0.4.0 - 2019-06-16

### Added
- Add support for `include_pr_number` configuration. Enabling `include_pr_number` with a non-default merge message option will append the pr number to the commit message, like the Github UI.
- Make merge body style (plain text, markdown, or HTML) configurable via `merge.message.body_type`.
- Add automatic deletion of branches on merge configurable via `merge.delete_branch_on_merge`.
- Add support for running multiple kodiak instances on the same repo via the `app_id` configuration option.
- Add redis-based persistence. Redis >=5 is now required.
- Add `merge.blacklist_title_regex` configuration to block merging PRs that match configured regex.
- Display kodiak status information in Github CheckRun.
- Add docs for testing kodiak locally.
- Add automerge label removal and PR comment when a merge conflict occurs. This is configurable via `merge.notify_on_conflict`.

### Changed
- move `block_on_reviews_requested` to `merge.block_on_reviews_requested`.
- replace `merge.whitelist` array with singular `merge.automerge_label`.
- rename `merge.blacklist` to `merge.blacklist_labels`.

## 0.3.0 - 2019-05-24

### Added
- Add support for configuring merge messages. Current options are default Github style or using pull request title and body.

### Fixed
- Fix handling of `CHANGE_REQUESTED` reviews. We weren't nullifying `CHANGE_REQUESTED` reviews after the user placed another review.

## 0.2.1 - 2019-05-23

### Fixed
- Fix incorrect calls to sentry client. `send_message` => `capture_message`
- Fix missing handling for Github CheckRuns.

## 0.2.0 - 2019-05-22

### Added
- Add `block_on_reviews_requested` configuration to block merging if there are unanswered review requests.

### Changed
- Update mergeability evaluation to trigger branch update after all other mergeability tests are verified.

## 0.1.0 - 2019-05-22

### Added

- Basic MVP
