import todoist_api_python.api as todoist_api
import os

API_KEY = os.getenv("TODOIST_API_KEY")
client = todoist_api.TodoistAPI(API_KEY)

header = "#Tutoring /Lessons"

# FOLLOWING SHOULD BE CALLED ASYNC

def add_lesson(student_name, date_time_string=""):
    title = header + " Lesson For " + student_name + " on " + date_time_string
    return client.add_task_quick(text=title)

def edit_lesson_date(task_id, new_date_time="", completed=False):
    print(f"Editing lesson with task_id: {task_id} to new date: {new_date_time}")

    if completed:
        client.complete_task(task_id)
    return client.update_task(task_id, due_string=new_date_time)