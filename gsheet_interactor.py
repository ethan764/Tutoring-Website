from gspread import service_account
from datetime import datetime, timezone

gc = service_account(filename="g_apikey.json") ###
sh = gc.open("Lesson and Payment Record Spreadsheet")


balance_sheet = sh.worksheet('balance')
def get_student_info():
    information=balance_sheet.get_all_records()

    students_update = {}

    for dict in information:
        if dict['Name'] != '':
            print(dict['Meeting Times'])
            students_update[dict['Name']] = {
                'lessons_taken' : int(dict['Hours Spent']),
                'lessons_credited' : int(dict['Hours Credited']),
                'meeting_link' : dict['Meet Link'],
                'schedule' : dict['Meeting Times'].split(', ')
            }

    return students_update

lessons_sheet = sh.worksheet('Lesson Record')
sheets_timestamp_format = "%m/%d/%Y %H:%M:%S"

def get_lesson_info():
    information=lessons_sheet.get_all_records()
    students_lesson_info = {} # dictionary with keys as student name; value pairs as dictionaries of dictionaries representing the lessons
    # not made to scale lol

    for lesson in information:
        students_lesson_info.setdefault(lesson['Student'], {})

        dt = datetime.strptime(lesson['Timestamp'], sheets_timestamp_format)
        students_lesson_info[lesson['Student']][str(dt.date())] = {
            'post_lesson_notes' : lesson['Notes'],
            'lesson_duration' : int(lesson['Length of Lesson (hrs)'])
        }

    return students_lesson_info