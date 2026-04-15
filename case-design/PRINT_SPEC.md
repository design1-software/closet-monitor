# Closet Monitor — 3D Print Specification

Two-piece enclosure for an ESP32-based environmental monitor: a main case for the ESP32 dev board and a remote sensor pod for the BME280, designed to maximize airflow around the sensor.

## Files in this package

| File | Description |
|---|---|
| `esp32_case.scad` | OpenSCAD source for the main ESP32 enclosure |
| `esp32_case.stl` | Print-ready STL of the main enclosure |
| `sensor_pod.scad` | OpenSCAD source for the BME280 sensor pod |
| `sensor_pod.stl` | Print-ready STL of the sensor pod |
| `PRINT_SPEC.md` | This file |

## Recommended print settings

| Setting | Value | Notes |
|---|---|---|
| **Material** | PETG | More heat-tolerant than PLA (closet may warm in summer) |
| **Color** | Black or dark gray | Hides dust, looks professional |
| **Layer height** | 0.2 mm | Standard quality, good detail |
| **Infill** | 30% | Strong enough; no need for solid |
| **Wall thickness** | 1.2 mm (3 perimeters) | Sturdy without bulk |
| **Top/bottom layers** | 4 | Clean appearance |
| **Supports** | None required | Designed to print support-free |
| **Build plate adhesion** | Brim recommended | Small parts, prevents lift |
| **Print orientation** | Both parts: largest flat side down | Optimal layer adhesion |

## Estimated print details

| Part | Approx. dimensions | Print time | Filament |
|---|---|---|---|
| ESP32 case | 60 × 33 × 22 mm | ~1.5 hours | ~15 g |
| Sensor pod | 30 × 14 × 13 mm | ~30 min | ~5 g |
| **Total** | — | **~2 hours** | **~20 g** |

## Recommended print services

If you don't own a 3D printer:

- **Craftcloud** (craftcloud3d.com) — aggregator, gets you the best price across multiple services
- **JLCPCB** (jlcpcb.com) — very cheap, ships from China, ~2 weeks delivery
- **Treatstock** (treatstock.com) — local printers in the US, faster delivery
- **Shapeways** (shapeways.com) — premium quality, more expensive

Expected total cost: **$8–15** including shipping for both parts in PETG.

## Design notes

### ESP32 main case
- **Side-rail cradle:** the PCB slides in by its long edges and is held by inward-facing rails on top, leaving the bottom pin headers free in the cavity below
- **USB-C cutout:** on one short end, sized for standard USB-C cables
- **Cable exit slot:** opposite end, sized to accept the 4 jumper wires going to the sensor pod
- **Button cutouts:** BOOT and EN buttons are accessible through openings on the long sides
- **Bottom vent slots:** four small slots underneath let heat from the AMS1117 voltage regulator escape
- **Flat back:** for 3M VHB (or similar double-sided) tape mounting

### Sensor pod
- **Open "lantern" frame:** two end caps connected by four corner posts, leaving the BME280 surrounded by air on all sides
- **Slot-mounted PCB:** the breakout board slides into matching slots in the end caps
- **Cable notch:** on one end cap for the 4 jumper wires
- **Backplate:** flat surface for VHB tape mounting; designed to sit a few inches away from the ESP32 case so the sensor isn't influenced by ESP32 heat

## Mounting

Both pieces are designed for **3M VHB tape (or any flat double-sided foam tape)** mounted on a wall, patch panel, or shelf surface. The sensor pod should be placed **a few inches away from the ESP32 case** to ensure airflow around the sensor isn't influenced by the warmth of the microcontroller.

## Customization

The `.scad` files are fully parameterized — you can adjust:
- Board dimensions if using a different ESP32 variant
- Wall thickness, vent count, button positions
- Backplate size for different mounting needs

Edit the values at the top of each `.scad` file in OpenSCAD (free download at openscad.org), then re-export as STL.

## Author

Designed for the [closet-monitor](https://github.com/design1-software/closet-monitor) project by Julius Moore.
