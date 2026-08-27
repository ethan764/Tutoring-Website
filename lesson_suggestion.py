import os
from ollama import Client

client = Client(
    host="https://ollama.com",
    headers={'Authorization': f'Bearer {os.environ['OLLAMA_API_KEY']}'}
)


def create_problem_set():
    pass

base_instructions_lessons = """ 
I need you to make a suggestion for the homework and notes of the next lesson.
Provided below are other general requirements for your message, standard acronyms and shorthand, 
    general notes regarding the student, and homework and lesson notes from the previous lesson.

-ItA RR. Refers to the book, "Intro to Algebra, by Richard Rusczyk".
-Keep your suggestion clear and relatively brief, Preferabbly less that 50 words.
-Consider the level of difficutly that previous lessons indicate the student can handle, the subject matter, and the long term goals of the student.
-Make inferences where the notes are missing key information, such as long term goals.

General Notes: {}

Previous Lesson Notes: {}""" # This instruction is from base_instructions_lesson.txt; but i was too lazy to connenct it to the file.

def format_previous_lessons(previous_lessons):
    formatted_lessons = []
    iterator = 1
    for lesson in previous_lessons:
        formatted_lesson = f"Lesson {iterator} on {lesson.lesson_date}: Homework: {str.replace(lesson.lesson_work, '\n', ';')} | Lesson Notes: {str.replace(lesson.lesson_notes, '\n', ';')} | Post-Lesson Notes: {str.replace(lesson.post_lesson_notes, '\n', ';')}"
        formatted_lessons.append(formatted_lesson)

        iterator += 1
    return "\n".join(formatted_lessons)

def suggest_lessons_ollama(previous_lessons, general_notes):
    prompt = base_instructions_lessons.format(general_notes, format_previous_lessons(previous_lessons))
    response = client.chat(model="gemma4:31b", messages=[{"role": "user", "content": prompt}])
    return response['message']['content']

