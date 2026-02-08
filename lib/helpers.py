from datetime import datetime
from .db import get_session
from .models import ChangeLog


def log_change(
    entidad: str,
    entidad_id: str,
    campo: str = None,
    valor_anterior: str = None,
    valor_nuevo: str = None,
    motivo: str = None,
    user: str = None,
):
    """Log a change to ChangeLog table."""
    with get_session() as session:
        log_entry = ChangeLog(
            ts=datetime.now(),
            user=user,
            entidad=entidad,
            entidad_id=entidad_id,
            campo=campo,
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
            motivo=motivo,
        )
        session.add(log_entry)
        session.commit()
