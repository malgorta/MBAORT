import io
import streamlit as st
import pandas as pd
from datetime import datetime

from lib import get_session, init_db, log_change
from lib.models import Student, Meeting, ChangeLog


def run():
    init_db()

    st.header("Gestión de Estudiantes")

    # Sidebar configuration
    user_name = st.sidebar.text_input("Usuario (para registro de cambios)", value="admin")

    # Tabs
    tab_crud, tab_import, tab_meetings = st.tabs(["CRUD Estudiantes", "Importar Estudiantes", "Reuniones"])

    # ===== TAB: CRUD =====
    with tab_crud:
        st.subheader("CRUD de Estudiantes")

        with get_session() as session:
            all_students = session.query(Student).all()

        if all_students:
            # Selection
            student_names = {f"{s.nombre} {s.apellido} ({s.email})": s for s in all_students}
            selected_label = st.selectbox("Seleccionar estudiante para editar", options=list(student_names.keys()))
            selected_student = student_names[selected_label]

            col1, col2, col3 = st.columns(3)

            with col1:
                nuevo_nombre = st.text_input("Nombre", value=selected_student.nombre)
            with col2:
                nuevo_apellido = st.text_input("Apellido", value=selected_student.apellido)
            with col3:
                nuevo_email = st.text_input("Email", value=selected_student.email)

            col4, col5 = st.columns(2)
            with col4:
                nuevo_programa = st.selectbox("Programa", ["MBA", "EMBA"], 
                                             index=["MBA", "EMBA"].index(selected_student.programa or "MBA"))
            with col5:
                nuevo_cohorte = st.text_input("Cohorte", value=selected_student.cohorte or "")

            if st.button("Actualizar Estudiante"):
                with get_session() as session:
                    s = session.get(Student, selected_student.student_id)
                    if s:
                        if s.nombre != nuevo_nombre:
                            log_change("Student", str(s.student_id), "nombre", s.nombre, nuevo_nombre, user=user_name)
                            s.nombre = nuevo_nombre
                        if s.apellido != nuevo_apellido:
                            log_change("Student", str(s.student_id), "apellido", s.apellido, nuevo_apellido, user=user_name)
                            s.apellido = nuevo_apellido
                        if s.email != nuevo_email:
                            log_change("Student", str(s.student_id), "email", s.email, nuevo_email, user=user_name)
                            s.email = nuevo_email
                        if s.programa != nuevo_programa:
                            log_change("Student", str(s.student_id), "programa", s.programa, nuevo_programa, user=user_name)
                            s.programa = nuevo_programa
                        if s.cohorte != nuevo_cohorte:
                            log_change("Student", str(s.student_id), "cohorte", s.cohorte, nuevo_cohorte, user=user_name)
                            s.cohorte = nuevo_cohorte
                        session.commit()
                st.success("Estudiante actualizado!")
                st.rerun()

            if st.button("Eliminar Estudiante (soft delete)", key="btn_del"):
                with get_session() as session:
                    s = session.get(Student, selected_student.student_id)
                    if s:
                        log_change("Student", str(s.student_id), "status", "activo", "eliminado", "Soft delete", user=user_name)
                        # In a real system, you'd set a 'deleted_at' or 'is_active' flag
                        session.delete(s)
                        session.commit()
                st.success("Estudiante eliminado!")
                st.rerun()

        # Create new student
        st.markdown("---")
        st.subheader("Crear Nuevo Estudiante")
        col_n, col_a, col_e = st.columns(3)
        with col_n:
            new_nombre = st.text_input("Nombre (nuevo)", key="new_nombre")
        with col_a:
            new_apellido = st.text_input("Apellido (nuevo)", key="new_apellido")
        with col_e:
            new_email = st.text_input("Email (nuevo)", key="new_email")

        col_p, col_c = st.columns(2)
        with col_p:
            new_programa = st.selectbox("Programa (nuevo)", ["MBA", "EMBA"], key="new_programa")
        with col_c:
            new_cohorte = st.text_input("Cohorte (nuevo)", key="new_cohorte")

        if st.button("Crear Estudiante"):
            if not new_nombre or not new_email:
                st.error("Nombre y email son requeridos.")
            else:
                with get_session() as session:
                    try:
                        new_student = Student(
                            nombre=new_nombre,
                            apellido=new_apellido,
                            email=new_email,
                            programa=new_programa,
                            cohorte=new_cohorte,
                        )
                        session.add(new_student)
                        session.flush()
                        session.commit()
                        log_change("Student", str(new_student.student_id), "creacion", None, "nuevo estudiante", user=user_name)
                        st.success("Estudiante creado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creando estudiante: {e}")

    # ===== TAB: IMPORTAR =====
    with tab_import:
        st.subheader("Importar Estudiantes desde CSV/Excel")

        uploaded_file = st.file_uploader("Cargar archivo (CSV o Excel)", type=["csv", "xlsx"])

        if uploaded_file:
            try:
                if uploaded_file.name.endswith(".csv"):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)

                required_cols = ["nombre", "apellido", "email", "programa"]
                missing = [c for c in required_cols if c.lower() not in [col.lower() for col in df.columns]]
                if missing:
                    st.error(f"Faltan columnas: {missing}")
                else:
                    # Map columns (case-insensitive)
                    col_map = {col.lower(): col for col in df.columns}
                    df_mapped = df.copy()
                    df_mapped.columns = [c.lower() for c in df_mapped.columns]

                    # Show preview
                    st.write("Vista previa (primeras 5 filas):")
                    st.dataframe(df_mapped.head())

                    if st.button("Importar Estudiantes"):
                        created_count = 0
                        error_list = []

                        with get_session() as session:
                            for idx, row in df_mapped.iterrows():
                                try:
                                    email = str(row.get("email", "")).strip()
                                    nombre = str(row.get("nombre", "")).strip()
                                    apellido = str(row.get("apellido", "")).strip()
                                    programa = str(row.get("programa", "MBA")).strip()

                                    if not email or not nombre:
                                        error_list.append(f"Fila {idx}: email o nombre vacíos")
                                        continue

                                    existing = session.query(Student).filter_by(email=email).one_or_none()
                                    if existing:
                                        error_list.append(f"Fila {idx}: email {email} ya existe")
                                        continue

                                    new_s = Student(
                                        nombre=nombre,
                                        apellido=apellido,
                                        email=email,
                                        programa=programa,
                                    )
                                    session.add(new_s)
                                    session.flush()
                                    created_count += 1
                                    
                                except Exception as e:
                                    error_list.append(f"Fila {idx}: {e}")

                            session.commit()

                        st.success(f"✅ {created_count} estudiantes importados.")
                        if error_list:
                            with st.expander("Ver errores"):
                                for err in error_list:
                                    st.write(f"❌ {err}")

            except Exception as e:
                st.error(f"Error leyendo archivo: {e}")

    # ===== TAB: REUNIONES =====
    with tab_meetings:
        st.subheader("Gestión de Reuniones")

        with get_session() as session:
            all_students = session.query(Student).all()

        if not all_students:
            st.info("No hay estudiantes registrados.")
        else:
            student_map = {f"{s.nombre} {s.apellido}": s for s in all_students}
            selected_student_label = st.selectbox("Seleccionar estudiante", list(student_map.keys()), key="sel_meeting")
            selected_student = student_map[selected_student_label]

            st.write(f"**Email:** {selected_student.email}")

            # Existing meetings
            with get_session() as session:
                meetings = session.query(Meeting).filter_by(student_id=selected_student.student_id).all()

            if meetings:
                st.write("### Reuniones pasadas")
                for m in sorted(meetings, key=lambda x: x.fecha or datetime.min):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{m.fecha}** - {m.orientacion_objetivo or 'Sin orientación'}")
                        if m.acuerdo_texto:
                            st.caption(f"Acuerdo: {m.acuerdo_texto}")
                        if m.notas:
                            st.caption(f"Notas: {m.notas}")
                    with col2:
                        if st.button("Eliminar", key=f"del_meeting_{m.id}"):
                            with get_session() as sess:
                                sess.delete(sess.get(Meeting, m.id))
                                sess.commit()
                            st.rerun()

            st.markdown("---")
            st.subheader("Nueva Reunión")

            col_f, col_o = st.columns(2)
            with col_f:
                meeting_date = st.date_input("Fecha", value=datetime.now())
            with col_o:
                meeting_orient = st.text_input("Orientación Objetivo")

            meeting_acuerdo = st.text_area("Acuerdo de texto")
            meeting_notas = st.text_area("Notas")

            if st.button("Guardar Reunión"):
                if meeting_date:
                    with get_session() as session:
                        meeting = Meeting(
                            student_id=selected_student.student_id,
                            fecha=meeting_date,
                            orientacion_objetivo=meeting_orient,
                            acuerdo_texto=meeting_acuerdo,
                            notas=meeting_notas,
                        )
                        session.add(meeting)
                        session.commit()
                    log_change("Meeting", str(meeting.id), "creacion", None, f"Reunión {meeting_date}", user=user_name)
                    st.success("Reunión guardada!")
                    st.rerun()
                else:
                    st.error("Seleccione una fecha.")

        # Summary table
        st.markdown("---")
        st.subheader("Resumen de Estudiantes")

        with get_session() as session:
            students_summary = []
            for s in session.query(Student).all():
                meeting_count = len(s.meetings) if s.meetings else 0
                last_orientation = s.meetings[-1].orientacion_objetivo if s.meetings else "N/A"
                students_summary.append({
                    "Nombre": f"{s.nombre} {s.apellido}",
                    "Email": s.email,
                    "Programa": s.programa,
                    "Cohorte": s.cohorte or "N/A",
                    "Tiene Reunión": "✓" if meeting_count > 0 else "✗",
                    "Orientación Objetivo": last_orientation,
                })

        if students_summary:
            df_summary = pd.DataFrame(students_summary)
            st.dataframe(df_summary, use_container_width=True)
