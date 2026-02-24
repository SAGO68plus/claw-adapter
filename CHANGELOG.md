# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.3.3] - 2026-02-24

### Fixed

- Sankey topology: output links clustered at top half of adapter nodes when multiple providers connect to the same adapter
- Replaced `computeWeights` with flow-balanced `propagateFlow` — scales provider→adapter input links proportionally so input flow = output flow at every adapter node, then propagates upstream to key and vendor layers

## [0.3.2] - 2026-02-19

### Added

- Soft validation for entity relationships across the five-layer model
- Extended database table columns for additional metadata

### Fixed

- Single provider-endpoint relation restriction bug

## [0.3.1] - 2026-02-18

### Changed

- Refactored database and route architecture (three-layer: routes → services → db)
- Separated English README and Chinese README (`README_CN.md`)

### Fixed

- Adapter file loading issues and database bug

## [0.3.0] - 2026-02-17

### Added

- Initial release of ClawAdapter
- Vendor, Key, Provider, Adapter, and Service five-layer management
- Adapter support for OpenClaw, SillyTavern, and Claude Code Router
- Config sync with automatic push on binding changes
- Fernet-encrypted API key storage
- ECharts Sankey diagram for topology visualization
- Single-file SPA frontend
- Apache 2.0 license

### Fixed

- Replaced hardcoded `/root/` paths with `expanduser` for portability
- Sanitized placeholder values in configuration

[Unreleased]: https://github.com/SAGO68plus/claw-adapter/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/SAGO68plus/claw-adapter/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/SAGO68plus/claw-adapter/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/SAGO68plus/claw-adapter/releases/tag/v0.3.0
