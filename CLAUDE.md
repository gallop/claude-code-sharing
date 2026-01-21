# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a sharing repository for Claude Code configurations. The repository is currently in its initial state with placeholder directories ready to be populated with content.

## Repository Structure

```
claude-code-sharing/
├── .claude/                  # Claude Code configuration
│   └── settings.local.json   # Local Claude permissions settings
├── agents/                   # Agent configurations (currently empty)
├── docs/                     # Documentation (currently empty)
├── notify/                   # Notification configurations (currently empty)
└── skills/                   # Skill definitions (currently empty)
```

## Current State

This repository is currently empty/placeholder. All directories (`agents/`, `docs/`, `notify/`, `skills/`) are intended to be populated with Claude Code related content but contain no files yet.

## Claude Configuration

The `.claude/settings.local.json` file currently grants Bash permissions to all directories:

```json
{
  "permissions": {
    "allow": [
      "Bash(dir:*)"
    ]
  }
}
```

## Development Notes

- No build system, package manager, or testing framework is currently configured
- This repository does not yet contain source code - it is a template/skeleton structure
