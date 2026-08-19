# Reference Rebuild

Use the deterministic fallback order below:

```text
snippet -> package -> asset -> recreate
```

Try the next level only when the current level fails a gate. Record the reason for every rejected level.

Before choosing a delivery level for a live URL, read [source-preview.md](source-preview.md) and inspect the real trigger and visible states. Capture a transient clip or storyboard when it helps the user confirm the target. If the user supplied a sufficient video or animation asset, treat that as the visual reference and do not replace it with synthetic evidence.

Resolve the target platform before selecting a delivery level. Treat a Web source as behavioral reference only when the target is mobile. Accept its snippet or package only if the publisher explicitly supports the target runtime; otherwise continue to a compatible asset or platform-native recreation.

## Common gates

Require all applicable conditions:

- the current source exists and is accessible without bypassing controls;
- the intended use is allowed by current source or item-level terms;
- the material is compatible with the user's target stack;
- the material is compatible with the user's target platform and accessibility model;
- the material contains the behavior needed for the requested result;
- the result does not introduce an unaccepted major dependency or runtime;
- the result can meet accessibility and performance constraints.

## Level 1: snippet

Use only a code block, download, or Copy action intentionally exposed by the publisher. Verify that required CSS, JavaScript, assets, and dependencies are present. Reclassify a snippet that fundamentally depends on a published package as `package`.

Do not translate CSS, DOM, or browser JavaScript into a mobile delivery by relabeling it. Reject the snippet level when the target runtime differs.

Do not extract minified bundles, private API responses, hidden page scripts, or arbitrary DOM implementation code.

## Level 2: package

Use the publisher's documented package or component API. Provide the installation command, import, smallest working usage, version assumptions, and required peer dependencies. Do not copy the package's internal source.

Require explicit support for the target framework. A React package is not a React Native package; a Web package is not a SwiftUI, Compose, or Flutter package.

Generate commands by default. Execute installation only when the user asks to integrate into the scoped project.

## Level 3: asset

Use only an explicitly downloadable asset with compatible format and item-level rights, such as Lottie JSON or a Rive file. State the runtime and dependency needed to render it.

Skip this level when the target cannot accept the asset runtime, when downloading is restricted, or when the license remains unclear.

## Level 4: recreate

Analyze the reference as motion behavior rather than source code:

- target hierarchy and visual states;
- triggers and interruption behavior;
- property channels and paths;
- duration, delay, easing, spring character, and staggering;
- loops, direction changes, and reduced-motion behavior.

Implement an equivalent from first principles. Do not copy non-public source, protected brand assets, or distinctive proprietary content. Label the delivery `recreate`.

Use platform-native primitives for the selected target and preserve its interruption, gesture, lifecycle, and reduced-motion semantics.

## Provenance record

Return this with the delivery:

```yaml
selected_mode: snippet | package | asset | recreate
source:
  url: current source URL
  license_status: verified | restricted | unclear
fallbacks:
  snippet: {status: selected | rejected | unavailable, reason: "..."}
  package: {status: selected | rejected | unavailable, reason: "..."}
  asset: {status: selected | rejected | unavailable, reason: "..."}
delivery:
  target_platform: web | ios | android | cross-platform
  dependencies: []
  files_changed: []
  verification: []
```

Do not call the work complete merely because code was produced. Verify the target behavior in the actual runtime when the environment allows it.
