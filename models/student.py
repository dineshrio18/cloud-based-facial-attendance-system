from dataclasses import dataclass
from typing import Optional


@dataclass
class Student:
    id: Optional[int]
    student_id: str
    full_name: str
    department: Optional[str] = None
    email: Optional[str] = None
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "Student":
        return cls(
            id=row.get("id"),
            student_id=row.get("student_id", ""),
            full_name=row.get("full_name", ""),
            department=row.get("department"),
            email=row.get("email"),
            status=row.get("status", "active"),
            created_at=str(row.get("created_at")) if row.get("created_at") else None,
            updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "student_id": self.student_id,
            "full_name": self.full_name,
            "department": self.department,
            "email": self.email,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
