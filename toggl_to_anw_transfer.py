import tkinter as tk
from tkinter import messagebox, ttk
import logging
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from dateutil import parser
from openpyxl import load_workbook
import xlwings as xw
import debugpy
import os, sys
import shutil
import re

from helper.toggl_parse_data import get_toggl_time_entries
   
def update_entries_in_anw_new (time_entry_list, folder, file, workingtime_by_day_list):
    logging.debug("In update_entries_in_anw_new")
    
    with xw.Book(folder + file) as wb:
        anw = wb.sheets["ANW"]
        
        last_row_before_days_of_month = 4 # days of month start after row 5 (or 4 in xlwings)
        
        # Enter working hours
        for project in time_entry_list:
            logging.debug("project: " + project)
            
            anw_project_column_start = 7 # H column
            anw_project_title_row = 3 # row 4 because xlwings starts with 0
            switch_col_number = -1
            for col in range(anw_project_column_start,100):
                if anw[anw_project_title_row, col].value == "angerechn. Reisezeit":
                    switch_col_number = col
                    break
                
            if switch_col_number == -1:
                logging.error("Column ""angerechn. Reisezeit"" not found in row 4 of the ANW")
                raise KeyError("Column ""angerechn. Reisezeit"" not found in row 4 of the ANW")
            
            if "reisen" not in project.lower():
                col_start = anw_project_column_start
                col_end = switch_col_number - 1
            else:
                col_start = switch_col_number + 1
                col_end = 43
            
            project_col = -1
            excel_proj = "empty"
            
            for col in range(col_start, col_end):
                if anw[anw_project_title_row, col].value is None or anw[anw_project_title_row, col].value == "":
                    continue
                excel_proj = anw[anw_project_title_row, col].value[:4] # type: ignore
                if excel_proj == project[:4]:
                    project_col = col
                    break
            
            if project_col == -1 or excel_proj != project[:4]:
                logging.error("project '" + str(project) + "' not found in excel")
                raise KeyError("project '" + str(project) + "' not found in excel")
            
            
            for date_str in time_entry_list[project]:
                logging.debug("date: " + date_str)
                logging.debug("hours: " + str(time_entry_list[project][date_str]["hours"]))
                
                
                day =  parser.parse(date_str).day
                
                anw[last_row_before_days_of_month + day, project_col].value = time_entry_list[project][date_str]["hours"]
        
        # Working times per day
        for date_str in workingtime_by_day_list:
            logging.debug("date: " + str(date_str))
            logging.debug("hours: " + str(workingtime_by_day_list[date_str]))
            
            day = parser.parse(date_str).day
            if  workingtime_by_day_list[date_str]["endtime"].hour == 0:
                hour = 24
            else:
                hour = int(workingtime_by_day_list[date_str]["endtime"].strftime("%H"))
            
            anw[last_row_before_days_of_month + day, 2].value = workingtime_by_day_list[date_str]["starttime"].hour + workingtime_by_day_list[date_str]["starttime"].minute/100
            anw[last_row_before_days_of_month + day, 3].value = hour + workingtime_by_day_list[date_str]["endtime"].minute/100
                        
        wb.save()
        
        root = tk.Tk()
        root.withdraw()  # Hides the main window
        
        result = messagebox.askyesno("Confirmation", "Passt alles so? Excel wird dann geschlossen.")
        if result:
            logging.info(f'Closing excel file: {file}')
        else:
            logging.info("User declined to close excel file")
            sys.exit()
        root.destroy()
    
    logging.debug("End of update_entries_in_anw_new")

# The function to update the cell M1, save the new file, and delete the old one
def adjust_anws_for_new_month(folder, file, prefix, month, suffix):
    logging.debug("In adjust_anw_for_new_month")
    
    root = tk.Tk()
    root.withdraw()  # Hides the main window
    
    result = messagebox.askyesno("Confirmation", "Sollen die Excel Dateien umbenannt werden?")
    if not result:
        logging.info("User declined to rename excel files")
        sys.exit()
    root.destroy()
    
    app = xw.App()
    file_original = prefix + month + suffix
    with xw.Book(folder + file_original) as wb:
        anw = wb.sheets["ANW"]
        
        date_obj = anw["M1"].value
        new_date = date_obj + relativedelta(months=1)
        anw["M1"].value = new_date
    
    new_filename = prefix + new_date.strftime("%Y%m") + suffix
    # rename original file for new month
    os.rename(folder + file_original, folder + new_filename)
    # rename filled file to
    os.rename(folder + file, folder + file_original)

    logging.info(f"Renamed originnal file: {folder + new_filename}")
    logging.info(f"Filled nw file '{file}' becase '{file_original}'")
    
    app.quit()
    
