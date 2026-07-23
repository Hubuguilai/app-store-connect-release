# App Store Connect Release Skill

[![Validate Skill](https://github.com/Hubuguilai/app-store-connect-release/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/Hubuguilai/app-store-connect-release/actions/workflows/validate-skill.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A safety-first Codex Skill for auditing, building, validating, and uploading Xcode apps to App Store Connect.

## Choose Your Language

### [English — Step-by-step beginner guide](docs/en/quick-start.md)

### [简体中文 — 零基础图文教程](docs/zh-CN/quick-start.md)

### [日本語 — 初心者向け画像付きガイド](docs/ja/quick-start.md)

![Release workflow](docs/assets/tutorial/04-release-workflow.png)

## Three Ways to Start

| Goal | Time | Apple credentials | Changes Apple? |
| --- | ---: | --- | --- |
| Audit an Xcode project | 5 minutes | Not required | No |
| Inspect App Store Connect | 10 minutes | Required | No |
| Validate or upload a build | 20+ minutes | Required | Only after confirmation |

The beginner guides explain every click and command, show the expected result, and include troubleshooting when your screen looks different.

## Install

```sh
git clone https://github.com/Hubuguilai/app-store-connect-release.git app-store-connect-release-repo
mkdir -p "$HOME/.codex/skills/app-store-connect-release"
rsync -a app-store-connect-release-repo/app-store-connect-release/ \
  "$HOME/.codex/skills/app-store-connect-release/"
```

Start a new Codex task, open your Xcode project folder, and ask:

```text
Use $app-store-connect-release to audit this Xcode project.
Read-only checks only. Do not archive, upload, or change any files.
```

## Safe by Default

- Audits and synchronization commands are read-only unless `--apply` is supplied.
- Upload requires `--confirm-upload`.
- Screenshot replacement requires `--apply --replace --confirm-replace`.
- Duplicate version/build uploads are blocked by default.
- Provisioning updates require `--allow-provisioning-updates`.
- Private-key contents and signed upload URLs are never printed.
- Uploading a build does not submit it for App Review.

## What It Supports

- iOS, iPadOS, macOS, watchOS, tvOS, and visionOS
- `.xcodeproj` and `.xcworkspace` discovery
- Archive, export, Apple validation, and confirmed upload
- Duplicate-build protection and build processing polling
- Localized metadata validation and preview/apply synchronization
- Screenshot validation, checksum comparison, upload, and guarded replacement
- In-app purchase discovery and localization synchronization
- JSON output and a staged GitHub Actions template

The complete agent workflow is in [`app-store-connect-release/SKILL.md`](app-store-connect-release/SKILL.md).

## Validation

```sh
cd app-store-connect-release-repo/app-store-connect-release
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The implementation has been tested with a real Xcode macOS app and live read-only App Store Connect endpoints. No project-specific identifiers or credentials are included in this repository.

## Official Apple References

- [Get started with the App Store Connect API](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api)
- [Create API keys for the App Store Connect API](https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api)
- [App Store Connect role permissions](https://developer.apple.com/help/app-store-connect/reference/account-management/role-permissions/)

## License

MIT
