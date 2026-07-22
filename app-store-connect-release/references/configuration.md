# Configuration

Use environment variables or the host project's secret manager. Do not store credentials in the repository.

## Required For API Work

- `ASC_API_KEY_ID`: App Store Connect API key ID.
- `ASC_API_ISSUER_ID`: App Store Connect issuer ID.
- `ASC_API_KEY_PATH`: path to `AuthKey_<key-id>.p8`.

The key path may be supplied by a CI secret mount or a local path such as `$HOME/.appstoreconnect/private_keys/AuthKey_<key-id>.p8`. Keep file permissions restrictive and never include the file in an archive, log, screenshot, or commit.

Read-only queries generally need an API key with access to the app. Metadata, screenshot, and IAP writes require a role permitted to edit those resources. Uploading builds and editing store resources may require different key roles; use the smallest key that satisfies the current operation.

The write-oriented scripts are intentionally conservative:

- `sync_metadata.py` defaults to a read-only diff; pass `--apply` to write.
- `sync_screenshots.py` defaults to a read-only diff; pass `--apply` to upload.
- `sync_screenshots.py --apply --replace` additionally requires `--confirm-replace`.
- `sync_iap.py` defaults to discovery/diff; pass `--apply` to create or update products.

## Project Context

Resolve these from Xcode unless the user supplies an override:

- `DEVELOPMENT_TEAM`
- `PRODUCT_BUNDLE_IDENTIFIER`
- workspace or project path
- scheme and configuration
- platform and generic archive destination
- marketing version and build number

Optional variables commonly used by release scripts include `ASC_API_KEY_SUBJECT`, `ARCHIVE_PATH`, `EXPORT_PATH`, and `EXPORT_OPTIONS_PLIST`. Prefer the repository's documented variable names when they already exist.

The bundled scripts accept command-line overrides for all credential values. This is useful in CI, but do not put a private key value directly in a command line. Point `ASC_API_KEY_PATH` at a protected file instead.

An optional project-specific configuration file can be maintained by the host project, for example:

```json
{
  "workspace": "Example.xcworkspace",
  "scheme": "Example",
  "platform": "macOS",
  "metadata_path": "fastlane/metadata",
  "screenshots_path": "fastlane/screenshots"
}
```

The Skill does not require this file; explicit command-line values and Xcode discovery remain the source of truth.

## CI Recommendations

Use a dedicated App Store Connect API key with the smallest role that supports the requested operation. Inject the issuer ID and key ID as ordinary variables and mount the `.p8` content as a protected file. Mask all three values in CI logs where the CI provider supports masking. Keep signing certificates and provisioning profiles in the CI provider's encrypted store.
