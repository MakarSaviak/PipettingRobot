import configparser
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog
from mecode import G
g = G()

# Loads the configuration from config.ini file
config = configparser.ConfigParser()
config.read('config.ini')
if not config.sections():
    raise ValueError("No config.ini found in the file.")
# Syringe Settings
available_syringes = [s for s in config.sections() if "syringe" in s.lower()]
if not available_syringes:
    raise ValueError("No sections containing 'syringe' found in config.ini.")
print("Available syringe names:")
for name in available_syringes:
    print(f" - {name}")

syringe_name = input("Enter the syringe name from the config file: ")
factor = config.getfloat(syringe_name, 'theoretical_factor')
backlash = config.getfloat(syringe_name, 'backlash_correction')
def syringe(volume):
    return (volume * factor) + backlash
# Vial Locations
vial1_s = [config.getfloat('Rack', 'vial1_x'), config.getfloat('Rack', 'vial1_y')]
dx_s = config.getint('Rack', 'dx_s') #TODO: why getint instead of getfloat?
dy_s = config.getint('Rack', 'dy_s')
solvent1_x = config.getfloat('Rack', 'solvent1_x')
solvent1_y = config.getfloat('Rack', 'solvent1_y')
vial_waste = [config.getfloat('Rack', 'waste_x'), config.getfloat('Rack', 'waste_y')]
vials_per_row = config.getint('Rack', 'vials_per_row')
columns = config.getint('Rack', 'columns')
syringe_vol = config.getint(syringe_name, 'max_volume')
# Machine Settings
Z_slow = config.getint('Machine', 'Z_slow')
Z_min = config.getint('Machine', 'Z_min')
Z_max = config.getint('Machine', 'Z_max')
Fz = config.getint('Machine', 'Fz')
Fxy = config.getint('Machine', 'Fxy')
Fa_push = config.getint('Machine', 'Fa_push')
Fa_push_slow = config.getint('Machine', 'Fa_push_slow')
Fa_pull = config.getint('Machine', 'Fa_pull')
Rest_x = config.getint('Machine', 'Rest_x')
Rest_y = config.getint('Machine', 'Rest_y')

#Assings the vial index to an absolute position on the sample rack for small vials
def vial_s(vial_index):
    col = vial_index // vials_per_row
    row = vial_index % vials_per_row
    print(col, row)
    total_vials = vials_per_row * columns
    if vial_index >= total_vials:
        raise ValueError(f"Vial index out of bounds {total_vials}")
    x = vial1_s[0] + col * dx_s
    y = vial1_s[1] + row * dy_s
    return x, y
#Function to perform the flush operation
def flush(volume, repeats=1):
    for _ in range(repeats):
        remove_from_vial(solvent1_x, solvent1_y, volume)
        g.absolute()
        g.move(z=Z_min, F=Fz)
        g.move(vial_waste[0], vial_waste[1], F=Fxy)
        g.move(z=Z_max, F=Fz)
        g.move(A=0, F=Fa_push)
        g.move(z=Z_min, F=Fz)
#Function to peform the fill vial operation
def fill_vial(x, y, non_contact=False):
    g.write("fill_vial")
    g.absolute()
    g.move(z=Z_min, F=Fz)
    g.move(x, y, F=Fxy)
    if non_contact:
        g.move(z=Z_slow, F=Fz)
    else:
        g.move(z=Z_max, F=Fz)
    g.move(A=0, F=Fa_push)
    g.absolute()
    g.move(z=Z_min, F=Fz)
#Function to perform the remove from vial operation
def remove_from_vial(x, y, volume):
    g.write("remove_from_vial")
    g.absolute()
    g.move(z=Z_min, F=Fz)
    g.move(x, y, F=Fxy)
    g.move(z=Z_max, F=Fz)
    g.move(A=syringe(volume), F=Fa_pull)
    g.move(z=Z_min, F=Fz)
#Function the put the machine in the rest state
def home():
    g.absolute()
    g.move(z=Z_min, F=Fz)
    g.move(Rest_x, Rest_y, F=Fxy)
    g.move(A=0, F=Fa_pull)
    g.move(z=Z_max, F=Fz)
    g.write('M84')

def generate_g_code_fast(syringe_vol: int,
                         pause: int,
                         x: float,
                         y: float,
                         n_vials_per_vol: int = 3,
                         n_data_points: int = 10,
                         initial_flush=True):
    """
    Creates a G-code for calibration
    :param syringe_vol: The volume of the syringe.
    :param x: The x coordinate of the vial on the scale.
    :param y: The y coordinate of the vial on the scale.
    :param n_vials_per_vol: How many vials per a volume data point u have.
    :param n_data_points: How many different volumes you have.
    :param pause: The time robot waits until the next pipetting in [ms].
    :param initial_flush: To flush or not to flush.
    :param g: the G() object.
    :return:
    """
    global g
    # Prompt the user for a filename
    filepath = filedialog.asksaveasfilename(defaultextension=".gcode", filetypes=[("G-code files", "*.gcode")])
    if filepath:  # Check if a path was selected
        g = G(outfile=filepath)
        g.write("G21")  # Set units to millimeters
        g.write("G28")  # Perform homing command
        if initial_flush:
            flush(500, repeats=3)  # Example initial flush with 500µL volume, 3 times
        start = 0.1 * syringe_vol
        stop = syringe_vol
        steps = n_data_points
        volumes = np.linspace(start=start, stop=stop, num=steps)
        vials_count = n_vials_per_vol * np.ones_like(volumes, dtype=int)
        current_vial = 0

        for vol_index, count in enumerate(vials_count):
            print(f"{current_vial}: {vol_index}, {count}")
            for i in range(count):
                print("iteration over count: ", i)  # i is only for the print
                volume = volumes[vol_index]
                g.dwell(pause) # time in [ms]
                remove_from_vial(solvent1_x, solvent1_y, volume)
                fill_vial(x, y)
                current_vial += 1

        home()
        messagebox.showinfo("Success", "G-code generation complete!")
    else:
        messagebox.showwarning("File Not Saved", "No file was selected. G-code generation was canceled.")


if __name__ == '__main__':
    x = 100
    y = 100
    pause = 10 * 1000 # convert [s] to [ms]
    generate_g_code_fast(syringe_vol=syringe_vol, pause=pause, x=x, y=y)

