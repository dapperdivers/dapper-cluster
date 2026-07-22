---
name: validate-recyclarr
description: Validate or update kubernetes/apps/media/recyclarr/app/config/recyclarr.yml against current recyclarr.dev docs and TRaSH guides. Use when editing recyclarr config, adding a *arr instance to it, after a recyclarr major-version bump, or when the sync CronJob logs deprecation/unknown-template errors.
allowed-tools: Read, WebFetch, WebSearch, Grep, Glob
---

# Recyclarr config validation

Config: `kubernetes/apps/media/recyclarr/app/config/recyclarr.yml` — instances
`sonarr`, `sonarr-uhd`, `radarr`, `radarr-uhd`. Config was migrated to the v8
format (2026-03); don't reintroduce pre-v8 syntax.

## Process

1. Read the config; note templates, `trash_ids`, quality profiles per instance.
2. Verify against the live docs (they change often — never validate from memory):
   - Config reference: <https://recyclarr.dev/wiki/yaml/config-reference/>
     (subpages: `quality-definition/`, `custom-formats/`, `media-naming/`,
     `quality-profiles/`, `include/`)
   - Template/trash_id catalogs: <https://recyclarr.dev/wiki/guide-configs/sonarr/>
     and `.../radarr/`
3. Check each: `include.template` names exist; `trash_ids` current (not
   deprecated/renamed); `quality_definition.type` valid (`series`/`movie`/`anime`);
   `media_naming` options valid for the app (Sonarr and Radarr differ); profile
   names match what the templates create.
4. Also WebSearch recyclarr release notes for breaking changes since the pinned
   image version (Renovate bumps the image without checking config compat).

## Report

Per instance: what's valid, what's deprecated/broken (with doc link), and any
newer recommended templates/custom formats worth adopting. Severity-ordered.
