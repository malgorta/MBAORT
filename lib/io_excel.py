import os
from typing import Union
import pandas as pd

from .validators import validate_cronograma_df
from .db import init_db, get_session
from .models import Course, CourseSource


def _norm_str(value):
    if pd.isna(value):
        return None
    s = str(value).strip()
    # collapse whitespace
    s = " ".join(s.split())
    return s


def import_schedule_excel(uploaded_file_or_path: Union[str, bytes, os.PathLike, object]):
    """Read sheet 'CronogramaConsolidado', validate and upsert into DB.

    Returns summary dict: created_courses, updated_courses, created_sources, updated_sources, errors
    """
    summary = {
        "created_courses": 0,
        "updated_courses": 0,
        "created_sources": 0,
        "updated_sources": 0,
        "errors": [],
    }

    # Read excel
    try:
        if hasattr(uploaded_file_or_path, "read"):
            df = pd.read_excel(uploaded_file_or_path, sheet_name="CronogramaConsolidado", engine="openpyxl")
        else:
            df = pd.read_excel(str(uploaded_file_or_path), sheet_name="CronogramaConsolidado", engine="openpyxl")
    except Exception as e:
        summary["errors"].append(f"Error leyendo Excel: {e}")
        return summary

    # Validate
    df, errors = validate_cronograma_df(df)
    if errors:
        summary["errors"].extend(errors)
        return summary

    # Ensure DB and tables exist
    init_db()

    with get_session() as session:
        for idx, row in df.reset_index(drop=True).iterrows():
            try:
                course_id = _norm_str(row.get("MateriaID"))
                if not course_id:
                    summary["errors"].append(f"Fila {idx}: MateriaID vacío")
                    continue

                # Normalize fields
                programa = _norm_str(row.get("Programa"))

                # Convert anio (Integer) - handle NaN safely
                try:
                    anio_val = row.get("Año")
                    if pd.isna(anio_val) or anio_val == '':
                        anio = None
                    else:
                        anio = int(float(anio_val))
                except (ValueError, TypeError):
                    anio = None

                modulo = _norm_str(row.get("Módulo"))
                materia = _norm_str(row.get("Materia"))

                # Convert horas (Float) - handle NaN safely
                try:
                    horas_val = row.get("Horas")
                    if pd.isna(horas_val) or horas_val == '':
                        horas = None
                    else:
                        horas = float(horas_val)
                except (ValueError, TypeError):
                    horas = None

                inicio = row.get("Inicio")
                final = row.get("Final")
                dia = _norm_str(row.get("Día"))
                horario = _norm_str(row.get("Horario"))
                formato = _norm_str(row.get("Formato"))
                tipo_materia = _norm_str(row.get("TipoMateria"))
                orientacion = _norm_str(row.get("Orientación"))
                comentarios = _norm_str(row.get("Comentarios"))

                # Convert dates to date only (if Timestamp)
                if pd.notna(inicio):
                    try:
                        inicio = pd.to_datetime(inicio).date()
                    except Exception:
                        inicio = None

                if pd.notna(final):
                    try:
                        final = pd.to_datetime(final).date()
                    except Exception:
                        final = None

                # Upsert Course
                existing = session.get(Course, course_id)
                if existing:
                    # Update fields
                    changed = False
                    for attr, val in (
                        ("programa", programa),
                        ("anio", anio),
                        ("materia", materia),
                        ("inicio", inicio),
                        ("final", final),
                        ("dia", dia),
                        ("horario", horario),
                        ("formato", formato),
                        ("horas", horas),
                        ("tipo_materia", tipo_materia),
                        ("orientacion", orientacion),
                        ("comentarios", comentarios),
                    ):
                        if val is not None and getattr(existing, attr) != val:
                            setattr(existing, attr, val)
                            changed = True
                    if changed:
                        summary["updated_courses"] += 1
                else:
                    new_course = Course(
                        course_id=course_id,
                        programa=programa,
                        anio=anio,
                        materia=materia,
                        inicio=inicio,
                        final=final,
                        dia=dia,
                        horario=horario,
                        formato=formato,
                        horas=horas,
                        tipo_materia=tipo_materia,
                        orientacion=orientacion,
                        comentarios=comentarios,
                    )
                    session.add(new_course)
                    summary["created_courses"] += 1

                # CourseSource upsert by (course_id, solapa_fuente, modulo, row_fuente)
                solapa = _norm_str(row.get("SolapaFuente"))
                modulo_src = modulo
                row_fuente = int(idx + 2)  # approximate original Excel row (header row assumed 1)

                src = (
                    session.query(CourseSource)
                    .filter_by(course_id=course_id, solapa_fuente=solapa, modulo=modulo_src, row_fuente=row_fuente)
                    .one_or_none()
                )

                if src:
                    changed = False
                    for attr, val in (("orientacion_fuente", _norm_str(row.get("Orientación"))),):
                        if val is not None and getattr(src, attr) != val:
                            setattr(src, attr, val)
                            changed = True
                    if changed:
                        summary["updated_sources"] += 1
                else:
                    src = CourseSource(
                        course_id=course_id,
                        solapa_fuente=solapa,
                        orientacion_fuente=_norm_str(row.get("Orientación")),
                        modulo=modulo_src,
                        row_fuente=row_fuente,
                    )
                    session.add(src)
                    summary["created_sources"] += 1

            except Exception as e:
                summary["errors"].append(f"Fila {idx}: error al procesar: {e}")

        try:
            session.commit()
        except Exception as e:
            session.rollback()
            summary["errors"].append(f"Error al guardar en la base: {e}")

    return summary
