# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
## 0.2.1 - 1029-05-23

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
