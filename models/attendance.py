from dataclasses import dataclass
from typing import Optional


@dataclass
class AttendanceRecord:
    id: Optional[int]
    student_id: int
    attendance_date: str
    attendance_time: str
    source: str = "facial_recognition"
    created_at: Optional[str] = None
    # Joined fields for presentation
    student_code: Optional[str] = None
    student_name: Optional[str] = None
    department: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "AttendanceRecord":
        return cls(
            id=row.get("id"),
            student_id=row.get("student_id"),
            attendance_date=str(row.get("attendance_date")),
            attendance_time=str(row.get("attendance_time")),
            source=row.get("source", "facial_recognition"),
            created_at=str(row.get("created_at")) if row.get("created_at") else None,
            student_code=row.get("student_code") or row.get("student_id_str"),
            student_name=row.get("student_name") or row.get("full_name"),
            department=row.get("department"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "attendance_date": self.attendance_date,
            "attendance_time": self.attendance_time,
            "source": self.source,
            "created_at": self.created_at,
            "student_code": self.student_code,
            "student_name": self.student_name,
            "department": self.department,
        }
