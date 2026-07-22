---
name: app-store-connect-release
description: Build, sign, validate, upload, inspect, and maintain Xcode app releases for App Store Connect using safe staged workflows, App Store Connect API authentication, localized metadata and screenshot checks, screenshot asset synchronization, and IAP localization management. Use when preparing an iOS, iPadOS, macOS, watchOS, tvOS, or visionOS app for TestFlight or App Store submission, auditing release readiness, uploading a signed archive, managing store content, or diagnosing App Store Connect processing and metadata issues.
---

# App Store Connect Release

Use this skill to operate the release path for an arbitrary Xcode project. Discover the project's configuration instead of assuming a product name, bundle ID, scheme, platform, localization set, pricing, or IAP product IDs. Keep local preparation, external upload, and final review submission as separate stages.

## Select A Mode

Choose the least destructive mode that satisfies the request:

- `status`: inspect local configuration and, when credentials are available, query App Store Connect.
- `audit`: run read-only checks and produce a release-readiness report.
- `prepare`: update requested release inputs and generate local artifacts, but do not contact Apple.
- `validate`: create or export an archive and validate it with Apple without uploading it.
- `upload`: upload an explicitly approved, validated artifact and report Apple's processing state.
- `handoff`: produce the remaining App Store Connect portal checklist; do not claim that review submission is complete.
- `metadata`: preview or apply localized app-info and version metadata updates.
- `screenshots`: preview or apply screenshot-set creation, upload, and explicitly confirmed replacement.
- `iap`: discover products or preview/apply product and localization changes.

Never infer permission to upload or submit from a request to audit or prepare. Ask for confirmation immediately before an external upload if the user did not explicitly request uploading.

## Start With Discovery

1. Inspect the worktree and preserve unrelated user changes. Do not reset, clean, or commit files automatically.
2. Find `.xcworkspace` and `.xcodeproj` files. Prefer the workspace when the project uses dependencies or CocoaPods/Swift Package integration.
3. Discover schemes with `xcodebuild -list` and build settings with `xcodebuild -showBuildSettings`.
4. Resolve the target platform, `PRODUCT_BUNDLE_IDENTIFIER`, `DEVELOPMENT_TEAM`, marketing version, build number, signing style, and archive destination from the project rather than hardcoding them.
5. Run the bundled read-only prerequisite check before any archive or API operation:

   ```sh
   python3 /path/to/app-store-connect-release/scripts/check_release_prerequisites.py \
     --project-root /path/to/project \
     --scheme MyApp \
     --platform macOS \
     --require-api
   ```

Load [configuration.md](references/configuration.md) for environment variables and credential handling. Never print, copy, commit, or include the contents of an App Store Connect `.p8` file in an artifact or report.

For a structured project snapshot, run `scripts/discover_xcode_project.py --root /path/to/project --scheme MyApp --json`. For local store content checks, run `scripts/validate_metadata.py` and `scripts/validate_screenshots.py` before contacting Apple.

## Run The Release Pipeline

Follow this order unless the user explicitly narrows the task:

1. **Source and version check**: inspect the diff, tests, release notes, version source of truth, entitlements, privacy manifest, and supported deployment target. Change the version or build number only when requested.
2. **Local quality gate**: run the repository's own tests and release checks. Prefer existing project scripts over replacing them. Confirm the app launches or use the project's documented smoke test when possible.
3. **Archive**: create a signed archive with the discovered workspace/project, scheme, configuration, platform destination, and the project's signing strategy. Use `-allowProvisioningUpdates` only when the user has configured Apple signing access and expects profile updates.
4. **Export and validate**: export an App Store Connect package using an explicit `ExportOptions.plist`, then validate it with the App Store Connect credentials. Keep the archive and exported package in a build output directory outside source-controlled files when possible.
5. **Metadata and assets**: validate localization names, character limits, screenshot dimensions, device families, and review notes. Use repository automation where available; otherwise produce a precise portal handoff. Read [metadata-and-assets.md](references/metadata-and-assets.md).
6. **Upload**: only in `upload` mode, upload the validated package using `xcrun altool` or the repository's maintained uploader. Record the package path, version, build number, upload time, and returned request/build identifier without recording credentials.
7. **Processing follow-up**: query App Store Connect until the build is processed or a bounded timeout is reached. Report `PROCESSING`, `VALID`, `INVALID`, or an equivalent Apple response and include the next diagnostic action.
8. **Handoff**: list portal-only work such as agreements, tax and banking, app privacy, export compliance, review information, attaching products, selecting the build, and submitting for review. Read [app-store-connect-boundaries.md](references/app-store-connect-boundaries.md).

Use `scripts/poll_build.py` after upload to monitor a specific build. Use `scripts/release_upload.py` for a portable Xcode wrapper; it requires `--confirm-upload` for an upload and checks for an existing matching version/build before sending it.

## Synchronize Store Content

The store-content scripts are read-only previews by default. `--apply` is the only switch that permits API writes. They never delete remote localizations that are absent locally.

