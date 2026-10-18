# Cloud-Based Facial Attendance Recognition System Using AWS

[![Python](https://img.shields.io/badge/Python-3.11%20|%203.12%20|%203.13%20|%203.14-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Backend-Flask%203.1-black.svg)](https://flask.palletsprojects.com/)
[![OpenCV](https://img.shields.io/badge/Computer%20Vision-OpenCV%20%7C%20Deep%20Metric%20128D-green.svg)](https://opencv.org/)
[![AWS](https://img.shields.io/badge/Cloud-AWS%20S3%20%7C%20AWS%20RDS%20MySQL-orange.svg)](https://aws.amazon.com/)
[![Tests](https://img.shields.io/badge/Automated%20Tests-21%20Passed%20(100%25)-success.svg)]()

A complete, enterprise-grade automated biometric attendance management system built with **Python**, **OpenCV**, **Flask**, **Amazon RDS (MySQL)**, and **Amazon S3**. The system captures facial biometric images via webcam, extracts continuous 128-dimensional metric embeddings, prevents duplicate records, and supports standalone **LOCAL mode** (SQLite) as well as production **CLOUD mode** (AWS RDS + S3).

Designed for college classrooms, employee check-ins, final-year computer science project reviews, and technical interviews.

---

## 1. Problem Statement & Objectives

### Problem Statement
Traditional attendance systems relying on paper sheets, RFID badges, or fingerprint scanners suffer from proxy attendance ("buddy punching"), slow queue throughput, hardware maintenance costs, and single-point physical failures.

### Objectives
- **Automated Verification**: Seamlessly recognize registered individuals in real time using webcam video streams.
- **Biometric Integrity**: Extract 128-dimensional Euclidean metric embeddings with configurable threshold cutoff to reject unauthorized or unknown individuals.
- **Enterprise Cloud Storage**: Store high-resolution facial datasets securely in private **Amazon S3** buckets with AES256 server-side encryption.
- **Relational Cloud Persistence**: Record immutable attendance logs in managed **Amazon RDS MySQL** with strict unique constraints preventing duplicate daily records.
- **Zero-Cloud Local Standalone**: Run 100% offline out-of-the-box using local SQLite without requiring AWS credentials for development or demonstrations.

---

## 2. Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Programming Language** | Python 3.11 – 3.14 |
| **Computer Vision Engine** | OpenCV, 128D Deep Metric Biometric Embeddings (dlib / PyTorch MobileNet / Haar Cascade) |
| **Web Framework & Backend** | Flask 3.1, Jinja2, Werkzeug (PBKDF2 Password Hashing), python-dotenv |
| **Frontend UI/UX** | Responsive HTML5, Modern CSS3 (Enterprise Navy / Slate Design System), JavaScript, WebRTC Video API |
| **Database** | Amazon RDS MySQL (Cloud Mode) / SQLite3 (Local Mode), `mysql-connector-python` with Connection Pooling |
| **Cloud Storage** | Amazon S3 with `boto3`, Server-Side Encryption (SSE-S3 AES256) |
| **Testing & Quality** | `pytest` with 21 unit & integration tests covering all services |

---

## 3. System Architecture & Project Structure

```
facialrecognition/
|-- app.py                          # Flask application factory, error handlers, and main entry
|-- config.py                       # Configuration loader, environment validation, path bindings
|-- requirements.txt                # Production and development dependencies
|-- .env.example                    # Template environment variables with placeholders
|-- .gitignore                      # Git exclusion rules for secrets, datasets, and caches
|-- pytest.ini                      # Pytest runner configuration
|-- README.md                       # Master system documentation
|
|-- routes/
|   |-- auth_routes.py              # PBKDF2 authentication, login, logout, CSRF token handling
|   |-- dashboard_routes.py         # Primary overview metrics, system health API
|   |-- student_routes.py           # Student enrollment, webcam frame validation, profile CRUD
|   |-- recognition_routes.py       # Dual MJPEG server stream and WebRTC frame inference
|   |-- attendance_routes.py        # Attendance log table, date/dept filters, CSV report export
|   |-- settings_routes.py          # Cloud sync retries, encoding recompilation, password update
|
|-- services/
|   |-- face_engine.py              # BaseFaceEngine, dlib ResNet & PyTorch Deep Metric adapters
|   |-- face_capture_service.py     # Image quality check (Laplacian blur, brightness, aspect ratio)
|   |-- face_encoding_service.py    # Versioned JSON encoding serialization, memory cache
|   |-- face_recognition_service.py # Live Euclidean distance thresholding, ambiguity checking
|   |-- attendance_service.py       # Atomic attendance recording, unique constraint, CSV builder
|   |-- database_service.py         # Unified SQLite/MySQL adapter, connection pool, health check
|   |-- s3_storage_service.py       # Amazon S3 upload, SSE-S3 AES256 encryption, retry manager
|   |-- auth_service.py             # Password verification, secure sessions, CSRF validators
|
|-- repositories/
|   |-- student_repository.py       # Student profiles and face_image_metadata CRUD
|   |-- attendance_repository.py    # Attendance persistence, duplicate-safe queries, metrics
|   |-- admin_repository.py         # Administrator account credentials and role storage
|
|-- models/
|   |-- student.py                  # Student entity dataclass
|   |-- attendance.py               # Attendance record entity dataclass
|   |-- haarcascade_frontalface_default.xml # Standard OpenCV Haar Cascade model
|
|-- templates/
|   |-- base.html                   # Responsive enterprise master layout with dark navy sidebar
|   |-- login.html                  # Operator authentication portal with show/hide password
|   |-- dashboard.html              # KPI metrics, infrastructure status pills, recent table
|   |-- students.html               # Student directory with search, filter, and pagination
|   |-- student_register.html       # Profile creation with biometric consent disclosure
|   |-- student_detail.html         # Interactive webcam capture module, progress, history
|   |-- recognition.html            # Real-time inference feed, dual camera mode, live event log
|   |-- attendance.html             # Filterable attendance logs, CSV export, manual entry modal
|   |-- settings.html               # Infrastructure diagnostics, S3 sync, model retrain
|   |-- error.html                  # User-friendly HTTP error page (400, 403, 404, 500)
|
|-- static/
|   |-- css/style.css               # Clean enterprise design system stylesheet
|   |-- js/dashboard.js             # Real-time health polling script
|
|-- database/
|   |-- schema.sql                  # Production MySQL / Amazon RDS DDL schema
|   |-- schema_sqlite.sql           # Local standalone SQLite DDL schema
|   |-- init_db.py                  # Schema migration and administrator seed CLI
|
|-- scripts/
|   |-- capture_faces.py            # Standalone CLI tool to capture 35 face images via webcam
|   |-- train_faces.py              # Standalone CLI tool to extract encodings and retrain model
|   |-- verify_database.py          # Standalone database connectivity diagnostic
|   |-- verify_s3.py                # Standalone Amazon S3 connectivity diagnostic
|   |-- test_database.py            # Proxy forwarder for database testing
|   |-- test_s3.py                  # Proxy forwarder for S3 testing
|   |-- init_admin.py               # Administrator account creation and password management
|
|-- tests/
|   |-- test_attendance.py          # Attendance duplicate protection and percentage tests
|   |-- test_database.py            # Parameterized query, SQL injection, and CRUD tests
|   |-- test_face_matching.py       # Distance math, thresholding, and unknown person tests
|   |-- test_auth.py                # Password hashing, CSRF, and session protection tests
|   |-- test_s3_storage.py          # S3 upload mocking, AES256 verification, and retry flow
|
|-- data/dataset/                   # Local face images (excluded from git)
|-- encodings/                      # Serialized biometric models (excluded from git)
|-- logs/                           # Application log files (excluded from git)
|-- docs/
|   |-- architecture.md             # Detailed architecture diagrams and pipeline breakdown
|   |-- aws_setup.md                # Comprehensive AWS RDS and Amazon S3 provisioning guide
|   |-- testing.md                  # Test suite summary and manual testing protocol
```

---

## 4. Installation & Setup Instructions (Windows)

### 4.1 Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit).
- **Python**: Python 3.11, 3.12, 3.13, or 3.14.
- **Hardware**: An integrated or USB webcam.

### 4.2 Installation Commands
Open PowerShell in the project directory:

```powershell
# 1. Create a Python virtual environment
python -m venv .venv

# 2. Activate the virtual environment
.venv\Scripts\activate

# 3. Upgrade pip to the latest release
python -m pip install --upgrade pip

# 4. Install project dependencies
pip install -r requirements.txt
```

> [!NOTE]
> **Windows Platform Compatibility for `dlib` / `face_recognition`:**
> The `face_recognition` library relies on `dlib`, which contains C++ binaries. On Windows, compiling `dlib` from source requires Microsoft Visual Studio C++ Build Tools and CMake.
> **Adaptive Architecture:** If `face_recognition` is not installed or C++ tools are not available on your Windows machine, the application **automatically initializes its built-in Deep Metric Learning Face Engine (OpenCV + PyTorch MobileNet)**, which extracts genuine 128D biometric feature vectors, performs strict L2 normalization, computes Euclidean distances, and executes identical threshold decisions without requiring C++ build tools.

---

## 5. First-Time Setup & Configuration

### 5.1 Environment Configuration
Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

### 5.2 Initialize Database & Admin User
Run the database initialization script. This creates all relational tables and seeds the default administrator account:

```powershell
python database/init_db.py
```

- **Default Administrator Username**: `admin`
- **Default Administrator Password**: `Admin@123`

You can change this password at any time via **Settings & Cloud** in the web dashboard or using:
```powershell
python scripts/init_admin.py --username admin --password "YourNewSecurePassword!"
```

### 5.3 Verify Database Health
Confirm database connectivity and table creation:
```powershell
python scripts/test_database.py
```

---

## 6. Running the Application

Start the Flask server:

```powershell
python app.py
```

Output:
```
[2026-10-18 18:35:00] [INFO] [app]: Initializing Facial Attendance Application [Mode: LOCAL]
[2026-10-18 18:35:00] [INFO] [attendance.face_engine]: Initialized DeepMetricFaceEngine (OpenCV/PyTorch 128D Metric backend)
[2026-10-18 18:35:00] [INFO] [app]: Starting server on http://127.0.0.1:5000
```

Open your browser and navigate to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

Sign in using:
- **Username**: `admin`
- **Password**: `Admin@123`

---

## 7. Operational Workflow

```
1. Operator Login
       |
       v
2. Register Student (Profile + Biometric Consent)
       |
       v
3. Interactive Camera Capture (35 samples with quality filtering)
       |
       v
4. Finalize Enrollment (Generate 128D encodings + optional S3 backup)
       |
       v
5. Launch Live Recognition (Dual WebRTC / MJPEG modes)
       |
       +---> Match found (Dist <= 0.50) ==> GREEN box ==> Attendance Recorded
       |
       +---> No match (Dist > 0.50)    ==> RED box   ==> Blocked as "Unknown"
       |
       v
6. View & Export Attendance Logs (Filter by date, department, export CSV)
```

### 7.1 Registering a Student
1. In the sidebar, click **Register Student**.
2. Enter **Student ID** (e.g. `CS202601`), **Full Name**, **Department**, and **Email**.
3. Check the **Biometric Consent** checkbox acknowledging facial data processing.
4. Click **Create Profile & Start Face Capture**.
5. Click **Open Camera & Start Capture**.
6. The webcam viewport will activate. Look at the camera and turn your head slightly ($\pm 15^\circ$) to collect 35 valid samples.
7. Click **Finalize Enrollment & Train Model**.

### 7.2 Running Live Recognition
1. Click **Live Recognition** in the navigation menu.
2. Select your preferred camera mode:
   - **Browser WebRTC Mode**: Captures directly via your web browser with client-side overlay.
   - **Server MJPEG Mode**: Streams directly from a webcam attached to the server machine.
3. Click **Start Camera**.
4. The system detects faces in real time:
   - **Registered Person**: Displays a **GREEN** bounding box, student name, ID, Euclidean distance, and confidence percentage. Attendance is marked automatically with duplicate protection.
   - **Unknown Person**: Displays a **RED** bounding box labeled **"Unknown Person"**. Attendance is **never** recorded for unmatched individuals.

### 7.3 Viewing & Exporting Attendance Records
1. Click **Attendance Records**.
2. Filter records by **Date Range**, **Department**, or **Verification Source**.
3. Click **Export to CSV** to download a spreadsheet report for institutional audits.

---

## 8. AWS Cloud Mode Configuration

To enable AWS Cloud integration:

### 8.1 AWS RDS MySQL
1. Follow the step-by-step RDS setup instructions in [docs/aws_setup.md](file:///c:/Users/Dinesh/OneDrive/Desktop/facialrecognition/docs/aws_setup.md).
2. Ensure the RDS security group allows inbound traffic on port 3306 from your IP address.
3. Apply the database schema to RDS:
   ```powershell
   python database/init_db.py --mode CLOUD
   ```

### 8.2 Amazon S3
1. Create a private Amazon S3 bucket with **Block All Public Access** enabled.
2. Enable default **Server-Side Encryption (SSE-S3 AES256)**.
3. Configure AWS CLI credentials on Windows:
   ```powershell
   aws configure
   ```

### 8.3 Switch Application to CLOUD Mode
Edit your `.env` file:
```ini
APP_MODE=CLOUD

DB_HOST=your-rds-endpoint.c1234567890.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_NAME=facial_attendance
DB_USER=admin
DB_PASSWORD=YourSecureRDSPassword
DB_CONNECT_TIMEOUT=10

AWS_REGION=us-east-1
S3_BUCKET_NAME=your-private-attendance-bucket
AWS_PROFILE=default
```

Run diagnostics to verify both connections:
```powershell
python scripts/test_database.py
python scripts/test_s3.py
```

---

## 9. Running Automated Tests

The test suite runs with 100% isolation and does not require AWS credentials or physical webcams:

```powershell
python -m pytest -v
```

Output:
```
============================= test session starts =============================
tests/test_attendance.py::test_mark_face_attendance_success PASSED       [  4%]
tests/test_attendance.py::test_duplicate_attendance_prevented PASSED     [  9%]
tests/test_attendance.py::test_database_unique_constraint_enforcement PASSED [ 14%]
tests/test_attendance.py::test_attendance_percentage_calculation PASSED  [ 19%]
tests/test_attendance.py::test_csv_export PASSED                         [ 23%]
tests/test_auth.py::test_password_verification PASSED                    [ 28%]
tests/test_auth.py::test_csrf_token_validation PASSED                    [ 33%]
tests/test_auth.py::test_protected_route_requires_login PASSED           [ 38%]
tests/test_auth.py::test_successful_admin_login PASSED                   [ 42%]
tests/test_database.py::test_database_health_check PASSED                [ 47%]
tests/test_database.py::test_parameterized_queries_prevent_injection PASSED [ 52%]
tests/test_database.py::test_duplicate_student_id_rejection PASSED       [ 57%]
tests/test_database.py::test_student_crud_lifecycle PASSED               [ 61%]
tests/test_database.py::test_database_connection_failure_handling PASSED [ 66%]
tests/test_face_matching.py::test_euclidean_distance_computation PASSED  [ 71%]
tests/test_face_matching.py::test_face_matching_threshold_and_unknown_handling PASSED [ 76%]
tests/test_face_matching.py::test_ambiguity_margin_rejection PASSED      [ 80%]
tests/test_face_matching.py::test_versioned_encoding_file_serialization_and_loading PASSED [ 85%]
tests/test_s3_storage.py::test_s3_health_check_unconfigured PASSED       [ 90%]
tests/test_s3_storage.py::test_s3_upload_success_with_mock PASSED        [ 95%]
tests/test_s3_storage.py::test_s3_upload_failure_and_retry_flow PASSED   [100%]
============================= 21 passed in 11.82s =============================
```

---

## 10. Security, Privacy & Biometric Ethics

1. **Biometric Data Consent**: The registration workflow mandates explicit operator confirmation of biometric consent before facial images can be stored.
2. **Password Security**: Passwords are never stored in plain text. Secure PBKDF2 with SHA-256 and salt is enforced via `werkzeug.security`.
3. **Session & CSRF Protection**: All state-changing POST requests validate a cryptographically secure CSRF token. Session cookies enforce `SameSite=Lax` and `HTTPOnly`.
4. **Parameterization**: All database queries use parameterized placeholders (`%s` / `?`) to prevent SQL injection vulnerabilities.
5. **Private Cloud Storage**: S3 buckets block all public access. All images are encrypted at rest with `ServerSideEncryption=AES256`. Public URLs are never generated or displayed.
6. **Data Deletion Rights**: Deleting a student permanently removes their database record, cascades deletion to attendance logs, purges local image datasets, purges S3 cloud objects, and recompiles biometric encodings so the individual can no longer be identified.

---

## 11. Known Limitations & Future Enhancements

- **Liveness Detection**: Real-time anti-spoofing against printed photos or video replays is **not active** in this release. An informational banner is displayed on the recognition screen. Multi-spectral infrared cameras or challenge-response eye-blink / texture analysis (e.g. MiniFASNet) is planned for a future release.
- **Multiple Simultaneous Faces**: Multiple faces in the frame are independently bounded and evaluated; however, in high-density crowd scenarios, individual single-person registration should be maintained.
- **Extreme Lighting Variations**: Under extreme backlight or complete darkness, facial feature extraction accuracy diminishes. Supplementary diffuse lighting is recommended.

---

## 12. Troubleshooting Common Issues

| Issue | Cause | Resolution |
| :--- | :--- | :--- |
| **"Webcam index 0 could not be opened"** | Camera is in use by another program (Teams, Zoom, Windows Camera app) or disconnected. | Close other webcam applications or switch to **Browser WebRTC Mode** on the recognition screen. |
| **"Failed building wheel for dlib"** | Missing Visual C++ tools on Windows. | No action required. The system includes an automatic fallback to the **OpenCV / PyTorch Deep Metric Face Engine**, which runs natively on Windows without C++ compilers. |
| **"Database connection failed"** | Missing `.env` credentials or RDS security group not allowing port 3306. | Set `APP_MODE=LOCAL` in `.env` to use SQLite, or verify that your current public IP is authorized in the RDS security group inbound rules. |
| **"Missing S3 configuration"** | S3 bucket name or region empty in `.env`. | Provide `S3_BUCKET_NAME` and `AWS_REGION` in `.env`, or remain in `LOCAL` mode. |

---

## 13. License & Academic Attribution
Developed as an advanced academic and enterprise engineering project for Automated Facial Attendance Verification using Computer Vision and AWS Cloud Services.
