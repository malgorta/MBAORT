import streamlit as st
import pandas as pd
from datetime import datetime

from lib.io_excel import import_schedule_excel
from lib.db import get_session
from lib.models import Course, CourseSource, ChangeLog


def run():
    st.header("📅 Importar Cronograma")

    # File uploader
    uploaded_file = st.file_uploader(
        "Cargar archivo Excel (Cronograma_2026_verificado_completo.xlsx)",
        type=["xlsx"],
        help="Debe contener la hoja 'CronogramaConsolidado'",
    )

    if uploaded_file:
        col1, col2 = st.columns(2)
        with col1:
            import_btn = st.button("Importar", key="import_btn", type="primary")
        with col2:
            st.write("")

        if import_btn:
            with st.spinner("Importando..."):
                summary = import_schedule_excel(uploaded_file)

            # Display summary
            st.subheader("📊 Resumen del Importación")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Cursos Creados", summary["created_courses"])
            with col2:
                st.metric("Cursos Actualizados", summary["updated_courses"])
            with col3:
                st.metric("Fuentes Creadas", summary["created_sources"])
            with col4:
                st.metric("Fuentes Actualizadas", summary["updated_sources"])

            # Display errors if any
            if summary["errors"]:
                st.error("⚠️ Errores encontrados:")
                for error in summary["errors"]:
                    st.write(f"- {error}")
            else:
                st.success("✅ Importación exitosa sin errores.")

            # Register in ChangeLog
            try:
                with get_session() as session:
                    log_entry = ChangeLog(
                        ts=datetime.utcnow(),
                        user="admin",
                        entidad="ScheduleImport",
                        entidad_id=None,
                        campo="import",
                        valor_anterior=None,
                        valor_nuevo=f"{summary['created_courses']} created, {summary['updated_courses']} updated",
                        motivo="Importación de cronograma desde Excel",
                    )
                    session.add(log_entry)
                    session.commit()
            except Exception as e:
                st.warning(f"No se pudo registrar en ChangeLog: {e}")

            st.success("✅ Cambios registrados en el log.")

    # Tabs for viewing courses and sources
    st.divider()
    st.subheader("📋 Datos Importados")

    tab1, tab2 = st.tabs(["Cursos", "Fuentes"])

    with tab1:
        st.write("**Filtros y búsqueda**")
        cols = st.columns(5)

        with get_session() as session:
            # Fetch unique values for filters
            programas = (
                session.query(Course.programa)
                .distinct()
                .filter(Course.programa != None)
                .order_by(Course.programa)
                .all()
            )
            programas = [p[0] for p in programas]

            anos = (
                session.query(Course.anio)
                .distinct()
                .filter(Course.anio != None)
                .order_by(Course.anio)
                .all()
            )
            anos = [a[0] for a in anos]

            tipo_materias = (
                session.query(Course.tipo_materia)
                .distinct()
                .filter(Course.tipo_materia != None)
                .order_by(Course.tipo_materia)
                .all()
            )
            tipo_materias = [t[0] for t in tipo_materias]

            orientaciones = (
                session.query(Course.orientacion)
                .distinct()
                .filter(Course.orientacion != None)
                .order_by(Course.orientacion)
                .all()
            )
            orientaciones = [o[0] for o in orientaciones]

        with cols[0]:
            selected_programa = st.selectbox("Programa", [""] + programas, key="prog_filter")
        with cols[1]:
            selected_ano = st.selectbox("Año", [""] + anos, key="ano_filter")
        with cols[2]:
            selected_tipo = st.selectbox("Tipo Materia", [""] + tipo_materias, key="tipo_filter")
        with cols[3]:
            selected_orient = st.selectbox("Orientación", [""] + orientaciones, key="orient_filter")
        with cols[4]:
            search_materia = st.text_input("Buscar Materia", key="materia_search")

        # Fetch courses with filters
        with get_session() as session:
            query = session.query(Course)

            if selected_programa:
                query = query.filter(Course.programa == selected_programa)
            if selected_ano:
                query = query.filter(Course.anio == selected_ano)
            if selected_tipo:
                query = query.filter(Course.tipo_materia == selected_tipo)
            if selected_orient:
                query = query.filter(Course.orientacion == selected_orient)
            if search_materia:
                query = query.filter(Course.materia.ilike(f"%{search_materia}%"))

            courses = query.all()

        if courses:
            # Convert to DataFrame for display and export
            df_courses = pd.DataFrame(
                [
                    {
                        "MateriaID": c.course_id,
                        "Programa": c.programa,
                        "Año": c.anio,
                        "Materia": c.materia,
                        "Horas": c.horas,
                        "Inicio": c.inicio,
                        "Final": c.final,
                        "Día": c.dia,
                        "Horario": c.horario,
                        "Formato": c.formato,
                        "Tipo Materia": c.tipo_materia,
                        "Orientación": c.orientacion,
                        "Comentarios": c.comentarios,
                    }
                    for c in courses
                ]
            )
            st.dataframe(df_courses, use_container_width=True)

            # Export button
            csv = df_courses.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Descargar como CSV",
                data=csv,
                file_name="cursos_filtrados.csv",
                mime="text/csv",
            )
        else:
            st.info("No hay cursos que coincidan con los filtros seleccionados.")

    with tab2:
        st.write("**Fuentes del Cronograma**")

        with get_session() as session:
            sources = session.query(CourseSource).all()

        if sources:
            df_sources = pd.DataFrame(
                [
                    {
                        "ID": s.id,
                        "MateriaID": s.course_id,
                        "Solapa": s.solapa_fuente,
                        "Orientación Fuente": s.orientacion_fuente,
                        "Módulo": s.modulo,
                        "Fila Fuente": s.row_fuente,
                    }
                    for s in sources
                ]
            )
            st.dataframe(df_sources, use_container_width=True)

            # Export button
            csv = df_sources.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Descargar como CSV",
                data=csv,
                file_name="fuentes.csv",
                mime="text/csv",
            )
        else:
            st.info("No hay fuentes registradas aún.")

run()