# Miniatured World

Miniatured World is a Windows desktop sandbox application concept where ordinary PC activity shapes a small, session-based world.

The current working product name in the specification is **Keyboard Garden**.

## Concept

普段のPC活動が、今日だけの小さな世界を作る。

The application observes abstract activity characteristics such as keyboard category volume, pointer movement intensity, click activity, scroll activity, rhythm, and idle time. It must not use typed content itself as game content.

## Project Status

Current project baseline: **V0.0 / v0.0.0**

Current implementation target: **V0.4 / v0.4.0 PySide6 product screens**

V0.0 is the project foundation phase. The purpose of this phase is to establish repository structure, project documents, agent operating rules, and the first development direction before implementation begins.

V0.4 introduces the first local runnable core, app runtime foundation, runtime command surface, and PySide6 Window View with World, Settings, and Discovery tabs. It does not yet include production Windows global input hooks, production task tray behavior, click-through Desktop View, installer packaging, or a formal public release.

## Core Product Principles

- **Activity, not Content**: use activity characteristics, not typed strings or raw input content.
- **Privacy by Design**: do not persist raw keyboard input, key sequences, mouse coordinates, window titles, screen captures, or clipboard content.
- **Ambient First**: the app must not interrupt ordinary PC work or gameplay.
- **Ephemeral World**: each application start creates a new world by default.
- **Persistent Discovery**: the world disappears, but discovered plants, creatures, and phenomena can remain.
- **Emergent, not Scripted**: activity changes conditions, and the world emerges from simulation rules.
- **Deterministic Core**: seed, tendency, traits, and activity frames should reproduce results where practical.
- **Content Driven**: tendencies, materials, plants, creatures, recipes, events, and phenomena should be data-driven.

## Initial Target

- OS: Windows 11 64-bit
- Planned language/runtime: Python
- Planned UI framework: PySide6
- Initial app shape: desktop/window/tray resident app
- Initial simulation direction: falling objects, grid or cellular simulation, plants, one creature, events, and discovery persistence

## Repository Layout

```text
assets/                 Visual/audio/source assets placeholder
config/                 Project and local configuration templates
docs/                   Planning, requirements, ADRs, and design notes
docs/adr/               Architecture Decision Records
scripts/                Developer utility scripts
src/miniatured_world/   Application source package
tests/unit/             Unit tests
tests/integration/      Integration tests
```

## Local Development

Run tests:

```powershell
python -m pytest
```

Run a privacy-safe smoke simulation without UI:

```powershell
$env:PYTHONPATH='src'
python -m miniatured_world --no-ui --frames 5
```

If PySide6 is installed, the default entry point starts the Qt Window View:

```powershell
$env:PYTHONPATH='src'
python -m miniatured_world
```

The current application entry point uses generated demo activity only. Real Windows activity acquisition remains a later PoC decision.

## Primary Specification

The current source specification is:

- [PC活動連動型デスクトップ箱庭アプリ 企画・要求仕様書 v0.1](docs/PC活動連動型デスクトップ箱庭アプリ%20企画・要求仕様書%20v0.1.md)

When implementation choices conflict with this README, the specification and project OODA decisions take precedence.

## Development Method

This project is developed through the OODA workflow:

1. Observe: collect evidence without changing project files.
2. Orient: interpret evidence and update planning-facing documents when appropriate.
3. Decide: define scope, acceptance criteria, and release contract.
4. Act: implement, verify, release, and record evidence.

See [AGENTS.md](AGENTS.md) for project-specific agent rules.

## Privacy Baseline

The following must not be persisted:

- raw keyboard events
- typed strings
- key sequences
- mouse absolute coordinates
- mouse movement trails
- click coordinates
- target application names
- window titles
- screen captures
- clipboard content

Any feature that weakens this baseline requires an explicit OODA decision before implementation.

## Implemented Core Surface

The current core includes:

- sanitized activity events
- keyboard category filtering
- pointer delta aggregation
- Direct Interaction exclusion from Ambient Activity
- normalized activity frames
- bundled data-driven content definitions
- seeded world session creation
- material generation
- simple grid settling simulation
- plant growth
- one creature behavior loop
- event and rare phenomenon hooks
- atomic JSON settings and discovery persistence
- activity provider abstraction
- runtime pause/resume and activity collection state
- privacy-safe UI snapshot model
- discovery manager
- grouped settings model
- runtime commands for show/hide, pause/resume, activity collection, mute, and exit
- PySide6 Window View with World, Settings, and Discovery tabs
- Qt smoke tests using offscreen construction
