import helper.config as config
import requests, re, logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from base64 import b64encode

# this function reads the data from the toggl service and stores them in a python dictionary data structure
def get_toggl_time_entries(start_date, end_date):
    logging.info("get toggl time entries for " + str(start_date) + " to " + str(end_date))
    # prepare headers
    api_auth = b64encode(bytes(config.toggl_api_token + ":api_token", 'ascii')).decode("ascii")
    # apiAUth = b64encode(bytes(config.toggl_cred + ":api_token", 'ascii')).decode("ascii") # alternative to api_token
    headers = { 'Authorization' : 'Basic %s' %  api_auth }

    # Request Clients
    client_list = {}
    response = requests.get('https://api.track.toggl.com/api/v9/me/clients', headers=headers)
    for client in response.json():
        if client_list.get(client["id"]) is None:
            client_list[client["id"]] = client["name"]

    # request project_list
    project_list = {}
    response = requests.get('https://api.track.toggl.com/api/v9/me/projects', headers=headers)
    for project in response.json():
        if project_list.get(project["id"]) is None:
            project_list[project["id"]] = {"name" : project["name"], "client_id" : project["client_id"]}


    # request time entries for start_date to end_date
    time_response = requests.get('https://api.track.toggl.com/api/v9/me/time_entries?start_date=' + str(start_date) + '&end_date=' + str(end_date), headers=headers)
    if time_response.status_code != 200:
        logging.error("Error: " + str(time_response.status_code) + " " + time_response.reason)
        raise Exception("Errortext: " + str(time_response.text))

    time_entry_list = {}
    workingtime_by_day_list = {}
    time_entry_list_detail = {}
    # json structure {'id': 2820044493, 'workspace_id': 3242752, 'project_id': 149577627, 'task_id': None, 'billable': False, 'start': '2023-01-27T13:15:34+00:00', 'stop': '2023-01-27T14:00:34Z', 'duration': 2700, 'description': 'Recherche crisp-dm | asum-dm', 'tags': None, 'tag_ids': None, 'duronly': True, 'at': '2023-01-27T13:59:06+00:00', 'server_deleted_at': None, ...}
    for time_entry in time_response.json():
        # skip entries with negative duration -> current running entries
        # skip entries with $ in description -> entries with $ are were done by other persons
        if time_entry["duration"] < 0 or "$" in time_entry["description"] \
                or client_list[project_list[time_entry["project_id"]]["client_id"]] == "Vit": # nicht die eigenen Projekte
            continue
        if "reisen" not in time_entry["description"].lower():
            project = project_list[time_entry["project_id"]]["name"]
        else:
            project = project_list[time_entry["project_id"]]["name"] + " - Reisen"
        
        # create project entry if missing
        if time_entry_list.get(project) is None:
            time_entry_list[project] = {}
            time_entry_list_detail[project] = {}
            
        startdatetime = datetime.strptime(time_entry["start"], "%Y-%m-%dT%H:%M:%S%z").astimezone(ZoneInfo('Europe/Berlin'))
        stopdatetime = datetime.strptime(time_entry["stop"], "%Y-%m-%dT%H:%M:%S%z").astimezone(ZoneInfo('Europe/Berlin'))
        date = str(startdatetime.date())
        day = startdatetime.date().day
        if time_entry_list[project].get(date) is None:
            time_entry_list[project][date] = {}
            time_entry_list_detail[project][date] = {}
        
        if time_entry_list[project][date].get("hours") is None:
                time_entry_list[project][date]["hours"] = time_entry["duration"] / 3600
        else:
            time_entry_list[project][date]["hours"] += time_entry["duration"] / 3600
        
        if time_entry_list[project][date].get("description") is None:
            time_entry_list[project][date]["description"] = time_entry["description"]
        else:
            time_entry_list[project][date]["description"] += ", " + time_entry["description"]
        
        # fill workingtime_by_day_list
        if workingtime_by_day_list.get(date) is None:
            workingtime_by_day_list[date] = {}
            
        if workingtime_by_day_list[date].get("hours") is None:
                workingtime_by_day_list[date]["hours"] = time_entry["duration"] / 3600
        else:
            workingtime_by_day_list[date]["hours"] += time_entry["duration"] / 3600
        
        # create or update start date entries if necessary
        if workingtime_by_day_list[date].get("starttime") is None:
            workingtime_by_day_list[date]["starttime"] = startdatetime
        else:
            # if current timeentry starts early for that date then take that as new master
            if workingtime_by_day_list[date]["starttime"] > startdatetime:
                workingtime_by_day_list[date]["starttime"] = startdatetime
        
        # create or update end date entries if necessary
        # if I worked into the next day, set 24:00 as enddate. The ANW cannot express the true enddate then
        if stopdatetime.date() != startdatetime.date():
            workingtime_by_day_list[date]["endtime"] = stopdatetime.replace(hour=0, minute=0)
        # create or update end date entries if necessary
        elif workingtime_by_day_list[date].get("endtime") is None:
            workingtime_by_day_list[date]["endtime"] = stopdatetime
        elif stopdatetime > workingtime_by_day_list[date]["endtime"]:
            workingtime_by_day_list[date]["endtime"] = stopdatetime
        
        # Eucon Jira Logic - seperate Eucon cases into Ticket-ID
        euc_ticket_string_reg = r"^\w+-\d+ - "
        if "2779 " in project:
            match = re.search(r"^\w+-\d+", time_entry["description"], re.IGNORECASE)
            if match:
                ticket = match.group(0).upper()
            else:
                raise Exception("-- Description '" + str(time_entry["description"]) + "' has no ticket id --")
        
            if time_entry_list[project][date].get(ticket) is None:
                time_entry_list[project][date][ticket] = {}
                time_entry_list_detail[project][date][ticket] = {}
            
            if time_entry_list[project][date][ticket].get("hours") is None:
                time_entry_list[project][date][ticket]["hours"] = time_entry["duration"] / 3600
            else:
                time_entry_list[project][date][ticket]["hours"] += time_entry["duration"] / 3600
            
            description = re.sub(euc_ticket_string_reg, "", time_entry["description"])
            if time_entry_list[project][date][ticket].get("description") is None:
                if "#" in description:
                    description = description[:description.index("#")].strip()
                time_entry_list[project][date][ticket]["description"] = description
            else:
                if "#" in description:
                    description = description[:description.index("#")].strip()
                if description not in time_entry_list[project][date][ticket]["description"]:
                    time_entry_list[project][date][ticket]["description"] += ", " + description
            
            # Logic for detail worklog list
            if time_entry_list_detail[project][date][ticket].get(description) is None:
                time_entry_list_detail[project][date][ticket][description] = time_entry["duration"] / 3600
            else:
                time_entry_list_detail[project][date][ticket][description] += time_entry["duration"] / 3600
    
    # adjust endtime or starttime if breaks were not taken
    for date in workingtime_by_day_list:
        start = workingtime_by_day_list[date]["starttime"]
        end = workingtime_by_day_list[date]["endtime"]
        workinghours = workingtime_by_day_list[date]["hours"]
        
        if workinghours > 9:
            breaktime = 0.75
        elif workinghours > 6:
            breaktime = 0.5
        else:
            breaktime = 0
        
        if end > start:
            delta_hours = (end - start).total_seconds()/3600
        
        if delta_hours < workinghours + breaktime:
            diff = (workinghours + breaktime) - delta_hours
            # either endate is already in the new day or enddate with break would be in the new day
            if workingtime_by_day_list[date]["starttime"].date() < workingtime_by_day_list[date]["endtime"].date() \
                or (workingtime_by_day_list[date]["endtime"] + timedelta(hours=diff)).date() > workingtime_by_day_list[date]["endtime"].date():
                # subtract diff from starttime via delta
                workingtime_by_day_list[date]["starttime"] = workingtime_by_day_list[date]["starttime"] - timedelta(hours=diff)
            else:
                # add the breack to the endtime
                workingtime_by_day_list[date]["endtime"] = workingtime_by_day_list[date]["endtime"] + timedelta(hours=diff)
    
    # pickle.dump(time_entry_list, open("time_entry_list.pickle", "wb"))
    return (time_entry_list, workingtime_by_day_list, time_entry_list_detail)