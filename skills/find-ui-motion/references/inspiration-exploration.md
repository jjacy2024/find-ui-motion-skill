# Inspiration Exploration

Use a semi-structured adaptive conversation. Fix the decision dimensions, question rules, and exit conditions; adapt the order, wording, and options to the user's context.

## Motion Brief dimensions

Track these fields without turning them into a questionnaire:

```yaml
scene:
  target: what moves
  trigger: when it moves
  purpose: why motion is needed
experience:
  feeling: desired perception
  intensity: restrained | balanced | expressive
  continuity: spatial | state | information
  avoid: unwanted qualities
implementation:
  platform: web | ios | android | cross-platform | unknown
  stack: css | javascript | react | vue | swiftui | compose | flutter | react-native | lottie | rive | unknown
  constraints: performance, accessibility, dependencies, browser or OS support
```

Prioritize `scene` and `experience`. Defer stack, duration, and easing parameters until a direction is selected unless they are already known.

## Conversation loop

For each round:

1. Restate the current understanding in one sentence.
2. Select the unresolved dimension whose answer would most change the candidates.
3. Ask at most one main question.
4. Offer 2-3 context-specific contrast directions and allow a free-form answer.
5. Update the brief with `confirmed`, `inferred`, and `unresolved` fields.
6. Show provisional directions as soon as they are useful; do not wait for a complete brief.

Prefer questions such as "more reassuring or more celebratory?" over parameter questions such as "which easing curve?". If the user remains unsure, ask what they most want to avoid.

## Exit conditions

Stop asking and produce candidate directions when any condition is true:

- the user selects a direction;
- three materially different candidates can be formed;
- the user asks to see examples or asks the agent to decide;
- three exploration rounds have completed;
- the user supplies a reference, which transitions to reference rebuild.

When three rounds end without convergence, use restrained, balanced, and expressive variants of the best-understood idea.

When the exit condition is a request to see examples, stop the questionnaire. A generic request to see examples does not authorize video-case search. Read [retrieval-ladder.md](retrieval-ladder.md), exhaust its local stages, and prioritize code-backed or runtime-backed cases that can be implemented on the target platform. Use `quick_fit=strong | usable` for the quick list; style and feeling preferences rank candidates without becoming all-keyword requirements. Follow `external_search.decision`: skip external work for `skip`, show local results and ask before `offer`, and use a labeled bounded Web supplement only for `required`. Keep that supplement code-first while `video_case_search_authorized=false`. Resolve concrete item links and show exactly eight eligible sparse quick links by default or at most ten when explicitly requested. Reduce below eight only when fewer unique, relevant, accessible code-implementable cases satisfy the current brief; return every eligible remainder and state the shortfall. Ask whether the user wants a separately labeled video supplement only when that verified code-first pool is insufficient, and do not start it before confirmation. Then continue through [visual-deep-match.md](visual-deep-match.md) unless the user asks for quick results only. Read [source-preview.md](source-preview.md) only when capture or explicit side-by-side comparison is needed. Do not respond with text-only cards or generic source-labeled shapes when real item links are available.

## Exploration output

Return 2-3 direction cards. Each card must contain:

- a memorable name and one-sentence intent;
- target, trigger, and motion channels;
- timing character, easing character, and orchestration;
- where the direction works well;
- the main risk or reason to reject it;
- local search terms for the next step.

After selection, keep a compact Motion Brief internally and transition to exact search. Show it only when the user asks for technical detail. Do not search every website during the discussion phase.
