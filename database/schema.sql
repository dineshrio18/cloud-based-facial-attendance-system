-- ==============================================================================
-- Cloud-Based Facial Attendance Recognition System
-- Database Schema for MySQL / Amazon RDS MySQL
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS facial_attendance
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE facial_attendance;

-- Table: admin_users
CREATE TABLE IF NOT EXISTS admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'admin',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_admin_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table: students
CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    department VARCHAR(100) NULL,
    email VARCHAR(150) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_student_status (status),
    INDEX idx_student_dept (department)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table: attendance
CREATE TABLE IF NOT EXISTS attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    attendance_date DATE NOT NULL,
    attendance_time TIME NOT NULL,
    source VARCHAR(30) NOT NULL DEFAULT 'facial_recognition',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_attendance_student FOREIGN KEY (student_id)
        REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT uq_student_attendance_date UNIQUE (student_id, attendance_date),
    INDEX idx_attendance_date (attendance_date),
    INDEX idx_attendance_student_id (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table: face_image_metadata
CREATE TABLE IF NOT EXISTS face_image_metadata (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    object_key VARCHAR(255) NULL,
    local_path VARCHAR(255) NOT NULL,
    image_status VARCHAR(30) NOT NULL DEFAULT 'local_only',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_image_student FOREIGN KEY (student_id)
        REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_image_student (student_id),
    INDEX idx_image_status (image_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
