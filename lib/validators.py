import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema, Check


EXPECTED_COLUMNS = [
    "Programa",
    "Año",
    "Módulo",
    "Materia",
    "Horas",
    "Profesor 1",
    "Profesor 2",
    "Profesor 3",
    "Inicio",
    "Final",
    "Día",
    "Horario",
    "Formato",
    "Orientación",
    "Comentarios",
    "TipoMateria",
    "SolapaFuente",
    "MateriaID",
    "MateriaKey",
]


def _coerce_dates(df: pd.DataFrame, col: str, errors: list):
    try:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    except Exception as e:
        errors.append(f"Error convirtiendo columna {col} a datetime: {e}")


def validate_cronograma_df(df: pd.DataFrame):
    """Validate and coerce the cronograma DataFrame.

    Returns (cleaned_df, errors_list).
    """
    errors = []

    # Check presence of required columns
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Faltan columnas requeridas: {missing}")
        return None, errors

    # Work on a copy
    df = df.copy()

    # AGGRESSIVE NaN CLEANING - Convert all NaN to None first
    # This prevents pandera validation errors and SQLAlchemy conversion errors
    df = df.where(pd.notna(df), None)

    # Coerce numeric - but handle None values properly
    try:
        # For Horas: convert to float, keeping None as is
        df["Horas"] = df["Horas"].apply(
            lambda x: None if x is None or pd.isna(x) else float(x)
        )
    except Exception as e:
        errors.append(f"Error en conversión de 'Horas': {e}")

    # For Año: convert to int, keeping None as is
    try:
        df["Año"] = df["Año"].apply(
            lambda x: None if x is None or pd.isna(x) else int(float(x))
        )
    except Exception as e:
        errors.append(f"Error en conversión de 'Año': {e}")

    # Coerce dates
    _coerce_dates(df, "Inicio", errors)
    _coerce_dates(df, "Final", errors)

    # Basic schema with pandera
    schema = DataFrameSchema(
        {
            "Programa": Column(pa.String, nullable=False),
            "Año": Column(pa.Int, nullable=False),
            "Módulo": Column(pa.String, nullable=False),
            "Materia": Column(pa.String, nullable=False),
            "Horas": Column(pa.Float, nullable=True),
            "Profesor 1": Column(pa.String, nullable=True),
            "Profesor 2": Column(pa.String, nullable=True),
            "Profesor 3": Column(pa.String, nullable=True),
            "Inicio": Column(pa.DateTime, nullable=True),
            "Final": Column(pa.DateTime, nullable=True),
            "Día": Column(pa.String, nullable=True),
            "Horario": Column(pa.String, nullable=True),
            "Formato": Column(pa.String, nullable=True),
            "Orientación": Column(pa.String, nullable=True),
            "Comentarios": Column(pa.String, nullable=True),
            "TipoMateria": Column(pa.String, nullable=True),
            "SolapaFuente": Column(pa.String, nullable=True),
            "MateriaID": Column(pa.String, nullable=False),
            "MateriaKey": Column(pa.String, nullable=True),
        },
        strict=False,
    )

    try:
        df = schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as e:
        # Collect readable errors
        for failure in e.failure_cases.itertuples(index=False):
            errors.append(f"Fila {failure.index}: {failure.column} -> {failure.failure_case}")

    # Final cleanup: replace any remaining NaN with None
    df = df.where(pd.notna(df), None)

    return df, errors
