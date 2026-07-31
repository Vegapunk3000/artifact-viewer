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

## Visual explanation pass

Before treating a visual artifact as finished, inspect each major section and ask: **would a diagram, simulation, matrix, timeline, or controlled motion communicate this more clearly than paragraphs alone?** Add visual treatment only where it carries information.

Use this hierarchy:

- **Architecture / systems:** show ownership, boundaries, and communication paths with labeled SVG or HTML diagrams. For important flows, let the user select a scenario and animate a small packet through the real path (for example: user message → control plane → tenant runtime → helper profile → provider → persisted result).
- **Competitive landscapes:** use a capability matrix or positioned map when comparison is central. Add restrained competitor wordmarks/marks or source-linked visual references where they improve recognition; never turn the page into a logo wall.
- **Processes / lifecycles:** use timelines, step sequences, or state transitions when order matters.
- **Quantitative sections:** use a chart, equation, or proportion bar when it exposes a relationship that prose hides.
- **Narrative / principles:** keep them typographic. Not every paragraph needs a component.

Motion rules:

- Use motion to reveal causality, sequence, state, or emphasis—not to decorate empty space.
- One orchestrated animation is better than many unrelated effects.
- Anime.js is allowed for meaningful interaction or staged flow animation. For self-contained artifacts, bundle the minified library inline or use CSS/vanilla JS when that is enough; do not create a fragile CDN dependency by default.
- Every animation must have a static readable state, keyboard-accessible controls, and a `prefers-reduced-motion` fallback.
- Do not respond to a request for richer visuals by covering the document in cards, pills, gradients, or looping motion. Preserve long-form reading measure and let each visual earn its space.

Verify the visual pass in a browser at desktop and mobile widths. Exercise every diagram control and confirm that motion changes a meaningful state rather than only toggling a class.

## Security boundary

- Published links are unlisted, not authenticated. Anyone holding a link can view it. Never publish secrets, credentials, private keys, raw `.env` content, or unnecessary personal data.
- The service only accepts `.html`/`.htm` files up to 2 MB.
- Public artifact links under `/a/{id}` serve the HTML directly with document-level CSP sandboxing and cannot be embedded; use `/preview/{id}` only when you explicitly need the legacy metadata/iframe shell.
- The publish API token stays in the active Hermes profile's protected secret file. Never copy it into an artifact or response.
- Prefer immutable republishing: publish a new artifact when the content changes, then share the new link. Delete stale sensitive artifacts explicitly.

## Fallback

If the plugin tool is unavailable in the current session, load this skill and use its local publisher script or invoke the plugin handler from the active profile. Do not expose the bearer token on the command line or in logs.

## Completion gate

An artifact task is complete only when the public HTTPS URL returns 200, the rendered content is visible inside the viewer, expected interactions work, and the browser console has no relevant errors.
