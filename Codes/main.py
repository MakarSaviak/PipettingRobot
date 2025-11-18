import configparser
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from mecode import G

# Initialize the global G object
g = G()

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')
print("Sections found:", config.sections())
if not config.sections():
    raise ValueError("No configuration sections found in the file.")


#Syringe settings for syringe 1
factor_1 = config.getfloat('Syringe_1', 'theoretical_factor') 
backlash_1 = config.getfloat('Syringe_1', 'backlash_correction')
vol_max_1 = config.getint('Syringe_1', 'max_volume')
vol_min_1 = config.getint('Syringe_1', 'min_volume')
#Syringe settings for syringe 2
factor_2 = config.getfloat('Syringe_2', 'theoretical_factor') 
backlash_2 = config.getfloat('Syringe_2', 'backlash_correction')
vol_max_2 = config.getint('Syringe_2', 'max_volume')
vol_min_2 = config.getint('Syringe_2', 'min_volume')
syringe2_offset_x = config.getfloat('Syringe_2', 'syringe2_offset_x')
syringe2_offset_y = config.getfloat('Syringe_2', 'syringe2_offset_y')

def syringe(volume):
    if volume <= vol_max_1 and volume >= vol_min_1:
        syringe_type = 1
        return (volume * factor_1) + backlash_1, syringe_type
    elif volume < vol_max_2 and volume >= vol_min_2:
        syringe_type = 2
        return (volume * factor_2) + backlash_2, syringe_type
    else:
        messagebox.showerror("Error", f"Volume out of Range; Please enter a volume between {vol_min_1} and {vol_max_2}")


#Vial Locations    
vial1_s = [config.getfloat('Rack', 'vial1_x'), config.getfloat('Rack', 'vial1_y')]
dx_s = config.getint('Rack', 'dx_s')
dy_s = config.getint('Rack', 'dy_s')
solvent1_x = config.getfloat('Rack', 'solvent1_x')
solvent1_y = config.getfloat('Rack', 'solvent1_y')  
solvent_y_increment = config.getint('Rack', 'increment_y')
vial_waste = [config.getfloat('Rack', 'waste_x'), config.getfloat('Rack', 'waste_y')]
vials_per_row = config.getint('Rack', 'vials_per_row')
columns = config.getint('Rack', 'columns')
solvent_number = config.getint('Rack', 'number_of_solvents')


#Machine Settings
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


# Calculating positions of vials
def vial_s(vial_index, syringe_type=1):
    # Determine the row and column based on the vial index
    row = vial_index // vials_per_row
    col = vial_index % vials_per_row
    # Calculate the number of vials in the rack
    total_vials = vials_per_row * columns
    # Check if the vial index is out of bounds
    if vial_index >= total_vials:
        messagebox.showwarning("Error", "Vial index out of bounds. Rack only has {} vials.".format(total_vials))
        return None
    # X-coordinate changes with the row
    x = vial1_s[0] + row * dx_s
    # Y-coordinate increments based on the column within the respective row
    y = vial1_s[1] + col * dy_s
    return x, y


# Calculating positions of solvents
solvent_positions = {
    f'Solvent_{i}': [solvent1_x, solvent1_y + ((i-1) * solvent_y_increment)] for i in range(1, solvent_number + 1)
}

# Flushes the syringe with a solvent and puts it to waste
def flush(volume, repeats=1, solvent_name='Solvent_1'):
    g.write("flush")
    solvent_position = solvent_positions[solvent_name]
    for _ in range(repeats):
        displacement, syringe_type = syringe(volume)
        remove_from_vial(*solvent_position, volume)
        g.write("fill_vial")
        g.absolute()
        if syringe_type == 2:
            adjusted_waste_position = (
            vial_waste[0] + syringe2_offset_x,
            vial_waste[1] + syringe2_offset_y
            )
            g.move(B=Z_max, F=Fz)
            g.move(adjusted_waste_position[0], adjusted_waste_position[1], F=Fxy)
            g.move(B=Z_min, F=Fz)
            g.move(C=0, F=Fa_push)
            g.move(B=Z_max, F=Fz)
        else:
            g.move(z=Z_max, F=Fz)
            g.move(vial_waste[0], vial_waste[1], F=Fxy)
            g.move(z=Z_min, F=Fz)
            g.move(A=0, F=Fa_push)
            g.move(z=Z_max, F=Fz)
        
