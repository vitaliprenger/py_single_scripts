import config
import logging
from datetime import date, datetime, timedelta
import calendar
from base64 import b64encode
import requests
import re
import pickle
from jira import JIRA


def get_toggl_time_entries(start_date, end_date):
    # prepare headers
    apiAUth = b64encode(bytes(config.toggl_api_token + ":api_token", 'ascii')).decode("ascii")
    # apiAUth = b64encode(bytes(config.toggl_cred + ":api_token", 'ascii')).decode("ascii") # alternative to api_token
    headers = { 'Authorization' : 'Basic %s' %  apiAUth }


    # request projectList
    projectList = {}
    response = requests.get('https://api.track.toggl.com/api/v9/me/projects', headers=headers)
    for project in response.json():
        if projectList.get(project["id"]) is None:
            projectList[project["id"]] = project["name"]


    # request time entries for start_date to end_date

    timeResponse = requests.get('https://api.track.toggl.com/api/v9/me/time_entries?start_date=' + str(start_date) + '&end_date=' + str(end_date), headers=headers)

    timeEntryList = {}
    # json structure {'id': 2820044493, 'workspace_id': 3242752, 'project_id': 149577627, 'task_id': None, 'billable': False, 'start': '2023-01-27T13:15:34+00:00', 'stop': '2023-01-27T14:00:34Z', 'duration': 2700, 'description': 'Recherche crisp-dm | asum-dm', 'tags': None, 'tag_ids': None, 'duronly': True, 'at': '2023-01-27T13:59:06+00:00', 'server_deleted_at': None, ...}
    for timeEntry in timeResponse.json():
        # skip entries with negative duration -> current running entries
        if timeEntry["duration"] < 0:
            continue
        
        if timeEntryList.get(projectList[timeEntry["project_id"]]) is None:
            timeEntryList[projectList[timeEntry["project_id"]]] = {}
        
        date = datetime.strptime(timeEntry["start"], "%Y-%m-%dT%H:%M:%S%z").date()
        if timeEntryList[projectList[timeEntry["project_id"]]].get(date) is None:
            timeEntryList[projectList[timeEntry["project_id"]]][date] = {}
        
        # seperate Eucon cases into Ticket-ID
        if "2779 Produkt" in projectList[timeEntry["project_id"]]:
            ticket = re.search(r"^\w+-\d+", timeEntry["description"], re.IGNORECASE).group(0)
            if timeEntryList[projectList[timeEntry["project_id"]]][date].get(ticket) is None:
                timeEntryList[projectList[timeEntry["project_id"]]][date][ticket] = {}
            
            if timeEntryList[projectList[timeEntry["project_id"]]][date][ticket].get("hours") is None:
                timeEntryList[projectList[timeEntry["project_id"]]][date][ticket]["hours"] = timeEntry["duration"] / 3600
            else:
                timeEntryList[projectList[timeEntry["project_id"]]][date][ticket]["hours"] += timeEntry["duration"] / 3600
            
            if timeEntryList[projectList[timeEntry["project_id"]]][date][ticket].get("description") is None:
                description = re.sub(r"^\w+-\d+ - ", "", timeEntry["description"])
                if "#" in description:
                    description = description[:description.index("#")].strip()
                timeEntryList[projectList[timeEntry["project_id"]]][date][ticket]["description"] = description
            else:
                description = re.sub(r"^\w+-\d+ - ", "", timeEntry["description"])
                if "#" in description:
                    description = description[:description.index("#")].strip()
                if description not in timeEntryList[projectList[timeEntry["project_id"]]][date][ticket]["description"]:
                    timeEntryList[projectList[timeEntry["project_id"]]][date][ticket]["description"] += ", " + description
        
        else:
            if timeEntryList[projectList[timeEntry["project_id"]]][date].get("hours") is None:
                timeEntryList[projectList[timeEntry["project_id"]]][date]["hours"] = timeEntry["duration"] / 3600
            else:
                timeEntryList[projectList[timeEntry["project_id"]]][date]["hours"] += timeEntry["duration"] / 3600
            
            if timeEntryList[projectList[timeEntry["project_id"]]][date].get("description") is None:
                description = re.sub(r"^\w+-\d+ - ", "", timeEntry["description"])
                if "#" in description:
                    description = description[:description.index("#")].strip()
                timeEntryList[projectList[timeEntry["project_id"]]][date]["description"] = description
            else:
                description = re.sub(r"^\w+-\d+ - ", "", timeEntry["description"])
                if "#" in description:
                    description = description[:description.index("#")].strip()
                if description not in timeEntryList[projectList[timeEntry["project_id"]]][date]["description"]:
                    timeEntryList[projectList[timeEntry["project_id"]]][date]["description"] += ", " + description

    pickle.dump(timeEntryList, open("timeEntryList.pickle", "wb"))
    return timeEntryList


