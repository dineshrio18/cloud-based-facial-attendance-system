"""
AWS RDS Cloud Database Inspector
Quickly inspect live tables and records in your Amazon RDS MySQL database.
"""
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def inspect_rds():
    print("=" * 70)
    print(" LIVE AWS RDS DATABASE INSPECTOR (facial_attendance)")
    print(" Host:", os.environ.get("DB_HOST"))
    print("=" * 70)

    try:
        conn = mysql.connector.connect(
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", 3306)),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            connection_timeout=10
        )
        cursor = conn.cursor(dictionary=True)

        # 1. Students Table
        print("\n[TABLE: students]")
        cursor.execute("SELECT id, student_id, full_name, department, email, status, created_at FROM students")
        students = cursor.fetchall()
        if not students:
            print("  (No student records found)")
        else:
            for s in students:
                print(f"  - ID: {s['id']} | Roll No: {s['student_id']} | Name: {s['full_name']} | Dept: {s['department']} | Status: {s['status']}")

        # 2. Attendance Table
        print("\n[TABLE: attendance]")
        cursor.execute("""
            SELECT a.id, s.student_id, s.full_name, a.attendance_date, a.attendance_time, a.source
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            ORDER BY a.attendance_date DESC, a.attendance_time DESC
        """)
        attendance = cursor.fetchall()
        if not attendance:
            print("  (No attendance records yet)")
        else:
            for a in attendance:
                print(f"  - {a['attendance_date']} at {a['attendance_time']} | Roll: {a['student_id']} | Name: {a['full_name']} | Source: {a['source']}")

        # 3. Face Images Metadata Table (Linked to S3)
        print("\n[TABLE: face_image_metadata]")
        cursor.execute("""
            SELECT fim.id, s.student_id, fim.object_key, fim.image_status, fim.created_at
            FROM face_image_metadata fim
            JOIN students s ON s.id = fim.student_id
            LIMIT 5
        """)
        images = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) as total FROM face_image_metadata")
        total_images = cursor.fetchone()["total"]
        print(f"  Total face images registered in RDS: {total_images}")
        for img in images:
            print(f"  - Img #{img['id']} (Roll {img['student_id']}) -> S3 Key: {img['object_key']} [{img['image_status']}]")
        if total_images > 5:
            print(f"    ... and {total_images - 5} more images in S3.")

        # 4. Admin Users Table
        print("\n[TABLE: admin_users]")
        cursor.execute("SELECT id, username, role, is_active, created_at FROM admin_users")
        admins = cursor.fetchall()
        for adm in admins:
            print(f"  - User: {adm['username']} | Role: {adm['role']} | Active: {bool(adm['is_active'])}")

        cursor.close()
        conn.close()
        print("\n" + "=" * 70)
        print("[SUCCESS] All records above were read live directly from Amazon RDS MySQL!")
        print("=" * 70)

    except Exception as e:
        print("\nError querying RDS:", e)


if __name__ == "__main__":
    inspect_rds()
