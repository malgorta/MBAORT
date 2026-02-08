import streamlit as st
import pandas as pd
from datetime import datetime

from lib import get_session, init_db
from lib.models import Student, Course, Enrollment
from lib.metrics import (
    check_rule_5_of_8,
    elective_counts_by_orientation,
    risk_score,
    aggregated_metrics_by_cohort,
    aggregated_metrics_by_program,
)


def run():
    init_db()

    st.header("Reportes y Análisis - Regla 5/8")

    tab_rule58, tab_metrics, tab_risk = st.tabs(["Regla 5/8", "Métricas por Grupo", "Análisis de Riesgo"])

    # ===== TAB: REGLA 5/8 =====
    with tab_rule58:
        st.subheader("Cumplimiento de la Regla 5/8")
        st.write("**Definición:** Un estudiante cumple la regla 5/8 si completó al menos 5 electivas en una misma orientación.")

        with get_session() as session:
            all_students = session.query(Student).all()

        if not all_students:
            st.info("No hay estudiantes registrados.")
        else:
            # Summary table
            summary_data = []
            for s in all_students:
                ok, best_orient, best_count = check_rule_5_of_8(s.student_id)
                counts_by_orient = elective_counts_by_orientation(s.student_id)
                total_electives = sum(counts_by_orient.values())

                summary_data.append({
                    "Estudiante": f"{s.nombre} {s.apellido}",
                    "Programa": s.programa,
                    "Cohorte": s.cohorte or "N/A",
                    "Total Electivas": total_electives,
                    "Mejor Orientación": best_orient or "N/A",
                    "Electivas en Mejor": best_count or 0,
                    "Cumple 5/8": "✅ Sí" if ok else "❌ No",
                })

            df_summary = pd.DataFrame(summary_data)
            st.dataframe(df_summary, use_container_width=True)

            # Detail view
            st.markdown("---")
            st.subheader("Detalle por Estudiante")

            with get_session() as session:
                all_students = session.query(Student).all()

            student_map = {f"{s.nombre} {s.apellido}": s for s in all_students}
            selected_label = st.selectbox("Seleccionar estudiante", list(student_map.keys()), key="detail_student")
            selected_student = student_map[selected_label]

            ok, best_orient, best_count = check_rule_5_of_8(selected_student.student_id)
            counts = elective_counts_by_orientation(selected_student.student_id)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Cumple Regla 5/8", "✅ Sí" if ok else "❌ No")
            with col2:
                st.metric("Mejor Orientación", best_orient or "N/A", f"{best_count} electivas")

            st.write("### Desglose por Orientación")
            for orient, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                progress = min(count / 5, 1.0)
                st.progress(progress, text=f"{orient}: {count}/5")

            # Show completed enrollments
            st.write("### Electivas Completadas")
            with get_session() as session:
                enrollments = session.query(Enrollment).filter(
                    Enrollment.student_id == selected_student.student_id,
                    Enrollment.status == "completed",
                ).join(Course).all()

                if enrollments:
                    enroll_data = []
                    for e in enrollments:
                        if e.course.tipo_materia == "electiva":
                            enroll_data.append({
                                "Materia": e.course.materia,
                                "Orientación": e.course.orientacion or "N/A",
                                "Calificación": e.nota_numerica or "N/A",
                                "Fecha": e.fecha_estado.date() if e.fecha_estado else "N/A",
                            })
                    if enroll_data:
                        df_enroll = pd.DataFrame(enroll_data)
                        st.dataframe(df_enroll, use_container_width=True)
                    else:
                        st.info("Sin electivas completadas.")
                else:
                    st.info("Sin inscripciones completadas.")

    # ===== TAB: MÉTRICAS POR GRUPO =====
    with tab_metrics:
        st.subheader("Métricas por Grupo")

        metric_type = st.selectbox("Agrupar por", ["Cohorte", "Programa"])

        with get_session() as session:
            if metric_type == "Cohorte":
                cohorts = session.query(Student.cohorte).distinct().all()
                groups = [c[0] for c in cohorts if c[0]]
            else:
                programs = session.query(Student.programa).distinct().all()
                groups = [p[0] for p in programs if p[0]]

        metrics_data = []
        for group in groups:
            if metric_type == "Cohorte":
                metrics = aggregated_metrics_by_cohort(group)
            else:
                metrics = aggregated_metrics_by_program(group)

            metrics_data.append({
                metric_type: group,
                "Total Estudiantes": metrics.get("total_students", 0),
                "Cumplen 5/8": metrics.get("rule_5_8_compliant", 0),
                "% Cumplimiento": f"{metrics.get('rule_5_8_compliance_rate', 0) * 100:.1f}%" if metrics.get("total_students", 0) > 0 else "0%",
                "Promedio Electivas": f"{metrics.get('avg_electives_completed', 0):.1f}",
            })

        if metrics_data:
            df_metrics = pd.DataFrame(metrics_data)
            st.dataframe(df_metrics, use_container_width=True)

            # Charts
            st.markdown("---")
            st.write("### Visualización")

            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.bar_chart(
                    pd.DataFrame(metrics_data).set_index(metric_type)["% Cumplimiento"].str.rstrip("%").astype(float),
                    y_label="% Cumplimiento Regla 5/8"
                )

            with col_chart2:
                st.bar_chart(
                    pd.DataFrame(metrics_data).set_index(metric_type)["Promedio Electivas"].astype(float),
                    y_label="Promedio de Electivas Completadas"
                )

    # ===== TAB: ANÁLISIS DE RIESGO =====
    with tab_risk:
        st.subheader("Análisis de Riesgo")
        st.write("Evaluación de cuán cerca están los estudiantes de cumplir la regla 5/8.")

        with get_session() as session:
            all_students = session.query(Student).all()

        if not all_students:
            st.info("No hay estudiantes registrados.")
        else:
            risk_data = []
            for s in all_students:
                risk = risk_score(s.student_id)
                risk_data.append({
                    "Estudiante": f"{s.nombre} {s.apellido}",
                    "Programa": s.programa,
                    "Electivas Completadas": risk["total_completed"],
                    "Mejor Orientación": risk["best_orientation"] or "N/A",
                    "Progreso (mejor)": f"{risk['best_count']}/5",
                    "Gap": risk["gap_to_target"],
                    "Riesgo": risk["risk_level"].upper(),
                })

            df_risk = pd.DataFrame(risk_data)

            # Color code by risk level
            st.write("### Tabla de Riesgo")
            st.dataframe(df_risk, use_container_width=True)

            # Risk distribution
            st.markdown("---")
            st.write("### Distribución de Riesgo")

            risk_counts = df_risk["Riesgo"].value_counts()
            col_pie, col_legend = st.columns([2, 1])

            with col_pie:
                st.bar_chart(risk_counts, y_label="Cantidad de Estudiantes")

            with col_legend:
                st.write("**Categorías:**")
                st.write("🟢 **LOW:** Cumple o casi cumple (0-1 electivas faltantes)")
                st.write("🟡 **MEDIUM:** En progreso (2 electivas faltantes)")
                st.write("🔴 **HIGH:** Lejos del cumplimiento (>2 electivas faltantes)")

            # Warning list
            high_risk = df_risk[df_risk["Riesgo"] == "HIGH"]
            if len(high_risk) > 0:
                st.warning(f"⚠️ {len(high_risk)} estudiantes en riesgo alto (>2 electivas faltantes)")
                with st.expander("Ver estudiantes en riesgo alto"):
                    st.dataframe(high_risk, use_container_width=True)
