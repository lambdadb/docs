# Documentation guidance

## Roadmap and changelog

Apply these rules when editing `guides/get-started/roadmap-changelog.mdx` or
adding documentation for a new feature, tool, or integration.

### Changelog scope

- Include new user-facing capabilities, tools, and integrations; significant
  performance, pricing, or limit changes; and compatibility changes that require
  users to take action. Initial SDK releases qualify as new integrations.
- Keep routine bug fixes, SDK/package version bumps, internal implementation
  work, and maintenance details in the relevant repository's release notes.
  Include a fix here only when its user impact meets the criteria above.
- Group entries by release month. Describe the capability or user benefit in one
  concise sentence with a link to the relevant guide. Add a short availability
  note only when useful. Avoid version lists and implementation details.
- Consolidate API, SDK, and tool support for the same feature into one entry
  unless they introduce independently meaningful capabilities.
- Verify public availability and release timing before announcing a release.
  Implementation completion, PR merge, and public release are distinct events;
  a dist-tag name alone does not establish a stable release. Do not use the date
  a guide was written as the feature's release date. If evidence is incomplete,
  leave the release unannounced and describe the gap in the PR.

### Roadmap scope

- Include only agreed, unreleased product plans. Do not infer commitments from
  implementation work or add speculative delivery dates.
- When a capability ships, remove or revise its roadmap entry and record the
  verified release in the changelog. Check the page description for stale plans.

### Keep release records complete

- When adding or substantially updating a feature, tool, or integration guide,
  check whether the change warrants a changelog entry and whether related roadmap
  items are complete. Do not add entries for every documentation edit.
- Update `Last updated` when changing the page's visible content. Preserve the
  release months of historical milestones and verify links to supporting guides.
