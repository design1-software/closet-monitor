// ============================================================
// BME280 Sensor Pod — Closet Monitor
// ============================================================
// Design: open-air "lantern" style frame that holds the BME280
// breakout board between two end caps with vertical posts —
// maximum airflow on all sides. Flat back for VHB tape.
//
// Board: SHILLEHTEK pre-soldered BME280 breakout
//   Length: ~13mm
//   Width:  ~10mm
//   Thickness: ~2mm with components
//
// Print: PETG, 0.2mm layer, 30% infill, no supports needed
// ============================================================

$fn = 60;

// ---------- TUNABLE PARAMETERS ----------
// BME280 board
board_length = 13.5;
board_width  = 10.5;
board_thick  = 2.5;     // includes the sensor chip on top

// End caps that hold the board
endcap_thick    = 2.5;
endcap_height   = 8;
endcap_width_extra = 2;  // extra width past the board for grip slots

// Posts that connect the two end caps (the "lantern" structure)
post_count   = 4;        // one at each corner
post_diameter = 2.5;
post_spacing  = 9;       // distance between posts (becomes airflow gap)

// Mounting back-plate (flat surface for VHB tape)
backplate_length = 28;
backplate_width  = 14;
backplate_thick  = 2.5;

// Cable exit (where the 4 jumpers come from the ESP32 case)
cable_notch_width  = 8;
cable_notch_height = 4;

// ---------- DERIVED ----------
endcap_total_width = board_width + endcap_width_extra;

// ============================================================
// MAIN ASSEMBLY
// ============================================================
module sensor_pod() {

    // ---------- BACKPLATE (for VHB adhesive mounting) ----------
    translate([-((backplate_length - post_spacing) / 2), -((backplate_width - endcap_total_width) / 2), 0])
        rounded_plate(backplate_length, backplate_width, backplate_thick, r=2);

    // ---------- LEFT END CAP (with PCB slot) ----------
    translate([0, 0, backplate_thick])
        endcap_with_slot();

    // ---------- RIGHT END CAP ----------
    translate([post_spacing + endcap_thick, 0, backplate_thick])
        endcap_with_slot();

    // ---------- CONNECTING POSTS (4 corners) ----------
    // The PCB is held between the two end caps; posts give airflow on all sides
    post_z = backplate_thick;
    post_h = endcap_height;

    // Top-front
    translate([endcap_thick + 1, 0.5, post_z])
        cylinder(h=post_h, d=post_diameter);
    // Top-back
    translate([endcap_thick + 1, endcap_total_width - 0.5, post_z])
        cylinder(h=post_h, d=post_diameter);
    // Bottom-front
    translate([post_spacing - 1, 0.5, post_z])
        cylinder(h=post_h, d=post_diameter);
    // Bottom-back
    translate([post_spacing - 1, endcap_total_width - 0.5, post_z])
        cylinder(h=post_h, d=post_diameter);
}

// End cap with a slot that the BME280 board slides into
module endcap_with_slot() {
    difference() {
        cube([endcap_thick, endcap_total_width, endcap_height]);

        // Slot for the PCB
        translate([-0.5, (endcap_total_width - board_width) / 2, 1.5])
            cube([endcap_thick + 1, board_width, board_thick]);

        // Cable notch on one end cap
        translate([-0.5, (endcap_total_width - cable_notch_width) / 2, endcap_height - cable_notch_height + 0.5])
            cube([endcap_thick + 1, cable_notch_width, cable_notch_height]);
    }
}

// Rounded plate helper
module rounded_plate(l, w, h, r=2) {
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
sensor_pod();
