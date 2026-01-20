# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.4] - 2024-01-20

### Added
- Options Flow for configuring poll interval and counter offsets
- Service `set_counter_value` for manually setting counter values
- Service `reset_counter` for resetting counter values
- Unit tests structure with pytest configuration
- GitHub Actions CI/CD workflows (tests, linting, HACS validation)
- Support for renamed devices (detection by service UUID)
- Proper error handling and logging throughout the codebase
- Type hints for better code quality
- Comprehensive README with usage examples and FAQ
- Missing 'requirements' field in manifest.json

### Fixed
- Critical bug in sensor state restoration (was saving State object instead of float value)
- Empty except blocks that were hiding errors
- IndexError in `is_encrypted()` when data is too short
- Typo: `midLittleIndian` → `midLittleEndian`
- Cyrillic 'о' in English translation "Nоt found" → "Not found"
- Inconsistent error messages in translations
- Documentation and issue tracker URLs in manifest.json

### Changed
- Counter values now properly apply ratio (multiplier) on display
- Counter values now support offsets for initial readings
- Poll interval is now configurable via Options Flow (60-86400 seconds)
- Improved English translations and capitalization consistency
- Enhanced documentation with examples and troubleshooting
- Version bumped to 0.0.4

## [0.0.3] - 2024-XX-XX

### Added
- Basic BLE advertisement parsing
- Support for encrypted advertisements with PIN
- Auto-discovery of aTick devices
- Water counter sensors (A and B)
- RSSI sensor for Bluetooth signal strength

### Fixed
- Basic connectivity and data parsing

## [0.0.2] - Earlier

### Added
- Initial alpha release
- Basic Bluetooth connectivity

## [0.0.1] - Initial

### Added
- Project structure
- HACS integration

[Unreleased]: https://github.com/trudenboy/hassio-atick/compare/v0.0.4...HEAD
[0.0.4]: https://github.com/trudenboy/hassio-atick/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/trudenboy/hassio-atick/releases/tag/v0.0.3
[0.0.2]: https://github.com/trudenboy/hassio-atick/releases/tag/v0.0.2
[0.0.1]: https://github.com/trudenboy/hassio-atick/releases/tag/v0.0.1
