import streamlit as st
import pandas as pd
from datetime import datetime

from lib import get_session, init_db, log_change
from lib.models import Student, PlanVersion, StudentPlanItem, Course, Enrollment, ChangeLog


def run():
    init_db()

    st.header("Gestión de Planes Académicos")

    user_name = st.sidebar.text_input("Usuario (para registro de cambios)", value="admin")

    tab_plan, tab_enroll = st.tabs(["Planes Versionados", "Inscripciones"])

    # ===== TAB: PLANES VERSIONADOS =====
    with tab_plan:
        st.subheader("Planes Versionados por Estudiante")

        with get_session() as session:
            all_students = session.query(Student).all()

        if not all_students:
            st.info("No hay estudiantes registrados.")
        else:
            student_map = {f"{s.nombre} {s.apellido}": s for s in all_students}
            selected_label = st.selectbox("Seleccionar estudiante", list(student_map.keys()), key="plan_student")
            selected_student = student_map[selected_label]

            # Show existing plans
            with get_session() as session:
                plans = session.query(PlanVersion).filter_by(student_id=selected_student.student_id).all()

            if plans:
                st.write("### Planes Existentes")
                for plan in sorted(plans, key=lambda p: p.version_num):
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        st.write(f"**v{plan.version_num}**")
                    with col2:
                        st.write(f"{plan.vigente_desde.date()} → {plan.vigente_hasta.date() if plan.vigente_hasta else 'Vigente'}")
                    with col3:
                        if st.button("Ver Items", key=f"view_plan_{plan.id}"):
                            st.session_state[f"show_plan_{plan.id}"] = True

                    if st.session_state.get(f"show_plan_{plan.id}", False):
                        with st.expander("Items del plan", expanded=True):
                            with get_session() as sess:
                                items = sess.query(StudentPlanItem).filter_by(plan_version_id=plan.id).all()
                                if items:
                                    for item in items:
                                        st.write(f"- {item.course.materia} ({item.estado_plan}) - Prioridad: {item.prioridad}")
                                else:
                                    st.write("Plan sin items.")

            # Create new plan
            st.markdown("---")
            st.subheader("Crear Nueva Versión de Plan")

            col_v, col_vf = st.columns(2)
            with col_v:
                version_num = st.number_input("Número de Versión", value=len(plans) + 1, min_value=1, step=1)
            with col_vf:
                vigente_desde = st.date_input("Vigente desde", value=datetime.now())

            vigente_hasta = st.date_input("Vigente hasta (opcional)", value=None)
            comentario = st.text_area("Comentario")

            if st.button("Crear Plan"):
                with get_session() as session:
                    try:
                        plan = PlanVersion(
                            student_id=selected_student.student_id,
                            version_num=version_num,
                            vigente_desde=vigente_desde,
                            vigente_hasta=vigente_hasta,
                            comentario=comentario,
                        )
                        session.add(plan)
                        session.flush()
                        session.commit()
                        log_change("PlanVersion", str(plan.id), "creacion", None, f"v{version_num}", user=user_name)
                        st.success("Plan creado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            # Add items to existing plan
            if plans:
                st.markdown("---")
                st.subheader("Agregar Items a Plan")

                selected_plan_label = st.selectbox("Seleccionar plan", [f"v{p.version_num}" for p in plans], key="add_item_plan")
                selected_plan = plans[[f"v{p.version_num}" for p in plans].index(selected_plan_label)]

                with get_session() as session:
                    all_courses = session.query(Course).all()

                if all_courses:
                    course_map = {f"{c.materia} ({c.programa} - {c.anio})": c for c in all_courses}
                    selected_course_label = st.selectbox("Seleccionar materia", list(course_map.keys()), key="add_item_course")
                    selected_course = course_map[selected_course_label]

                    col_p, col_e = st.columns(2)
                    with col_p:
                        prioridad = st.number_input("Prioridad", value=1, step=1)
                    with col_e:
                        estado = st.selectbox("Estado del plan", ["planned", "backup"], key="add_item_state")

                    nota = st.text_area("Nota (opcional)")

                    if st.button("Agregar Item"):
                        with get_session() as session:
                            try:
                                item = StudentPlanItem(
                                    plan_version_id=selected_plan.id,
                                    course_id=selected_course.course_id,
                                    prioridad=prioridad,
                                    estado_plan=estado,
                                    nota=nota,
                                )
                                session.add(item)
                                session.commit()
                                log_change("StudentPlanItem", str(item.id), "creacion", None, f"{selected_course.materia}", user=user_name)
                                st.success("Item agregado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

    # ===== TAB: INSCRIPCIONES =====
    with tab_enroll:
        st.subheader("Inscripciones de Estudiantes")

        with get_session() as session:
            all_students = session.query(Student).all()

        if not all_students:
            st.info("No hay estudiantes registrados.")
        else:
            student_map = {f"{s.nombre} {s.apellido}": s for s in all_students}
            selected_label = st.selectbox("Seleccionar estudiante", list(student_map.keys()), key="enroll_student")
            selected_student = student_map[selected_label]

            # Show existing enrollments
            with get_session() as session:
                enrollments = session.query(Enrollment).filter_by(student_id=selected_student.student_id).all()

            if enrollments:
                st.write("### Inscripciones Existentes")
                for enroll in enrollments:
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    with col1:
                        st.write(f"**{enroll.course.materia}**")
                    with col2:
                        st.write(f"`{enroll.status}`")
                    with col3:
                        st.write(f"Nota: {enroll.nota_numerica or 'N/A'}")
                    with col4:
                        if st.button("Editar", key=f"edit_enroll_{enroll.id}"):
                            st.session_state[f"edit_enroll_{enroll.id}"] = True

                    if st.session_state.get(f"edit_enroll_{enroll.id}", False):
                        with st.expander("Editar inscripción", expanded=True):
                            col_s, col_n = st.columns(2)
                            with col_s:
                                new_status = st.selectbox(
                                    "Estado",
                                    ["planned", "registered", "completed", "withdrawn", "failed"],
                                    index=["planned", "registered", "completed", "withdrawn", "failed"].index(enroll.status),
                                    key=f"status_{enroll.id}",
                                )
                            with col_n:
                                new_nota = st.number_input("Calificación", value=enroll.nota_numerica or 0.0, step=0.1, key=f"nota_{enroll.id}")

                            if st.button("Actualizar", key=f"update_enroll_{enroll.id}"):
                                with get_session() as sess:
                                    e = sess.get(Enrollment, enroll.id)
                                    if new_status != e.status:
                                        log_change("Enrollment", str(e.id), "status", e.status, new_status, user=user_name)
                                        e.status = new_status
                                    if new_nota != e.nota_numerica:
                                        log_change("Enrollment", str(e.id), "nota_numerica", e.nota_numerica, new_nota, user=user_name)
                                        e.nota_numerica = new_nota
                                    if new_status == "completed":
                                        e.fecha_estado = datetime.now()
                                    sess.commit()
                                st.success("Inscripción actualizada!")
                                st.rerun()

            # Create new enrollment
            st.markdown("---")
            st.subheader("Nueva Inscripción")

            with get_session() as session:
                all_courses = session.query(Course).all()

            if all_courses:
                course_map = {f"{c.materia} ({c.programa} - {c.anio})": c for c in all_courses}
                selected_course_label = st.selectbox("Seleccionar materia", list(course_map.keys()), key="new_enroll_course")
                selected_course = course_map[selected_course_label]

                col_s, col_n = st.columns(2)
                with col_s:
                    status = st.selectbox("Estado", ["planned", "registered", "completed", "withdrawn", "failed"], key="new_enroll_status")
                with col_n:
                    nota = st.number_input("Calificación (opcional)", value=None, key="new_enroll_nota")

                if st.button("Crear Inscripción"):
                    with get_session() as session:
                        try:
                            # Check if already enrolled
                            existing = session.query(Enrollment).filter_by(
                                student_id=selected_student.student_id,
                                course_id=selected_course.course_id,
                            ).one_or_none()

                            if existing:
                                st.error("Este estudiante ya está inscrito en esta materia.")
                            else:
                                enroll = Enrollment(
                                    student_id=selected_student.student_id,
                                    course_id=selected_course.course_id,
                                    status=status,
                                    nota_numerica=nota if nota else None,
                                    fecha_registro=datetime.now(),
                                    fecha_estado=datetime.now() if status == "completed" else None,
                                )
                                session.add(enroll)
                                session.commit()
                                log_change("Enrollment", str(enroll.id), "creacion", None, f"{selected_course.materia} - {status}", user=user_name)
                                st.success("Inscripción creada!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        # Summary table
        st.markdown("---")
        st.subheader("Resumen de Inscripciones")

        with get_session() as session:
            stats = []
            for s in session.query(Student).all():
                enroll_count = len(s.enrollments) if s.enrollments else 0
                completed_count = len([e for e in (s.enrollments or []) if e.status == "completed"])
                stats.append({
                    "Estudiante": f"{s.nombre} {s.apellido}",
                    "Total Inscripciones": enroll_count,
                    "Completadas": completed_count,
                    "Promedio": f"{sum(e.nota_numerica for e in (s.enrollments or []) if e.nota_numerica) / max(completed_count, 1):.2f}" if completed_count > 0 else "N/A",
                })

        if stats:
            df_stats = pd.DataFrame(stats)
            st.dataframe(df_stats, use_container_width=True)
