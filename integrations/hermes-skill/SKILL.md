---
name: artifact-viewer
description: Create and publish self-contained interactive HTML artifacts when Discord or chat cannot render them natively. Use for dashboards, visual explainers, diagrams, lesson pages, reports, calculators, timelines, and interactive demos that should be shared as a browser link.
---

# Artifact Viewer

Turn browser-native output into an unlisted HTTPS link that works from Discord.

## Workflow

1. Decide whether an artifact materially improves the answer. Use one for interactive, visual, spatial, data-rich, or reusable output; do not turn ordinary prose into a web page for vanity.
2. Create one self-contained UTF-8 `.html` file. Put CSS and JavaScript inline. External HTTPS libraries are allowed when genuinely useful, but prefer no dependency for durable artifacts.
3. Make it responsive and usable on a phone first. Include a useful `<title>`, semantic HTML, accessible contrast, keyboard support for controls, and clear empty/error states.
4. Validate before publishing:
   - parse or inspect the HTML;
   - run any project tests;
   - open locally in a browser when interaction or layout matters;
   - check browser console errors.
5. Call `artifact_viewer` with `action="publish"`, the absolute HTML path, a precise title, a short description, useful tags, and a source label.
6. Open the returned URL and verify the deployed artifact—not merely the local file. Return the HTTPS URL to the user.

## Tool examples

Publish:

```json
{
  "action": "publish",
  "path": "/absolute/path/report.html",
  "title": "German A1 Progress",
  "description": "Current strengths, gaps, and learning route.",
  "tags": ["german", "learning"],
  "source": "language-teacher"
}
```

List recent artifacts:

```json
{"action": "list", "limit": 20}
```

Delete:

```json
{"action": "delete", "artifact_id": "the-returned-id"}
```

## Security boundary

- Published links are unlisted, not authenticated. Anyone holding a link can view it. Never publish secrets, credentials, private keys, raw `.env` content, or unnecessary personal data.
- The service only accepts `.html`/`.htm` files up to 2 MB.
- Artifacts run inside an iframe sandbox without `allow-same-origin` or top-navigation privileges. Do not weaken that boundary to make an artifact work; redesign the artifact instead.
- The publish API token stays in the active Hermes profile's protected secret file. Never copy it into an artifact or response.
- Prefer immutable republishing: publish a new artifact when the content changes, then share the new link. Delete stale sensitive artifacts explicitly.

## Fallback

If the plugin tool is unavailable in the current session, load this skill and use its local publisher script or invoke the plugin handler from the active profile. Do not expose the bearer token on the command line or in logs.

## Completion gate

An artifact task is complete only when the public HTTPS URL returns 200, the rendered content is visible inside the viewer, expected interactions work, and the browser console has no relevant errors.
