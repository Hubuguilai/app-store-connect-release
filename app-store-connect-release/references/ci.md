# CI Usage

The template at `assets/github-actions/app-store-connect-release.yml` assumes the Skill directory is available inside the checked-out repository at `.codex/skills/app-store-connect-release`. Copy the Skill into that path or adapt `SKILL_DIR` to the installation path used by the runner.

Configure these GitHub values:

- Secret `ASC_API_KEY_ID`.
- Secret `ASC_API_ISSUER_ID`.
- Secret `ASC_API_KEY_P8_B64`, containing the base64-encoded contents of the private key file.
- Repository variable `APP_SCHEME` when the project has more than one scheme.
- Repository variable `APP_PLATFORM`, such as `macOS` or `iOS`.

Keep signing certificates and provisioning profiles in the runner's encrypted secret store. The workflow deliberately separates archive, validation, and upload. Require a human-controlled `confirm_upload` input for upload jobs and keep the `validate` mode as the default.

The `allow_provisioning_updates` input is also off by default. Enable it only when the runner is intentionally allowed to create or update signing assets in the Apple developer account.
