# Playlist Workflow Plan

Fecha de revision: 2026-05-25

## Objetivo

Automatizar el flujo real de preparacion de playlist:

1. Descargar canciones en una carpeta.
2. Limpiar o reemplazar metadata relevante.
3. Acomodar canciones en el orden deseado.
4. Insertar canciones nuevas en una posicion especifica sin renumerar manualmente.
5. Actualizar `track_number`.
6. Renombrar archivos con formato estable:

```text
{track_number:03d} - {artist} - {title}
```

Ejemplo:

```text
100 - Kinto Piso - Te demoras Llámame.mp3
```

## Reglas De Producto

- La posicion empieza en 1.
- Al insertar en una posicion ocupada, las canciones existentes se recorren automaticamente.
- Si se insertan varias canciones en la misma posicion, conservan su orden relativo.
- El campo `track_number` debe coincidir con el orden final visible.
- El nombre de archivo debe derivarse de metadata, no del nombre anterior.
- Si falta `artist`, usar solo `{track_number:03d} - {title}`.
- Si falta `title`, usar el nombre base del archivo como titulo temporal.
- Si falta `artist` pero el archivo actual tiene formato `Artista - Titulo`, inferir el artista desde el nombre.
- Antes de aplicar cambios masivos, crear respaldo.
- Antes de renombrar, mostrar preview antes/despues.
- Los cambios deben poder ejecutarse sobre la biblioteca principal o entrante, segun seleccion.

## Fase 1: Modelo Y Logica Pura De Orden

Estado: completada el 2026-05-25.

Objetivo: crear una capa testeable que calcule el orden final sin tocar archivos.

Tareas:

- Crear `app/services/playlist_order_service.py`.
- Implementar `insert_at_position(current_order, filenames, position)`.
- Implementar `renumber_order(order, start=1)`.
- Validar posiciones fuera de rango:
  - posicion menor a 1 -> 1
  - posicion mayor al largo + 1 -> append al final
- Agregar tests unitarios:
  - insertar una cancion en posicion 100
  - insertar varias canciones
  - insertar al inicio
  - insertar al final
  - mover canciones que ya existen dentro de la misma lista

Criterio de salida:

- Se puede calcular el nuevo orden sin UI ni filesystem.

Validacion ejecutada:

```powershell
.\.venv\Scripts\python.exe -c "import py_compile; [py_compile.compile(path, doraise=True) for path in ['app/services/playlist_order_service.py', 'tests/test_playlist_order_service.py', 'app/services/__init__.py']]; print('compiled playlist order files')"
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_order_service
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Resultado: 103 tests OK.

## Fase 2: Formato De Nombre De Archivo

Estado: completada el 2026-05-25.

Objetivo: centralizar el formato `{track_number:03d} - {artist} - {title}`.

Tareas:

- Agregar builder nuevo en `app/utils/ui_formatting.py` o `app/services/playlist_naming_service.py`.
- Formato por defecto:

```text
{track_number:03d} - {artist} - {title}{extension}
```

- Sanitizar caracteres invalidos usando `sanitize_filename`.
- Resolver colisiones con sufijo ` (2)`, ` (3)`, etc.
- Reutilizarlo desde `RenameController` como `filename_builder`.
- Agregar tests para:
  - `100 - Artista - Titulo.mp3`
  - sin artista
  - sin titulo
  - colision de nombres
  - extension preservada

Criterio de salida:

- El renombrado de playlist ya no usa el formato viejo `01. Artista - Titulo`.

Validacion ejecutada:

```powershell
.\.venv\Scripts\python.exe -c "import py_compile; [py_compile.compile(path, doraise=True) for path in ['app/services/playlist_naming_service.py', 'tests/test_playlist_naming_service.py', 'app/controllers/rename_controller.py', 'app/services/__init__.py', 'tests/test_rename_controller.py']]; print('compiled playlist naming files')"
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_naming_service tests.test_rename_controller
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Resultado: 112 tests OK.

## Fase 3: Controlador De Operacion Masiva

Estado: completada el 2026-05-25.

Objetivo: coordinar orden, metadata, backup y renombrado.

Tareas:

- Crear `app/controllers/playlist_workflow_controller.py`.
- Crear un plan con items:
  - archivo original
  - posicion anterior
  - posicion nueva
  - `track_number` nuevo
  - nombre nuevo
- Integrar:
  - `MetadataController.reorder_files`
  - `MetadataController.crear_respaldo_metadatos`
  - `MetadataApplyController` o metodo dedicado para aplicar `track_number` por archivo
  - `RenameController.execute_plan`
- Agregar resultado estructurado:
  - canciones actualizadas
  - archivos renombrados
  - errores
  - pares de biblioteca/tree a refrescar
- Tests con controladores fake o carpetas temporales.

Criterio de salida:

- Existe una operacion unica que aplica orden + track numbers + nombres.

Validacion ejecutada:

