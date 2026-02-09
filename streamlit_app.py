import sys
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.db import get_session, init_db
from lib.models import Course, Student, PlanVersion, Enrollment

st.set_page_config(page_title="Gestión de Rutas Académicas MBA/EMBA", layout="wide")

# Initialize database tables on app startup (if they don't exist)
# This ensures the database is ready before any health checks or queries
init_db()

# Sidebar global
st.sidebar.title("⚙️ Configuración Global")
st.sidebar.text_input("Nombre de usuario", value="admin", key="global_user")

db_path = Path("data/app.db")
st.sidebar.write(f"DB: `{db_path}`")

if st.sidebar.button("🔄 Inicializar DB"):
    init_db()
    st.sidebar.success("DB inicializada")
    st.rerun()

# Health check básico
try:
    with get_session() as session:
        st.sidebar.metric("Cursos", session.query(Course).count())
        st.sidebar.metric("Estudiantes", session.query(Student).count())
        st.sidebar.metric("Planes", session.query(PlanVersion).count())
        st.sidebar.metric("Inscripciones", session.query(Enrollment).count())
except Exception as e:
    st.sidebar.error(f"Health error: {e}")

st.title("Gestión de Rutas Académicas MBA/EMBA")
st.write("Usá el menú de la izquierda para navegar.")