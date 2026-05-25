# MokaMusic Architecture Migration Plan

Fecha de revision: 2026-05-25

## Resumen

La migracion de arquitectura esta cerrada. La app ya tiene la estructura nueva por capas y el punto de entrada `from app.ui import iniciar_app` resuelve al paquete `app/ui/__init__.py`.

Estado estimado: Fases 1-4 completadas.

Lo que falta queda en Fase 5: documentacion final, verificacion manual de flujos visuales y limpieza operativa.

## Capas Ya Migradas

- `app/controllers/`: controladores por responsabilidad.
- `app/models/`: resultados, enums y datos compartidos.
- `app/services/`: operaciones de archivos, respaldos, portadas y biblioteca.
- `app/ui/`: clase principal y workflows extraidos.
- `app/views/`: paneles principales.
- `app/views/modals/`: modales separados.
- `app/ui_helpers/`: widgets reutilizables.
- `app/utils/`: utilidades puras de formato y limpieza.

## Raiz Actual De `app/`

La raiz de `app/` ya quedo reducida a archivos compartidos y paquetes:

```text
app/
  __init__.py
  constants.py
  i18n.py
  controllers/
  models/
  services/
  ui/
  ui_helpers/
  utils/
  views/
```

## Fase 1: Asegurar Punto De Entrada

Estado: completada el 2026-05-25.

Objetivo: dejar claro que el paquete nuevo es la entrada oficial.

Tareas:

- Cambiar `main.py` para importar explicitamente desde `app.ui`.
- Mantener `app/ui/__init__.py` como export publico de `MokaMusicApp` e `iniciar_app`.
- Agregar o mantener smoke tests de `main` y `app.ui`.
- Verificar con:

```powershell
.\.venv\Scripts\python.exe -c "import app.ui; print(app.ui.__file__)"
.\.venv\Scripts\python.exe -m unittest tests.test_smoke
```

Criterio de salida:

- El primer comando imprime una ruta terminada en `app\ui\__init__.py`.
- Los smoke tests pasan.

Validacion ejecutada:

```powershell
.\.venv\Scripts\python.exe -c "import app.ui; print(app.ui.__file__)"
.\.venv\Scripts\python.exe -m unittest tests.test_smoke
.\.venv\Scripts\python.exe -m py_compile main.py app\ui\__init__.py app\ui\app.py
```

## Fase 2: Quitar Imports De Compatibilidad En Tests

Estado: completada el 2026-05-25.

Objetivo: que los tests ya no dependan de wrappers viejos.

Tareas:

- Reemplazar imports desde `app.controller` por:
  - `app.controllers.metadata_controller.MetadataController`
  - `app.models.FilterMode`
  - `app.models.SortMode`
  - `app.models.TrackInfo`
- Revisar cualquier test que importe wrappers antiguos.
- Ejecutar:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Criterio de salida:

- No queda ningun import de `app.controller`, `app.player_controls` ni `app.preview_panel` en archivos `.py`.

Validacion ejecutada:

```powershell
rg --glob "*.py" "from app\.controller\b|import app\.controller\b|from app\.player_controls\b|import app\.player_controls\b|from app\.preview_panel\b|import app\.preview_panel\b" tests app main.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

## Fase 3: Borrar Duplicados Seguros

Estado: completada el 2026-05-25.

Objetivo: eliminar archivos que ya no tienen responsabilidad propia.

Tareas:

- Borrar `app/ui.py`.
- Borrar `app/player_controls.py`, `app/preview_panel.py` y `app/controller.py` solo despues de Fase 2.
- Borrar `__pycache__/` y archivos `.pyc`.
- Ejecutar compilacion:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app\ui\app.py app\ui\app_lifecycle.py app\ui\interaction_workflow.py app\ui\library_workflow.py app\ui\metadata_workflow.py
```

Criterio de salida:

- La app importa y compila sin depender de los archivos borrados.

Validacion ejecutada:

