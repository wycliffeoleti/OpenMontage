# Content Creator integration v1

This directory is a private-production overlay owned for the Content Creator consumer. It is not presented as generic OpenMontage core.

Public contracts:

- integration version: `1.0.0`
- composition IDs: `ExplainerStory`, `ExplainerVertical`
- validated portrait cuts: `hero_title`, `callout`, `terminal_scene`
- story producer shape: `beats`, `captions`, `audio`, optional presenter, attribution, and outro fields

The overlay preserves OpenMontage's upstream notices and AGPL-3.0 license. Inputs are treated as trusted local render props; exposing rendering to untrusted callers requires filesystem/network allowlists and process isolation.
