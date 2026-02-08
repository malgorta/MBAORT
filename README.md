# Gestión de Rutas Académicas MBA/EMBA

Una aplicación Streamlit para gestionar cronogramas, estudiantes, planes académicos versionados e inscripciones en programas MBA/EMBA, con análisis de cumplimiento de la regla 5/8 (mínimo 5 electivas en una orientación).

## Características

### 🗓️ Importación de Cronograma (01_Cronograma)
- Carga de archivo Excel consolidado (`Cronograma_2026_verificado_completo.xlsx`)
- Validación automática de columnas y datos
- Persistencia en SQLite con modelos `Course` y `CourseSource`
- Filtros por Programa, Año, Tipo Materia, Orientación
- Búsqueda por Materia
- Exportación a CSV de datos filtrados
- Registro automático de importación en ChangeLog

### 👥 Gestión de Estudiantes (02_Estudiantes)
- **CRUD Estudiantes**: crear, editar, eliminar
- **Importación masiva**: desde CSV/Excel (nombre, apellido, email, programa)
- **Gestión de Reuniones**: fecha, orientación objetivo, acuerdo, notas
- Tabla resumen con indicadores: tiene reunión, orientación objetivo
- Registro de cambios en ChangeLog

### � Gestión de Rutas Académicas (03_Rutas)
- **Planes Versionados**: selector de estudiante, autoincrement de version_num
- **UI Intuitiva**: filtros (Programa/Año/Tipo) + búsqueda para agregar materias
- **Estados del Plan**: marcar cada item como planned o backup con prioridad
- **Validaciones Visibles**:
  - Progreso hacia 8 electivas planned (meta de completitud)
  - Advertencia si con lo planned no es posible alcanzar 5 en orientación objetivo
  - Gap display por orientación
- **Ciclo de Versiones**: cerrar versión (vigente_hasta) y crear nueva automáticamente
- Registro completo en ChangeLog de altas/bajas de items y cambios de versión

### �📚 Planes Académicos (03_Planes)
- **Planes Versionados**: crear múltiples versiones para cada estudiante
- **Vigencia**: rango de fechas (vigente_desde, vigente_hasta)
- **Items del Plan**: agregar materias con prioridad y estado (planned/backup)
- **Inscripciones**: registrar, editar estado (planned/registered/completed/withdrawn/failed)
- Calificaciones numéricas y seguimiento de fechas
### 📝 Gestión de Inscripciones (04_Inscripciones)
- **Merge Plan vs Enrollments**: visualizar plan vigente vs inscripciones reales por course_id
- **Crear Inscripciones Masivas**: botón para generar todos los enrollments planned del plan en un clic
- **Formulario de Inscripción**: status, nota texto, nota numérica, fecha de finalización
- **Alertas Automáticas**:
  - ❌ Completó materia no en el plan
  - ❌ Duplicó materia (mismo course_id múltiple veces)
  - ⚠️ No llega a 5/8 según electivas completadas + planned
- **Registro de Cambios**: cada actualización de status en ChangeLog
- **Dashboard de Progreso**: resumen de inscripciones y cumplimiento regla 5/8
### 📊 Reportes y Análisis (04_Reportes)
- **Regla 5/8**: verificación automatizada (5+ electivas en una orientación)
- **Métricas por Grupo**: cohorte y programa
- **Análisis de Riesgo**: categorización (bajo, medio, alto) según progreso hacia meta
- Tablas comparativas y gráficos
- Identificación de estudiantes en riesgo

### 🔍 Auditoría (05_Auditoria)
- **Filtros avanzados**: fecha (desde/hasta), usuario, entidad, estudiante
- **Tabla de ChangeLog**: ordenada por timestamp descendente
- **Exportación CSV**: descarga completa o filtrada de registros de auditoría
- **Estadísticas**: resumen de cambios por entidad y usuario con gráficos

### 📊 Reportes Gerenciales (06_Reportes)
- **Demanda por Curso**: cantidad de estudiantes con materia planned (filtros: Programa/Año/Orientación)
- **Demanda Temporal**: distribución por módulo y mes de inicio
- **Cumplimiento Regla 5/8**: % de estudiantes OK, promedio electivas completadas, distribución por orientación
- **Estudiantes en Riesgo**: gap a 5 electivas, nivel de riesgo (bajo/medio/alto), electivas restantes
- **Exportación**: CSV y Excel para todos los reportes

## Estructura del Proyecto