```powershell
rg --glob "*.py" "from app\.controller\b|import app\.controller\b|from app\.player_controls\b|import app\.player_controls\b|from app\.preview_panel\b|import app\.preview_panel\b" tests app main.py
.\.venv\Scripts\python.exe -m py_compile main.py app\ui\app.py app\ui\app_lifecycle.py app\ui\interaction_workflow.py app\ui\library_workflow.py app\ui\metadata_workflow.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Notas:

- Se borraron `app/ui.py`, `app/controller.py`, `app/player_controls.py` y `app/preview_panel.py`.
- Se limpiaron caches generados. Windows/OneDrive reporto acceso denegado sobre algunos `.pyc` viejos; son artefactos ignorados por `.gitignore` y no afectan la app.

## Fase 4: Migrar Modulos Planos Que Siguen Vivos

Estado: completada el 2026-05-25.

Objetivo: terminar la separacion por capas sin romper comportamiento.

### Fase 4A: Acciones, Agregado Y Dialogos

Estado: completada el 2026-05-25.

Objetivo: cerrar los modulos planos relacionados con acciones de biblioteca, agregado de canciones y seleccion de archivos.

Alcance:

1. Completado el 2026-05-25: `app/player_utils.py` hacia `app/utils/audio_utils.py`; wrapper borrado.
2. Completado el 2026-05-25: `app/file_handler.py` hacia `app/ui_helpers/file_dialogs.py` y `app/services/file_service.py`. `FileHandler` vive en UI helpers; los helpers puros viven en servicios.
3. Completado el 2026-05-25: `app/song_info.py` hacia `app/services/song_info_service.py`; wrapper borrado.
4. Completado el 2026-05-25: `app/metadata_editor.py` hacia `app/services/metadata_editor_service.py`; wrapper borrado.
5. Completado el 2026-05-25: `app/song_actions.py` hacia `app/controllers/song_actions_controller.py`; wrapper borrado.
6. Completado el 2026-05-25: `app/add_music_button.py` hacia `app/controllers/add_music_controller.py`; wrapper borrado.

### Fase 4B: Playback, Tema Y Wrappers

Estado: completada el 2026-05-25.

Objetivo: cerrar subsistemas restantes y borrar wrappers temporales cuando no haya imports viejos.

Alcance:

1. Completado el 2026-05-25: `app/audio_player.py` y `app/audio_thread.py` hacia `app/services/playback/`.
2. Completado el 2026-05-25: `app/style_config.py` hacia `app/ui/theme.py`.
3. Completado el 2026-05-25: wrappers temporales borrados:
   - `app/player_utils.py`
   - `app/song_info.py`
   - `app/metadata_editor.py`
   - `app/song_actions.py`
   - `app/add_music_button.py`
   - `app/audio_player.py`
   - `app/audio_thread.py`
   - `app/style_config.py`

Criterio de salida:

- La raiz `app/` queda solo con `__init__.py`, `constants.py`, `i18n.py` y paquetes.
- Los imports de la app apuntan a paquetes nuevos.

Validacion final ejecutada para Fase 4:

```powershell
rg --glob "*.py" "from app\.(file_handler|player_utils|song_info|metadata_editor|song_actions|add_music_button|audio_player|audio_thread|style_config)\b|import app\.(file_handler|player_utils|song_info|metadata_editor|song_actions|add_music_button|audio_player|audio_thread|style_config)\b|from \.(file_handler|player_utils|song_info|metadata_editor|song_actions|add_music_button|audio_player|audio_thread|style_config)\b|from \.\.(file_handler|player_utils|song_info|metadata_editor|song_actions|add_music_button|audio_player|audio_thread|style_config)\b" app tests main.py
.\.venv\Scripts\python.exe -m py_compile main.py app\ui\app.py app\ui_helpers\file_dialogs.py app\controllers\add_music_controller.py app\controllers\song_actions_controller.py app\services\metadata_editor_service.py app\services\song_info_service.py app\services\playback\audio_player.py app\services\playback\audio_thread.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

## Fase 5: Limpieza Final

Estado: validacion automatica completada el 2026-05-25. Prueba manual visual pendiente.

Objetivo: dejar el proyecto mantenible y sin deuda de migracion.

Tareas:

- Actualizar README con la arquitectura final.
- Asegurar que `requirements.txt` siga siendo fuente de verdad.
- Agregar `.gitignore` para `__pycache__/`, `*.pyc`, logs y configuracion local si no esta completo.
- Correr suite completa.
- Hacer prueba manual de:
  - arranque
  - abrir carpetas
  - reproducir
  - editar metadata individual
  - editar en lote
  - respaldar/restaurar
  - mover/agregar/eliminar canciones

Validacion automatica ejecutada:

```powershell
rg "app/(ui|controller|player_controls|preview_panel|file_handler|player_utils|song_info|metadata_editor|song_actions|add_music_button|audio_player|audio_thread|style_config)\.py|app\\(ui|controller|player_controls|preview_panel|file_handler|player_utils|song_info|metadata_editor|song_actions|add_music_button|audio_player|audio_thread|style_config)\.py|app\.(controller|player_controls|preview_panel|file_handler|player_utils|song_info|metadata_editor|song_actions|add_music_button|audio_player|audio_thread|style_config)" README.md app tests main.py
.\.venv\Scripts\python.exe -c "from pathlib import Path; import py_compile; files=list(Path('app').rglob('*.py'))+list(Path('tests').rglob('*.py'))+[Path('main.py')]; [py_compile.compile(str(path).replace('\\\\','/'), doraise=True) for path in files]; print(f'compiled {len(files)} python files')"
.\.venv\Scripts\python.exe -c "import main; print(main.check_dependencies())"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Resultados:

- No quedan referencias a modulos planos borrados en `README.md`, `app/`, `tests/` ni `main.py`.
- Se compilaron 90 archivos Python.
- Dependencias requeridas presentes: `(True, [])`.
- Suite completa: 95 tests OK.

Nota: `python -m compileall` y `python -m py_compile` reportaron un acceso denegado del ejecutable base de Python en `AppData`; la validacion equivalente con `py_compile` desde `python -c` si paso correctamente.

## Regla Para Borrar Archivos

Antes de borrar un archivo:

1. Buscar referencias con `rg --glob "*.py" "nombre_modulo|from app.modulo|import app.modulo" .`.
2. Confirmar que no sea punto de entrada indirecto.
3. Correr tests relevantes.
4. Borrar.
5. Correr smoke tests y suite completa.

Como esta carpeta no esta inicializada como repositorio Git, conviene crear un commit o una copia antes de la Fase 3.