def get_eucon_jira_worklog_list(start_date, end_date):
    # get booked time entries in Jira
    jira = JIRA(
        basic_auth=(config.jira_user, config.jira_token),
        options={
            'server': 'https://projects.eucon-services.com/jira'
        }
    )
    jql = "worklogDate >= " + str(start_date) + " AND worklogDate <= " + str(end_date) + " AND worklogAuthor = currentUser()"
    issues = jira.search_issues(jql, maxResults=1000)
    jiraWorklogList = {}
    for issue in issues:
        # create jira api request for worklog of issue
        url = "https://projects.eucon-services.com/jira/rest/api/2/issue/" + issue.key + "/worklog"
        response = requests.get(url, auth=(config.jira_user, config.jira_token))
        for worklog in response.json()["worklogs"]:
            
            worklogDate = datetime.strptime(worklog["started"][:worklog["started"].index("T")], '%Y-%m-%d').date()
            if worklog["author"]["name"] == config.jira_user and start_date <= worklogDate <= end_date:
                if jiraWorklogList.get(worklogDate) is None:
                    jiraWorklogList[worklogDate] = {}
                
                if jiraWorklogList[worklogDate].get(issue.key) is None:
                    jiraWorklogList[worklogDate][issue.key] = worklog["timeSpentSeconds"] / 3600
    
    pickle.dump(jiraWorklogList, open("jiraWorklogList.pickle", "wb"))
    return jiraWorklogList


def add_missing_entries_for_eucon (timeEntryList, jiraWorklogList):
    # add missing entries to Jira
    jira = JIRA(
        basic_auth=(config.jira_user, config.jira_token),
        options={
            'server': 'https://projects.eucon-services.com/jira'
        }
    )
    for project in timeEntryList:
        if "2779 Produkt" in project:
            for date in timeEntryList[project]:
                for ticket in timeEntryList[project][date]:
                    if jiraWorklogList.get(date) is None or jiraWorklogList[date].get(ticket) is None or jiraWorklogList[date][ticket] != timeEntryList[project][date][ticket]["hours"]:
                        # add missing entry to Jira
                        logging.info("Adding missing entry for " + ticket + " on " + str(date) + " with " + str(timeEntryList[project][date][ticket]["hours"]) + "h")
                        # date to datetime with timezone
                        datetime_with_zone = datetime.strptime(date.strftime("%Y-%m-%d") + "T00:00:00.000+0100", '%Y-%m-%dT%H:%M:%S.000%z')
                        jira.add_worklog(ticket, timeSpentSeconds=timeEntryList[project][date][ticket]["hours"] * 3600, started=datetime_with_zone, comment=timeEntryList[project][date][ticket]["description"])



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
    
    start_date = date(2022, 11, 1)
    end_date = datetime.now().date()
    logging.debug("Start Date: " + str(start_date))
    logging.debug("End Date: " + str(end_date))
    
    time_entry_list = get_toggl_time_entries(start_date, end_date)

    # time_entry_list = pickle.load(open("timeEntryList.pickle", "rb"))
    
    jira_worklog_list = get_eucon_jira_worklog_list(start_date, end_date)
    
    # jira_worklog_list = pickle.load(open("jiraWorklogList.pickle", "rb"))
    
    add_missing_entries_for_eucon(time_entry_list, jira_worklog_list)
    
    