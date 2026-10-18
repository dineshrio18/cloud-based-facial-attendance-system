# Automated & Manual Testing Documentation

## 1. Automated Test Suite Summary

The automated test suite runs via `pytest` without requiring physical webcam hardware or active AWS credentials:

| Test Module | Coverage Scope | Status |
| :--- | :--- | :--- |
| `tests/test_auth.py` | PBKDF2 password hashing, invalid credentials rejection, session management, CSRF token validation, route authorization guards | **PASSED (4/4)** |
| `tests/test_database.py` | Database connectivity health check, SQL injection prevention with parameterized queries, duplicate student ID rejection, student CRUD lifecycle, connection failure handling | **PASSED (5/5)** |
| `tests/test_attendance.py` | Live facial recognition attendance recording, duplicate attendance prevention on identical date, database unique constraint `(student_id, attendance_date)`, real-time percentage calculations, CSV export generation | **PASSED (5/5)** |
| `tests/test_face_matching.py` | 128D Euclidean distance computation, strict thresholding cutoff, unknown individual classification, ambiguity margin check between top candidates, versioned JSON serialization and cache loading | **PASSED (4/4)** |
| `tests/test_s3_storage.py` | S3 health check when unconfigured, private S3 upload with SSE-S3 AES256 server-side encryption, error detection, database status tracking (`upload_failed`), and batch retry reconciliation | **PASSED (3/3)** |

**Total Automated Coverage: 21 Passed / 0 Failed (100% Pass Rate)**

### Executing Automated Tests:
```powershell
python -m pytest -v
```

---

## 2. Threshold Calibration: False Acceptance vs. False Rejection

In biometric recognition, the Euclidean distance threshold controls the trade-off between:
- **False Acceptance Rate (FAR)**: An unknown person or imposter is mistakenly recognized as a registered student.
- **False Rejection Rate (FRR)**: A legitimate, registered student is not recognized by the system.

$$\text{Euclidean Distance: } d(u, v) = \sqrt{\sum_{i=1}^{128} (u_i - v_i)^2}$$

| Threshold ($T$) | Characteristics | Recommended Usage |
| :---: | :--- | :--- |
| **0.40 - 0.45** | Very strict. Low FAR, higher FRR. Requires clean lighting and direct facial orientation. | High-security facilities, examination access. |
| **0.50 (Default)** | Balanced enterprise baseline. Optimal trade-off between recognition convenience and security. | Classroom and institutional daily attendance. |
| **0.55 - 0.60** | Forgiving. Lower FRR, higher risk of false acceptance if multiple individuals share similar facial structures. | Casual demonstrations, low-light environments. |

---

## 3. Manual Live Testing Protocol with Consenting Participants

For laboratory demonstration and technical evaluation:

### Step 1: Pre-requisites
- Ensure local PC has an attached webcam.
- Start application: `python app.py`.
- Navigate to `http://127.0.0.1:5000` and sign in with admin credentials (`admin` / `Admin@123`).

### Step 2: Student Registration
1. Navigate to **Register Student**.
2. Enter Student ID: `TEST001`, Full Name: `Test Participant Alpha`, Department: `Computer Science`.
3. Check the **Biometric Consent** box.
4. Click **Create Profile & Start Face Capture**.
5. Click **Open Camera & Start Capture**.
6. The participant should face the camera and slowly turn their head $\pm 15^\circ$ horizontally and vertically until 35 samples are captured.
7. Click **Finalize Enrollment & Train Model**.

### Step 3: Positive Identification Verification
1. Navigate to **Live Recognition**.
2. Click **Start Camera**.
3. Participant Alpha faces the camera.
4. Verify:
   - Green bounding box appears around their face.
   - Name `Test Participant Alpha (TEST001)` is displayed with Euclidean distance ($\le 0.50$) and confidence percentage.
   - Attendance status indicates: `Attendance recorded for Test Participant Alpha`.
   - Subsequent frames show `Recognition cooldown active` or `Already marked today`.

### Step 4: Unknown Individual Verification
1. Have an unregistered participant (Participant Beta) step in front of the camera.
2. Verify:
   - A **RED bounding box** appears around Participant Beta's face.
   - Label reads **"Unknown Person"** with distance $> 0.50$.
   - **No attendance record is created** in the database.

### Step 5: Duplicate Prevention Audit
1. Navigate to **Attendance Records**.
2. Verify that Participant Alpha has **exactly 1 attendance record** for today's date.
3. Test manual mark for the same student on today's date and observe rejection by the system.
4. Click **Export to CSV** and confirm generated CSV file contains the record.
