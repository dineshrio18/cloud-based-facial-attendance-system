# System Architecture & Technical Design

## 1. High-Level Architectural Overview

The **Cloud-Based Facial Attendance Recognition System** implements an enterprise, multi-tiered architecture that strictly decouples the user interface, biometric computer vision engine, domain business logic, relational persistence, and cloud object storage.

```
+-----------------------------------------------------------------------------------+
|                                Client Layer                                       |
|  - Modern Web Browser (HTML5, Responsive CSS3, JavaScript, WebRTC Video API)     |
+-----------------------------------------------------------------------------------+
                                         |
                                         | HTTP / REST / MJPEG Streams
                                         v
+-----------------------------------------------------------------------------------+
|                        Flask Application Controller Layer                         |
|  - auth_routes.py         : PBKDF2 Password Auth, Sessions, CSRF Validation      |
|  - dashboard_routes.py    : Real-time KPIs, Cloud Infrastructure Diagnostics      |
|  - student_routes.py      : Biometric Registration, Quality Filtering, CRUD       |
|  - recognition_routes.py  : Dual WebRTC / MJPEG Real-Time Inference Stream       |
|  - attendance_routes.py   : Attendance Logs, Filtering, Sorting, CSV Export      |
|  - settings_routes.py     : Cloud Sync Retries, Model Retraining, Security       |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                             Service Logic Layer                                   |
|  - AuthService            : Session Tokens, Role Verification, Password Hashing   |
|  - FaceCaptureService     : Illumination, Sharpness (Laplacian), Aspect Filter   |
|  - FaceEncodingService    : Versioned 128D Vector Serialization & Memory Cache   |
|  - FaceRecognitionService : Real-time Euclidean Distance & Ambiguity Thresholding|
|  - AttendanceService      : Timezone-aware Atomic Attendance, Anti-duplication    |
|  - DatabaseService        : Unified Query Adaptation (%s <-> ?) & Pooling         |
|  - S3StorageService       : Private Object Backup, SSE-S3 AES256, Batch Retries   |
+-----------------------------------------------------------------------------------+
           |                                                      |
           v                                                      v
+------------------------------------+        +-------------------------------------+
|         Data Persistence           |        |         Cloud Object Storage        |
|  - Local Mode: SQLite3 with FKs    |        |  - AWS S3 Private Bucket            |
|  - Cloud Mode: AWS RDS MySQL       |        |  - Server-Side Encryption (AES256)  |
|    with Connection Pooling & TLS   |        |  - Strict Block Public Access       |
+------------------------------------+        +-------------------------------------+
```

---

## 2. Computer Vision & Biometric Pipeline

The biometric pipeline operates on genuine 128-dimensional continuous metric embeddings:

```
[ Camera Frame (BGR) ]
          |
          v
[ Face Detection & Localization ]
  - Haar Cascade Classifier / Adaptive Chrominance Locator
  - Returns bounding box (top, right, bottom, left)
          |
          v
[ Quality & Geometry Validation ]
  - Single-person frame check
  - Sharpness check: Var(Laplacian) >= 35.0
  - Exposure check: 40.0 <= Mean(Intensity) <= 230.0
  - Resolution: Minimum 60x60 pixel face box
          |
          v
[ 128D Metric Embedding Generation ]
  - Primary Engine : dlib ResNet (face_recognition library)
  - Fallback Engine: PyTorch Deep Metric Feature Extractor (L2 Normalized)
          |
          v
[ Matching & Decision Logic ]
  - Calculate Euclidean distance: d = ||v_query - v_candidate||_2
  - Distance Threshold (Default 0.50):
      * If d <= 0.50 AND (d_second - d) >= 0.05:
            ==> Recognized Subject
            ==> Render GREEN bounding box & Trigger Attendance
      * If d > 0.50 OR d_second - d < 0.05:
            ==> Classified as UNKNOWN
            ==> Render RED bounding box & Block Attendance
```

---

## 3. Database Schema & Relational Integrity

The relational layer enforces strict referential integrity and duplicate prevention at the database level:

```
+--------------------+              +------------------------+
|      students      | 1          * |       attendance       |
+--------------------+--------------+------------------------+
| id (PK)            |              | id (PK)                |
| student_id (UNIQUE)|              | student_id (FK)        |
| full_name          |              | attendance_date (DATE) |
| department         |              | attendance_time (TIME) |
| email              |              | source                 |
| status             |              | created_at             |
| created_at         |              +------------------------+
| updated_at         |              | UNIQUE(student_id,     |
+--------------------+              |        attendance_date)|
          | 1                       +------------------------+
          |
          | *
+------------------------+
|  face_image_metadata   |
+------------------------+
| id (PK)                |
| student_id (FK)        |
| object_key             |
| local_path             |
| image_status           |
| created_at             |
+------------------------+
```

### Unique Attendance Constraint
The unique constraint on `(student_id, attendance_date)` ensures that a student cannot be recorded more than once on any given calendar day, even if multiple camera frames trigger recognition within milliseconds.

---

## 4. Dual Local / Cloud Operating Modes

The system operates deterministically in one of two declared modes:

1. **LOCAL Mode (`APP_MODE=LOCAL`)**:
   - Uses local SQLite database (`data/attendance.db`).
   - Stores captured dataset locally (`data/dataset/<student_id>/`).
   - Operates completely without AWS connectivity or credentials.
   - Ideal for offline classrooms, network outages, and local development.

2. **CLOUD Mode (`APP_MODE=CLOUD`)**:
   - Connects to AWS RDS MySQL via connection pooling.
   - Backs up captured face samples to a private Amazon S3 bucket with server-side encryption.
   - If AWS services are unreachable or misconfigured, errors are reported transparently on the dashboard rather than silently masking failures.
