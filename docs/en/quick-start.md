# App Store Connect Release: Beginner Guide

[English](quick-start.md) | [简体中文](../zh-CN/quick-start.md) | [日本語](../ja/quick-start.md) | [Repository home](../../README.md)

This guide assumes you have never used an App Store Connect API key. Follow the steps in order. Start with read-only checks and stop before upload until you understand the report.

> Screens marked `SCHEMATIC` are instructional diagrams. Apple may adjust the portal layout; the stable field names and workflow are verified against Apple’s official documentation.

## Choose a Route

| Route | Result | API key required | Writes to Apple |
| --- | --- | --- | --- |
| A | Audit the local Xcode project | No | No |
| B | Query App Store Connect | Yes | No |
| C1 | Create a local Archive | No | No |
| C2 | Validate with Apple or upload | Yes | Upload only after confirmation |

New users should complete Route A first, then continue to Route B.

## Step 0: Check What You Need

- A Mac with Xcode installed.
- A folder containing an `.xcodeproj` or `.xcworkspace`.
- Codex with terminal access to that folder.
- For Route B or C2: access to the app in App Store Connect.
- For a team API key: an Account Holder or Admin account.

You do not need an API key for a local read-only audit.

## Step 1: Install the Skill

Open Terminal and run:

```sh
git clone https://github.com/Hubuguilai/app-store-connect-release.git app-store-connect-release-repo
mkdir -p "$HOME/.codex/skills/app-store-connect-release"
rsync -a app-store-connect-release-repo/app-store-connect-release/ \
  "$HOME/.codex/skills/app-store-connect-release/"
```

![Install the Skill](../assets/tutorial/03-install-skill-flow.png)

Verify the installation:

```sh
test -f "$HOME/.codex/skills/app-store-connect-release/SKILL.md" \
  && echo "Skill installed successfully"
```

Expected result:

```text
Skill installed successfully
```

Start a new Codex task after installation.

## Step 2: Run a Local Read-Only Audit

Open the folder containing your Xcode project in Codex. Copy this prompt:

```text
Use $app-store-connect-release to audit this Xcode project.
Read-only checks only. Do not archive, upload, or change any files.
```

Codex should report the project or workspace, scheme, Bundle ID, team, platform, version, build number, and signing configuration.

Success means:

- the Skill is detected;
- the intended Xcode container and scheme are found;
- no archive or upload command runs;
- missing prerequisites are listed clearly.

If this is all you need, stop here. Route A is complete.

## Step 3: Open the API Key Page

For App Store Connect queries, open:

```text
App Store Connect → Users and Access → Integrations
→ App Store Connect API → Team Keys
```

![App Store Connect API key page](../assets/tutorial/01-app-store-connect-api-key-page.png)

The numbered markers show:

1. Open **Integrations**.
2. Select **Team Keys**.
3. Copy the **Issuer ID**.
4. Click `+` to create a key.
5. The generated **Key ID** appears in the list.

If the API page displays **Request Access**, the Account Holder must request access first. Apple reviews these requests. If you cannot see Team Keys or the add button, ask the Account Holder or Admin to create the key.

## Step 4: Generate a Team API Key

Click `+` or **Generate API Key**.

![Generate API key schematic](../assets/tutorial/07-generate-api-key-schematic.png)

1. Enter a reference name, for example `Codex Release`.
2. Choose the least-privilege role that supports your intended work.
3. Click **Generate**.

Important:

- Apple says a team key requires Account Holder or Admin access.
- A team key applies across all apps in the account.
- The key name and access level cannot be edited after generation.
- If you need a different role later, revoke the key and create another one.

For initial setup, do not select a broader role merely to avoid understanding a permission error. Start with the smallest suitable role and increase it only when the required Apple operation proves it is necessary.

## Step 5: Download the `.p8` File Once

After generating the key, click its download link.

![Download API key schematic](../assets/tutorial/08-download-api-key-schematic.png)

1. Confirm the filename matches `AuthKey_<KEY_ID>.p8`.
2. Remember that the private key is available for download only once.
3. Click **Download** and store it securely.

Apple does not keep a downloadable copy. If the key is lost or compromised, revoke it and create a new key.

Never:

- paste the private-key contents into Codex or an issue;
- commit a `.p8` file;
- store it inside the Xcode project;
- send it by email or chat.

## Step 6: Store and Configure the Key

Replace `YOUR_KEY_ID` before running these commands:

```sh
mkdir -p "$HOME/.appstoreconnect/private_keys"
mv "$HOME/Downloads/AuthKey_YOUR_KEY_ID.p8" \
  "$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
chmod 600 "$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

Set the credentials for the current Terminal session:

```sh
export ASC_API_KEY_ID="YOUR_KEY_ID"
export ASC_API_ISSUER_ID="YOUR_ISSUER_ID"
export ASC_API_KEY_PATH="$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

