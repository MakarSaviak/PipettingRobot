# Pipetting Robot - User Guide

## 1. Getting Started

### Installation

This software does not require a traditional installation. It runs directly from the folder provided.

Important:

* `PipetGui.exe` is the program you launch.
* The `_internal` folder next to it must stay in place. It contains the files required by the application, including configurations, bundled libraries, and the local database.

### Launching

Double-click `PipetGui.exe` to start the application.

---

## 2. The Main Tabs

The GUI is organized into four tabs:

* `G-code`: select the current robot setup, create an Excel template, and generate the final G-code program.
* `Configuration`: create and manage saved setups, machine definitions, and rack definitions.
* `Syringes and Solvents`: maintain the local syringe, solvent, and syringe-solvent link data used by the software.
* `Calibration`: generate calibration routines, evaluate measurements, and apply updated calibration values.

---

## 3. Preparing the Robot Setup

Before generating a pipetting program, the software needs to know which machine, racks, and syringe are currently in use.

### Option A: Load a Saved Setup

1. Open the `G-code` tab.
2. Choose a saved setup from the `Setup` dropdown.
3. The corresponding machine, rack order, and syringe are loaded automatically.

### Option B: Configure Manually

If no saved setup matches the current hardware arrangement, configure it directly in the `G-code` tab:

1. Select the installed syringe.
2. Select the machine profile.
3. Select the rack or racks on the deck in the correct order. _This will simply influence the solvent and vial indexes in the excel template._

Notes:

* The current workflow uses one active syringe at a time.
* Saved setups can be created or updated later in the `Configuration` tab.

---

## 4. Managing Configurations

The `Configuration` tab is used to maintain reusable hardware definitions.

It allows you to manage:

* `Setups`: combinations of one machine, one syringe, and an ordered list of racks.
* `Machines`: motion limits, feed rates, and rest positions.
* `Racks`: vial and solvent geometry, spacing, and waste coordinates.

You can create new entries, edit existing ones, overwrite them with `Save`, or create a derived copy with `Save As`.

For machine settings, the most important parameters are:

* `z_min_limit` and `z_max_limit`: the hard allowed vertical range for the machine.
* `z_min` and `z_max`: the normal working range used during pipetting moves.
* `Fz`: the Z-axis feed rate.
* `Fxy`: the XY travel feed rate.
* `Fa_push`, `Fa_push_slow`, and `Fa_pull`: the syringe-axis feed rates for dispensing, slow dispensing, and aspiration.
* `rest_x` and `rest_y`: the parking position used at the end of a run.

For rack settings, the most important parameters are:

* `vial1_x` and `vial1_y`: the XY position of the first vial in the rack.
* `vial_dx` and `vial_dy`: the spacing between neighboring vial positions.
* `vial_rows` and `vial_columns`: the vial grid dimensions.
* `z_min_vials`: the target Z position used at vial locations. If left at the special default, the machine `z_min` is used instead.
* `solvent1_x` and `solvent1_y`: the XY position of the first solvent position.
* `solvent_dx` and `solvent_dy`: the spacing between neighboring solvent positions.
* `solvent_rows` and `solvent_columns`: the solvent grid dimensions.
* `z_min_solvents`: the target Z position used at solvent locations. If left at the special default, the machine `z_min` is used instead.
* `waste_x` and `waste_y`: the XY position used for flushing and waste dispensing for that rack.

---

## 5. Managing Syringes, Solvents, and Link Data

The `Syringes and Solvents` tab is used to maintain the local liquid-handling database.

In this tab you can:

* add or edit syringe entries,
* add or edit solvent entries,
* maintain syringe-solvent links, including correlation and backlash parameters, which are the linear and constant terms for the linear calibration of syringes.

These values are used by the software when converting liquid volumes into machine movement. 

---

## 6. Creating the Protocol

The robot reads instructions from an Excel file (`.xlsx`). The software can generate a template so you do not need to start from scratch.

1. Open the `G-code` tab.
2. Create an Excel template and save it.
3. Open the template and fill it in according to the instructions in the workbook. _There are some instructions in the excel file too._
4. **Save the Excel file** (important) when the protocol is ready.

In general, the Excel program defines which solvent is used, which vial is targeted, and which volume should be dispensed. It also includes the flush and slow pipetting (fill the volume cell with any color) functionalities.

---

## 7. Generating G-Code

Once the Excel protocol is prepared:

* Generate G-code from the `G-code` tab.

If generation is successful, the machine code is written to the chosen output file. If an error occurs, the log in the GUI helps identify the problem.

---

## 8. Calibration

The `Calibration` tab supports calibration workflows for dispensing performance.

It can be used to:

* generate calibration G-code,
* evaluate measured mass values,
* estimate updated calibration parameters,
* apply those parameters to the syringe-solvent link data.

Calibration of a syringe-solvent link is mainly needed when very high precision is required. In practice, two consecutive calibration runs are usually enough. For water, the first run is often already above `99.95%` accuracy, and the second run is mainly useful to quantify and confirm the remaining error. A good standard workflow is `7` datapoints with `3` repeats each, but `3-5` datapoints are often sufficient as well. A common starting range is from about `10%` of the syringe volume up to `100%` of the syringe volume.

The tab supports two calibration procedures:

* `Same vial`: this is usually the preferred workflow. Use the scale with the vial-tower setup, do not use a septum, and choose a pause duration. This approach is faster and more convenient because all dispenses go into the same vial.
* `Different vials`: this is slower, but it can still be useful in special cases, for example when calibrating the `10 µL` syringe in contact mode.

During same-vial calibration, the measured masses can be entered directly into the evaluation table while the run is happening. For different-vial calibration, the table can be filled afterwards. After selecting the syringe and solvent, the evaluation table shows the expected masses for the ideal `100%`-accuracy case as placeholder values. When you run `Evaluate calibration`, the GUI reports the error of the latest calibration run and calculates updated correlation and backlash values. In this context, `CF` is the linear term and `BC` is the constant term. `Apply calibration` writes the updated values directly into the syringe-solvent link in the local database, so you do not need to edit the database manually.

---

## 9. Running the Robot

This software generates the instructions for the robot, but it does not directly control the hardware connection during execution. A host program such as Pronterface is typically used to send the generated G-code to the machine.

General workflow:

1. Connect to the robot in your host software (e.g. Pronterface).
2. Home the robot before the run.
3. Load the generated `.gcode` file.
4. Start the run and supervise the first execution carefully.

---

## Safety and Troubleshooting

* Ensure racks are placed exactly as defined by the selected configuration. After homing the device, it is good practice to verify important positions manually in Pronterface at low speed, for example with commands such as `G1 X<mm> Y<mm> F1000` for horizontal motion and `G1 Z<mm> F300` for vertical motion.
* Ensure the physical syringe matches the syringe selected in the GUI.
* Review calibration and syringe-solvent link values if dispensing accuracy changes.
* Keep an emergency stop or power cutoff accessible during test runs.

---

## Contact and Support

For hardware configurations, database updates, or bug reports, please contact:

Makar Saviak
Catalysis Research Center
Technical University of Munich (TUM)
makar.saviak@tum.de
