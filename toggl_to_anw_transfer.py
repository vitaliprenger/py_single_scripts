import config
import logging
from datetime import date, datetime, timedelta
import calendar
from base64 import b64encode
import requests
import pickle
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

start_date = date(2023, 5, 1)

def get_toggl_time_entries(start_date, end_date):
    logging.info("get toggl time entries for " + str(start_date) + " to " + str(end_date))
    # prepare headers
    api_auth = b64encode(bytes(config.toggl_api_token + ":api_token", 'ascii')).decode("ascii")
    # apiAUth = b64encode(bytes(config.toggl_cred + ":api_token", 'ascii')).decode("ascii") # alternative to api_token
    headers = { 'Authorization' : 'Basic %s' %  api_auth }


    # request project_list
    project_list = {}
    response = requests.get('https://api.track.toggl.com/api/v9/me/projects', headers=headers)
    for project in response.json():
        if project_list.get(project["id"]) is None:
            project_list[project["id"]] = project["name"]


    # request time entries for start_date to end_date

    time_response = requests.get('https://api.track.toggl.com/api/v9/me/time_entries?start_date=' + str(start_date) + '&end_date=' + str(end_date), headers=headers)
    if time_response.status_code != 200:
        logging.error("Error: " + str(time_response.status_code) + " " + time_response.reason)
        raise Exception("Errortext: " + str(time_response.text))

    time_entry_list = {}
    # json structure {'id': 2820044493, 'workspace_id': 3242752, 'project_id': 149577627, 'task_id': None, 'billable': False, 'start': '2023-01-27T13:15:34+00:00', 'stop': '2023-01-27T14:00:34Z', 'duration': 2700, 'description': 'Recherche crisp-dm | asum-dm', 'tags': None, 'tag_ids': None, 'duronly': True, 'at': '2023-01-27T13:59:06+00:00', 'server_deleted_at': None, ...}
    for time_entry in time_response.json():
        # skip entries with negative duration -> current running entries
        # skip entries with $ in description -> entries with $ are were done by other persons
        if time_entry["duration"] < 0 or "$" in time_entry["description"]:
            continue
        if "reisen" not in time_entry["description"].lower():
            project = project_list[time_entry["project_id"]]
        else:
            project = project_list[time_entry["project_id"]] + " - Reisen"
        
        # create project entry if missing
        if time_entry_list.get(project) is None:
            time_entry_list[project] = {}
            
        date = datetime.strptime(time_entry["start"], "%Y-%m-%dT%H:%M:%S%z").date()
        if time_entry_list[project].get(date) is None:
            time_entry_list[project][date] = {}
        
        if time_entry_list[project][date].get("hours") is None:
                time_entry_list[project][date]["hours"] = time_entry["duration"] / 3600
        else:
            time_entry_list[project][date]["hours"] += time_entry["duration"] / 3600
        
        if time_entry_list[project][date].get("description") is None:
            time_entry_list[project][date]["description"] = time_entry["description"]
        else:
            time_entry_list[project][date]["description"] += ", " + time_entry["description"]
                
    # pickle.dump(time_entry_list, open("time_entry_list.pickle", "wb"))
    return time_entry_list

    
def update_entries_in_anw (time_entry_list, file_path):
    logging.info("update entries in anw")
    wb = load_workbook(file_path)
    anw = wb["ANW"]
    for project in time_entry_list:
        logging.debug("project: " + project)
        
        if "reisen" not in project.lower():
            col_start = 8
            col_end = 34
        else:
            col_start = 36
            col_end = 40
        
        for col in range(col_start, col_end):
            if anw.cell(row=4, column=col).value is None or anw.cell(row=4, column=col).value == "":
                continue
            excel_proj = anw.cell(row=4, column=col).value[:4]
            if excel_proj == project[:4]:
                project_col = col
                break
        
        if project_col is None or excel_proj != project[:4]:
            logging.error("project not found in excel")
            raise KeyError("project not found in excel")
        
        
        for date in time_entry_list[project]:
            logging.debug("date: " + str(date))
            logging.debug("hours: " + str(time_entry_list[project][date]["hours"]))
            
            row_offset = 5
            
            day = date.day
            
            anw.cell(row = day + row_offset, column=col).value = time_entry_list[project][date]["hours"]
                    
                    
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
    
    start_date = start_date.replace(day=1)
    end_date = (start_date + timedelta(days=32)).replace(day=1) # start of next month
    logging.debug("Start Date: " + str(start_date))
    logging.debug("End Date: " + str(end_date))
        
    time_entry_list = get_toggl_time_entries(start_date, end_date)

    # time_entry_list = pickle.load(open("time_entry_list.pickle", "rb"))
    
    file_path = "/mnt/c/Users/PrV/OneDrive - viadee Unternehmensberatung AG/Arbeitsnachweis/Anw_PrV_" + str(start_date.year) + str(start_date.month).zfill(2) + ".xlsx"
    
    update_entries_in_anw(time_entry_list, file_path)
    
    logging.info("Finished Toggl to Anw Transfer")