![API key setup flow](../assets/tutorial/02-api-key-setup-flow.png)

Do not put the private-key contents in an environment variable. `ASC_API_KEY_PATH` must point to the file.

To reuse these values in future sessions, add the three `export` lines to `~/.zshrc`, then restart Terminal and Codex.

## Step 7: Test Authentication Safely

Run the read-only probe:

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

`apps_returned` can differ. If it is `0`, confirm that the key’s account and role can access the intended app.

You have now completed Route B setup.

## Step 8: Run the Complete Read-Only Audit

Open the project in Codex and copy:

```text
Use $app-store-connect-release to perform a complete release-readiness audit.
Query App Store Connect, but do not change metadata, screenshots, IAPs,
files, signing assets, or builds. Do not upload anything.
```

![Read-only audit result](../assets/tutorial/05-read-only-audit-result.png)

Check that the report shows:

- the expected project and scheme;
- the correct Bundle ID;
- the intended version and build number;
- successful API authentication;
- `UPLOAD: NOT RUN`.

Do not continue when Codex finds the wrong app, scheme, Bundle ID, version, or build number.

## Step 9: Understand the Release Stages

![Release workflow](../assets/tutorial/04-release-workflow.png)

1. **AUDIT**: inspect the project and Apple state.
2. **ARCHIVE**: create a local `.xcarchive`.
3. **VALIDATE**: ask Apple to validate the exported `.ipa` or `.pkg`.
4. **UPLOAD**: send the build only after confirmation.
5. **PROCESSING**: wait for Apple to process the build.
6. **VALID**: the processed build is selectable; it is not App Review approval.

Use one prompt per stage.

Archive without upload:

```text
Use $app-store-connect-release to create a Release archive.
Do not upload it and do not change provisioning unless required and approved.
```

Validate without upload:

```text
Use $app-store-connect-release to export and validate the new archive with Apple.
Do not upload it.
```

Check processing once:

```text
Use $app-store-connect-release to check the current build processing status.
Read only.
```

## Step 10: Upload Only After Reviewing the Target

Use this only when the audit and Apple validation have passed:

```text
Use $app-store-connect-release to upload the validated package.
Show the exact package path, Bundle ID, version, build number,
Apple validation result, and duplicate-build result before confirmation.
Do not submit the version for App Review.
```

![Upload confirmation](../assets/tutorial/06-upload-confirmation.png)

Before confirming, verify every value yourself:

- package filename and path;
- Bundle ID;
- marketing version;
- build number;
- Apple validation passed;
- no duplicate build was found.

Upload requires `--confirm-upload`. Uploading a build does not submit the app for review.

## Copy-and-Paste Prompts

Read-only project check:

```text
Use $app-store-connect-release to audit this project. Read only.
```

Read-only Apple status:

```text
Use $app-store-connect-release to inspect the App Store Connect version,
build, screenshot, metadata, and IAP status. Do not apply changes.
```

Preview metadata:

```text
Use $app-store-connect-release to preview localized metadata differences.
Do not apply them.
```

Preview one screenshot locale:

```text
Use $app-store-connect-release to preview screenshot differences for en-US.
Do not upload, delete, or replace anything.
```

Whenever unsure, add:

```text
Show the plan first and perform read-only checks only.
```

## Common Problems

### `ASC_API_ISSUER_ID is required`

Run the three `export` commands again in the current Terminal session. Restart Terminal and Codex if you added them to `~/.zshrc`.

### `App Store Connect key file was not found`

Check the exact path:

```sh
ls -l "$HOME/.appstoreconnect/private_keys/AuthKey_YOUR_KEY_ID.p8"
```

The filename’s Key ID must match `ASC_API_KEY_ID`.

### No `+` or Generate API Key button

Team keys require Account Holder or Admin access. The Account Holder may also need to request API access first.

### `Could not uniquely discover an Xcode workspace/project`

The repository contains multiple containers. Tell Codex which app to release, or pass an explicit workspace/project path.

### `A unique scheme was not discovered`

Ask Codex to list schemes, then select the intended shared scheme explicitly.

### Duplicate-build protection stopped the command

Increase the build number. Do not bypass the protection unless you have verified why Apple already has the same version/build.

### Xcode asks for signing permission

Unlock the login keychain and verify the certificate/profile. Provisioning updates remain disabled unless explicitly approved.

## Portal Work That Still Remains Manual

Depending on the app and account, App Store Connect may still require agreements, tax and banking information, pricing, territories, privacy answers, export compliance, age rating, review contact details, build selection, IAP attachment, and final App Review submission.

The Skill must report these items. It must not claim they are complete merely because a build was uploaded.

## Official Apple References

- [Get started with the App Store Connect API](https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api)
- [Creating API keys for the App Store Connect API](https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api)
- [Role permissions](https://developer.apple.com/help/app-store-connect/reference/account-management/role-permissions/)

---

[Back to repository home](../../README.md)
