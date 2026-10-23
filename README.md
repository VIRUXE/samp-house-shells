# samp-house-shells

Making SA-MP's enterable house shells look like they belong in San Andreas.

The SA-MP client ships a set of house models in `SAMP\SAMP.img`: an exterior that reuses a vanilla house's
textures plus a separate interior, for LS, SF and LV.

| ids | exteriors | interiors |
|---|---|---|
| 19489–19496 | `sfhouse1`–`sfhouse4` | `sfhouse1int`–`sfhouse4int` |
| 19497–19504 | `lvhouse1`–`lvhouse4` | `lvhouse1int`–`lvhouse4int` |
| 19505–19512 | `lshouse1`–`lshouse4` | `lshouse1int`–`lshouse4int` |

Servers use them in place of the solid vanilla houses so that players can walk in. Next to the vanilla city they look
out of place. This repo holds the tooling, the reworked models and before/after screenshots. The goal is replacement
DFF/TXD files that any SA-MP or MTA:SA server can use as a drop-in.

## What is wrong (before)

| | noon | midnight |
|---|---|---|
| LS `lshouse1` exterior | ![](screenshots/before/ls-ganton-lshouse1-exterior-noon.png) | ![](screenshots/before/ls-ganton-lshouse1-exterior-midnight.png) |
| LS `lshouse1int` interior | ![](screenshots/before/ls-ganton-lshouse1-interior-noon.png) | ![](screenshots/before/ls-ganton-lshouse1-interior-midnight.png) |
| SF `sfhouse2` exterior | ![](screenshots/before/sf-sfhouse2-exterior-noon.png) | ![](screenshots/before/sf-sfhouse2-exterior-midnight.png) |
| LV `lvhouse1` exterior | ![](screenshots/before/lv-lvhouse1-exterior-noon.png) | ![](screenshots/before/lv-lvhouse1-exterior-midnight.png) |

- **Interiors have no baked lighting.** The `*int` DFFs (and SA-MP's `wall0xx` building pieces) have no vertex colours
  and no night colours (geometry flags `0x10036`, no prelit `0x08` bit). They stay as bright at midnight as at noon
  while everything around them darkens. The exteriors do have both.
- **The windows are flat panes.** They read as grey boards by day and glow white at night.
- **There is no ceiling from inside.** The interior has none and the exterior roof is single-sided. This was seen in
  Ariane and has not yet been confirmed in-game.
- **Every interior uses the same `all_walls` texture set**, whatever the district.
- **There are no LOD models**, so the shells pop in at their 200 m draw distance where the vanilla houses had LODs.

The screenshots are viewport captures from [Ariane](https://github.com/Dryxio/ariane) with weather 1. The placements
are a real server's: the house maps of [Scavenge & Survive](https://github.com/Southclaws/ScavengeSurvive) (CC BY-SA
4.0), which also remove the vanilla houses underneath.

## Tools

- [Ariane](https://github.com/Dryxio/ariane) Agent Alpha 1 (map editor with a CLI/MCP agent interface), on a
  dedicated copy of the game so it never writes to the install you play on.
- [GTA Scout](https://github.com/Dryxio/gta-scout) to find vanilla textures and props that fit.
- Blender 5.2 with [DragonFF](https://github.com/Parik27/DragonFF) (DFF import/export, prelight) and
  [blender-mcp](https://github.com/ahujasid/blender-mcp).

## Setup

1. Copy the game (with its `SAMP` folder) somewhere else, e.g. `D:\Games\GTA San Andreas\ariane-sa`, and put
   `ariane.exe` and `fonts\` from the Agent Alpha bundle next to `gta_sa.exe`.
2. In the copy's `data\gta.dat`, add the following lines. Put the `IMG` lines after the existing `IMG` lines, the
   `IDE` lines after the last `IDE` line, and the `IPL` line at the end:

   ```
   IMG SAMP\SAMP.IMG
   IMG SAMP\SAMPCOL.IMG
   IMG SAMP\CUSTOM.IMG
   IDE SAMP\SAMP.IDE
   IDE SAMP\CUSTOM.IDE
   IPL SCAVENGE\SCAVENGE.IPL
   ```

3. Generate the placements and run the editor:

   ```powershell
   python -I tools/make_ipl.py <scavengesurvive-mta checkout> <game copy> <game copy>\scavenge
   pwsh ariane/start.ps1              # editor on port 48731, token in %LOCALAPPDATA%\ariane-agent\token
   pwsh ariane/apply-removals.ps1     # replays the maps' RemoveBuildingForPlayer list as a scratch session
   pwsh ariane/ctl.ps1 camera 2712 -1972 22 2695.1 -1983.8 16 60
   pwsh ariane/ctl.ps1 capture C:\path\shot.png
   ```

`make_ipl.py` reads the map data that [scavengesurvive-mta](https://github.com/VIRUXE/scavengesurvive-mta) generates
from the upstream `.map` files. It writes a text IPL plus the removal list. Map-wide removals are expanded into
one entry per vanilla instance, because Ariane caps `suppress-world-models` at a 250 m radius.

## Licence

The scripts and screenshots are under MIT (see `LICENSE`). GTA San Andreas and SA-MP assets are not included. You
need your own copies.
