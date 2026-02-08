from datetime import datetime
from sqlalchemy import and_, func, or_
from .db import get_session
from .models import (
    Student,
    PlanVersion,
    Enrollment,
    Course,
    StudentPlanItem,
)


def get_current_plan(student_id: int):
    """Get the current (vigente) PlanVersion for a student.

    Returns PlanVersion if found, None otherwise.
    """
    with get_session() as session:
        plan = (
            session.query(PlanVersion)
            .filter(and_(
                PlanVersion.student_id == student_id,
                PlanVersion.vigente_desde <= datetime.now(),
                or_(
                    PlanVersion.vigente_hasta.is_(None),
                    PlanVersion.vigente_hasta >= datetime.now(),
                ),
            ))
            .order_by(PlanVersion.vigente_desde.desc())
            .first()
        )
        return plan


def count_electives_completed(student_id: int, elective_type: str = "electiva") -> int:
    """Count total completed electives for a student.

    Args:
        student_id: Student identifier
        elective_type: Value in Course.tipo_materia to match (default: 'electiva')

    Returns:
        Count of completed electives
    """
    with get_session() as session:
        count = (
            session.query(func.count(Enrollment.id))
            .join(Course, Enrollment.course_id == Course.course_id)
            .filter(and_(
                Enrollment.student_id == student_id,
                Enrollment.status == "completed",
                Course.tipo_materia == elective_type,
            ))
            .scalar()
        )
        return count or 0


def elective_counts_by_orientation(student_id: int, elective_type: str = "electiva") -> dict:
    """Count completed electives per orientation.

    Returns dict: {orientation: count}
    """
    with get_session() as session:
        rows = (
            session.query(Course.orientacion, func.count(Enrollment.id))
            .join(Enrollment, Enrollment.course_id == Course.course_id)
            .filter(and_(
                Enrollment.student_id == student_id,
                Enrollment.status == "completed",
                Course.tipo_materia == elective_type,
            ))
            .group_by(Course.orientacion)
            .all()
        )
        return {orient or "sin_orientacion": count for orient, count in rows}


def check_rule_5_of_8(student_id: int, elective_type: str = "electiva", required_count: int = 5) -> tuple:
    """Check if student meets the 5/8 rule: at least `required_count` electives in one orientation.

    Returns (ok: bool, best_orientation: str, best_count: int)
    """
    counts = elective_counts_by_orientation(student_id, elective_type)
    if not counts:
        return (False, None, 0)

    best_orient = max(counts.items(), key=lambda x: x[1])
    best_orient_name, best_count = best_orient
    ok = best_count >= required_count
    return (ok, best_orient_name, best_count)


def risk_score(student_id: int, elective_type: str = "electiva", target_count: int = 5) -> dict:
    """Simple risk scoring for a student.

    Returns dict with:
        - total_completed: total electives completed
        - gap_to_target: difference to reach target_count in best orientation
        - best_orientation: best performing orientation
        - best_count: best count achieved
        - risk_level: 'low' if ok, 'medium' if close, 'high' if far
    """
    counts = elective_counts_by_orientation(student_id, elective_type)
    total = sum(counts.values())

    if not counts:
        return {
            "total_completed": 0,
            "gap_to_target": target_count,
            "best_orientation": None,
            "best_count": 0,
            "risk_level": "high",
        }

    best_orient, best_count = max(counts.items(), key=lambda x: x[1])
    gap = max(0, target_count - best_count)

    if gap == 0:
        risk_level = "low"
    elif gap <= 2:
        risk_level = "medium"
    else:
        risk_level = "high"

    return {
        "total_completed": total,
        "gap_to_target": gap,
        "best_orientation": best_orient,
        "best_count": best_count,
        "risk_level": risk_level,
    }


def aggregated_metrics_by_cohort(cohort: str, elective_type: str = "electiva") -> dict:
    """Aggregate metrics for all students in a cohort.

    Returns dict with stats: total_students, rule_5_8_compliant, avg_electives_completed, by_orientation_avg
    """
    with get_session() as session:
        students = session.query(Student.student_id).filter(Student.cohorte == cohort).all()
        student_ids = [s[0] for s in students]

        if not student_ids:
            return {
                "cohort": cohort,
                "total_students": 0,
                "rule_5_8_compliant": 0,
                "avg_electives_completed": 0.0,
            }

        compliant_count = sum(
            1 for sid in student_ids if check_rule_5_of_8(sid, elective_type)[0]
        )
        avg_completed = sum(
            count_electives_completed(sid, elective_type) for sid in student_ids
        ) / len(student_ids)

        return {
            "cohort": cohort,
            "total_students": len(student_ids),
            "rule_5_8_compliant": compliant_count,
            "rule_5_8_compliance_rate": compliant_count / len(student_ids),
            "avg_electives_completed": avg_completed,
        }


def aggregated_metrics_by_program(program: str, elective_type: str = "electiva") -> dict:
    """Aggregate metrics for all students in a program.

    Returns dict with stats
    """
    with get_session() as session:
        students = session.query(Student.student_id).filter(Student.programa == program).all()
        student_ids = [s[0] for s in students]

        if not student_ids:
            return {
                "program": program,
                "total_students": 0,
                "rule_5_8_compliant": 0,
                "avg_electives_completed": 0.0,
            }

        compliant_count = sum(
            1 for sid in student_ids if check_rule_5_of_8(sid, elective_type)[0]
        )
        avg_completed = sum(
            count_electives_completed(sid, elective_type) for sid in student_ids
        ) / len(student_ids)

        return {
            "program": program,
            "total_students": len(student_ids),
            "rule_5_8_compliant": compliant_count,
            "rule_5_8_compliance_rate": compliant_count / len(student_ids),
            "avg_electives_completed": avg_completed,
        }
