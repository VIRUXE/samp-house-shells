# The houses

Every SA-MP house shell, rendered in Blender by `tools/render_houses.py`: SA-MP's original on the left, this repo's
on the right, noon on top and midnight below. Each render loads the exterior together with its interior, so the glass
has a room behind it.

Materials are shaded the way the game lights buildings: texture × material colour × 2 × prelight, with the prelight
blended from the day colours to the night colours. The products are taken in gamma space, as SA does. Midnight
renders are exposed 1.3 stops up so they stay readable; in game, the ambient light added to buildings does much the
same. The camera looks from the corner between the two walls with the most glass.

Frames follow the window texture in each house's vanilla TXD (`STYLES` in `tools/add_panes.py`), so a pane looks like
the windows on the vanilla houses next to it.

| house | vanilla TXD | window reference | frame |
|---|---|---|---|
| `sfhouse1`–`sfhouse4` | `boxhses_sfsx` | `ws_boxhouse_wins5`, `ws_boxhouse_wins7` | white sash: thick meeting rail at half height, glazing bars about every 0.75 m |
| `lshouse1`, `lshouse2` | `ganghouse1_lax` | `gangwin1_LAe` | weathered wood: centre mullion on wide openings, transom |
| `lshouse3` | `comedhos1_la` | `comptwindo1` | aluminium louvres: six horizontal slats |
| `lshouse4` | `glenphouse_lax` | `ws_boxhouse_wins3` | dark grey, four panes |
| `lvhouse1` | `vegashse2` | `comptwindo4` | off-white frame with security bars every 12 cm |
| `lvhouse2` | `vegashse3` | `newindow10` | blue-painted frame, four panes |
| `lvhouse3` | `vegashse6` | `sw_wind10` | grey mullions about every 0.8 m |
| `lvhouse4` | `vegashse4` | `comptwindo4`, `sw_wind07` | thin silver sliders, split in two |

## San Fierro

![sfhouse1](../screenshots/houses/sfhouse1.png)
![sfhouse2](../screenshots/houses/sfhouse2.png)
![sfhouse3](../screenshots/houses/sfhouse3.png)
![sfhouse4](../screenshots/houses/sfhouse4.png)

## Los Santos

![lshouse1](../screenshots/houses/lshouse1.png)
![lshouse2](../screenshots/houses/lshouse2.png)
![lshouse3](../screenshots/houses/lshouse3.png)
![lshouse4](../screenshots/houses/lshouse4.png)

## Las Venturas

![lvhouse1](../screenshots/houses/lvhouse1.png)
![lvhouse2](../screenshots/houses/lvhouse2.png)
![lvhouse3](../screenshots/houses/lvhouse3.png)
![lvhouse4](../screenshots/houses/lvhouse4.png)

## Regenerating

```powershell
# needs the vanilla TXDs in work/txd (see the README's Setup); renders go to work/renders
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python tools/render_houses.py
python -I tools/gallery.py
```
