import streamlit as st
import pandas as pd
from datetime import datetime

from lib import get_session, init_db, log_change
from lib.models import Student, PlanVersion, StudentPlanItem, Course, Enrollment
from lib.metrics import get_current_plan, check_rule_5_of_8


def run():
    init_db()

    st.header("📝 Gestión de Inscripciones")

    user_name = st.sidebar.text_input("Usuario (para ChangeLog)", value="admin")

    with get_session() as session:
        all_students = session.query(Student).all()

    if not all_students:
        st.info("No hay estudiantes registrados.")
        return

    student_map = {f"{s.nombre} {s.apellido}": s for s in all_students}
    selected_label = st.selectbox("Seleccionar estudiante", list(student_map.keys()), key="enroll_student")
    selected_student = student_map[selected_label]

    st.write(f"**Email:** {selected_student.email} | **Programa:** {selected_student.programa} | **Cohorte:** {selected_student.cohorte or 'N/A'}")

    # Get current plan and enrollments
    current_plan = get_current_plan(selected_student.student_id)

    with get_session() as session:
        enrollments = session.query(Enrollment).filter_by(student_id=selected_student.student_id).all()

    # ===== SECTION: Alerts & Validations =====
    st.markdown("---")
    st.subheader("⚠️ Alertas y Validaciones")

    alerts = []

    # Alert 1: Duplicated courses
    with get_session() as session:
        course_ids = [e.course_id for e in enrollments]
        duplicated = [c for c in set(course_ids) if course_ids.count(c) > 1]

    if duplicated:
        for course_id in duplicated:
            alert_msg = f"Materia {course_id}: inscrito P{enrollments.count(e for e in enrollments if e.course_id == course_id)} veces (DUPLICADO)"
            alerts.append(alert_msg)

    # Alert 2: Completed courses not in plan
    if current_plan:
        with get_session() as session:
            plan_items = session.query(StudentPlanItem).filter_by(plan_version_id=current_plan.id).all()
            plan_course_ids = set(item.course_id for item in plan_items)

            completed = session.query(Enrollment).filter(
                Enrollment.student_id == selected_student.student_id,
                Enrollment.status == "completed",
            ).all()

            for enroll in completed:
                if enroll.course_id not in plan_course_ids:
                    alerts.append(f"Completó {enroll.course_id} que NO está en el plan vigente")

    # Alert 3: Won't reach 5/8
    with get_session() as session:
        completed_enrolls = session.query(Enrollment).filter(
            Enrollment.student_id == selected_student.student_id,
            Enrollment.status == "completed",
        ).all()
        completed_count = len(completed_enrolls)

        if current_plan:
            plan_items = session.query(StudentPlanItem).filter_by(plan_version_id=current_plan.id).all()
            planned_items = [i for i in plan_items if i.estado_plan == "planned"]

            # Count orientations in completed + planned
            all_items = completed_enrolls + [StudentPlanItem(course_id=p.course_id, estado_plan=p.estado_plan) for p in planned_items]
            orientation_counts = {}

            for item in all_items:
                course = session.get(Course, item.course_id if isinstance(item, StudentPlanItem) else item.course_id)
                if course and course.tipo_materia == "electiva":
                    orient = course.orientacion or "sin_orientacion"
                    orientation_counts[orient] = orientation_counts.get(orient, 0) + 1

            if orientation_counts:
                best_count = max(orientation_counts.values())
                if best_count < 5:
                    gap = 5 - best_count
                    alerts.append(f"⚠️ Máximo en una orientación: {best_count}/5 (gap: {gap} electivas)")

    if alerts:
        for alert in alerts:
            st.error(f"❌ {alert}")
    else:
        st.success("✅ Sin alertas detectadas")

    # ===== SECTION: Plan vs Enrollments View =====
    st.markdown("---")
    st.subheader("📋 Plan Vigente vs Inscripciones Reales")

    if current_plan:
        with get_session() as session:
            plan_items = session.query(StudentPlanItem).filter_by(plan_version_id=current_plan.id).all()

            comparison_data = []

            # Get all courses from plan items
            for item in plan_items:
                course = session.get(Course, item.course_id)
                materia_name = course.materia if course else "N/A"
                tipo = course.tipo_materia if course else "N/A"
                orientacion = course.orientacion if course else "N/A"

                # Find corresponding enrollment
                matching_enroll = next((e for e in enrollments if e.course_id == item.course_id), None)

                if matching_enroll:
                    enroll_status = matching_enroll.status
                    enroll_nota = matching_enroll.nota_numerica or "-"
                else:
                    enroll_status = "-"
                    enroll_nota = "-"

                comparison_data.append({
                    "Materia ID": item.course_id,
                    "Materia": materia_name,
                    "Tipo": tipo,
                    "Orientación": orientacion,
                    "Plan Estado": item.estado_plan,
                    "Enrollments Status": enroll_status,
                    "Nota": enroll_nota,
                })

            # Add enrollments not in plan
            plan_course_ids = set(item.course_id for item in plan_items)
            for enroll in enrollments:
                if enroll.course_id not in plan_course_ids:
                    course = session.get(Course, enroll.course_id)
                    materia_name = course.materia if course else "N/A"
                    tipo = course.tipo_materia if course else "N/A"
                    orientacion = course.orientacion if course else "N/A"

                    comparison_data.append({
                        "Materia ID": enroll.course_id,
                        "Materia": materia_name,
                        "Tipo": tipo,
                        "Orientación": orientacion,
                        "Plan Estado": "❌ NO EN PLAN",
                        "Enrollments Status": enroll.status,
                        "Nota": enroll.nota_numerica or "-",
                    })

            if comparison_data:
                df_comparison = pd.DataFrame(comparison_data)
                st.dataframe(df_comparison, use_container_width=True)
            else:
                st.info("Sin items en el plan vigente")
    else:
        st.info("Este estudiante no tiene plan vigente")

    # ===== SECTION: Bulk Create Enrollments from Plan =====
    st.markdown("---")
    st.subheader("📥 Crear Inscripciones desde Plan Vigente")

    if current_plan:
        with get_session() as session:
            plan_items = session.query(StudentPlanItem).filter_by(
                plan_version_id=current_plan.id,
                estado_plan="planned",
            ).all()

            # Filter items without enrollment
            pending_items = []
            for item in plan_items:
                if not any(e.course_id == item.course_id for e in enrollments):
                    pending_items.append(item)

        if pending_items:
            st.write(f"Se pueden crear {len(pending_items)} inscripciones desde el plan planned:")

            if st.button("Crear todas las inscripciones planned", key="bulk_create"):
                created_count = 0
                with get_session() as session:
                    for item in pending_items:
                        enroll = Enrollment(
                            student_id=selected_student.student_id,
                            course_id=item.course_id,
                            status="planned",
                            nota_numerica=None,
                            fecha_registro=datetime.now(),
                            fecha_estado=None,
                        )
                        session.add(enroll)
                        session.flush()
                        created_count += 1
                        log_change("Enrollment", str(enroll.id), "creacion", None, f"{item.course_id} (planned)", motivo="Creado desde plan_version", user=user_name)

                    session.commit()

                st.success(f"✅ {created_count} inscripciones creadas")
                st.rerun()
        else:
            st.info("Todas las materias planned ya tienen inscripción")
    else:
        st.info("Sin plan vigente para generar enrollments")

    # ===== SECTION: Add/Edit Enrollment =====
    st.markdown("---")
    st.subheader("➕ Agregar o Editar Inscripción")

    with get_session() as session:
        all_courses = session.query(Course).all()

    if all_courses:
        # Filter to show only courses not yet enrolled (or allow editing)
        course_map = {f"{c.materia} ({c.programa}/{c.anio})": c for c in all_courses}
        selected_course_label = st.selectbox("Seleccionar materia", list(course_map.keys()), key="enroll_course")
        selected_course = course_map[selected_course_label]

        col1, col2, col3 = st.columns(3)

        with col1:
            status = st.selectbox(
                "Estado",
                ["planned", "registered", "completed", "withdrawn", "failed"],
                key="enroll_status"
            )

        with col2:
            nota_text = st.text_input("Nota (texto)", value="", key="enroll_nota_text")

        with col3:
            nota_numerica = st.number_input("Calificación (0-100)", min_value=0.0, max_value=100.0, value=None, key="enroll_nota_num")

        fecha_estado = None
        if status == "completed":
            fecha_estado = st.date_input("Fecha de finalización", value=datetime.now(), key="enroll_fecha")

        # Check if enrollment exists
        existing_enroll = next((e for e in enrollments if e.course_id_ref == selected_course.id), None)

        if existing_enroll:
            st.info(f"Este estudiante ya está inscrito en {selected_course.materia} (estado: {existing_enroll.status})")
            col_upd, col_del = st.columns(2)

            with col_upd:
                if st.button("Actualizar Inscripción", key="update_enroll"):
                    with get_session() as session:
                        enroll = session.get(Enrollment, existing_enroll.id)
                        old_status = enroll.status

                        enroll.status = status
                        enroll.nota = nota_text if nota_text else None
                        enroll.nota_numerica = nota_numerica if nota_numerica else None
                        if fecha_estado:
                            enroll.fecha_estado = fecha_estado

                        session.commit()

                    if old_status != status:
                        log_change("Enrollment", str(existing_enroll.id), "status", old_status, status, motivo="Actualización manual", user=user_name)

                    st.success("✅ Inscripción actualizada")
                    st.rerun()

            with col_del:
                if st.button("Eliminar Inscripción", key="del_enroll"):
                    with get_session() as session:
                        session.delete(session.get(Enrollment, existing_enroll.id))
                        session.commit()

                    log_change("Enrollment", str(existing_enroll.id), "eliminacion", status, None, motivo="Eliminada manualmente", user=user_name)
                    st.success("✅ Inscripción eliminada")
                    st.rerun()

        else:
            # Create new enrollment
            if st.button("Crear Inscripción", key="create_enroll"):
                with get_session() as session:
                    enroll = Enrollment(
                        student_id=selected_student.student_id,
                        course_id_ref=selected_course.id,
                        course_id=selected_course.course_id,  # Store for reference
                        status=status,
                        nota=nota_text if nota_text else None,
                        nota_numerica=nota_numerica if nota_numerica else None,
                        fecha_registro=datetime.now(),
                        fecha_estado=fecha_estado if fecha_estado else None,
                    )
                    session.add(enroll)
                    session.flush()
                    session.commit()

                log_change("Enrollment", str(enroll.id), "creacion", None, f"{selected_course.course_id} ({status})", motivo="Creada manualmente", user=user_name)
                st.success(f"✅ Inscripción en {selected_course.materia} creada")
                st.rerun()

    # ===== SECTION: Current Status Summary =====
    st.markdown("---")
    st.subheader("📊 Sumario de Inscripciones")

    with get_session() as session:
        enrolls = session.query(Enrollment).filter_by(student_id=selected_student.student_id).all()

    if enrolls:
        status_counts = {}
        for e in enrolls:
            status_counts[e.status] = status_counts.get(e.status, 0) + 1

        col_stat = st.columns(len(status_counts))
        for idx, (s, count) in enumerate(sorted(status_counts.items())):
            with col_stat[idx]:
                st.metric(s.capitalize(), count)

        # Summary table
        enroll_summaries = []
        with get_session() as session:
            for e in enrolls:
                course = session.get(Course, e.course_id)
                enroll_summaries.append({
                    "Materia": course.materia if course else e.course_id,
                    "Estado": e.status,
                    "Nota Numérica": e.nota_numerica or "-",
                    "Nota Texto": e.nota or "-",
                    "Fecha Registro": e.fecha_registro.date() if e.fecha_registro else "-",
                    "Fecha Estado": e.fecha_estado.date() if e.fecha_estado else "-",
                })

        df_enrolls = pd.DataFrame(enroll_summaries)
        st.dataframe(df_enrolls, use_container_width=True)
    else:
        st.info("Sin inscripciones aún")

    # ===== SECTION: Rule 5/8 Check =====
    st.markdown("---")
    st.subheader("🎯 Progreso Regla 5/8")

    ok, best_orient, best_count = check_rule_5_of_8(selected_student.student_id)

    col_ok, col_orient, col_count = st.columns(3)

    with col_ok:
        if ok:
            st.success("✅ CUMPLE Regla 5/8")
        else:
            st.error("❌ NO CUMPLE Regla 5/8")

    with col_orient:
        st.metric("Mejor Orientación", best_orient or "N/A")

    with col_count:
        st.metric("Electivas Completadas", f"{best_count}/5")

run()