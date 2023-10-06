from toggl_parse_data import get_toggl_time_entries
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from base64 import b64encode
from jira import JIRA

jira_url = "https://eucon.atlassian.net"

def printDoneTasks (timeEntryList):
    doneListSummed = {}
    doneListByTicket = {}
    for project in timeEntryList:
        if "2779 " in project:
            for date in timeEntryList[project]:
                for ticket in timeEntryList[project][date]:
                    if ticket != "hours" and ticket != "description":
                        if doneListSummed.get(ticket) is None:
                            doneListSummed[ticket] = {}
                        if doneListSummed[ticket].get("hours") is None:
                            doneListSummed[ticket]["hours"] = timeEntryList[project][date][ticket]["hours"]
                            doneListSummed[ticket]["description"] = timeEntryList[project][date][ticket]["description"]
                        else:
                            doneListSummed[ticket]["hours"] += timeEntryList[project][date][ticket]["hours"]
                            doneListSummed[ticket]["description"] += ", " + timeEntryList[project][date][ticket]["description"]
                    
                        if doneListByTicket.get(ticket) is None:
                            doneListByTicket[ticket] = {}
                        doneListByTicket[ticket][date] = timeEntryList[project][date][ticket]
    
    sorted_tickets = sorted(doneListSummed.items(), key=lambda x: x[1]["hours"], reverse=True)
    for key, value in sorted_tickets:
        ticket = doneListByTicket[key]
        sorted_dates = sorted(ticket.items(), key=lambda x: x[1]["hours"], reverse=True)
        print(f"-- {key}: {value['hours']}h")
        for key_date, value_date in sorted_dates:
            print(f"---- {key_date}: {value_date['hours']}h - {value_date['description']}")
        

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
    logging.info("List ToDos")
    logging.debug("Debugging is enabled")
    
    
    # start_date = date(2023, 9, 1)
    # set start date to first day of previous month
    start_date = date.today().replace(day=1) - relativedelta(weeks=1)
    
    end_date = datetime.now().date()
    logging.debug("Start Date: " + str(start_date))
    logging.debug("End Date: " + str(end_date))
    
    time_entry_list, workingtime_by_day_list = get_toggl_time_entries(start_date, end_date)
    
    printDoneTasks(time_entry_list)

    logging.info("Finished List ToDos")