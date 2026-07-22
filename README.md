# App Store Connect Release Skill

[![Validate Skill](https://github.com/Hubuguilai/app-store-connect-release/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/Hubuguilai/app-store-connect-release/actions/workflows/validate-skill.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A safety-first Codex Skill for taking an arbitrary Xcode app from release-readiness checks to an App Store Connect upload. It discovers the host project's settings instead of hardcoding app-specific values, keeps previews separate from writes, and reports Apple's actual release state without confusing upload, processing, review, and approval.

## What It Covers

- Xcode workspace/project, scheme, signing, version, and build discovery
- Read-only release prerequisites and structured project snapshots
- Archive, export, Apple validation, and explicitly confirmed upload
- Duplicate version/build protection and bounded processing polling
- Localized metadata validation and App Store Connect preview/apply sync
- Screenshot validation, checksum diffing, upload, and guarded replacement
- In-app purchase discovery plus product/localization preview/apply sync
- GitHub Actions release template with human-controlled upload and signing gates
- Clear handoff for portal-only work such as agreements, pricing, review details, and final submission

The Skill supports iOS, iPadOS, macOS, watchOS, tvOS, and visionOS projects. Its Python tools use the standard library; JWT signing uses the Ruby/OpenSSL runtime included with macOS developer environments.

## Install

```sh
git clone https://github.com/Hubuguilai/app-store-connect-release.git
mkdir -p ~/.codex/skills
cp -R app-store-connect-release/app-store-connect-release ~/.codex/skills/app-store-connect-release
```

Then ask Codex:

```text
Use $app-store-connect-release to audit this Xcode project for App Store Connect.
```

The full agent workflow is in [`app-store-connect-release/SKILL.md`](app-store-connect-release/SKILL.md).

## Safe By Default

- Audits and content synchronization are read-only unless `--apply` is supplied.
- Build upload additionally requires `--confirm-upload`.
- Screenshot replacement requires `--apply --replace --confirm-replace`.
- Duplicate version/build uploads are blocked unless intentionally overridden.
- Xcode provisioning updates require the explicit `--allow-provisioning-updates` switch.
- API key contents and signed upload URLs are never included in reports.
- The tools do not submit a version for review or pretend portal-only work is complete.

## App Store Connect Credentials

Use a least-privilege API key and keep its `.p8` file outside the repository:

```sh
export ASC_API_KEY_ID="YOUR_KEY_ID"
export ASC_API_ISSUER_ID="YOUR_ISSUER_ID"
export ASC_API_KEY_PATH="$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

Start with a read-only authentication probe:

```sh
python3 app-store-connect-release/scripts/asc_api_client.py auth
```

## Example Workflows

Discover an Xcode project:

```sh
python3 app-store-connect-release/scripts/discover_xcode_project.py \
  --root /path/to/project --scheme MyApp --json
```

Preview localized metadata changes without writing:

```sh
python3 app-store-connect-release/scripts/sync_metadata.py \
  --metadata-root /path/to/fastlane/metadata \
  --bundle-id com.example.app --version 2.0.0 --platform iOS
```

Preview screenshot synchronization for one locale:

```sh
python3 app-store-connect-release/scripts/sync_screenshots.py \
  --screenshots-root /path/to/screenshots --manifest /path/to/screenshots.json \
  --bundle-id com.example.app --version 2.0.0 --platform iOS --locale en-US
```

Inspect in-app purchases without writing:

```sh
python3 app-store-connect-release/scripts/sync_iap.py \
  --bundle-id com.example.app --json
```

Archive and validate remain separate stages. Upload is only available through an explicitly confirmed command. See the Skill and bundled references for the complete workflow and API boundaries.

## Validation

```sh
cd app-store-connect-release
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The implementation has also been forward-tested against a real Xcode macOS app and live App Store Connect read-only endpoints for build duplicate detection, localized screenshot reconciliation, and in-app purchase discovery. No project-specific identifiers or credentials are included in this repository.

## Contributing

Issues and pull requests are welcome, especially reproducible fixtures for additional Xcode project layouts, App Store platforms, localization structures, and API response variants. Never attach `.p8` files, signing assets, signed upload URLs, or private App Store Connect payloads.

## License

MIT