For a Fastlane metadata directory:

```sh
python3 scripts/sync_metadata.py \
  --metadata-root fastlane/metadata \
  --bundle-id com.example.app --version 1.0.0 --platform macOS
```

Review the operations, then add `--apply` to write them. A JSON manifest is also supported; see [metadata-and-assets.md](references/metadata-and-assets.md). App-level privacy policy URL updates are kept separate from locale fields.

For screenshots:

```sh
python3 scripts/sync_screenshots.py \
  --screenshots-root fastlane/screenshots \
  --manifest screenshots.json \
  --bundle-id com.example.app --version 1.0.0 --platform macOS
```

The script creates App Store screenshot sets, registers files, uploads through Apple's signed upload operations, and confirms each upload. Existing files with the same name but a different checksum stop the run unless `--replace` is supplied. Applying replacement also requires `--confirm-replace`.

For IAP products and localizations:

```sh
python3 scripts/sync_iap.py \
  --manifest iap.json --bundle-id com.example.app
```

Use `--apply` after reviewing the product IDs, product types, localized names, descriptions, and locales. Pricing, review screenshots/details, attaching products to a version, and final review submission remain explicit portal/account actions. Read [iap-and-commerce.md](references/iap-and-commerce.md).

## Standard Tool Choices

Use the project's existing tooling first. For a plain Xcode project, the usual commands are:

```sh
xcodebuild -list -workspace MyApp.xcworkspace
xcodebuild archive -workspace MyApp.xcworkspace -scheme MyApp \
  -configuration Release -destination 'generic/platform=iOS' \
  -archivePath build/MyApp.xcarchive
xcodebuild -exportArchive -archivePath build/MyApp.xcarchive \
  -exportPath build/export -exportOptionsPlist ExportOptions.plist
xcrun altool --validate-app build/export/MyApp.ipa \
  --api-key "$ASC_API_KEY_ID" --api-issuer "$ASC_API_ISSUER_ID" \
  --p8-file-path "$ASC_API_KEY_PATH"
xcrun altool --upload-package build/export/MyApp.ipa --wait \
  --api-key "$ASC_API_KEY_ID" --api-issuer "$ASC_API_ISSUER_ID" \
  --p8-file-path "$ASC_API_KEY_PATH"
```

Use `-project` instead of `-workspace` for project-only apps, and use the platform-appropriate export artifact (`.ipa`, `.pkg`, or another package produced by Xcode). Do not assume that every Xcode version exposes identical `altool` flags; consult `xcrun altool --help` and prefer a repository's tested uploader when one exists.

For Fastlane projects, use the existing `Fastfile` and lane when it already encodes signing and metadata correctly. Do not introduce Fastlane solely because this skill was invoked.

## Failure Handling

- Stop on signing, entitlement, export, validation, or API errors. Preserve the archive and logs for diagnosis.
- If an API key, issuer ID, Team ID, signing identity, or project scheme is missing, report the exact missing prerequisite and do not guess it.
- If Apple reports invalid metadata or screenshots, identify the locale, field, asset, and constraint that failed.
- If the build is still processing, do not upload a duplicate unless the user explicitly asks.
- If the repository has unrelated changes, report them separately and do not include them in a release commit.

## Final Report

Report the mode used, project and scheme, platform, version/build, checks run, archive/package paths, API/upload result, processing status, and remaining manual actions. Distinguish clearly between:

- local archive created;
- package validated by Apple;
- package uploaded and processing;
- build processed and selectable;
- version submitted for review;
- app approved or released.

Never describe one state as another.

## Resources

- Run `scripts/check_release_prerequisites.py` for deterministic, read-only local and credential checks.
- Run `scripts/discover_xcode_project.py` to emit a portable Xcode project/scheme/build-settings snapshot.
- Use `scripts/asc_api_client.py` for authenticated read-only App Store Connect queries or import its client for explicit API operations.
- Use `scripts/release_upload.py` for staged archive, validation, and upload commands with duplicate-build protection.
- Use `scripts/poll_build.py` to monitor Apple processing with a bounded timeout.
- Run `scripts/validate_metadata.py` and `scripts/validate_screenshots.py` for local store asset validation.
- Use `scripts/sync_metadata.py` for API-backed metadata preview/apply workflows.
- Use `scripts/sync_screenshots.py` for manifest-driven screenshot set and asset preview/apply workflows.
- Use `scripts/sync_iap.py` for IAP discovery and product/localization preview/apply workflows.
- Read [configuration.md](references/configuration.md) for portable environment configuration.
- Read [app-store-connect-boundaries.md](references/app-store-connect-boundaries.md) before making claims about API coverage or portal automation.
- Read [metadata-and-assets.md](references/metadata-and-assets.md) when handling localized store content or screenshots.
- Read [ci.md](references/ci.md) before adapting the GitHub Actions template at `assets/github-actions/app-store-connect-release.yml`.
