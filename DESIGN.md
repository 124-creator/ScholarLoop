# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-06-21
- Primary product surfaces:
  - `index.html`: GitHub Pages public-safe flagship demo.
  - `README.md`: repository-level project proof.
  - `docs/demo/README.md`: demo boundary and verification notes.
- Evidence reviewed:
  - verified plan/report: click-to-verify demo, span fidelity, trail fidelity.
  - flagship plan: flagship demo direction, deterministic SVG graph, design-token-driven visual upgrade.
  - Public reports: `reports/m120/public_validation_summary.json`.

## Brand
- Personality: high-trust, research-grade, competition-ready, sharp but not noisy.
- Trust signals: verified metrics, source-span equality rule, public-safe boundary, visible handoff artifacts.
- Avoid: fake live search, unsupported claims, generic AI-agent hype, single-color dashboard monotony.

## Product goals
- Goals:
  - Make the AI competition direction obvious in the first screen.
  - Show that ScholarLoop is a trusted academic search and evidence-chain agent, not only a ranking list.
  - Translate local verified artifacts into a public-safe recruiter-facing demo.
- Non-goals:
  - Do not expose private corpora, secrets, raw caches, or unpublished competition data.
  - Do not present optional realtime search as verified production behavior.
- Success signals:
  - Visitor can identify official scoring logic, Search Loop, Trust Loop, and verification metrics within 60 seconds.
  - Page contains zero fabricated live-service claims.

## Personas and jobs
- Primary personas:
  - Internship recruiter / hiring manager for AI Agent, RAG, LLM application engineering.
  - Competition reviewer interested in structured display and evidence traceability.
- User jobs:
  - Understand what problem the project solves.
  - Verify that numbers and claims are grounded.
  - See whether the candidate can build polished demos independently.
- Key contexts of use:
  - GitHub profile review.
  - Resume link click-through.
  - Interview screen sharing.

## Information architecture
- Primary navigation:
  - 比赛特点 -> 双 Loop -> 交互 Demo -> 点即核验 -> 验证指标 -> GitHub.
- Core routes/screens:
  - Single static `index.html` page.
- Content hierarchy:
  - Hero: trusted paper search agent.
  - Score board: F1 / efficiency / structure / expert review.
  - Loop architecture: Search Loop + Trust Loop.
  - Interaction: query, steps, handoff artifact.
  - Verification: clickable source-span proof.
  - Metrics and honest boundary.

## Design principles
- Principle 1: Every beautiful visual element must map to a verified project claim or competition requirement.
- Principle 2: Color encodes meaning: retrieval blue, trust green, efficiency amber, risk/claim rose, competition violet.
- Tradeoffs:
  - Static public-safe page is preferred over fake live network search.
  - Inline CSS/JS is acceptable to keep GitHub Pages deployment simple and dependency-free.

## Visual language
- Color:
  - Background: deep navy aurora gradient.
  - Search/retrieval: cyan to blue.
  - Trust/evidence: green to mint.
  - Efficiency/cost: amber to orange.
  - Expert/structure: violet to fuchsia.
  - Risk/final claim: rose.
- Typography:
  - System UI + Microsoft YaHei / PingFang SC for Chinese readability.
  - Large compressed hero typography for portfolio impact.
- Spacing/layout rhythm:
  - 1200px max width, 18-22px card gaps, generous hero padding.
- Shape/radius/elevation:
  - Rounded glass panels, 24-30px radius, soft shadows, thin borders.
- Motion:
  - Slow aurora background, hover lift, graph node glow; no layout jitter.
- Imagery/iconography:
  - SVG graph and simple line icon only; no stock images.

## Components
- Existing components to reuse:
  - Static HTML cards, evidence buttons, SVG graph, metric tiles.
- New/changed components:
  - Competition score board.
  - Dual-loop stage cards.
  - Handoff artifact timeline.
  - Stronger metric grid and honest boundary card.
- Variants and states:
  - Active step, active evidence field, graph node hover, input focus.
- Token/component ownership:
  - CSS variables in `index.html` root own all colors and spacing.

## Accessibility
- Target standard: practical WCAG AA contrast where possible.
- Keyboard/focus behavior:
  - Native buttons/links are used for interaction.
- Contrast/readability:
  - Dark background with high-contrast white/blue/green text.
- Screen-reader semantics:
  - Sections, buttons, links, SVG role labels.
- Reduced motion and sensory considerations:
  - Motion is decorative and slow; no flashing effects.

## Responsive behavior
- Supported breakpoints/devices:
  - Desktop portfolio view, tablet, mobile.
- Layout adaptations:
  - Two-column hero/loops/demo collapse to one column below 960px.
  - Metric grid collapses to two columns, then one column.
- Touch/hover differences:
  - Buttons are large enough for touch; hover is decorative, not required.

## Interaction states
- Loading:
  - Public static page simulates handoff switching only; no external loading.
- Empty:
  - Query field has a default example.
- Error:
  - Public-safe boundary explains why live private search is not exposed.
- Success:
  - Active step updates handoff artifact text.
- Disabled:
  - Not used.
- Offline/slow network:
  - Entire demo works as a static page after load.

## Content voice
- Tone:
  - Direct, evidence-first, competition-aware, recruiter-readable.
- Terminology:
  - Use Search Loop, Trust Loop, evidence card, source span, public-safe, mismatch = 0.
- Microcopy rules:
  - Avoid vague words like “革命性” or “顶尖” without evidence.
  - Pair every number with its source or boundary.

## Implementation constraints
- Framework/styling system:
  - Single static HTML file, inline CSS/JS, no frontend framework.
- Design-token constraints:
  - Colors should come from `:root` variables.
- Performance constraints:
  - No remote fonts, no heavy images, no live API calls.
- Compatibility constraints:
  - GitHub Pages static hosting.
- Test/screenshot expectations:
  - `pytest` should assert core content, metrics, public-safe boundary, and no mojibake.
  - Render screenshot after visual changes.

## Open questions
- [ ] If flagship realtime `/studio` becomes verified later, decide whether public demo should expose a separate “realtime non-verified” mode.
