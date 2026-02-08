import streamlit as st
st.sidebar.info("RUNNING: streamlit_app.py (router)")

import importlib
import pkgutil
import streamlit as st
from pathlib import Path

from lib.db import get_session, init_db
from lib.models import Course, Student, PlanVersion, Enrollment

st.set_page_config(page_title="Gestión de Rutas Académicas MBA/EMBA", layout="wide")


def discover_pages(package):
    """
    Discover modules in the `pages` package that expose a `run()` function.
    Returns a dict: {display_name: module_name}
    """
    pages = {}

    for _, name, _ in pkgutil.iter_modules(package.__path__):
        module_name = f"{package.__name__}.{name}"

        # Import safely and only keep modules exposing run()
        try:
            module = importlib.import_module(module_name)
        except Exception:
            # If a module fails to import, skip it (avoid breaking the whole app)
            continue

        if not hasattr(module, "run"):
            continue

        # Friendly display name
        display = name.replace("_", " ").title()
        pages[display] = module_name

    return pages


def load_and_run(module_name):
    try:
        module = importlib.import_module(module_name)
        module.run()
    except Exception as e:
        st.error(f"Error al ejecutar la página {module_name}")
        st.exception(e)


def render_sidebar():
    st.sidebar.title("⚙️ Configuración Global")

    st.sidebar.markdown("### 👤 Usuario")
    user_name = st.sidebar.text_input("Nombre de usuario", value="admin", key="global_user")
    st.session_state["global_user"] = user_name

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

    import pages

    pages_map = discover_pages(pages)
    if not pages_map:
        st.sidebar.warning("No hay páginas válidas en `pages` (deben exponer run()).")
        st.title("Gestión de Rutas Académicas MBA/EMBA")
        st.write("Agregá módulos en `pages/` que tengan una función `run()`.")
        return

    # Default: Home si existe
    page_names = sorted(pages_map.keys())
    default_idx = 0
    for i, name in enumerate(page_names):
        if name.lower() == "home":
            default_idx = i
            break

    choice = st.sidebar.selectbox("Seleccionar página", page_names, index=default_idx, key="page_select")
    load_and_run(pages_map[choice])


if __name__ == "__main__":
    main()
