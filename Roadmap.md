# Miniatured World Roadmap

This roadmap translates the project specification into development phases. It is intentionally coarse at V0.0; detailed scope, acceptance criteria, and release contracts must be decided through the OODA workflow.

## Version Policy

- Human-facing phase label: `V0.0`, `V0.1`, `V0.2`, ...
- OODA and release metadata should use v-prefixed semantic versions such as `v0.0.0`.
- `V0.0 / v0.0.0` is the initial project foundation baseline.

## V0.0: Project Foundation

Goal: create the minimum project skeleton needed for disciplined development.

Scope:

- repository folder structure
- README
- roadmap
- agent operating rules
- primary specification reference
- initial OODA baseline

Non-scope:

- runnable application
- input hook implementation
- UI implementation
- simulation implementation
- packaging and release automation

Exit criteria:

- project purpose and principles are visible from the repository root
- roadmap is aligned with the specification
- agent rules define how OODA is used
- future implementation work can be planned without guessing the project direction

## V0.1: Technical PoC

Goal: prove that the application can observe safe activity signals and run as a Windows resident app without disrupting the user.

Status: in progress. The first core foundation has been implemented locally; production Windows input acquisition and task tray behavior remain pending.

Candidate scope:

- Windows 11 desktop application shell
- PySide6 application bootstrap
- task tray residency
- keyboard activity categorization proof
- mouse activity aggregation proof
- privacy filter proof
- activity frame model
- minimal world view
- seeded simulation loop prototype
- evidence that raw input is not persisted

Key decisions:

- Windows input API choice
- low-level hook adoption or rejection
- activity aggregation interval
- Direct Interaction versus Ambient Input separation
- minimum privacy test strategy

## V0.2: Simulation Prototype

Goal: prove that abstract PC activity can generate a small emergent world.

Status: partially implemented locally. The project now has a deterministic simulation core, content catalog, app runtime state, activity provider boundary, discovery manager, and privacy-safe snapshot model. Deeper visual simulation and production UI remain pending.

Candidate scope:

- material definitions
- falling object or particle presentation
- grid or cellular simulation
- simple plant lifecycle
- one creature with finite-state behavior
- tendency and trait modifiers
- event rules
- rare phenomenon hook
- deterministic random provider

Key decisions:

- simulation update frequency
- maximum particle and creature budgets
- content definition format
- recipe/rule evaluation model

## V0.3: Product Prototype

Goal: turn the simulation into a usable desktop product shape.

Status: in progress locally. Runtime controls and PySide6 Window View screens now exist for World, Settings, and Discovery. Production task tray integration, Desktop View click-through behavior, and full visual QA remain pending.

Candidate scope:

- Window View
- Desktop View feasibility
- settings screen
- discovery screen
- pause and resume
- hide/show behavior
- basic notifications
- sound toggle
- atomic settings/discovery persistence
- error isolation by subsystem
- performance quality controls

Key decisions:

- click-through desktop window approach
- high-DPI behavior
- user data storage location
- discovery schema
- crash and recovery behavior

## V0.4: MVP Release Candidate

Goal: satisfy the specification's MVP acceptance criteria at release-candidate quality.

Candidate scope:

- privacy verification
- 8-hour stability test
- compatibility checks
- Windows installer candidate
- uninstall behavior
- user-facing documentation
- performance measurement
- accessibility pass
- release packaging

Key decisions:

- license
- distribution method
- installer technology
- support policy
- external communication policy

## V1.0: MVP Release

Goal: publish the first stable MVP once V0.4 release-candidate obligations are met.

Expected characteristics:

- safe-by-default activity observation
- non-disruptive desktop presence
- session-based world generation
- discovery persistence
- basic settings and privacy controls
- documented limitations
- reproducible build and release process

## Deferred Candidates

These are intentionally outside the first MVP unless later OODA decisions adopt them:

- advanced fragmentation physics
- complex creature AI
- large rare phenomenon catalog
- external content delivery
- paid content
- cloud sync
- detailed replay
- multiple simultaneous worlds
- advanced multi-monitor effects