def fill_vial(x, y, volume, solvent_name):
    slow_push = solvent_slow_push_vars[solvent_name].get()
    g.write("fill_vial")
    g.absolute()
    displacement, syringe_type = syringe(volume)
    adjusted_x, adjusted_y = x, y
    if syringe_type == 2:
        adjusted_x += syringe2_offset_x
        adjusted_y += syringe2_offset_y
        g.move(B=Z_max, F=Fz)  # Move second Z-axis to safe height
        g.move(adjusted_x, adjusted_y, F=Fxy)
        if slow_push:
            g.move(B=Z_slow, F=Fz)
            g.move(C=0, F=Fa_push_slow)
            print("slow push")
        else:
            g.move(B=Z_min, F=Fz)
            g.move(C=0, F=Fa_push)
        g.move(B=Z_max, F=Fz)  # Move second Z-axis up
    else:
        g.move(z=Z_max, F=Fz)
        g.move(adjusted_x, adjusted_y, F=Fxy)
        if slow_push:
            g.move(z=Z_slow, F=Fz)
            g.move(A=0, F=Fa_push_slow)
            print("slow push")
        else:
            g.move(z=Z_min, F=Fz)
            g.move(A=0, F=Fa_push)
        g.move(z=Z_max, F=Fz)
    
def remove_from_vial(x, y, volume):
    g.write("remove_from_vial")
    g.absolute()
    displacement, syringe_type = syringe(volume)
    adjusted_x, adjusted_y = x, y
    if syringe_type == 2:
        adjusted_x += syringe2_offset_x
        adjusted_y += syringe2_offset_y
        g.move(B=Z_max, F=Fz)  # Move Z-axis to safe height
        g.move(adjusted_x, adjusted_y, F=Fxy)  # Move to solvent position
        g.move(B=Z_min, F=Fz)  # Move second Z-axis down
        g.relative()
        g.move(C=displacement, F=Fa_pull)  # Move second syringe
        g.absolute()
        g.move(B=Z_max, F=Fz)  # Move second Z-axis up
    else:
        g.move(z=Z_max, F=Fz)
        g.move(adjusted_x, adjusted_y, F=Fxy)
        g.move(z=Z_min, F=Fz)
        g.relative()
        g.move(A=displacement, F=Fa_pull)
        g.absolute()
        g.move(z=Z_max, F=Fz)
    
def home():
    g.absolute()
    g.move(z=Z_max, B=Z_max, F=Fz)
    g.move(Rest_x, Rest_y, F=Fxy)
    g.move(z=Z_min,B=Z_min, F=Fz)
    g.write('M84')  # Turns off the drivers (Z-axis drops)

############################################
def generate_g_code():
    global g
    # Prompt the user for a filename
    filepath = filedialog.asksaveasfilename(defaultextension=".gcode", filetypes=[("G-code files", "*.gcode")])
    # Check if a path was selected
    if filepath:  
        g = G(outfile=filepath)
        # Set units to millimeters
        g.write("G21")
        # Perform homing command
        g.write("G28 Z B") # Homes both Z-axis
        g.write("G28 Y X A C") # Homes other axes
        if fill_vial_mode_var.get(): 
            for vial_index, entries in enumerate(vial_entries, start=1):
                for solvent_index, (entry, flush_var) in enumerate(entries[1:]): 
                    volume = entry.get()
                    flush_required = flush_var.get()
                    solvent_name = solvents[solvent_index]
                    if volume:
                        process_vial(float(volume), flush_required, solvent_name, vial_index)
                        
        elif fill_solvent_mode_var.get():
            for solvent_index, solvent_name in enumerate(solvents):
                for vial_index, entries in enumerate(vial_entries, start=1):
                    entry, flush_var = entries[1:][solvent_index]
                    volume = entry.get()
                    flush_required = flush_var.get()
                    if volume:
                        process_vial(float(volume), flush_required, solvent_name, vial_index)
        home()
        print("G-code generation complete!")
        messagebox.showinfo("G-Code Generation Complete", "The G-code generation process has finished. Please restart the program for the next file generation.")
        root.destroy()
    else:
        messagebox.showwarning("File Not Saved", "No file was selected. G-code generation was canceled.")

    
def process_vial(volume, flush_required, solvent_name, vial_index):
    volume = float(volume)
    if flush_required:
        flush(volume, solvent_name=solvent_name)
    print(f"Picking up {volume}µL of {solvent_name}")
    solvent_position = solvent_positions[solvent_name]
    displacement, syringe_type = syringe(volume)
    remove_from_vial(*solvent_position, volume)
    x, y = vial_s(vial_index - 1)
    fill_vial(x, y, volume, solvent_name)



