# App Store Connect Release Skill

[![Validate Skill](https://github.com/Hubuguilai/app-store-connect-release/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/Hubuguilai/app-store-connect-release/actions/workflows/validate-skill.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A safety-first Codex Skill that helps you inspect, build, validate, and upload an Xcode app to App Store Connect.

You do not need to learn every script in this repository. Install the Skill, open your Xcode project in Codex, and describe the release task in plain language. The default workflow is read-only, and uploads require explicit confirmation.

## Beginner Quick Start

This path takes about 10 minutes. Complete the steps in order.

### Before You Start

You need:

- a Mac with Xcode installed;
- an Xcode app project (`.xcodeproj` or `.xcworkspace`);
- access to the app in App Store Connect;
- an App Store Connect API key if you want to query Apple, validate a package, or upload a build.

You do **not** need an API key for a local project audit.

### Step 1: Install the Skill

Open Terminal and run:

```sh
git clone https://github.com/Hubuguilai/app-store-connect-release.git app-store-connect-release-repo
mkdir -p "$HOME/.codex/skills/app-store-connect-release"
rsync -a app-store-connect-release-repo/app-store-connect-release/ \
  "$HOME/.codex/skills/app-store-connect-release/"
```

Confirm that installation succeeded:

```sh
test -f "$HOME/.codex/skills/app-store-connect-release/SKILL.md" \
  && echo "Skill installed successfully"
```

Expected result:

```text
Skill installed successfully
```

Start a new Codex task after installation so Codex can discover the Skill.

### Step 2: Open Your Xcode Project in Codex

Open the folder that contains your `.xcodeproj` or `.xcworkspace` in the Codex app.

For your first run, copy this prompt exactly:

```text
Use $app-store-connect-release to audit this Xcode project.
Read-only checks only. Do not archive, upload, or change any files.
```

Codex should report the discovered project or workspace, schemes, Bundle ID, team, platform, marketing version, build number, signing configuration, and missing prerequisites.

If this works, the Skill is installed correctly. You can stop here if you only wanted a local release audit.

### Step 3: Create an App Store Connect API Key

Skip this step if you only need local checks.

In App Store Connect, create an API key from the Users and Access / Integrations area. Record these three items:

1. **Key ID** — a short identifier for the key.
2. **Issuer ID** — the issuer identifier shown by App Store Connect.
3. **Private key file** — the downloaded `AuthKey_YOUR_KEY_ID.p8` file.

Apple normally allows the `.p8` file to be downloaded only once. Keep it outside your project and never commit it to Git.

Move the downloaded key to the standard local directory:

```sh
mkdir -p "$HOME/.appstoreconnect/private_keys"
mv "$HOME/Downloads/AuthKey_YOUR_KEY_ID.p8" \
  "$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
chmod 600 "$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

Replace `YOUR_KEY_ID` with the real Key ID before running the command.

### Step 4: Configure Credentials

Set the credentials for the current Terminal session:

```sh
export ASC_API_KEY_ID="YOUR_KEY_ID"
export ASC_API_ISSUER_ID="YOUR_ISSUER_ID"
export ASC_API_KEY_PATH="$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

These values identify the key file. Do not paste the contents of the `.p8` file into a command, chat, issue, or configuration file.

To make the variables available in future Terminal sessions, add the three `export` lines to `~/.zshrc`, then restart Terminal and Codex.

### Step 5: Test the Apple Connection Safely

Run this read-only authentication probe:

```sh
python3 "$HOME/.codex/skills/app-store-connect-release/scripts/asc_api_client.py" auth
```

Expected result:

```json
{
  "authenticated": true,
  "apps_returned": 1
}
```

`apps_returned` may be `0` when the key cannot access any apps. Authentication can still succeed, but you must verify the key role and app access before continuing.

### Step 6: Run the First Complete Read-Only Audit

Open your project folder in Codex and use:

```text
Use $app-store-connect-release to perform a complete release-readiness audit.
Query App Store Connect, but do not change metadata, screenshots, IAPs, files, signing assets, or builds.
Do not upload anything.
```

The report should clearly separate:

- local project checks;
- App Store Connect checks;
- warnings that need attention;
- portal actions that still require a human;
- actions that were deliberately not performed.

You now have a working installation. Continue only if you want to create or upload a release build.

## What Should I Ask Codex?

Use the prompt that matches your goal.

| Goal | Copy this prompt | Changes Apple? |
| --- | --- | --- |
| Check the project | `Use $app-store-connect-release to audit this project. Read only.` | No |
| Check Apple status | `Use $app-store-connect-release to inspect the current App Store Connect build and version status. Read only.` | No |
| Prepare locally | `Use $app-store-connect-release to prepare this release locally, but do not contact Apple or upload anything.` | No |
| Archive locally | `Use $app-store-connect-release to create an App Store archive. Do not upload it.` | Normally no |
| Validate with Apple | `Use $app-store-connect-release to validate the existing package with Apple. Do not upload it.` | Sends package for validation, not upload |
| Upload a build | `Use $app-store-connect-release to validate and upload this exact package. Stop before any review submission.` | Yes, after confirmation |
| Preview metadata | `Use $app-store-connect-release to preview App Store metadata differences. Do not apply them.` | No |
| Preview screenshots | `Use $app-store-connect-release to preview screenshot differences for en-US. Do not upload or replace anything.` | No |
| Inspect IAPs | `Use $app-store-connect-release to list the app's in-app purchases. Read only.` | No |

If you are unsure, add this sentence to any request:

```text
Show me the plan and perform read-only checks only.
```

## Release Workflow for Beginners

Treat release as five separate stages. Do not jump directly to upload.

### 1. Audit

```text
Use $app-store-connect-release to audit version 2.0.0. Read only.
```

Fix failed tests, signing problems, missing metadata, incorrect versions, and privacy issues before continuing.

### 2. Archive

```text
Use $app-store-connect-release to create a Release archive for version 2.0.0. Do not upload it.
```

This creates a local `.xcarchive`. It does not mean Apple has received the build.

### 3. Validate

```text
Use $app-store-connect-release to export and validate the new archive with Apple. Do not upload it.
```

Validation checks whether Apple accepts the package format, signing, and important release properties. A successful validation is still not an upload.

### 4. Upload

Only use this prompt after checking the version, build number, Bundle ID, and package path:

```text
Use $app-store-connect-release to upload the validated package for version 2.0.0 build 42.
Show me the exact package, Bundle ID, version, and build number before the final upload confirmation.
Do not submit the version for review.
```

The upload command requires `--confirm-upload`. Duplicate version/build uploads are blocked by default.

### 5. Check Processing and Finish in the Portal

```text
Use $app-store-connect-release to check whether version 2.0.0 build 42 finished processing. Read only.
```

Possible states include `PROCESSING`, `VALID`, and `INVALID`. A valid processed build is not the same as a version submitted for review.

The App Store Connect portal may still require agreements, pricing, tax and banking details, app privacy, export compliance, review information, build selection, IAP attachment, and final review submission.

## Manual Commands (Optional)

Most users can let Codex run these tools. Use the commands below when debugging or integrating CI.

Set a short variable for the installed scripts:

```sh
ASC_SKILL="$HOME/.codex/skills/app-store-connect-release"
```

### Discover the Project

Run this from the project folder:

```sh
python3 "$ASC_SKILL/scripts/discover_xcode_project.py" --root "$PWD" --json
```

If more than one scheme exists, add `--scheme MyApp`. If more than one container exists, add `--workspace MyApp.xcworkspace` or `--project MyApp.xcodeproj`.

### Check Prerequisites

```sh
python3 "$ASC_SKILL/scripts/check_release_prerequisites.py" \
  --project-root "$PWD" --scheme MyApp --platform iOS --require-api
```

Use `macOS`, `iOS`, `tvOS`, `watchOS`, or `visionOS` as appropriate.

### Inspect a Build Once

```sh
python3 "$ASC_SKILL/scripts/poll_build.py" \
  --bundle-id com.example.app --version 2.0.0 --build-number 42 --once --json
```

### Preview Metadata Changes

```sh
python3 "$ASC_SKILL/scripts/sync_metadata.py" \
  --metadata-root fastlane/metadata \
  --bundle-id com.example.app --version 2.0.0 --platform iOS
```

No metadata is written unless `--apply` is added.

### Preview Screenshot Changes

```sh
python3 "$ASC_SKILL/scripts/sync_screenshots.py" \
  --screenshots-root fastlane/screenshots \
  --manifest screenshots.json \
  --bundle-id com.example.app --version 2.0.0 \
  --platform iOS --locale en-US
```

No screenshot is uploaded unless `--apply` is added. Replacing an existing screenshot set requires all three switches: `--apply --replace --confirm-replace`.

### Inspect In-App Purchases

```sh
python3 "$ASC_SKILL/scripts/sync_iap.py" \
  --bundle-id com.example.app --json
```

This is read-only unless a desired-product manifest and `--apply` are supplied.

## Common Problems

### `ASC_API_ISSUER_ID is required`

The environment variables are missing from the current shell. Run the three `export` commands again, or restart Terminal after adding them to `~/.zshrc`.

### `App Store Connect key file was not found`

Check the exact filename and path:

```sh
ls -l "$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

The Key ID in the filename must match `ASC_API_KEY_ID`.

### `Could not uniquely discover an Xcode workspace/project`

Your repository contains multiple Xcode containers. Tell Codex which app to release, or pass an explicit `--workspace` or `--project` path.

### `A unique scheme was not discovered`

Run the discovery command, look at the `schemes` list, and pass `--scheme` with the intended shared scheme.

### `Validation blocked: App Store Connect already has version ... build ...`

Apple already has that version/build combination. Increase the build number. Do not use `--allow-duplicate` unless you understand why the duplicate check is being bypassed.

### `Archive does not exist`

Run the archive stage first, or pass the exact existing `.ipa` or `.pkg` with `--package`.

### Screenshot checksum conflict

The remote screenshot has the same filename but different contents. Preview the complete target set before using replacement. Replacement deletes existing screenshots and therefore requires explicit confirmation.

### Xcode asks for signing access

Unlock the login keychain and verify the distribution certificate and provisioning profile. The Skill does not enable provisioning updates unless `--allow-provisioning-updates` is explicitly supplied.

## Safety Rules

- Audits and synchronization commands are read-only unless `--apply` is supplied.
- Upload additionally requires `--confirm-upload`.
- Screenshot replacement requires `--apply --replace --confirm-replace`.
- Duplicate version/build uploads are blocked unless intentionally overridden.
- Provisioning updates require `--allow-provisioning-updates`.
- Private keys and signed upload URLs must never appear in reports, commits, issues, or screenshots.
- The tools do not submit a version for App Review or claim that portal-only work is complete.

## Supported Workflows

- iOS, iPadOS, macOS, watchOS, tvOS, and visionOS projects
- `.xcodeproj` and `.xcworkspace` discovery
- Xcode archive, export, Apple validation, and confirmed upload
- App Store Connect build discovery and processing polling
- Fastlane-style localized metadata validation and synchronization
- Screenshot validation, checksum diffing, upload, and guarded replacement
- In-app purchase discovery and product/localization synchronization
- GitHub Actions template for staged releases
- JSON output for CI and other automation

The Python tools use the standard library. JWT signing uses Ruby/OpenSSL, which is normally available in macOS developer environments.

## Update the Skill

From the cloned repository:

```sh
cd app-store-connect-release-repo
git pull
rsync -a app-store-connect-release/ \
  "$HOME/.codex/skills/app-store-connect-release/"
```

Start a new Codex task after updating.

## Run the Tests

```sh
cd app-store-connect-release-repo/app-store-connect-release
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The implementation has been tested against a real Xcode macOS app and live read-only App Store Connect endpoints for project discovery, prerequisite checks, build lookup, duplicate detection, localized metadata preview, screenshot reconciliation, and IAP discovery. No project-specific identifiers or credentials are included in this repository.

## Contributing

Issues and pull requests are welcome, especially reproducible fixtures for additional Xcode project layouts, App Store platforms, localization structures, and API response variants.

Never attach `.p8` files, signing assets, signed upload URLs, or private App Store Connect payloads to an issue or pull request.

## License

MIT
