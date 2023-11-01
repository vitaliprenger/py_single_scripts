import config
from toggl_parse_data import get_toggl_time_entries
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from base64 import b64encode
import requests
import re
from jira import JIRA

jira_url = "https://eucon.atlassian.net"

def get_eucon_jira_worklog_list(start_date, end_date):
    logging.info("get eucon jira tempo worklog for " + str(start_date) + " to " + str(end_date))
    # get booked time entries in Jira
    jira = JIRA(
        basic_auth=(config.jira_user, config.jira_token),
        options={
            'server': jira_url
        }
    )
    jql = f"worklogDate >= {start_date} AND worklogDate <= {end_date} AND worklogAuthor = currentUser()"
    issues = jira.search_issues(jql, maxResults=1000)
    
    # Create a dictionary for the request body
    jiraWorklogList = {}
    for issue in issues:
        # create jira api request for worklog of issue
        worklogs = jira.worklogs(issue)
        for worklog in worklogs:
            worklogDate = datetime.strptime(worklog.started[:worklog.started.index("T")], '%Y-%m-%d').date()
            worklogDateStr = str(worklogDate)
            if hasattr(worklog.author, 'emailAddress') and worklog.author.emailAddress == config.jira_user \
                    and start_date <= worklogDate <= end_date:
                
                if jiraWorklogList.get(worklogDateStr) is None:
                    jiraWorklogList[worklogDateStr] = {}
                
                if jiraWorklogList[worklogDateStr].get(issue.key) is None: # type: ignore
                    jiraWorklogList[worklogDateStr][issue.key] = worklog.timeSpentSeconds / 3600 # type: ignore
    
    # pickle.dump(jiraWorklogList, open("jiraWorklogList.pickle", "wb"))
    return jiraWorklogList


def add_missing_entries_for_eucon (timeEntryList, jiraWorklogList):
    # add missing entries to Jira
    jira = JIRA(
        basic_auth=(config.jira_user, config.jira_token),
        options={
            'server': jira_url
        }
    )
    for project in timeEntryList:
        if "2779 " in project:
            for date in timeEntryList[project]:
                for ticket in timeEntryList[project][date]:
                    if (jiraWorklogList.get(date) is None or jiraWorklogList[date].get(ticket) is None or jiraWorklogList[date][ticket] != timeEntryList[project][date][ticket]["hours"]) and ticket != "hours" and ticket != "description":
                        
                        hours = timeEntryList[project][date][ticket]["hours"]
                        desc = timeEntryList[project][date][ticket]["description"]
                        if jiraWorklogList.get(date) is not None and jiraWorklogList[date].get(ticket) is not None and \
                                time_entry_list[project][date][ticket]["hours"] != jiraWorklogList[date][ticket]:
                            
                            hours_jira = jiraWorklogList[date].get(ticket)
                            logging.info("Wrong time in Jira. toggl: " + str(hours) + "h, Jira: " + str(hours_jira) + "h. " + ticket + " on " + str(date))
                            answer = input("Should the entry nevertheless be added? (y/n): ")
                            if answer != "y":
                                continue
                        # add missing entry to Jira
                        logging.info("Adding missing entry for " + ticket + " on " + date + " with " + str(hours) + "h")
                        # date to datetime with timezone
                        datetime_with_zone = datetime.strptime(date + "T00:00:00.000+0100", '%Y-%m-%dT%H:%M:%S.000%z')
                        jira.add_worklog(ticket, timeSpentSeconds = hours * 3600, started=datetime_with_zone, comment=desc)



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
    
    
    # start_date = date(2023, 9, 1)
    # set start date to first day of previous month
    start_date = date.today().replace(day=1) - relativedelta(months=1)
    
    end_date = datetime.now().date()
    logging.debug("Start Date: " + str(start_date))
    logging.debug("End Date: " + str(end_date))
    
    time_entry_list, workingtime_by_day_list, time_entry_list_detail = get_toggl_time_entries(start_date, end_date)

    # time_entry_list = pickle.load(open("timeEntryList.pickle", "rb"))
    
    jira_worklog_list = get_eucon_jira_worklog_list(start_date, end_date)
    
    # jira_worklog_list = pickle.load(open("jiraWorklogList.pickle", "rb"))
    
    add_missing_entries_for_eucon(time_entry_list, jira_worklog_list)
    
    logging.info("Finished Toggl to Jira Transfer")