#GUI functions
def add_vial():
    frame = ttk.Frame(inputs_frame, relief='groove', borderwidth=2)
    frame.pack(fill='x', padx=5, pady=5, expand=True)
    vial_number = len(vial_entries) + 1
    vial_label = f"Vial {str(vial_number).zfill(2)}:" 
    ttk.Label(frame, text=vial_label).pack(side='left', padx=(5, 20))
    vial_entry_group = [frame]  
    for i, solvent in enumerate(solvents):
        entry_frame = ttk.Frame(frame)
        entry_frame.pack(side='left', padx=(5, 5 if i < len(solvents) - 1 else 0))
        entry = ttk.Entry(entry_frame, width=10)
        entry.pack(side='left')
        flush_cb_var = tk.BooleanVar()
        flush_cb = ttk.Checkbutton(entry_frame, text='Flush', variable=flush_cb_var)
        flush_cb.pack(side='left')
        vial_entry_group.append((entry, flush_cb_var))
    vial_entries.append(vial_entry_group)
    update_vials_count_label()


def remove_vial():
    if vial_entries:
        last_vial_frame = vial_entries.pop()
        last_vial_frame[0].destroy()
        update_vials_count_label()


def update_vials_count_label():
    vials_count_label.config(text=f"Vials: {len(vial_entries)}")
    
    
def setup_solvent_headers():
    column_index = 0
    ttk.Label(headers_frame, text="Position").grid(row=0, column=column_index, padx=(5, 11), sticky='w')  # Adjust padding as needed
    column_index += 1
    for solvent in solvents:
        header_frame = ttk.Frame(headers_frame)
        header_frame.grid(row=0, column=column_index, padx=8, sticky='w')
        ttk.Label(header_frame, text=f"{solvent}", width=10).pack(side='left')
        slow_push_var = tk.BooleanVar()
        ttk.Checkbutton(header_frame, text='Slow', variable=slow_push_var).pack(side='left')
        solvent_slow_push_vars[solvent] = slow_push_var
        column_index += 1


def enforce_checkbox_exclusivity(checked_var):
    if checked_var == fill_vial_mode_var:
        if fill_vial_mode_var.get():
            fill_solvent_mode_var.set(False)
        else:
            fill_solvent_mode_var.set(True)
    elif checked_var == fill_solvent_mode_var:
        if fill_solvent_mode_var.get():
            fill_vial_mode_var.set(False)
        else:
            fill_vial_mode_var.set(True)
            

def save_method():
    include_flush = messagebox.askyesno("Export Options", "Do you want to export flush information as well?")
    
    # Build a table-like structure for all vials and solvents
    method_data = {"Vial": []}
    for solvent in solvents:
        method_data[solvent] = []
        if include_flush:
            method_data[f"{solvent}_Flush"] = []

    for vial_index, vial_group in enumerate(vial_entries, start=1):
        method_data["Vial"].append(vial_index)
        for i, solvent in enumerate(solvents):
            entry, flush_var = vial_group[1:][i]
            volume_value = entry.get()
            
            if volume_value:
                method_data[solvent].append(volume_value)
                if include_flush:
                    method_data[f"{solvent}_Flush"].append(flush_var.get())
            else:
                method_data[solvent].append("")
                if include_flush:
                    # No volume → no flush
                    method_data[f"{solvent}_Flush"].append(False)

    df = pd.DataFrame(method_data)

    # Ask user whether to save as Excel or CSV
    filepath = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
    )
    if not filepath:
        return

    if filepath.endswith(".csv"):
        df.to_csv(filepath, index=False)
    else:
        df.to_excel(filepath, index=False)

    messagebox.showinfo("Save Successful", f"Method saved successfully to {filepath}")
        
