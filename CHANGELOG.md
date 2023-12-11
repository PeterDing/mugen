# Changelog

## v0.6.1 - 2023-12-11

### Updated

- Update dependencies

## v0.6.0 - 2021-07-22

### Added

- Support Proxy-Authorization

  ```python
  await mugen.get("http://example.com", proxy='http://user:pwd@127.0.0.1:8888')
  ```

## v0.5.1 - 2021-07-16

### Fixed

- FIXME: File descriptor n is used by transport

## v0.5.0 - 2021-07-14

### Changed

- Use async-await instead of asyncio.coroutine descriptor.
- Merge all test cases into one file
- Let poetry to manage building and publishing.