```
/workspaces/MBAORT/
├── streamlit_app.py        # Router multipágina (autodetecta páginas)
├── requirements.txt         # Dependencias
├── data/
│   └── app.db              # Base de datos SQLite (se crea automáticamente)
├── lib/
│   ├── db.py               # Configuración SQLAlchemy y session management
│   ├── models.py           # ORM models (Course, Student, Meeting, etc.)
│   ├── validators.py       # Validación de DataFrames (pandera)
│   ├── io_excel.py         # Importación y procesamiento de Excel
│   ├── helpers.py          # Funciones auxiliares (log_change)
│   └── metrics.py          # Análisis de regla 5/8 y métricas
└── pages/
    ├── 00_home.py             # Página inicial
    ├── 01_Cronograma.py    # Importación y gestión de cronograma
    ├── 02_Estudiantes.py   # Gestión de estudiantes y reuniones
    ├── 03_Rutas.py         # Gestión de rutas (planes versionados)
    ├── 03_Planes.py        # Planes versionados e inscripciones
    ├── 04_Inscripciones.py # Gestión de inscripciones con validaciones
    ├── 04_Reportes.py      # Reportes y análisis (regla 5/8)
    ├── 05_Auditoria.py     # Auditoría y ChangeLog
    └── 06_Reportes.py      # Reportes gerenciales y KPIs
```

## Base de Datos

### Tablas principales

| Tabla | Descripción |
|-------|---|
| `courses` | Materias del cronograma (MateriaID como PK) |
| `course_sources` | Trazabilidad del origen de cada materia |
| `students` | Estudiantes (nombre, apellido, email, programa, cohorte) |
| `meetings` | Reuniones de tutoría/seguimiento |
| `plan_versions` | Versiones de planes académicos (vigente_desde, vigente_hasta) |
| `student_plan_items` | Items dentro de un plan (materia, prioridad, estado) |
| `enrollments` | Inscripciones de estudiantes en materias |
| `change_logs` | Auditoría de cambios (entidad, campo, usuario, timestamp) |

## Instalación y Ejecución

### 1. Instalar dependencias

```bash
cd /workspaces/MBAORT
pip install -r requirements.txt
```

### 2. Ejecutar la aplicación

#### En GitHub Codespaces (recomendado):

```bash
streamlit run streamlit_app.py --server.enableCORS false --server.enableXsrfProtection false
```

#### En máquina local:

```bash
streamlit run streamlit_app.py
```

La app estará disponible en `http://localhost:8501` (o en la URL que indica Streamlit en Codespaces).

### 3. Base de Datos

- **Ubicación**: `data/app.db` (archivo SQLite)
- **Creación automática**: Se genera en la primera ejecución o al hacer clic en "🔄 Inicializar DB" en la barra lateral
- **Tamaño inicial**: ~120 KB (solo schema)

#### Resetear la base de datos:

**Opción A - Desde la UI (recomendado):**
1. En la barra lateral izquierda, sección "💾 Base de Datos"
2. Haz clic en el botón "🔄 Inicializar DB"
3. Se resetea el schema manteniendo la estructura

**Opción B - Desde terminal:**
```bash
rm -f data/app.db
# Luego ejecuta streamlit nuevamente para recrearla
```

⚠️ **Advertencia**: Resetear la DB borra todos los datos (cronogramas, estudiantes, planes, inscripciones, auditoría). Exporta tus datos antes si es necesario.

## Dependencias

- **streamlit**: UI interactiva
- **pandas**: manipulación de datos
- **openpyxl**: lectura de archivos Excel
- **sqlalchemy**: ORM y base de datos
- **pandera**: validación de DataFrames

## Flujo de Trabajo Típico

1. **Importar cronograma**: sube el Excel consolidado desde la página 01_Cronograma
2. **Registrar estudiantes**: usa CRUD o importación CSV en 02_Estudiantes
3. **Crear planes**: crea versiones de planes en 03_Planes, agrega materias
4. **Hacer inscripciones**: registra estudiantes en materias y actualiza estado
5. **Analizar progreso**: consulta reportes de regla 5/8 en 04_Reportes

## Validación

- Las columnas esperadas en Excel se validan automáticamente
- Mensajes de error claros si faltan datos o columnas
- Cada cambio se registra en ChangeLog con usuario, entidad, campo, valores anterior/nuevo

## Notas

- La base de datos SQLite se crea automáticamente en `data/app.db`
- La regla 5/8 se calcula sobre `Enrollment.status == 'completed'` y `Course.tipo_materia == 'electiva'`
- Los usuarios pueden registrar cambios indicando su nombre en la barra lateral

