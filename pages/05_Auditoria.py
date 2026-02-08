import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from lib import get_session, init_db
from lib.models import ChangeLog, Student


def run():
    init_db()

    st.header("🔍 Auditoría y ChangeLog")

    st.write("Visualiza y audita todos los cambios registrados en el sistema.")

    # ===== SECTION: Filters =====
    st.markdown("---")
    st.subheader("🔎 Filtros")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        fecha_desde = st.date_input("Desde", value=datetime.now() - timedelta(days=30), key="audit_desde")

    with col_f2:
        fecha_hasta = st.date_input("Hasta", value=datetime.now(), key="audit_hasta")

    with col_f3:
        user_filter = st.text_input("Usuario (contiene)", value="", key="audit_user")

    with col_f4:
        entidad_filter = st.text_input("Entidad (contiene)", value="", key="audit_entidad")

    # Get students for filter
    with get_session() as session:
        all_students = session.query(Student).all()

    student_map = {f"{s.nombre} {s.apellido} ({s.email})": s.student_id for s in all_students}
    student_filter_label = st.selectbox("Estudiante (opcional)", [""] + list(student_map.keys()), key="audit_student")
    student_filter_id = student_map.get(student_filter_label) if student_filter_label else None

    # ===== SECTION: Fetch and Filter Logs =====
    with get_session() as session:
        query = session.query(ChangeLog)

        # Date range filter
        query = query.filter(
            ChangeLog.ts >= datetime.combine(fecha_desde, datetime.min.time()),
            ChangeLog.ts <= datetime.combine(fecha_hasta, datetime.max.time()),
        )

        # User filter
        if user_filter:
            query = query.filter(ChangeLog.user.ilike(f"%{user_filter}%"))

        # Entidad filter
        if entidad_filter:
            query = query.filter(ChangeLog.entidad.ilike(f"%{entidad_filter}%"))

        # Student filter (by entidad_id if it's a student ID or by matching enrollments/plans)
        if student_filter_id:
            # Filter logs that reference this student
            query = query.filter(
                (ChangeLog.entidad_id == str(student_filter_id)) |
                (ChangeLog.entidad == "Student")
            )

        # Order by timestamp descending
        logs = query.order_by(ChangeLog.ts.desc()).all()

    # ===== SECTION: Display Logs Table =====
    st.markdown("---")
    st.subheader(f"📋 Registros de Cambios ({len(logs)} resultados)")

    if logs:
        log_data = []
        for log in logs:
            log_data.append({
                "Timestamp": log.ts,
                "Usuario": log.user or "-",
                "Entidad": log.entidad,
                "Entidad ID": log.entidad_id or "-",
                "Campo": log.campo or "-",
                "Valor Anterior": log.valor_anterior or "-",
                "Valor Nuevo": log.valor_nuevo or "-",
                "Motivo": log.motivo or "-",
            })

        df_logs = pd.DataFrame(log_data)

        # Format timestamp for display
        df_logs["Timestamp"] = df_logs["Timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

        st.dataframe(df_logs, use_container_width=True)

        # Export button
        csv = df_logs.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar como CSV",
            data=csv,
            file_name=f"auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No hay registros que coincidan con los filtros seleccionados.")

    # ===== SECTION: Summary Stats =====
    st.markdown("---")
    st.subheader("📊 Estadísticas")

    with get_session() as session:
        all_logs = session.query(ChangeLog).all()

        if all_logs:
            # Count by entidad
            entidad_counts = {}
            user_counts = {}
            for log in all_logs:
                entidad_counts[log.entidad] = entidad_counts.get(log.entidad, 0) + 1
                if log.user:
                    user_counts[log.user] = user_counts.get(log.user, 0) + 1

            col_stat1, col_stat2, col_stat3 = st.columns(3)

            with col_stat1:
                st.metric("Total Cambios", len(all_logs))

            with col_stat2:
                st.metric("Usuarios Únicos", len(user_counts))

            with col_stat3:
                st.metric("Entidades Auditadas", len(entidad_counts))

            # Charts
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.write("#### Cambios por Entidad")
                df_entidad = pd.DataFrame(sorted(entidad_counts.items(), key=lambda x: x[1], reverse=True), columns=["Entidad", "Cantidad"])
                st.bar_chart(df_entidad.set_index("Entidad"))

            with col_chart2:
                st.write("#### Cambios por Usuario")
                df_user = pd.DataFrame(sorted(user_counts.items(), key=lambda x: x[1], reverse=True), columns=["Usuario", "Cantidad"])
                st.bar_chart(df_user.set_index("Usuario"))
