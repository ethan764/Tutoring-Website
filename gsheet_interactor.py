from gspread import service_account
from datetime import datetime, timezone

gc = service_account(filename="g_apikey.json") ###
sh = gc.open("Lesson and Payment Record Spreadsheet")


balance_sheet = sh.worksheet('balance')
def update_student_info():
    information=balance_sheet.get_all_records()

    students_update = {}

    for dict in information:
        if dict['Name'] != '':
            students_update[dict['Name']] = {
                'lessons_taken' : dict['Hours Spent'],
                'lessons_credited' : dict['Hours Credited'],
                'meeting_link' : dict['Meet Link'],
                'schedule' : dict['Meeting Times']
            }

    return students_update

lessons_sheet = sh.worksheet('Lesson Record')
sheets_timestamp_format = "%m/%d/%Y %H:%M:%S"

def get_lesson_info(student_name):
    information=lessons_sheet.get_all_records()
    lesson_info = {}

    for lesson in information:
        dt = datetime.strptime(lesson['Timestamp'], sheets_timestamp_format)
        lesson_info[dt.date] = {}