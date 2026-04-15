// ============================================================
// ESP32 Closet Monitor — Main Enclosure
// ============================================================
// Design: side-grip cradle, USB-C accessible, BOOT/EN buttons
// reachable, flat back for 3M VHB tape mounting.
//
// Board: Teyleten ESP32-WROOM-32 38-pin USB-C
//   Length: ~55mm
//   Width:  ~28mm
//   Height: ~13mm (including stacked pin headers below)
//
// Print: PETG, 0.2mm layer, 30% infill, no supports needed
// ============================================================

// ---------- TUNABLE PARAMETERS ----------
$fn = 60;  // smoothness of curves

// Board dimensions (with small clearance)
board_length = 55.5;
board_width  = 28.5;
board_thick  = 1.6;     // PCB only
pin_clearance = 12;     // space below board for pin headers

// Wall thickness
wall = 2.0;

// Side rails that grip the PCB
rail_height = 1.5;      // how much the rail sticks up over the PCB top
rail_grip   = 1.0;      // how far the rail extends inward over the PCB

// USB-C cutout (left end of board)
usb_width  = 10;
usb_height = 5;
usb_y_offset = 0;       // centered on board height

// Cable exit slot for the 4 sensor jumper wires (right end)
cable_slot_width  = 14;
cable_slot_height = 6;

// Button access cutouts (BOOT and EN are on opposite sides near the USB end)
button_cutout_width  = 6;
button_cutout_height = 5;
button_y_from_usb_end = 8;  // approx distance from USB end to buttons

// Vent slots on the bottom (so heat from the regulator can escape)
vent_count = 4;
vent_width = 2;
vent_length = 15;

// ---------- DERIVED ----------
inner_length = board_length;
inner_width  = board_width;
outer_length = inner_length + (2 * wall);
outer_width  = inner_width  + (2 * wall);
outer_height = pin_clearance + board_thick + rail_height + wall;

// ============================================================
// MAIN BODY
// ============================================================
module esp32_case() {
    difference() {
        // Solid outer shell
        rounded_box(outer_length, outer_width, outer_height, r=2);

        // Hollow out the interior cavity (where pin headers live)
        translate([wall, wall, wall])
            cube([inner_length, inner_width, pin_clearance + board_thick + rail_height + 1]);

        // USB-C cutout (one end)
        translate([-1, (outer_width - usb_width) / 2, wall + pin_clearance + (board_thick - usb_height)/2])
            cube([wall + 2, usb_width, usb_height + 2]);

        // Cable exit slot (opposite end, raised so wires exit above the PCB)
        translate([outer_length - wall - 1, (outer_width - cable_slot_width)/2, wall + pin_clearance + board_thick])
            cube([wall + 2, cable_slot_width, cable_slot_height]);

        // BOOT button access (one side, near USB end)
        translate([button_y_from_usb_end, -1, wall + pin_clearance])
            cube([button_cutout_width, wall + 2, button_cutout_height]);

        // EN button access (opposite side, near USB end)
        translate([button_y_from_usb_end, outer_width - wall - 1, wall + pin_clearance])
            cube([button_cutout_width, wall + 2, button_cutout_height]);

        // Bottom vent slots (for AMS1117 voltage regulator heat)
        for (i = [0 : vent_count - 1]) {
            x_pos = (outer_length / (vent_count + 1)) * (i + 1) - vent_length/2;
            translate([x_pos, (outer_width - vent_width)/2, -1])
                cube([vent_length, vent_width, wall + 2]);
        }
    }

    // ---------- INTERNAL SIDE RAILS THAT GRIP THE PCB ----------
    // The PCB rests on these ledges; the lip above holds it down
    rail_z = wall + pin_clearance;

    // Long-edge rails (front and back of the cradle)
    translate([wall, wall - 0.01, rail_z])
        side_rail(inner_length, rail_grip, board_thick + rail_height);

    translate([wall, outer_width - wall - rail_grip + 0.01, rail_z])
        side_rail(inner_length, rail_grip, board_thick + rail_height);
}

// A side rail that the PCB edge slides into
module side_rail(length, depth, height) {
    cube([length, depth, height]);
}

// Rounded box helper
module rounded_box(l, w, h, r=2) {
    hull() {
        for (x = [r, l - r]) {
            for (y = [r, w - r]) {
                translate([x, y, 0])
                    cylinder(h=h, r=r);
            }
        }
    }
}

// ============================================================
// RENDER
// ============================================================
esp32_case();
