from toggl_parse_data import get_toggl_time_entries
import logging
from datetime import date, datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo
from base64 import b64encode
import requests
from openpyxl import load_workbook
import os

   
def update_entries_in_anw (time_entry_list, file_path, workingtime_by_day_list):
    logging.info("update entries in anw")
    wb = load_workbook(file_path)
    anw = wb["ANW"]
    
    # enter working hours
    for project in time_entry_list:
        logging.debug("project: " + project)
        
        if "reisen" not in project.lower():
            col_start = 8
            col_end = 34
        else:
            col_start = 36
            col_end = 40
        
        project_col = -1
        excel_proj = "empty"
        
        for col in range(col_start, col_end):
            if anw.cell(row=4, column=col).value is None or anw.cell(row=4, column=col).value == "":
                continue
            excel_proj = anw.cell(row=4, column=col).value[:4] # type: ignore
            if excel_proj == project[:4]:
                project_col = col
                break
        
        if project_col == -1 or excel_proj != project[:4]:
            logging.error("project '" + str(project) + "' not found in excel")
            raise KeyError("project '" + str(project) + "' not found in excel")
        
        
        for date in time_entry_list[project]:
            logging.debug("date: " + str(date))
            logging.debug("hours: " + str(time_entry_list[project][date]["hours"]))
            
            row_offset = 5
            
            day = date.day
            
            anw.cell(row = day + row_offset, column=project_col).value = time_entry_list[project][date]["hours"]
    
    # working times per day       
    for date in workingtime_by_day_list:
        logging.debug("date: " + str(date))
        logging.debug("hours: " + str(workingtime_by_day_list[date]))
        
        row_offset = 5
        
        day = date.day
        if  workingtime_by_day_list[date]["endtime"].hour == 0:
            hour = 24
        else:
            hour = int(workingtime_by_day_list[date]["endtime"].strftime("%H"))
        
        anw.cell(row = day + row_offset, column=3).value = workingtime_by_day_list[date]["starttime"].hour + workingtime_by_day_list[date]["starttime"].minute/100
        anw.cell(row = day + row_offset, column=4).value = hour + workingtime_by_day_list[date]["endtime"].minute/100
                    
    wb.save(file_path.replace(".xlsx", "") + "n.xlsx")


if __name__ == '__main__':

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler("debug.log"),
            logging.StreamHandler()
        ]
    )

    logging.info("----------------------------------------")
    logging.info("Starting Toggl to Jira Transfer")
    logging.debug("Debugging is enabled")
    

    # start_date = date(2023, 5, 1)
    # start_date = start_date.replace(day=1)
    start_date = date.today().replace(day=1)- relativedelta(months=1) # set to first of last month
    
    folder = "/mnt/c/Users/PrV/OneDrive - viadee Unternehmensberatung AG/Arbeitsnachweis/"
    file = "Anw_PrV_" + str(start_date.year) + str(start_date.month).zfill(2) + ".xlsx"
    
    # check if file_path exists
    if not os.path.isfile(folder + file):
        # if not, check if file_path of last month exists
        start_date_new = start_date - relativedelta(months=1)	
        file_month_before = "Anw_PrV_" + str(start_date_new.year) + str(start_date_new.month).zfill(2) + ".xlsx"
        if os.path.isfile(folder + file_month_before):
            file = file_month_before
            start_date = start_date_new
        else:
            raise FileNotFoundError("File '" + folder + file + "' not found")
        
    
    end_date = (start_date + timedelta(days=32)).replace(day=1) # start of next month
    logging.debug("Start Date: " + str(start_date))
    logging.debug("End Date: " + str(end_date))
        
    time_entry_list, workingtime_by_day_list, time_entry_list_detail = get_toggl_time_entries(start_date, end_date)

    # time_entry_list = pickle.load(open("time_entry_list.pickle", "rb"))
    
    update_entries_in_anw(time_entry_list, folder + file, workingtime_by_day_list)
    
    logging.info("Finished Toggl to Anw Transfer")