import configparser
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
# Machine Settings
Z_slow = config.getint('Machine', 'Z_slow')
Z_max = config.getint('Machine', 'Z_max')
Z_min = config.getint('Machine', 'Z_min')
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
        g.move(z=Z_max, F=Fz)
        g.move(vial_waste[0], vial_waste[1], F=Fxy)
        g.move(z=Z_min, F=Fz)
        g.move(A=0, F=Fa_push)
        g.move(z=Z_max, F=Fz)
#Function to peform the fill vial operation
def fill_vial(x, y, non_contact):
    g.write("fill_vial")
    g.absolute()
    g.move(z=Z_max, F=Fz)
    g.move(x, y, F=Fxy)
    if non_contact:
        g.move(z=Z_slow, F=Fz)
    else:
        g.move(z=Z_min, F=Fz)
    g.move(A=0, F=Fa_push)
    g.absolute()
    g.move(z=Z_max, F=Fz)
#Function to perform the remove from vial operation
def remove_from_vial(x, y, volume):
    g.write("remove_from_vial")
    g.absolute()
    g.move(z=Z_max, F=Fz) # remove from vial
    g.move(x, y, F=Fxy)
    g.move(z=Z_min, F=Fz) # move into the vial
    g.move(A=syringe(volume), F=Fa_pull)
    g.move(z=Z_max, F=Fz)
#Function to put the machine in the rest state
def home():
    g.absolute()
    g.move(z=Z_max, F=Fz)
    g.move(Rest_x, Rest_y, F=Fxy)
    g.move(A=0, F=Fa_pull)
    g.move(z=Z_min, F=Fz)
    g.write('M84') 

#Function to generate the G-code file
def generate_g_code(num_vials_10, num_vials_50, num_vials_100, initial_flush, leading_air_gap, non_contact):
    global g
    # Prompt the user for a filename
    filepath = filedialog.asksaveasfilename(defaultextension=".gcode", filetypes=[("G-code files", "*.gcode")])
    if filepath:  # Check if a path was selected
        g = G(outfile=filepath)
        g.write("G21")  # Set units to millimeters
        g.write("G28")  # Perform homing command
        if initial_flush:
            flush(500, repeats=3)  # Example initial flush with 500µL volume, 3 times

        volumes = [0.1, 0.5, 1.0]
        vials_count = [num_vials_10, num_vials_50, num_vials_100]
        current_vial = 0

        for vol_index, count in enumerate(vials_count):
            for _ in range(count):
                volume = volumes[vol_index] * config.getint(syringe_name, 'max_volume')
                remove_from_vial(solvent1_x, solvent1_y, volume)
                if leading_air_gap:
                    air_gap_volume = 0.1 * volume
                    g.relative()
                    g.move(A=syringe(air_gap_volume), F=Fa_pull)  # Aspirate air
                fill_vial(*vial_s(current_vial), non_contact)
                current_vial += 1

        home()
        messagebox.showinfo("Success", "G-code generation complete!")
        root.destroy()
    else:
        messagebox.showwarning("File Not Saved", "No file was selected. G-code generation was canceled.")

# GUI setup
root = tk.Tk()
root.title("Syringe Volume Calibration")

# Number of vials inputs
ttk.Label(root, text="Number of vials for 10% volume:").grid(row=0, column=0, padx=10, pady=5)
num_vials_10_entry = ttk.Entry(root)
num_vials_10_entry.grid(row=0, column=1, padx=10, pady=5)

ttk.Label(root, text="Number of vials for 50% volume:").grid(row=1, column=0, padx=10, pady=5)
num_vials_50_entry = ttk.Entry(root)
num_vials_50_entry.grid(row=1, column=1, padx=10, pady=5)

ttk.Label(root, text="Number of vials for 100% volume:").grid(row=2, column=0, padx=10, pady=5)
num_vials_100_entry = ttk.Entry(root)
num_vials_100_entry.grid(row=2, column=1, padx=10, pady=5)

# Initial flush checkbox
initial_flush_var = tk.BooleanVar()
ttk.Checkbutton(root, text="Initial Flush", variable=initial_flush_var).grid(row=3, column=0, columnspan=2, pady=5)
# Leading air gap checkbox
leading_air_gap_var = tk.BooleanVar()
ttk.Checkbutton(root, text="Leading Air Gap", variable=leading_air_gap_var).grid(row=4, column=0, columnspan=2, pady=5)
# Non Contact checkbox
non_contact_var = tk.BooleanVar()
ttk.Checkbutton(root, text="Non Contact", variable=non_contact_var).grid(row=5, column=0, columnspan=2, pady=5)

# Display Backlash Correction
ttk.Label(root, text=f"Backlash correction: {backlash} mm").grid(row=6, column=0, columnspan=2, pady=5)

# Display Syringe Size
ttk.Label(root, text=f"Syringe size: {config.getint(syringe_name, 'max_volume')} µL").grid(row=7, column=0, columnspan=2, pady=5)

def on_generate_button_click():
    try:
        num_vials_10 = int(num_vials_10_entry.get())
        num_vials_50 = int(num_vials_50_entry.get())
        num_vials_100 = int(num_vials_100_entry.get())
        non_contact = non_contact_var.get()
        initial_flush = initial_flush_var.get()
        leading_air_gap = leading_air_gap_var.get()
        generate_g_code(num_vials_10, num_vials_50, num_vials_100, initial_flush, leading_air_gap, non_contact)
    except ValueError as e:
        messagebox.showerror("Input Error", str(e))

# Generate G-Code button
generate_button = ttk.Button(root, text="Generate G-Code", command=on_generate_button_click)
generate_button.grid(row=8, column=0, columnspan=2, pady=10)

root.mainloop()

