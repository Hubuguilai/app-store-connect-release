# Metadata And Screenshot Checks

Before uploading store content, inspect every locale and device family represented by the target version.

Check:

- locale identifiers match the App Store Connect locale names;
- title, subtitle, keyword, description, and release-note limits are respected;
- translations describe the actual shipped behavior and do not promise unavailable features;
- URLs are reachable over HTTPS and point to the intended support and privacy pages;
- screenshots use the required pixel dimensions, file type, and device family;
- screenshots contain no private clipboard data, personal accounts, API keys, customer data, or debug overlays;
- screenshots match the submitted build and do not show a different product name or version;
- review notes explain any permissions, login steps, test accounts, or non-obvious interaction required by the app.

Keep source copy and generated upload files separate. Preserve the original asset filenames and locale mapping so a failed upload can be corrected without regenerating unrelated locales.

## Metadata Inputs

`sync_metadata.py` accepts either a Fastlane metadata directory or a JSON manifest, but not both in one invocation.

Fastlane fields map as follows:

| Local file | App Store Connect field |
| --- | --- |
| `name.txt` | app info localization `name` |
| `subtitle.txt` | app info localization `subtitle` |
| `description.txt` | version localization `description` |
| `keywords.txt` | version localization `keywords` |
| `promotional_text.txt` | version localization `promotionalText` |
| `release_notes.txt` | version localization `releaseNotes` |
| `support_url.txt` | version localization `supportUrl` |
| `marketing_url.txt` | version localization `marketingUrl` |
| `privacy_url.txt` | app-level `privacyPolicyUrl` |

The privacy policy URL is app-level in this workflow. Prefer a root-level `privacy_url.txt` or `--privacy-url`; a single identical locale value is accepted as a fallback. Conflicting locale privacy URLs are not silently selected.

The JSON form is:

```json
{
  "privacy_url": "https://example.com/privacy",
  "localizations": {
    "en-US": {
      "name": "Example App",
      "subtitle": "A focused utility",
      "description": "A complete description.",
      "keywords": "utility,productivity",
      "release_notes": "Bug fixes and improvements.",
      "support_url": "https://example.com/support",
      "marketing_url": "https://example.com"
    }
  }
}
```

Run the local validator before `sync_metadata.py`. The synchronizer creates or patches only fields present in the source and does not delete remote fields or locales that are absent locally.

## Screenshot Manifest

The simplest screenshot manifest reuses the validator's locale/scene format:

```json
{
  "display_type": "APP_DESKTOP",
  "locales": ["en-US", "ja"],
  "scenes": [
    {"id": "01", "filename": "{locale}-01.png"},
    {"id": "02", "filename": "{locale}-02.png"}
  ]
}
```

For different device families or different file lists per locale, use explicit sets:

```json
{
  "sets": [
    {"locale": "en-US", "display_type": "APP_DESKTOP", "files": ["en-US-01.png", "en-US-02.png"]},
    {"locale": "ja", "display_type": "APP_DESKTOP", "files": ["ja-01.png", "ja-02.png"]}
  ]
}
```

Files are resolved below `--screenshots-root/<locale>/`. The uploader calculates the file size and checksum, registers the screenshot with Apple, uploads bytes using the signed operations returned by Apple, and confirms the resource. Signed upload URLs are never printed in reports.
