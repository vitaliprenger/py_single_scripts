from helper.toggl_parse_data import get_toggl_time_entries
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

jira_url = "https://eucon.atlassian.net"

def printDoneTasks (timeEntryList):
    
    doneListSummed = {}
    doneListByTicket = {}
    hoursSum = 0
    for project in timeEntryList:
        if "2779 " in project:
            for date in timeEntryList[project]:
                for ticket in timeEntryList[project][date]:
                    for description, hours in timeEntryList[project][date][ticket].items():
                            
                        if doneListSummed.get(ticket) is None:
                            doneListSummed[ticket] = {}
                        if doneListSummed[ticket].get("hours") is None:
                            doneListSummed[ticket]["hours"] = hours
                            doneListSummed[ticket]["description"] = description
                        else:
                            doneListSummed[ticket]["hours"] += hours
                            doneListSummed[ticket]["description"] += ", " + description
                    
                        if doneListByTicket.get(ticket) is None:
                            doneListByTicket[ticket] = {}
                        if doneListByTicket[ticket].get(description) is None:
                            doneListByTicket[ticket][description] = hours
                        else:
                            doneListByTicket[ticket][description] += hours
                        
                        hoursSum += hours
    
    print(f"--------- Sort by Time Spend -----------------------------------------")
    sorted_tickets = sorted(doneListSummed.items(), key=lambda x: x[1]["hours"], reverse=True) # sorted by hours
    for key, value in sorted_tickets:
        ticket = doneListByTicket[key]
        sorted_dates = sorted(ticket.items(), key=lambda x: x[1], reverse=True)
        print(f"{key}: {value['hours']}h")
        # for key_desc, value_desc in sorted_dates:
        #     print(f"-- {value_desc}h - {key_desc}")
    print("Gesamtstunden: " + str(hoursSum) + " h")
        

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
    start_date = date.today().replace(day=1) - relativedelta(months=1)
    
    end_date = datetime.now().date().replace(day=1) #+ relativedelta(days=1)
    logging.debug("Start Date: " + str(start_date))
    logging.debug("End Date: " + str(end_date))
    
    time_entry_list, workingtime_by_day_list, time_entry_list_detail = get_toggl_time_entries(start_date, end_date)
    
    printDoneTasks(time_entry_list_detail)

    logging.info("Finished List ToDos")