import logging
import os
import re
import shutil
import sys
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox

import debugpy

# from openpyxl import load_workbook
import xlwings as xw
from dateutil import parser
from dateutil.relativedelta import relativedelta

# Import handling for both direct execution and module execution
try:
    from .helper.toggl_parse_data import get_toggl_time_entries
except ImportError:
    # Direct execution fallback
    from helper.toggl_parse_data import get_toggl_time_entries  # type: ignore


def update_entries_in_anw_new(time_entry_list, folder, file, workingtime_by_day_list):
    logging.debug("In update_entries_in_anw_new")

    with xw.Book(folder + file) as wb:
        anw = wb.sheets["ANW"]

        last_row_before_days_of_month = (
            4  # days of month start after row 5 (or 4 in xlwings)
        )

        # Enter working hours
        for project in time_entry_list:
            logging.debug("project: " + project)

            anw_project_column_start = 7  # H column
            anw_project_title_row = 3  # row 4 because xlwings starts with 0
            switch_col_number = -1
            # Fetch the entire row at once for better performance
            row_values = anw[anw_project_title_row, anw_project_column_start:100].value
            for idx, cell_value in enumerate(row_values):
                if cell_value == "angerechn. Reisezeit":
                    switch_col_number = anw_project_column_start + idx
                    break

            if switch_col_number == -1:
                logging.error(
                    "Column angerechn. Reisezeit not found in row 4 of the ANW"
                )
                raise KeyError(
                    "Column angerechn. Reisezeit not found in row 4 of the ANW"
                )

            if "reisen" not in project.lower():
                col_start = anw_project_column_start
                col_end = switch_col_number - 1
            else:
                col_start = switch_col_number + 1
                col_end = 200

            project_col = -1
            excel_proj = "empty"

            # Fetch the entire row at once for better performance
            row_values = anw[anw_project_title_row, col_start:col_end].value
            for idx, cell_value in enumerate(row_values):
                if cell_value is None or cell_value == "":
                    continue
                excel_proj = str(cell_value)[:4]
                if excel_proj == project[:4]:
                    project_col = col_start + idx
                    break

            if project_col == -1 or excel_proj != project[:4]:
                logging.error("project '" + str(project) + "' not found in excel")
                raise KeyError("project '" + str(project) + "' not found in excel")

            for date_str in time_entry_list[project]:
                logging.debug("date: " + date_str)
                logging.debug(
                    "hours: " + str(time_entry_list[project][date_str]["hours"])
                )

                day = parser.parse(date_str).day

                anw[
                    last_row_before_days_of_month + day, project_col
                ].value = time_entry_list[project][date_str]["hours"]

        # Working times per day
        for date_str in workingtime_by_day_list:
            logging.debug("date: " + str(date_str))
            logging.debug("hours: " + str(workingtime_by_day_list[date_str]))

            day = parser.parse(date_str).day
            if workingtime_by_day_list[date_str]["endtime"].hour == 0:
                hour = 24
            else:
                hour = int(workingtime_by_day_list[date_str]["endtime"].strftime("%H"))

            anw[last_row_before_days_of_month + day, 2].value = (
                workingtime_by_day_list[date_str]["starttime"].hour
                + workingtime_by_day_list[date_str]["starttime"].minute / 100
            )
            anw[last_row_before_days_of_month + day, 3].value = (
                hour + workingtime_by_day_list[date_str]["endtime"].minute / 100
            )

        new_overtimehours = anw["F42"].value
        wb.save()

        root = tk.Tk()
        root.withdraw()  # Hides the main window

        result = messagebox.askyesno(
            "Confirmation", "Passt alles so? Excel wird dann geschlossen."
        )
        if result:
            logging.info(f"Closing excel file: {file}")
        else:
            logging.info("User declined to close excel file")
            sys.exit()
        root.destroy()

    logging.debug("End of update_entries_in_anw_new")
    return new_overtimehours


