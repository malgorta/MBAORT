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
    return s if s else None


def _norm_int(value):
    """Convert value to int, handling NaN and invalid values."""
    if value is None:
        return None
    
    # Handle pandas/numpy NaN types
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    
    # Handle numpy integer types
    try:
        import numpy as np
        if isinstance(value, (np.floating, np.integer)):
            if pd.isna(value):
                return None
            return int(value)
    except ImportError:
        pass
    
    try:
        # Handle float values
        if isinstance(value, float):
            if pd.isna(value):
                return None
            return int(value)
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _norm_float(value):
    """Convert value to float, handling NaN and invalid values."""
    if value is None:
        return None
    
    # Handle pandas/numpy NaN types
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    
    # Handle numpy types
    try:
        import numpy as np
        if isinstance(value, (np.floating, np.integer)):
            if pd.isna(value):
                return None
            result = float(value)
            if pd.isna(result):
                return None
            return result
    except ImportError:
        pass
    
    try:
        result = float(value)
        if pd.isna(result):
            return None
        return result
    except (ValueError, TypeError):
        return None


def _sanitize_for_db(value):
    """Final sanitization: ensure value is either None or a valid Python type (not NaN)."""
    if value is None:
        return None
    # Check for float NaN specifically
    if isinstance(value, float) and pd.isna(value):
        return None
    # Check for NaN in any form
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


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
                anio = _norm_int(row.get("Año"))
                modulo = _norm_str(row.get("Módulo"))
                materia = _norm_str(row.get("Materia"))
                horas = _norm_float(row.get("Horas"))
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
                else:
                    inicio = None

                if pd.notna(final):
                    try:
                        final = pd.to_datetime(final).date()
                    except Exception:
                        final = None
                else:
                    final = None

                # DEFENSIVE: Ensure no NaN values in numeric fields
                if pd.isna(anio) or (isinstance(anio, float) and pd.isna(anio)):
                    anio = None
                if pd.isna(horas) or (isinstance(horas, float) and pd.isna(horas)):
                    horas = None

                # Sanitize all values before database operations
                programa = _sanitize_for_db(programa)
                anio = _sanitize_for_db(anio)
                materia = _sanitize_for_db(materia)
                inicio = _sanitize_for_db(inicio)
                final = _sanitize_for_db(final)
                dia = _sanitize_for_db(dia)
                horario = _sanitize_for_db(horario)
                formato = _sanitize_for_db(formato)
                horas = _sanitize_for_db(horas)
                tipo_materia = _sanitize_for_db(tipo_materia)
                orientacion = _sanitize_for_db(orientacion)
                comentarios = _sanitize_for_db(comentarios)

                # Upsert Course
                existing = (
                    session.query(Course)
                    .filter_by(course_id=course_id, orientacion=orientacion)
                    .one_or_none()
                )
                if existing:
                    existing.programa = programa
                    existing.anio = anio
                    existing.materia = materia
                    existing.inicio = inicio
                    existing.final = final
                    existing.dia = dia
                    existing.horario = horario
                    existing.formato = formato
                    existing.horas = horas
                    existing.tipo_materia = tipo_materia
                    existing.comentarios = comentarios
                    session.merge(existing)
                    summary["updated_courses"] += 1
                    course_db = existing
                else:
                    try:
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
                        session.flush()
                        summary["created_courses"] += 1
                        course_db = new_course
                    except Exception as e:
                        summary["errors"].append(f"Fila {idx}: error al crear curso: {e}")
                        course_db = None

                # Solo crear CourseSource si el curso existe y tiene id
                if not course_db or not getattr(course_db, "id", None):
                    summary["errors"].append(f"Fila {idx}: no se pudo crear CourseSource porque el curso no se creó correctamente (course_id={course_id}, orientacion={orientacion})")
                    continue

                # CourseSource upsert by (course_id_ref, solapa_fuente, modulo, row_fuente)
                solapa = _norm_str(row.get("SolapaFuente"))
                modulo_src = modulo
                row_fuente = int(idx + 2)
                src = (
                    session.query(CourseSource)
                    .filter_by(course_id_ref=course_db.id, solapa_fuente=solapa, modulo=modulo_src, row_fuente=row_fuente)
                    .one_or_none()
                )
                orientacion_fuente = _norm_str(row.get("Orientación"))
                if src:
                    if orientacion_fuente and src.orientacion_fuente != orientacion_fuente:
                        src.orientacion_fuente = orientacion_fuente
                        session.merge(src)
                        summary["updated_sources"] += 1
                else:
                    src = CourseSource(
                        course_id_ref=course_db.id,
                        course_id=course_id,
                        solapa_fuente=solapa,
                        orientacion_fuente=orientacion_fuente,
                        modulo=modulo_src,
                        row_fuente=row_fuente,
                    )
                    session.merge(src)
                    summary["created_sources"] += 1
            except Exception as e:
                summary["errors"].append(f"Fila {idx}: error al procesar: {e}")
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            summary["errors"].append(f"Error al guardar en la base: {e}")
    return summary
