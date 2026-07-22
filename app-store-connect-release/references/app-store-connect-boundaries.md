# App Store Connect Automation Boundaries

App Store Connect API automation is useful but does not remove Apple's account and review gates.

## Usually Automatable

- Authenticate with an API key and issuer ID.
- Read app, build, version, localization, IAP, and processing state.
- Upload a signed build package.
- Create or update API-supported metadata and IAP localization objects when the key role permits it.
- Upload supported screenshot assets through a maintained uploader.
- Create and update supported IAP product records when the product state and key role permit it.

## Often Requires Portal Or Account-Holder Action

- Creating the initial app record when the available API surface does not expose it.
- Accepting agreements and completing tax or banking information.
- Some app privacy, export compliance, age rating, pricing, and review-information fields.
- Attaching products to a version or selecting the final build where the project's API implementation does not support it.
- Price schedules, territory availability, subscription-group configuration, and some IAP review fields.
- Sandbox purchase testing and device-dependent QA.
- Submitting for review and interpreting Apple's review response.

The exact surface changes over time. Verify the current API endpoint and the repository's implementation before claiming that an action is automated. When an action is unavailable, produce a portal handoff with the object name, required value, dependency, and verification command.

## Safety Rules

- Treat upload and submission as external state changes.
- Require an explicit user request for upload; require a separate confirmation before final submission if the request is ambiguous.
- Never accept or invent an API private key in chat.
- Never mark a tracker item complete only because a local file exists. Mark it complete only after the Apple state is verified.