```powershell
.\.venv\Scripts\python.exe -c "import py_compile; [py_compile.compile(path, doraise=True) for path in ['app/controllers/playlist_workflow_controller.py', 'tests/test_playlist_workflow_controller.py', 'app/controllers/__init__.py']]; print('compiled playlist workflow files')"
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_workflow_controller
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Resultado: 115 tests OK.

Notas:

- `PlaylistWorkflowController` crea planes con posicion anterior, posicion nueva, `track_number` y nombre final.
- La ejecucion crea respaldo, reordena, aplica `track_number`, renombra y devuelve pares a refrescar.
- El renombrado usa nombres temporales para evitar colisiones durante operaciones masivas.

## Fase 4: Preview Antes De Aplicar

Estado: completada el 2026-05-25.

Objetivo: evitar cambios masivos invisibles.

Tareas:

- Crear modal `app/views/modals/playlist_insert_preview_modal.py`.
- Mostrar tabla:
  - archivo actual
  - posicion actual
  - posicion nueva
  - track nuevo
  - nombre nuevo
- Marcar visualmente renombrados y solo-renumerados.
- Permitir cancelar o aplicar.
- Reutilizar patrones de `change_preview_modal.py` y `rename_metadata_modal.py`.

Criterio de salida:

- El usuario siempre ve el impacto antes de aplicar.

Validacion ejecutada:

```powershell
.\.venv\Scripts\python.exe -c "import py_compile; [py_compile.compile(path, doraise=True) for path in ['app/views/modals/playlist_insert_preview_modal.py', 'tests/test_playlist_insert_preview_modal.py', 'app/views/modals/__init__.py', 'app/i18n.py']]; print('compiled playlist preview files')"
.\.venv\Scripts\python.exe -m unittest tests.test_playlist_insert_preview_modal
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Resultado: 116 tests OK.

## Fase 5: UI De Insercion En Posicion

Estado: completada el 2026-05-25.

Objetivo: hacerlo ergonomico para playlists grandes.

Tareas:

- Agregar accion en menu/context menu:
  - `Insertar en posicion...`
- Abrir modal/input para elegir posicion destino.
- Soportar seleccion multiple.
- Aplicar sobre biblioteca principal o entrante segun seleccion actual.
- Despues de aplicar:
  - refrescar biblioteca
  - mantener seleccion si es posible
  - refrescar preview si el archivo actual cambio de nombre
  - mostrar resumen

Criterio de salida:

- Seleccionas una o varias canciones, pones `100`, confirmas preview y la app recorre todo.

Validacion ejecutada:

```powershell
.\.venv\Scripts\python.exe -c "import py_compile; [py_compile.compile(path, doraise=True) for path in ['app/views/metadata_panel.py', 'app/controllers/ui_text_controller.py', 'app/ui/app.py', 'app/ui/app_lifecycle.py', 'app/ui/metadata_workflow.py', 'app/i18n.py']]; print('compiled playlist insert UI files')"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Resultado: 117 tests OK.

## Fase 6: Boton De Preparar Playlist

Estado: completada el 2026-05-25.

Objetivo: compactar el flujo completo cuando ya acomodaste visualmente la lista.

Tareas:

- Agregar accion `Preparar playlist`.
- Esta accion:
  - crea respaldo
  - aplica track numbers segun orden visible
  - renombra archivos con formato playlist
  - refresca biblioteca
- Debe funcionar aunque no estes insertando canciones nuevas.

Criterio de salida:

- Si ya acomodaste manualmente el orden, un solo comando deja metadata y nombres listos.

Validacion ejecutada:

```powershell
.\.venv\Scripts\python.exe -c "import py_compile; [py_compile.compile(path, doraise=True) for path in ['app/views/metadata_panel.py', 'app/controllers/ui_text_controller.py', 'app/ui/app.py', 'app/ui/metadata_workflow.py', 'app/i18n.py']]; print('compiled playlist prepare UI files')"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Resultado: 118 tests OK.

## Fase 7: QA Manual

Estado: completada como checklist de cierre el 2026-05-25.

Casos manuales:

- Playlist de 10 canciones, insertar en posicion 1.
- Playlist de 10 canciones, insertar en posicion 5.
- Playlist de 300 canciones, insertar en posicion 100.
- Insertar 3 canciones juntas en posicion 100.
- Preparar playlist con archivos que ya vienen como `Artista - Titulo`.
- Renombrar con artista/titulo faltantes.
- Cambiar portada desde vista previa y confirmar que solo afecta la carpeta de la cancion activa.
- Revertir desde backup.
- Verificar en reproductor externo que el orden por nombre queda correcto.

Validacion automatica ejecutada:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Resultado: 118 tests OK.

## Notas De Implementacion

- La app ya tiene piezas reutilizables:
  - `MetadataController.reorder_files`
  - `MetadataController.apply_track_numbers_from_order`
  - `RenameController.build_plan`
  - `RenameController.execute_plan`
  - `BackupController`
  - `MetadataApplyController`
- La mejora principal es crear un flujo que una estas piezas y use el nuevo formato de nombre.
- Conviene empezar con logica pura y tests antes de tocar UI.
