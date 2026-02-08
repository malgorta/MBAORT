import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

from lib import get_session, init_db
from lib.models import Student, Course, CourseSource, PlanVersion, StudentPlanItem, Enrollment
from lib.metrics import check_rule_5_of_8, elective_counts_by_orientation, risk_score


def run():
    init_db()

    st.header("📊 Reportes y KPIs - Gestión Académica")

    # Create tabs for different reports
    tab1, tab2, tab3, tab4 = st.tabs(["Demanda por Curso", "Demanda Temporal", "Cumplimiento", "Estudiantes en Riesgo"])

    # ===== TAB 1: Demanda por Curso =====
    with tab1:
        st.subheader("📈 Demanda por Curso")
        st.write("Cantidad de estudiantes que tienen cada materia como 'planned' en su plan vigente.")

        # Filters
        col_f1, col_f2, col_f3 = st.columns(3)

        with get_session() as session:
            programas = sorted(set(c.programa for c in session.query(Course).all() if c.programa))
            anos = sorted(set(c.anio for c in session.query(Course).all() if c.anio))
            orientaciones = sorted(set(c.orientacion for c in session.query(Course).all() if c.orientacion))

        with col_f1:
            filt_programa = st.selectbox("Programa", [""] + programas, key="demand_prog")
        with col_f2:
            filt_ano = st.selectbox("Año", [""] + [str(a) for a in anos], key="demand_ano")
        with col_f3:
            filt_orientacion = st.selectbox("Orientación", [""] + orientaciones, key="demand_orient")

        # Calculate demand
        with get_session() as session:
            planned_items = session.query(StudentPlanItem, Course, PlanVersion).join(
                Course, StudentPlanItem.course_id == Course.course_id
            ).join(
                PlanVersion, StudentPlanItem.plan_version_id == PlanVersion.id
            ).filter(
                StudentPlanItem.estado_plan == "planned",
                PlanVersion.vigente_hasta.is_(None),  # Only vigente plans
            ).all()

            # Count by course
            course_demand = {}
            for item, course, plan in planned_items:
                # Apply filters
                if filt_programa and course.programa != filt_programa:
                    continue
                if filt_ano and str(course.anio) != filt_ano:
                    continue
                if filt_orientacion and course.orientacion != filt_orientacion:
                    continue

                key = course.course_id
                if key not in course_demand:
                    course_demand[key] = {
                        "MateriaID": course.course_id,
                        "Materia": course.materia,
                        "Programa": course.programa,
                        "Año": course.anio,
                        "Tipo": course.tipo_materia,
                        "Orientación": course.orientacion or "N/A",
                        "Estudiantes Planned": 0,
                    }
                course_demand[key]["Estudiantes Planned"] += 1

            # Convert to dataframe
            if course_demand:
                df_demand = pd.DataFrame(list(course_demand.values()))
                df_demand = df_demand.sort_values("Estudiantes Planned", ascending=False)
                st.dataframe(df_demand, use_container_width=True)

                # Export buttons
                col_csv, col_excel = st.columns(2)
                with col_csv:
                    csv = df_demand.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "📥 Descargar CSV",
                        data=csv,
                        file_name=f"demanda_cursos_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        key="demand_csv"
                    )
                with col_excel:
                    # Create Excel file
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df_demand.to_excel(writer, sheet_name="Demanda", index=False)
                    output.seek(0)
                    st.download_button(
                        "📥 Descargar Excel",
                        data=output.getvalue(),
                        file_name=f"demanda_cursos_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="demand_excel"
                    )
            else:
                st.info("No hay demanda con los filtros seleccionados.")

    # ===== TAB 2: Demanda Temporal =====
    with tab2:
        st.subheader("📅 Demanda por Mes/Módulo")
        st.write("Distribución de demanda según módulo y mes de inicio de los cursos.")

        with get_session() as session:
            # Get course sources with module info
            sources = session.query(CourseSource, Course).join(
                Course, CourseSource.course_id == Course.course_id
            ).all()

            # Count demand by source
            demand_temporal = {}
            for source, course in sources:
                # Check if any planned student has this course
                planned_count = session.query(StudentPlanItem).filter(
                    StudentPlanItem.course_id == course.course_id,
                    StudentPlanItem.estado_plan == "planned",
                ).count()

                if planned_count > 0:
                    modulo = source.modulo or "Sin módulo"
                    mes = "Sin fecha"
                    if course.inicio:
                        mes = course.inicio.strftime("%B %Y")

                    key = (modulo, mes)
                    if key not in demand_temporal:
                        demand_temporal[key] = 0
                    demand_temporal[key] += planned_count

            if demand_temporal:
                df_temporal = pd.DataFrame([
                    {"Módulo": k[0], "Mes Inicio": k[1], "Demanda": v}
                    for k, v in sorted(demand_temporal.items(), key=lambda x: x[1], reverse=True)
                ])
                st.dataframe(df_temporal, use_container_width=True)

                # Chart
                st.bar_chart(df_temporal.set_index("Mes Inicio")["Demanda"])

                # Export
                csv = df_temporal.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Descargar CSV",
                    data=csv,
                    file_name=f"demanda_temporal_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="temporal_csv"
                )
            else:
                st.info("Sin información temporal disponible.")

    # ===== TAB 3: Cumplimiento =====
    with tab3:
        st.subheader("✅ Cumplimiento - Regla 5/8")

        with get_session() as session:
            all_students = session.query(Student).all()

        if not all_students:
            st.info("No hay estudiantes registrados.")
        else:
            # Calculate metrics
            rule_58_compliant = 0
            total_electives_completed = []
            orientation_distribution = {}

            for student in all_students:
                ok, best_orient, best_count = check_rule_5_of_8(student.student_id)
                if ok:
                    rule_58_compliant += 1

                counts = elective_counts_by_orientation(student.student_id)
                if counts:
                    total_electives_completed.append(sum(counts.values()))
                    for orient, count in counts.items():
                        orientation_distribution[orient] = orientation_distribution.get(orient, 0) + count

            # KPI Metrics
            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

            with col_kpi1:
                cumplimiento_pct = (rule_58_compliant / len(all_students) * 100) if all_students else 0
                st.metric("% Cumplimiento 5/8", f"{cumplimiento_pct:.1f}%")

            with col_kpi2:
                st.metric("Estudiantes OK", f"{rule_58_compliant}/{len(all_students)}")

            with col_kpi3:
                avg_electives = sum(total_electives_completed) / len(all_students) if all_students else 0
                st.metric("Promedio Electivas", f"{avg_electives:.1f}")

            with col_kpi4:
                st.metric("Orientaciones", len(orientation_distribution))

            # Distribution by orientation
            st.markdown("---")
            st.write("**Distribución por Orientación (electivas completadas)**")

            if orientation_distribution:
                df_orient = pd.DataFrame([
                    {"Orientación": k, "Total Completadas": v}
                    for k, v in sorted(orientation_distribution.items(), key=lambda x: x[1], reverse=True)
                ])
                st.dataframe(df_orient, use_container_width=True)
                st.bar_chart(df_orient.set_index("Orientación"))

                # Export
                csv = df_orient.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Descargar CSV",
                    data=csv,
                    file_name=f"cumplimiento_orientaciones_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="cumpl_csv"
                )

    # ===== TAB 4: Estudiantes en Riesgo =====
    with tab4:
        st.subheader("⚠️ Estudiantes en Riesgo")
        st.write("Análisis de estudiantes que no cumplen la regla 5/8 o están cerca del limite.")

        with get_session() as session:
            all_students = session.query(Student).all()

        if not all_students:
            st.info("No hay estudiantes registrados.")
        else:
            risk_data = []

            for student in all_students:
                ok, best_orient, best_count = check_rule_5_of_8(student.student_id)
                risk = risk_score(student.student_id)

                risk_data.append({
                    "Estudiante": f"{student.nombre} {student.apellido}",
                    "Email": student.email,
                    "Programa": student.programa,
                    "Cohorte": student.cohorte or "N/A",
                    "Orientación Objetivo": best_orient or "N/A",
                    "Electivas Completadas": risk["total_completed"],
                    "Mejor Count": risk["best_count"],
                    "Gap a 5": risk["gap_to_target"],
                    "Nivel Riesgo": risk["risk_level"].upper(),
                    "Cumple 5/8": "✅ Sí" if ok else "❌ No",
                })

            df_risk = pd.DataFrame(risk_data)

            # Filter by risk level
            risk_levels = st.multiselect("Filtrar por Nivel de Riesgo", ["LOW", "MEDIUM", "HIGH"], default=["MEDIUM", "HIGH"], key="risk_filter")

            if risk_levels:
                df_filtered = df_risk[df_risk["Nivel Riesgo"].isin(risk_levels)]
            else:
                df_filtered = df_risk

            st.dataframe(df_filtered, use_container_width=True)

            # Risk distribution
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.write("**Distribución de Riesgo**")
                risk_counts = df_risk["Nivel Riesgo"].value_counts()
                st.bar_chart(risk_counts)

            with col_chart2:
                st.write("**Gap a 5 Electivas**")
                gap_dist = df_risk["Gap a 5"].value_counts().sort_index()
                st.bar_chart(gap_dist)

            # Export filtered data
            st.markdown("---")
            col_csv, col_excel = st.columns(2)

            with col_csv:
                csv = df_filtered.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Descargar CSV",
                    data=csv,
                    file_name=f"estudiantes_riesgo_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="risk_csv"
                )

            with col_excel:
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_filtered.to_excel(writer, sheet_name="Riesgo", index=False)
                output.seek(0)
                st.download_button(
                    "📥 Descargar Excel",
                    data=output.getvalue(),
                    file_name=f"estudiantes_riesgo_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="risk_excel"
                )

            # Summary statistics
            if df_risk["Nivel Riesgo"].str.contains("HIGH").any():
                high_risk_count = len(df_risk[df_risk["Nivel Riesgo"] == "HIGH"])
                st.error(f"⚠️ {high_risk_count} estudiantes en RIESGO ALTO (requieren intervención)")