# def update_entries_in_anw_with_openpyxl (time_entry_list, file_path, workingtime_by_day_list):
#     logging.info("update entries in anw")
#     wb = load_workbook(file_path)
#     anw = wb["ANW"]

#     # enter working hours
#     for project in time_entry_list:
#         logging.debug("project: " + project)

#         if "reisen" not in project.lower():
#             col_start = 8
#             col_end = 37
#         else:
#             col_start = 39
#             col_end = 43

#         project_col = -1
#         excel_proj = "empty"

#         for col in range(col_start, col_end):
#             if anw.cell(row=4, column=col).value is None or anw.cell(row=4, column=col).value == "":
#                 continue
#             excel_proj = anw.cell(row=4, column=col).value[:4] # type: ignore
#             if excel_proj == project[:4]:
#                 project_col = col
#                 break

#         if project_col == -1 or excel_proj != project[:4]:
#             logging.error("project '" + str(project) + "' not found in excel")
#             raise KeyError("project '" + str(project) + "' not found in excel")


#         for date_str in time_entry_list[project]:
#             logging.debug("date: " + date_str)
#             logging.debug("hours: " + str(time_entry_list[project][date_str]["hours"]))

#             row_offset = 5

#             day =  parser.parse(date_str).day

#             anw.cell(row = day + row_offset, column=project_col).value = time_entry_list[project][date_str]["hours"]

#     # working times per day
#     for date_str in workingtime_by_day_list:
#         logging.debug("date: " + str(date_str))
#         logging.debug("hours: " + str(workingtime_by_day_list[date_str]))

#         row_offset = 5

#         day = parser.parse(date_str).day
#         if  workingtime_by_day_list[date_str]["endtime"].hour == 0:
#             hour = 24
#         else:
#             hour = int(workingtime_by_day_list[date_str]["endtime"].strftime("%H"))

#         anw.cell(row = day + row_offset, column=3).value = workingtime_by_day_list[date_str]["starttime"].hour + workingtime_by_day_list[date_str]["starttime"].minute/100
#         anw.cell(row = day + row_offset, column=4).value = hour + workingtime_by_day_list[date_str]["endtime"].minute/100

#     wb.save(file_path.replace(".xlsx", "") + "n.xlsx")


# The function to update the cell M1, save the new file, and delete the old one
def adjust_anws_for_new_month(
    folder, file, prefix, yearmonth, suffix, new_overtimehours
):
    logging.debug("In adjust_anw_for_new_month")

    root = tk.Tk()
    root.withdraw()  # Hides the main window

    result = messagebox.askyesno(
        "Confirmation", "Sollen die Excel Dateien umbenannt werden?"
    )
    if not result:
        logging.info("User declined to rename excel files")
        sys.exit()
    root.destroy()

    app = xw.App()
    file_original = prefix + yearmonth + suffix
    with xw.Book(folder + file_original) as wb:
        anw = wb.sheets["ANW"]

        date_obj = anw["M1"].value
        new_date = date_obj + relativedelta(months=1)
        anw["M1"].value = new_date

        anw["F39"].value = new_overtimehours

    new_filename = prefix + new_date.strftime("%Y%m") + suffix
    # rename original file for new month
    os.rename(folder + file_original, folder + new_filename)
    # rename filled file to
    os.rename(folder + file, folder + file_original)

    logging.info(f"Renamed originnal file to {folder + new_filename}")
    logging.info(f"Renamed Excel '{file}' to '{file_original}'")

    app.quit()


