import streamlit as st
import pandas as pd
from datetime import datetime

from lib import get_session, init_db, log_change
from lib.models import Student, PlanVersion, StudentPlanItem, Course, Enrollment
from lib.metrics import elective_counts_by_orientation, get_current_plan


def run():
    init_db()

    st.header("📍 Gestión de Rutas Académicas (Planes)")

    user_name = st.sidebar.text_input("Usuario (para ChangeLog)", value="admin")

    with get_session() as session:
        all_students = session.query(Student).all()

    if not all_students:
        st.info("No hay estudiantes registrados.")
        return

    student_map = {f"{s.nombre} {s.apellido}": s for s in all_students}
    selected_label = st.selectbox("Seleccionar estudiante", list(student_map.keys()), key="route_student")
    selected_student = student_map[selected_label]

    st.write(f"**Email:** {selected_student.email} | **Programa:** {selected_student.programa} | **Cohorte:** {selected_student.cohorte or 'N/A'}")

    # Fetch student's plans
    with get_session() as session:
        plans = session.query(PlanVersion).filter_by(student_id=selected_student.student_id).order_by(PlanVersion.version_num).all()

    # ===== SECTION: Current Plan Overview =====
    st.markdown("---")
    st.subheader("📋 Estado Actual del Plan")

    if plans:
        # Find current (vigente) plan
        current_plan = get_current_plan(selected_student.student_id)

        if current_plan:
            with get_session() as session:
                items = session.query(StudentPlanItem).filter_by(plan_version_id=current_plan.id).all()
                planned_count = len([i for i in items if i.estado_plan == "planned"])
                backup_count = len([i for i in items if i.estado_plan == "backup"])

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Versión Vigente", f"v{current_plan.version_num}")
            with col2:
                st.metric("Items Planned", planned_count)
            with col3:
                st.metric("Items Backup", backup_count)
            with col4:
                progress = min(planned_count / 8, 1.0)
                st.metric("Progreso Meta (8)", f"{planned_count}/8")

            # Validation: Check if planned can reach 5 in best orientation
            st.write("### ✓ Validaciones del Plan")
            col_val1, col_val2 = st.columns(2)

            with col_val1:
                if planned_count < 8:
                    st.warning(f"⚠️ Plan incompleto: {planned_count}/8 electivas planned (meta: 8)")
                else:
                    st.success(f"✅ Plan completo: {planned_count}/8 electivas planned")

            with col_val2:
                # Check if orientation goal is reachable
                if items:
                    with get_session() as session:
                        planned_items = session.query(StudentPlanItem, Course).join(
                            Course, StudentPlanItem.course_id_ref == Course.id
                        ).filter(
                            StudentPlanItem.plan_version_id == current_plan.id,
                            StudentPlanItem.estado_plan == "planned",
                            Course.tipo_materia == "electiva",
                        ).all()

                        orientation_counts = {}
                        for item, course in planned_items:
                            orient = course.orientacion or "sin_orientacion"
                            orientation_counts[orient] = orientation_counts.get(orient, 0) + 1

                        if orientation_counts:
                            best_orient = max(orientation_counts.items(), key=lambda x: x[1])
                            best_count = best_orient[1]
                            best_name = best_orient[0]

                            if best_count >= 5:
                                st.success(f"✅ {best_name}: {best_count}/5 electivas planned (meta alcanzable)")
                            elif best_count >= 3:
                                st.warning(f"⚠️ {best_name}: {best_count}/5 electivas planned (gap: {5 - best_count})")
                            else:
                                st.error(f"❌ {best_name}: {best_count}/5 electivas planned (gap: {5 - best_count} - RIESGO)")
                        else:
                            st.warning("⚠️ Sin electivas planned aún")
        else:
            st.info("Sin plan vigente actualmente")
    else:
        st.info("Este estudiante no tiene planes aún")

    # ===== SECTION: List of Plan Versions =====
    st.markdown("---")
    st.subheader("📚 Historial de Versiones")

    if plans:
        for plan in plans:
            with get_session() as session:
                items = session.query(StudentPlanItem).filter_by(plan_version_id=plan.id).all()
                item_count = len(items)

            col_info, col_action = st.columns([4, 1])

            with col_info:
                vigencia = f"{plan.vigente_desde.date()}"
                if plan.vigente_hasta:
                    vigencia += f" → {plan.vigente_hasta.date()}"
                else:
                    vigencia += " → Vigente"

                st.write(f"**v{plan.version_num}** | {vigencia} | {item_count} items")
                if plan.comentario:
                    st.caption(f"💬 {plan.comentario}")

            with col_action:
                if st.button("Expandir", key=f"expand_plan_{plan.id}"):
                    st.session_state[f"show_plan_{plan.id}"] = not st.session_state.get(f"show_plan_{plan.id}", False)

            if st.session_state.get(f"show_plan_{plan.id}", False):
                with st.expander("Contenido del plan", expanded=True):
                    if items:
                        with get_session() as session:
                            plan_data = []
                            for item in items:
                                course = session.get(Course, item.course_id)
                                plan_data.append({
                                    "Materia": course.materia if course else "N/A",
                                    "Tipo": course.tipo_materia if course else "N/A",
                                    "Orientación": course.orientacion if course else "N/A",
                                    "Estado": item.estado_plan,
                                    "Prioridad": item.prioridad,
                                    "Nota": item.nota or "",
                                })

                            df_plan = pd.DataFrame(plan_data)
                            st.dataframe(df_plan, use_container_width=True)

                        # Remove item buttons
                        st.write("**Eliminar items:**")
                        for idx, item in enumerate(items):
                            col_del, col_space = st.columns([1, 5])
                            with col_del:
                                if st.button("X", key=f"del_item_{item.id}"):
                                    with get_session() as sess:
                                        i = sess.get(StudentPlanItem, item.id)
                                        course_name = session.get(Course, i.course_id).materia if session.get(Course, i.course_id) else "N/A"
                                        sess.delete(i)
                                        sess.commit()
                                    log_change("StudentPlanItem", str(item.id), "eliminacion", f"Materia {course_name}", None, motivo="Eliminado del plan", user=user_name)
                                    st.rerun()

    # ===== SECTION: Create or Manage Current Version =====
    st.markdown("---")
    st.subheader("✨ Crear o Editar Versión")

    if not plans:
        # Create first version
        st.write("Este estudiante no tiene planes aún. Crea la primera versión:")
        with st.form("create_first_plan"):
            comentario = st.text_area("Comentario para v1", value="Plan inicial")
            submitted = st.form_submit_button("Crear Plan v1")

            if submitted:
                with get_session() as session:
                    plan = PlanVersion(
                        student_id=selected_student.student_id,
                        version_num=1,
                        vigente_desde=datetime.now(),
                        vigente_hasta=None,
                        comentario=comentario,
                    )
                    session.add(plan)
                    session.flush()
                    session.commit()
                    log_change("PlanVersion", str(plan.id), "creacion", None, "v1", motivo="Nuevo plan del estudiante", user=user_name)
                st.success("✅ Plan v1 creado!")
                st.rerun()

    else:
        # Manage current plan or create new version
        current_plan = get_current_plan(selected_student.student_id)

        if current_plan:
            st.write(f"Plan vigente: **v{current_plan.version_num}**")

            col_edit, col_close = st.columns(2)

            with col_edit:
                st.write("### Agregar Materia a Plan Vigente")

                # Fetch available courses
                with get_session() as session:
                    all_courses = session.query(Course).all()
                    existing_ids = set(
                        session.query(StudentPlanItem.course_id).filter_by(plan_version_id=current_plan.id).all()
                    )
                    existing_ids = {c[0] for c in existing_ids}

                # Filter courses not yet in plan
                available_courses = [c for c in all_courses if c.course_id not in existing_ids]

                if available_courses:
                    # Filters
                    with get_session() as session:
                        programas = sorted(set(c.programa for c in all_courses if c.programa))
                        anos = sorted(set(c.anio for c in all_courses if c.anio))
                        tipo_materias = sorted(set(c.tipo_materia for c in all_courses if c.tipo_materia))
                        orientaciones = sorted(set(c.orientacion for c in all_courses if c.orientacion))

                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        filt_programa = st.selectbox("Programa", [""] + programas, key="route_prog")
                        filt_tipo = st.selectbox("Tipo Materia", [""] + tipo_materias, key="route_tipo")
                    with col_f2:
                        filt_ano = st.selectbox("Año", [""] + [str(a) for a in anos], key="route_ano")
                        filt_orient = st.selectbox("Orientación", [""] + orientaciones, key="route_orient")

                    search_text = st.text_input("Buscar por materia", key="route_search")

                    # Filter courses
                    filtered = available_courses
                    if filt_programa:
                        filtered = [c for c in filtered if c.programa == filt_programa]
                    if filt_tipo:
                        filtered = [c for c in filtered if c.tipo_materia == filt_tipo]
                    if filt_ano:
                        filtered = [c for c in filtered if str(c.anio) == filt_ano]
                    if filt_orient:
                        filtered = [c for c in filtered if c.orientacion == filt_orient]
                    if search_text:
                        filtered = [c for c in filtered if search_text.lower() in c.materia.lower()]

                    if filtered:
                        course_labels = [f"{c.materia} ({c.programa}/{c.anio}) - {c.tipo_materia}" for c in filtered]
                        selected_idx = st.selectbox("Seleccionar materia", range(len(filtered)), format_func=lambda i: course_labels[i], key="route_course_select")
                        selected_course = filtered[selected_idx]

                        col_p, col_s = st.columns(2)
                        with col_p:
                            prioridad = st.number_input("Prioridad", min_value=1, value=1, step=1)
                        with col_s:
                            estado = st.selectbox("Estado del Plan", ["planned", "backup"], key="route_state")

                        nota = st.text_area("Nota (opcional)", key="route_nota")

                        if st.button("Agregar a Plan", key="add_to_plan"):
                            with get_session() as session:
                                item = StudentPlanItem(
                                    plan_version_id=current_plan.id,
                                    course_id_ref=selected_course.id,
                                    course_id=selected_course.course_id,  # Store for reference
                                    prioridad=prioridad,
                                    estado_plan=estado,
                                    nota=nota if nota else None,
                                )
                                session.add(item)
                                session.commit()
                            log_change("StudentPlanItem", str(item.id), "creacion", None, f"{selected_course.materia} ({estado})", motivo="Agregado a plan vigente", user=user_name)
                            st.success(f"✅ {selected_course.materia} agregado ({estado})")
                            st.rerun()
                    else:
                        st.info("No hay materias disponibles con los filtros seleccionados.")
                else:
                    st.info("Todas las materias disponibles ya están en el plan.")

            with col_close:
                st.write("### Cerrar Versión")
                st.write(f"Plan v{current_plan.version_num} - Vigente desde {current_plan.vigente_desde.date()}")

                if st.button("Cerrar esta versión y crear nueva", key="close_version"):
                    # Close current plan
                    with get_session() as session:
                        plan_to_close = session.get(PlanVersion, current_plan.id)
                        plan_to_close.vigente_hasta = datetime.now()
                        session.commit()

                    log_change("PlanVersion", str(current_plan.id), "cierre", "vigente_hasta", None, datetime.now().date(), motivo="Cerrada para crear nueva versión", user=user_name)

                    # Create new version
                    with get_session() as session:
                        next_version = max([p.version_num for p in plans]) + 1
                        new_plan = PlanVersion(
                            student_id=selected_student.student_id,
                            version_num=next_version,
                            vigente_desde=datetime.now(),
                            vigente_hasta=None,
                            comentario=f"Plan v{next_version} (nueva versión)",
                        )
                        session.add(new_plan)
                        session.commit()

                    log_change("PlanVersion", str(new_plan.id), "creacion", None, f"v{next_version}", motivo="Nueva versión tras cerrar anterior", user=user_name)
                    st.success(f"✅ Versión cerrada. Nuevo plan v{next_version} creado.")
                    st.rerun()

        else:
            # No current plan, but there are old plans
            with get_session() as session:
                max_version = max([p.version_num for p in plans])

            st.write(f"No hay plan vigente. Última versión: v{max_version}")
            st.write("Crea una nueva versión:")

            with st.form("create_new_version"):
                comentario = st.text_area("Comentario", value=f"Plan v{max_version + 1}")
                submitted = st.form_submit_button(f"Crear Plan v{max_version + 1}")

                if submitted:
                    with get_session() as session:
                        new_plan = PlanVersion(
                            student_id=selected_student.student_id,
                            version_num=max_version + 1,
                            vigente_desde=datetime.now(),
                            vigente_hasta=None,
                            comentario=comentario,
                        )
                        session.add(new_plan)
                        session.flush()
                        session.commit()
                        log_change("PlanVersion", str(new_plan.id), "creacion", None, f"v{max_version + 1}", motivo="Nueva versión", user=user_name)
                    st.success(f"✅ Plan v{max_version + 1} creado!")
                    st.rerun()

    # ===== SECTION: Summary Table =====
    st.markdown("---")
    st.subheader("📊 Sumario de Planes del Estudiante")

    if plans:
        summary_data = []
        for plan in plans:
            with get_session() as session:
                items = session.query(StudentPlanItem).filter_by(plan_version_id=plan.id).all()
                planned = len([i for i in items if i.estado_plan == "planned"])
                backup = len([i for i in items if i.estado_plan == "backup"])

            status = "Vigente" if (not plan.vigente_hasta) else "Cerrada"
            summary_data.append({
                "Versión": f"v{plan.version_num}",
                "Desde": plan.vigente_desde.date(),
                "Hasta": plan.vigente_hasta.date() if plan.vigente_hasta else "Vigente",
                "Planned": planned,
                "Backup": backup,
                "Total": len(items),
                "Estado": status,
            })

        df_summary = pd.DataFrame(summary_data)
        st.dataframe(df_summary, use_container_width=True)

run()