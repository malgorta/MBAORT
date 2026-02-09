import sys
from pathlib import Path
import importlib
import pkgutil

import streamlit as st

# --- Ensure repo root is importable (fix for Streamlit Cloud) ---
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.db import get_session, init_db
from lib.models import Course, Student, PlanVersion, Enrollment

st.set_page_config(page_title="Gestión de Rutas Académicas MBA/EMBA", layout="wide")

# Watermark to confirm entrypoint
st.sidebar.info("RUNNING: streamlit_app.py (router)")


def discover_pages(package):
    """
    Discover modules in the `pages` package that expose a `run()` function.
    Returns a dict: {display_name: module_name}
    """
    pages = {}
    for _, name, _ in pkgutil.iter_modules(package.__path__):
        module_name = f"{package.__name__}.{name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            st.sidebar.error(f"Import fail {module_name}: {e}")
            continue

        if not hasattr(module, "run"):
            continue

        display = name.replace("_", " ").title()
        pages[display] = module_name

    return pages


def load_and_run(module_name: str):
    st.write(f"DEBUG running: {module_name}")
    try:
        module = importlib.import_module(module_name)

        if not hasattr(module, "run"):
            st.error(f"{module_name} no expone run()")
            return

        module.run()

    except Exception as e:
        st.error(f"Error al ejecutar la página {module_name}")
        st.exception(e)



def render_sidebar():
    st.sidebar.title("⚙️ Configuración Global")

    # --- User input for ChangeLog ---
    st.sidebar.markdown("### 👤 Usuario")
    st.sidebar.text_input("Nombre de usuario", value="admin", key="global_user")
    # No asignar st.session_state["global_user"] manualmente:
    # el widget ya lo maneja.

    # --- Database info ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💾 Base de Datos")

    db_path = Path("data/app.db")
    st.sidebar.write(f"**Ruta:** `{db_path}`")

    if db_path.exists():
        db_size_mb = db_path.stat().st_size / (1024 * 1024)
        st.sidebar.write(f"**Tamaño:** {db_size_mb:.2f} MB")
    else:
        st.sidebar.warning("Base de datos no encontrada")

    if st.sidebar.button("🔄 Inicializar DB", key="init_db_btn"):
        try:
            init_db()
            st.sidebar.success("✅ Base de datos inicializada")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

    # --- Health checks ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🏥 Health Check")

    try:
        with get_session() as session:
            curso_count = session.query(Course).count()
            student_count = session.query(Student).count()
            plan_count = session.query(PlanVersion).count()
            enroll_count = session.query(Enrollment).count()

        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("Cursos", curso_count)
            st.metric("Planes", plan_count)
        with col2:
            st.metric("Estudiantes", student_count)
            st.metric("Inscripciones", enroll_count)

        if curso_count > 0 and student_count > 0:
            st.sidebar.success("✅ Sistema operativo")
        else:
            st.sidebar.warning("⚠️ Datos insuficientes (importar cronograma y crear estudiantes)")

    except Exception as e:
        st.sidebar.error(f"❌ Error en health check: {e}")

    st.sidebar.markdown("---")


def main():
    render_sidebar()
    st.sidebar.markdown("### 📖 Navegación")

    import pages  # requires pages/__init__.py

    pages_map = discover_pages(pages)
    if not pages_map:
        st.sidebar.warning("No hay páginas válidas en `pages` (deben exponer run()).")
        st.title("Gestión de Rutas Académicas MBA/EMBA")
        st.write("Agregá módulos en `pages/` que tengan una función `run()`.")
        return

    page_names = sorted(pages_map.keys())

    # Default selection: Home if available