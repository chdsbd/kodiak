# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Add `block_on_reviews_requested` configuration to block merging if there are unanswered review requests.
- Add `require_branch_protection` configuration to block merging if branch protection is not enabled for target.

### Changed
- Update mergeability evaluation to trigger branch update after all other mergeability tests are verified.
- Remove unused dependencies related to FastAPI install.

## 0.1.0 - 2019-05-22

### Added

- Basic MVP