# Function to ask the user to select an Excel file using a list box
def ask_user_to_select_file(files):
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    selected_file = None

    def on_select(event):
        nonlocal selected_file
        selected_file = listbox.get(listbox.curselection())

    def on_close():
        if selected_file is not None:
            root.destroy()  # Close the window
        else:
            messagebox.showerror("Error", "No file selected. Please try again.")

    top = tk.Toplevel(root)
    top.title("Select an Excel file")

    tk.Label(
        top, text="Multiple Excel files found.\nWhich should be used as template?"
    ).pack(pady=5)

    listbox = tk.Listbox(top)
    listbox.pack(padx=10, pady=5)
    for file in files:
        listbox.insert(tk.END, file)
    listbox.bind("<<ListboxSelect>>", on_select)

    # Button to close window if no selection made
    button = tk.Button(top, text="Close", command=on_close)
    button.pack(pady=5)

    # root.wait_window(top)
    root.mainloop()

    return selected_file


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            # logging.FileHandler("debug.log"), # For logging to file
            logging.StreamHandler()
        ],
    )
    if debugpy.is_client_connected():
        logging.getLogger().setLevel(logging.DEBUG)

    logging.info("----------------------------------------")
    logging.info("Starting Toggl to ANW Transfer")
    logging.debug("Debugging is enabled")

    linux_folder = (
        "/mnt/c/Users/PrV/OneDrive - viadee Unternehmensberatung AG/Arbeitsnachweis/"
    )
    mac_folder = "/Users/prv/Library/CloudStorage/OneDrive-viadeeUnternehmensberatungAG/Arbeitsnachweis/"
    windows_folder = linux_folder.replace("/mnt/c", "C:").replace("/", "\\")
    if sys.platform == "linux":  # execution in WSL Linux
        folder = linux_folder
    elif sys.platform == "darwin":  # execution on macOS
        folder = mac_folder
    else:  # execution probably in windows
        folder = windows_folder

    excel_files = [
        f
        for f in os.listdir(folder)
        if f.endswith(".xlsx") and not f.endswith("n.xlsx")
    ]

    # Check if there are multiple Excel files
    if len(excel_files) > 1:
        file = ask_user_to_select_file(excel_files)
        if not file:
            raise FileNotFoundError("User did not select a valid file.")
    elif len(excel_files) == 1:
        file = excel_files[0]
    else:
        raise FileNotFoundError(f"No Excel files found in folder: {folder}")

    match = re.search(r"(Anw_PrV_)(\d{6}).*(\.xlsx)$", file)
    matchOrig = re.search(r"Anw_PrV_(\d{6})\.xlsx$", file)
    if match:
        fileshort = match.group(2)
        start_date = datetime.strptime(fileshort, "%Y%m").date().replace(day=1)
    else:
        raise ValueError(
            f"Filename '{file}' does not match the expected format 'Anw_PrV_YYYYMM*.xlsx'"
        )

    end_date = (start_date + timedelta(days=32)).replace(day=1)  # start of next month
    logging.debug("Start Date: " + str(start_date))
    logging.debug("End Date: " + str(end_date))

    time_entry_list, workingtime_by_day_list, time_entry_list_detail = (
        get_toggl_time_entries(start_date, end_date)
    )

    # time_entry_list = pickle.load(open("time_entry_list.pickle", "rb"))
    if matchOrig:
        file_new = file.replace(".xlsx", "n.xlsx")
        # Copy the file before making updates
        try:
            shutil.copy(folder + file, folder + file_new)
            logging.info(
                f"Copied original Excel '{file}' to '{file_new}'. Existing file was replaced."
            )
        except IOError:
            logging.info(
                f"Original Excel file should not be edited. But new Excel '{file_new}' already exists and is opened. . If it should be replaced, close it and restart Skript."
            )
        file = file_new

    # on_windows = True;
    # if on_windows:
    new_overtimehours = update_entries_in_anw_new(
        time_entry_list, folder, file, workingtime_by_day_list
    )
    adjust_anws_for_new_month(
        folder, file, match.group(1), match.group(2), match.group(3), new_overtimehours
    )
    # else:
    #     update_entries_in_anw_with_openpyxl(time_entry_list, folder, file, workingtime_by_day_list)

    logging.info("Finished Toggl to Anw Transfer")
    logging.info("Finished Toggl to Anw Transfer")