# Function to ask the user to select an Excel file using a list box
def ask_user_to_select_file(files):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    def on_select(event):
        selected_file = listbox.get(listbox.curselection())
        root.selected_file = selected_file

    def on_close():
        if hasattr(root, 'selected_file'):
            root.destroy()  # Close the window
        else:
            messagebox.showerror("Error", "No file selected. Please try again.")
    
    top = tk.Toplevel(root)
    top.title("Select an Excel file")

    tk.Label(top, text="Multiple Excel files found:").pack(pady=5)
    
    listbox = tk.Listbox(top)
    listbox.pack(padx=10, pady=5)
    for file in files:
        listbox.insert(tk.END, file)
    listbox.bind('<<ListboxSelect>>', on_select)
        
    # Button to close window if no selection made
    button = tk.Button(top, text="Close", command=on_close)
    button.pack(pady=5)
    
    # root.wait_window(top)
    root.mainloop()
    
    return getattr(root, 'selected_file', None)

if __name__ == '__main__':

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            # logging.FileHandler("debug.log"), # For logging to file
            logging.StreamHandler()
        ]
    )
    if debugpy.is_client_connected():
        logging.getLogger().setLevel(logging.DEBUG)

    logging.info("----------------------------------------")
    logging.info("Starting Toggl to ANW Transfer")
    logging.debug("Debugging is enabled")
    
    linux_folder = "/mnt/c/Users/PrV/OneDrive - viadee Unternehmensberatung AG/Arbeitsnachweis/"
    windows_folder = linux_folder.replace('/mnt/c', 'C:').replace('/', '\\')
    if sys.platform == 'linux': # execution in WSL Linux
        folder = linux_folder
    else: # execution probably in windows
        folder = windows_folder
    
    excel_files = [f for f in os.listdir(folder) if f.endswith('.xlsx')]

    # Check if there are multiple Excel files
    if len(excel_files) > 1:
        file = ask_user_to_select_file(excel_files)
        if not file:
            raise FileNotFoundError("User did not select a valid file.")
    elif len(excel_files) == 1:
        file = excel_files[0]
    else:
        raise FileNotFoundError(f"No Excel files found in folder: {folder}")
        
    match = re.search(r'(Anw_PrV_)(\d{6}).*(\.xlsx)$', file)
    matchOrig = re.search(r'Anw_PrV_(\d{6})\.xlsx$', file)
    if match:
        fileshort = match.group(2)
        start_date = datetime.strptime(fileshort, "%Y%m").date().replace(day=1)
    else:
        raise ValueError(f"Filename '{file}' does not match the expected format 'Anw_PrV_YYYYMM*.xlsx'")
        
    end_date = (start_date + timedelta(days=32)).replace(day=1) # start of next month
    logging.debug("Start Date: " + str(start_date))
    logging.debug("End Date: " + str(end_date))
        
    time_entry_list, workingtime_by_day_list, time_entry_list_detail = get_toggl_time_entries(start_date, end_date)

    # time_entry_list = pickle.load(open("time_entry_list.pickle", "rb"))
    if matchOrig:
        file_new = file.replace(".xlsx", "n.xlsx")
        # Copy the file before making updates
        try:
            shutil.copy(folder + file, folder + file_new)
            logging.info(f"Copied original Excel '{file}' to '{file_new}'. Existing file was replaced.")
        except IOError:
            logging.info(f"Original Excel file should not be edited. But new Excel '{file_new}' already exists and is opened. . If it should be replaced, close it and restart Skript.")
        file = file_new
        
    update_entries_in_anw_new(time_entry_list, folder, file, workingtime_by_day_list)
    adjust_anws_for_new_month(folder, file, match.group(1), match.group(2), match.group(3))
    
    logging.info("Finished Toggl to Anw Transfer")