def load_from_excel():
    filepath = filedialog.askopenfilename(filetypes=[("Excel/CSV files", "*.xlsx *.csv")])
    if not filepath:
        return
    
    # Load table
    if filepath.endswith(".csv"):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    include_flush = messagebox.askyesno("Import Options", "Do you want to import flush information if available?")
    
    # --- Detect solvents automatically ---
    solvent_names = []
    for col in df.columns:
        if col.startswith("Solvent_") and not col.endswith("_Flush"):
            solvent_names.append(col)

    if not solvent_names:
        messagebox.showerror("Error", "No solvent columns found (expected columns like 'Solvent_1').")
        return

    # Update global solvents list
    global solvents
    solvents = solvent_names  

    # Reset solvent_slow_push_vars, since headers are regenerated
    solvent_slow_push_vars.clear()
    for widget in headers_frame.winfo_children():
        widget.destroy()
    setup_solvent_headers()

    # Clear existing vials
    global vial_entries
    for vial_group in vial_entries:
        vial_group[0].destroy()
    vial_entries.clear()

    # --- Populate vial_entries dynamically ---
    for _, row in df.iterrows():
        frame = ttk.Frame(inputs_frame, relief='groove', borderwidth=2)
        frame.pack(fill='x', padx=5, pady=5, expand=True)
        vial_number = len(vial_entries) + 1
        ttk.Label(frame, text=f"Vial {str(vial_number).zfill(2)}:").pack(side='left', padx=(5, 20))
        
        vial_entry_group = [frame]
        for solvent in solvents:
            entry_frame = ttk.Frame(frame)
            entry_frame.pack(side='left', padx=(5, 5))
            
            # Volume entry
            entry = ttk.Entry(entry_frame, width=10)
            entry_value = row.get(solvent, "")
            entry.insert(0, str(entry_value) if pd.notna(entry_value) else "")
            entry.pack(side='left')
            
            # Flush flag (only if requested and column exists)
            flush_flag = False
            if include_flush and f"{solvent}_Flush" in df.columns:
                flush_flag = bool(row.get(f"{solvent}_Flush", False)) if pd.notna(row.get(f"{solvent}_Flush", False)) else False
            
            flush_cb_var = tk.BooleanVar(value=flush_flag)
            flush_cb = ttk.Checkbutton(entry_frame, text='Flush', variable=flush_cb_var)
            flush_cb.pack(side='left')
            
            vial_entry_group.append((entry, flush_cb_var))
        
        vial_entries.append(vial_entry_group)

    update_vials_count_label()
    messagebox.showinfo("Import Successful", f"Loaded method with {len(solvents)} solvent(s) from {filepath}")
    
# Tkinter setup
root = tk.Tk()
root.title("Liquid Handling System")
root.geometry("620x480")
solvents = [f'Solvent_{i+1}' for i in range(solvent_number)]

main_frame = ttk.Frame(root)
main_frame.pack(padx=10, pady=10, fill='both', expand=True)

top_frame = ttk.Frame(main_frame)
top_frame.pack(fill='x')

mode_selection_frame = ttk.Frame(main_frame)
mode_selection_frame.pack(fill='x', pady=5)

fill_vial_mode_var = tk.BooleanVar(value=True)  # Default to fill one vial after another
fill_solvent_mode_var = tk.BooleanVar(value=False)

headers_frame = ttk.Frame(main_frame)
headers_frame.pack(fill='x', padx=5)


#Scrollable Input Frame
def setup_scrollable_inputs():
    canvas = tk.Canvas(main_frame, borderwidth=0)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    # Configure the canvas
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    # Pack scrollbar and canvas
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    # Add the frame to the canvas
    canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')

    # Function to update the scrollregion when new frames are added
    def on_frame_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    scrollable_frame.bind('<Configure>', on_frame_configure)
    return scrollable_frame

inputs_frame = setup_scrollable_inputs()

actions_frame = ttk.Frame(main_frame)
actions_frame.pack(fill='x')

solvent_slow_push_vars = {}
setup_solvent_headers()
vial_entries = []

# BUTTONS
add_vial_button = ttk.Button(mode_selection_frame, text="Add Vial", command=add_vial)
add_vial_button.pack(side='left')

remove_vial_button = ttk.Button(mode_selection_frame, text="Remove Vial", command=remove_vial)
remove_vial_button.pack(side='left')

save_button = ttk.Button(top_frame, text="Export Excel", command=save_method)
save_button.pack(side='left')

import_excel_button = ttk.Button(top_frame, text="Import Excel/CSV", command=load_from_excel)
import_excel_button.pack(side='left')

generate_button = ttk.Button(mode_selection_frame, text="Generate G-Code", command=generate_g_code)
generate_button.pack(side='right')

ttk.Checkbutton(mode_selection_frame, text="Vial after Vial", variable=fill_vial_mode_var,
                command=lambda: enforce_checkbox_exclusivity(fill_vial_mode_var)).pack(side='left', padx=10)
ttk.Checkbutton(mode_selection_frame, text="Solvent after Solvent", variable=fill_solvent_mode_var,
                command=lambda: enforce_checkbox_exclusivity(fill_solvent_mode_var)).pack(side='left', padx=10)

vials_count_label = ttk.Label(mode_selection_frame, text="Vials: 0")
vials_count_label.pack()

# This loop adds 10 vials
for _ in range(10):
    add_vial()

root.mainloop()