import sqlite3
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

sq_conn = sqlite3.connect('data/attendance.db')
sq_conn.row_factory = sqlite3.Row
sq_cur = sq_conn.cursor()

my_conn = mysql.connector.connect(
    host=os.environ['DB_HOST'],
    port=int(os.environ['DB_PORT']),
    user=os.environ['DB_USER'],
    password=os.environ['DB_PASSWORD'],
    database=os.environ['DB_NAME']
)
my_cur = my_conn.cursor()

# 1. Migrate Students
sq_cur.execute('SELECT id, student_id, full_name, department, email, status, created_at FROM students')
students = sq_cur.fetchall()
id_map = {}
for s in students:
    my_cur.execute(
        'INSERT INTO students (student_id, full_name, department, email, status, created_at) VALUES (%s, %s, %s, %s, %s, %s)',
        (s['student_id'], s['full_name'], s['department'], s['email'], s['status'], s['created_at'])
    )
    new_id = my_cur.lastrowid
    id_map[s['id']] = new_id
    print(f"Migrated student {s['student_id']} -> MySQL ID {new_id}")

# 2. Migrate Attendance
sq_cur.execute('SELECT student_id, attendance_date, attendance_time, source, created_at FROM attendance')
attendances = sq_cur.fetchall()
for a in attendances:
    if a['student_id'] in id_map:
        my_cur.execute(
            'INSERT INTO attendance (student_id, attendance_date, attendance_time, source, created_at) VALUES (%s, %s, %s, %s, %s)',
            (id_map[a['student_id']], a['attendance_date'], a['attendance_time'], a['source'], a['created_at'])
        )
print(f"Migrated {len(attendances)} attendance records")

# 3. Migrate Face Image Metadata
sq_cur.execute('SELECT student_id, object_key, local_path, image_status, created_at FROM face_image_metadata')
images = sq_cur.fetchall()
for img in images:
    if img['student_id'] in id_map:
        my_cur.execute(
            'INSERT INTO face_image_metadata (student_id, object_key, local_path, image_status, created_at) VALUES (%s, %s, %s, %s, %s)',
            (id_map[img['student_id']], img['object_key'], img['local_path'], img['image_status'], img['created_at'])
        )
print(f"Migrated {len(images)} face image metadata records")

my_conn.commit()
my_cur.close()
my_conn.close()
sq_conn.close()
print("DATA MIGRATION TO AWS RDS FINISHED SUCCESSFULLY!")
