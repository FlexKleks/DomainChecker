# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-10-28

### Fixed
- Available domains were always reported as `taken`. Four separate defects contributed
  (reported by [@rkahv](https://github.com/rkahv)):
  - **Duplicated `/domain/` in RDAP URLs** - most configured endpoints already end
    with `/domain/`, but the path segment was appended unconditionally, producing
    URLs such as `https://rdap.verisign.com/com/v1/domain/domain/google.com`
    that registries answer with HTTP 400. The segment is now only appended when
    the endpoint does not already end with it.
  - **HTTP 404 with an empty body treated as an error** - a 404 was only accepted
    as "not found" if the body contained one of a few text markers. Verisign and
    others answer with 404 and no body, so those responses became
    `RDAPStatus.ERROR` and therefore `taken`. Per RFC 7480 the status code is now
    the authoritative signal; a 404 is only rejected if the body carries an RDAP
    error object whose `errorCode` contradicts it.
  - **Unmatched WHOIS "no match" signals** - the `.com`/`.net` signal was
    `No match for domain`, while Verisign actually replies
    `No match for "EXAMPLE.COM".`. The `.org`, `.io` and `.biz` signals were
    likewise wrong, so WHOIS confirmation returned `AMBIGUOUS` and the
    conservative logic fell back to `taken`. Signals were corrected against the
    live registry responses.
  - **Misleading confidence for `taken`** - every `taken` result reported `high`
    confidence, including results that only came from errors, timeouts or missing
    confirmation. `high` is now reserved for results backed by an actual
    registration signal (RDAP `FOUND` or WHOIS `FOUND`); conservative fallbacks
    report `low`.
- Unclassifiable HTTP 404 responses are no longer retried. They previously fell
  through to the generic `server_error` branch, causing four identical requests
  per domain against the registry.
- `__version__` was stuck at `0.1.0` while the package version was already
  `0.2.0`, so `domain-checker --version` reported the wrong release. Both are
  now kept in sync.

### Credits
- Thanks to [@rkahv](https://github.com/rkahv) for reporting the invalid RDAP
  URLs and the false `taken` results, and for narrowing the problem down to
  `_is_not_found_response()` and the `taken`/`high` mapping in the decision
  engine.

## [0.2.0] - 2025-12-10

### Added
- **190+ TLD support** - Expanded from 6 to 193 TLDs across 15 categories
- New TLD registry module (`tld_registry.py`) with organized TLD configurations
- Full documentation of all supported TLDs in `SUPPORTED_TLDS.md`
- Support for new gTLDs: `.xyz`, `.online`, `.site`, `.store`, `.shop`, `.club`, `.live`, `.life`, `.world`, `.space`, `.fun`, `.top`, `.vip`, `.one`, `.blog`, `.news`, `.email`, `.link`, `.click`
- Tech TLDs: `.io`, `.co`, `.app`, `.dev`, `.ai`, `.tech`, `.cloud`, `.digital`, `.software`, `.systems`, `.network`, `.solutions`, `.agency`, `.studio`, `.design`, `.media`
- European ccTLDs: `.ch`, `.li`, `.nl`, `.be`, `.fr`, `.it`, `.es`, `.pt`, `.pl`, `.cz`, `.sk`, `.hu`, `.ro`, `.bg`, `.hr`, `.si`, `.rs`, `.gr`, `.tr`
- Nordic ccTLDs: `.se`, `.dk`, `.no`, `.fi`, `.is`
- UK & Ireland: `.uk`, `.co.uk`, `.org.uk`, `.me.uk`, `.ie`
- Americas: `.us`, `.ca`, `.mx`, `.br`, `.ar`, `.cl`, `.pe`
- Asia Pacific: `.au`, `.com.au`, `.nz`, `.jp`, `.cn`, `.hk`, `.tw`, `.kr`, `.in`, `.sg`, `.my`, `.th`, `.id`, `.ph`, `.vn`
- Middle East & Africa: `.ae`, `.sa`, `.il`, `.za`, `.ng`, `.ke`, `.eg`, `.ma`
- CIS: `.ru`, `.ua`, `.by`, `.kz`, `.uz`
- Special TLDs: `.me`, `.tv`, `.cc`, `.ws`, `.fm`, `.gg`, `.to`, `.la`, `.ly`, `.vc`, `.gl`, `.im`, `.sh`, `.ac`
- Business TLDs: `.company`, `.business`, `.consulting`, `.services`, `.group`, `.team`, `.work`, `.jobs`, `.careers`, `.finance`, `.money`, `.capital`, `.ventures`, `.holdings`, `.partners`, `.legal`, `.law`, `.tax`, `.accountant`, `.insurance`
- Lifestyle TLDs: `.art`, `.music`, `.video`, `.photo`, `.photography`, `.gallery`, `.fashion`, `.style`, `.fitness`, `.health`, `.yoga`, `.travel`, `.holiday`, `.restaurant`, `.cafe`, `.bar`, `.beer`, `.wine`, `.pizza`, `.game`, `.games`, `.casino`, `.bet`
- Real Estate TLDs: `.house`, `.homes`, `.property`, `.properties`, `.land`, `.estate`, `.apartments`, `.rent`
- Education TLDs: `.edu`, `.academy`, `.school`, `.university`, `.college`, `.training`, `.courses`, `.community`, `.social`, `.chat`, `.forum`
- Google TLDs: `.page`, `.new`, `.how`, `.soy`, `.foo`

### Changed
- Improved timestamp formatting in notifications (localized for German/English)
- Enhanced README with better documentation and badges
- Reorganized TLD configuration into dedicated registry module

### Fixed
- Fixed timestamp display in notification messages
- Fixed linting issues in multiple modules
- Stabilized flaky rate limiter tests

## [0.1.0] - 2025-12-10

### Added
- Initial release
- Multi-TLD domain availability checking (`.de`, `.com`, `.net`, `.org`, `.eu`, `.at`)
- RDAP protocol support with official registry endpoints
- WHOIS fallback for secondary confirmation
- Notification channels: Telegram, Discord, Email, Webhooks
- Rate limiting with configurable delays
- Retry logic with exponential backoff
- State persistence to prevent duplicate notifications
- CLI with `check`, `check-list`, `config`, and `self-test` commands
- Multilingual support (German/English)
- Simulation mode for testing
- JSON configuration file support
