import json
from pathlib import Path
import sys
import numpy as np
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import TestingConfig
from services.face_engine import BaseFaceEngine, get_face_engine
from services.face_encoding_service import FaceEncodingService
from repositories.student_repository import StudentRepository
from services.database_service import DatabaseService
from database.init_db import init_sqlite_database


def test_euclidean_distance_computation():
    engine = get_face_engine()

    # Identical vectors -> distance 0.0
    v1 = np.ones(128, dtype=np.float32) / np.sqrt(128)
    dist_same = engine.compute_distance(v1, v1)
    assert abs(dist_same - 0.0) < 1e-6

    # Orthogonal vectors -> distance sqrt(2) ≈ 1.4142
    v_a = np.zeros(128, dtype=np.float32)
    v_a[0] = 1.0
    v_b = np.zeros(128, dtype=np.float32)
    v_b[1] = 1.0
    dist_ortho = engine.compute_distance(v_a, v_b)
    assert abs(dist_ortho - np.sqrt(2)) < 1e-5


def test_face_matching_threshold_and_unknown_handling():
    engine = get_face_engine()
    threshold = 0.50

    # Registered known face vectors
    known_1 = np.zeros(128, dtype=np.float32)
    known_1[0] = 1.0

    known_2 = np.zeros(128, dtype=np.float32)
    known_2[1] = 1.0

    known_encodings = [known_1, known_2]

    # Test 1: Close match to known_1 (small perturbation)
    query_match = known_1.copy()
    query_match[2] = 0.1
    query_match /= np.linalg.norm(query_match)

    best_idx, best_dist, is_ambiguous = engine.find_best_match(
        known_encodings, query_match, threshold=threshold
    )
    assert best_idx == 0
    assert best_dist < threshold
    assert is_ambiguous is False

    # Test 2: Unknown person (completely distinct vector)
    query_unknown = np.zeros(128, dtype=np.float32)
    query_unknown[10] = 1.0

    best_idx_unk, best_dist_unk, _ = engine.find_best_match(
        known_encodings, query_unknown, threshold=threshold
    )
    # MUST classify as Unknown (best_idx is None) even though a mathematical nearest neighbor exists!
    assert best_idx_unk is None
    assert best_dist_unk > threshold


def test_ambiguity_margin_rejection():
    engine = get_face_engine()
    threshold = 0.50
    ambiguity_margin = 0.05

    # Two known faces that are very close
    known_a = np.zeros(128, dtype=np.float32)
    known_a[0] = 0.99
    known_a[1] = 0.10
    known_a /= np.linalg.norm(known_a)

    known_b = np.zeros(128, dtype=np.float32)
    known_b[0] = 0.99
    known_b[2] = 0.10
    known_b /= np.linalg.norm(known_b)

    query = np.zeros(128, dtype=np.float32)
    query[0] = 1.0

    best_idx, best_dist, is_ambiguous = engine.find_best_match(
        [known_a, known_b], query, threshold=threshold, ambiguity_margin=ambiguity_margin
    )
    # Distances to known_a and known_b are identical/within 0.05, so is_ambiguous must be True
    assert is_ambiguous is True


def test_versioned_encoding_file_serialization_and_loading(tmp_path):
    enc_file = tmp_path / "encodings.json"

    # Synthetic payload
    payload = {
        "version": "1.0",
        "engine": "TestEngine",
        "generated_at": "2026-10-18T12:00:00",
        "total_students": 1,
        "total_encodings": 2,
        "students": [
            {
                "id": 1,
                "student_id": "CS001",
                "name": "Alice Tester",
                "encodings": [
                    [0.1] * 128,
                    [0.2] * 128
                ]
            }
        ]
    }
    with open(enc_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    service = FaceEncodingService(encodings_file=enc_file)
    assert service.load_encodings() is True
    encs, meta = service.get_registered_encodings()
    assert len(encs) == 2
    assert len(meta) == 2
    assert meta[0]["student_code"] == "CS001"
    assert meta[0]["name"] == "Alice Tester"
