# AWS Cloud Infrastructure Setup Guide
## Amazon RDS MySQL & Amazon S3 Integration

This document outlines the step-by-step procedure to provision and configure AWS RDS MySQL and Amazon S3 for cloud-mode operation of the Facial Attendance System.

---

## 1. AWS RDS MySQL Provisioning

### 1.1 Create RDS MySQL Instance
1. Sign in to the AWS Management Console and open the **Amazon RDS Console**.
2. Click **Create database**.
3. Choose **Standard create** and engine **MySQL** (version 8.0 or 8.4 recommended).
4. Templates: Select **Free tier** (or Dev/Test).
5. Settings:
   - **DB instance identifier**: `facial-attendance-rds`
   - **Master username**: `admin`
   - **Master password**: Use a strong, generated password (record this securely).
6. Instance configuration: `db.t3.micro` or `db.t4g.micro`.
7. Storage: 20 GiB General Purpose SSD (gp2 or gp3).
8. Connectivity:
   - **Virtual Private Cloud (VPC)**: Default VPC or custom institutional VPC.
   - **Publicly accessible**: Choose **Yes** only if connecting directly from your development Windows PC over the internet, OR **No** if connecting via an AWS Site-to-Site VPN or AWS Client VPN.
   - **VPC security group**: Create a new security group named `rds-facial-attendance-sg`.
9. Database authentication: Password authentication.
10. Initial database name: `facial_attendance`.
11. Click **Create database**.

---

### 1.2 Configure RDS Security Group Inbound Rules
> [!CAUTION]
> Never open MySQL port 3306 to `0.0.0.0/0` (the entire internet). Restrict access strictly to your authorized client IP address.

1. In the RDS Console, click your new DB instance and view **Connectivity & security**.
2. Click the link under **VPC security groups**.
3. In the security group editor, click **Edit inbound rules**.
4. Add rule:
   - **Type**: MySQL/Aurora (Port 3306)
   - **Source**: **My IP** (e.g. `203.0.113.45/32`)
   - **Description**: Authorized workstation access for attendance system.
5. Save rules.

---

### 1.3 Download RDS TLS/SSL Certificate (Optional for strict verification)
Amazon RDS supports TLS encrypted connections. To enforce CA verification:
1. Download the Amazon Global CA Bundle:
   ```powershell
   Invoke-WebRequest -Uri "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem" -OutFile "certs/global-bundle.pem"
   ```
2. Set `DB_SSL_CA=certs/global-bundle.pem` in `.env`.

---

## 2. Amazon S3 Bucket Provisioning

### 2.1 Create S3 Bucket
1. Open the **Amazon S3 Console** and click **Create bucket**.
2. Settings:
   - **Bucket name**: e.g., `institutional-facial-attendance-images-prod` (must be globally unique).
   - **AWS Region**: Select the same region as your RDS instance (e.g. `us-east-1`).
3. **Block Public Access settings**:
   - Ensure **"Block all public access"** is checked `[X]`.
   - Facial image biometrics must remain strictly private.
4. **Default encryption**:
   - Server-side encryption: **Enable**.
   - Encryption type: **Amazon S3-managed keys (SSE-S3)** or AWS KMS key.
5. Bucket Versioning: Recommended to enable for audit recovery.
6. Click **Create bucket**.

---

### 2.2 IAM Least-Privilege Policy
Create an IAM Policy with only the permissions required for the attendance system:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AttendanceS3BucketCheck",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::institutional-facial-attendance-images-prod"
    },
    {
      "Sid": "AttendanceS3ObjectOperations",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::institutional-facial-attendance-images-prod/students/*"
    }
  ]
}
```

Attach this policy to an IAM User (for local workstation access) or an IAM Role (for EC2/cloud deployments).

---

## 3. Configuring Local Workstation `.env`

Update your `.env` configuration file:

```ini
APP_MODE=CLOUD

# AWS RDS MySQL Settings
DB_HOST=facial-attendance-rds.c1234567890.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_NAME=facial_attendance
DB_USER=admin
DB_PASSWORD=YourSecureRDSPasswordHere
DB_CONNECT_TIMEOUT=10
DB_SSL_CA=

# AWS S3 Settings
AWS_REGION=us-east-1
S3_BUCKET_NAME=institutional-facial-attendance-images-prod
AWS_PROFILE=default
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

### Initializing RDS Database Schema:
```powershell
python database/init_db.py --mode CLOUD
```

### Validating Cloud Connections:
```powershell
python scripts/test_database.py
python scripts/test_s3.py
```
