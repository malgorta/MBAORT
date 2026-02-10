from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    Text,
    Float,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base


class Course(Base):
    __tablename__ = "courses"
    course_id = Column(String, primary_key=True, index=True)
    programa = Column(String, index=True)
    anio = Column(Integer, index=True, nullable=True)
    materia = Column(String, index=True)
    inicio = Column(Date, nullable=True)
    final = Column(Date, nullable=True)
    dia = Column(String, nullable=True)
    horario = Column(String, nullable=True)
    formato = Column(String, nullable=True)
    horas = Column(Float, nullable=True)
    tipo_materia = Column(String, nullable=True)
    orientacion = Column(String, nullable=True, index=True)
    comentarios = Column(Text)


class CourseSource(Base):
    __tablename__ = "course_sources"
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(String, ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False, index=True)
    solapa_fuente = Column(String, nullable=True)
    orientacion_fuente = Column(String, nullable=True)
    modulo = Column(String, nullable=True)
    row_fuente = Column(Integer, nullable=True)

    course = relationship("Course", backref="sources")

    __table_args__ = (UniqueConstraint("course_id", "solapa_fuente", "row_fuente", name="uq_course_source"),)


class Student(Base):
    __tablename__ = "students"
    student_id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    programa = Column(String, nullable=True, index=True)
    cohorte = Column(String, nullable=True)
    extra = Column(Text, nullable=True)


class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="SET NULL"), nullable=True, index=True)
    fecha = Column(DateTime, nullable=False)
    orientacion_objetivo = Column(String, nullable=True)
    acuerdo_texto = Column(Text, nullable=True)
    notas = Column(Text, nullable=True)

    student = relationship("Student", backref="meetings")


class PlanVersion(Base):
    __tablename__ = "plan_versions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    version_num = Column(Integer, nullable=False)
    vigente_desde = Column(DateTime, nullable=False)
    vigente_hasta = Column(DateTime, nullable=True)
    comentario = Column(Text, nullable=True)

    student = relationship("Student", backref="plan_versions")

    __table_args__ = (Index("ix_student_version", "student_id", "version_num"),)


class StudentPlanItem(Base):
    __tablename__ = "student_plan_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_version_id = Column(Integer, ForeignKey("plan_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.course_id", ondelete="RESTRICT"), nullable=False, index=True)
    prioridad = Column(Integer, nullable=True)
    estado_plan = Column(String, nullable=False)  # planned/backup
    nota = Column(Text, nullable=True)

    plan_version = relationship("PlanVersion", backref="items")
    course = relationship("Course")


class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.course_id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String, nullable=False, index=True)  # planned/registered/completed/withdrawn/failed
    nota = Column(Text, nullable=True)
    nota_numerica = Column(Float, nullable=True)
    fecha_registro = Column(DateTime, server_default=func.now(), nullable=False)
    fecha_estado = Column(DateTime, nullable=True)

    student = relationship("Student", backref="enrollments")
    course = relationship("Course")


class ChangeLog(Base):
    __tablename__ = "change_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, server_default=func.now(), nullable=False)
    user = Column(String, nullable=True)
    entidad = Column(String, nullable=False)
    entidad_id = Column(String, nullable=True)
    campo = Column(String, nullable=True)
    valor_anterior = Column(Text, nullable=True)
    valor_nuevo = Column(Text, nullable=True)
    motivo = Column(Text, nullable=True)

    __table_args__ = (Index("ix_changelog_entidad", "entidad", "entidad_id"),)
