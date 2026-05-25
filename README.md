# MokaMusic

MokaMusic es una app de escritorio para revisar, reproducir, limpiar y editar metadatos de canciones locales. Esta pensada para preparar musica antes de moverla a playlists: puedes trabajar con dos carpetas, corregir datos en lote, reordenar canciones, renombrar archivos y conservar respaldos antes de cambios importantes.

## Estado actual

El proyecto usa un entorno virtual local creado por ti. La carpeta `venv/` anterior ya no es necesaria; usa `.venv/` con el Python instalado en tu maquina.

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si `python` no existe en tu PATH, instala Python 3.10+ y activa la opcion de agregarlo al PATH.

## Ejecutar

```powershell
python main.py
```

## Flujo principal

1. Abre una carpeta en `Biblioteca principal` y, si hace falta, otra en `Biblioteca entrante`.
2. Selecciona una o varias canciones para previsualizar portada y metadatos.
3. Usa `Editar metadata...` para modificar una cancion o aplicar campos seleccionados a varias.
4. Usa las acciones rapidas para limpiar nombres, numerar pistas o copiar artista a artista album.
5. Reproduce la seleccion con el panel inferior y revisa tiempo, progreso, volumen y modo de reproduccion.
6. Antes de cambios masivos, la app genera respaldos que puedes restaurar desde `Herramientas`.

## Funciones principales

- Dos bibliotecas lado a lado: principal y entrante.
- Busqueda por nombre o metadata y filtros por campos faltantes, canciones sin portada y duplicadas.
- Lista organizada con seleccion multiple y orden manual.
- Reordenar canciones con drag and drop y numerar pistas segun el orden actual.
- Ordenar por nombre, artista, album, numero de pista, duracion o fecha.
- Vista previa compacta con portada, titulo, artista, artista album, album, ano, genero, pista y comentario.
- Edicion individual y edicion por lotes con previsualizacion antes/despues.
- Acciones rapidas de limpieza:
  - Quitar `feat`, `ft` y `featuring`.
  - Quitar texto entre parentesis o corchetes.
  - Conservar solo titulo.
  - Crear titulo desde nombre de archivo.
  - Numerar pistas segun el orden visible.
  - Copiar artista a artista album.
  - Renombrar archivos desde metadata.
  - Buscar portada automaticamente desde la carpeta.
- Presets personalizados para guardar varias acciones de limpieza y aplicarlas juntas.
- Eliminar metadata con modal para elegir que campos conservar.
- Gestion de caratulas: arrastra una imagen JPG o PNG sobre la portada para incrustarla.
- Mover canciones entre carpetas, agregar canciones, renombrar y eliminar con envio seguro a papelera cuando esta disponible.
- Reproductor integrado con play/pausa, detener, anterior, siguiente, repetir, aleatorio, salto de 10s, volumen, barra de progreso, tiempo y visualizador.
- Temas claro/oscuro e idioma Espanol/Ingles.
- Logs en `mokamusic.log`.

## Respaldos

La app crea respaldos JSON antes de cambios de metadata en lote, limpieza, renombrado o portada. Los respaldos incluyen metadata y caratula cuando esta disponible.

Desde el menu `Herramientas` puedes usar:

- `Historial de respaldos`: ver fecha, accion, carpeta y cantidad de canciones afectadas.
- `Deshacer ultimo cambio de metadata`: restaurar el respaldo mas reciente de la sesion.

## Pruebas

Compilar modulos principales:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app\ui\app.py app\ui\metadata_workflow.py app\ui\theme.py app\services\metadata_editor_service.py app\services\song_info_service.py app\services\playback\audio_player.py
```

Ejecutar pruebas:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

## Dependencias

`requirements.txt` es la fuente de verdad:

- `eyed3` y `mutagen` para leer/escribir metadata.
- `Pillow` para portadas.
- `pygame` para reproduccion.
- `tkinterdnd2` para arrastrar y soltar.
- `Send2Trash` para borrado seguro cuando esta disponible.

## Arquitectura

El proyecto empezo con modulos planos dentro de `app/`. La app ahora usa una estructura por capas para que las siguientes mejoras sean mas faciles de mantener:

```text
app/
  controllers/      Coordinacion entre UI y servicios
  models/           Datos, enums y resultados compartidos
  services/         Logica de metadata, backups, portadas, archivos y playlists
  ui/               App principal y workflows UI extraidos
  views/            Paneles y ventanas Tkinter
  views/modals/     Modales de edicion, preview, backups y presets
  ui_helpers/       Widgets reutilizables y tooltips extraidos de vistas grandes
  utils/            Utilidades puras de texto, audio y nombres de archivo
```
<<<<<<< HEAD
=======

La migracion se hizo por fases para mantener la app funcionando mientras se reducian archivos grandes. La app principal vive en `app/ui/app.py`, y `app/ui/__init__.py` exporta `from app.ui import iniciar_app`. La limpieza de texto ya vive en `app/utils/text_cleanup.py`.
Los workflows de metadata, portadas, respaldos, limpieza y renombrado ya viven en `app/ui/metadata_workflow.py`; la clase principal `MokaMusicApp` los consume como mixin.
Los workflows de bibliotecas, renderizado, reorder y vista previa ya viven en `app/ui/library_workflow.py`.
Los workflows de reproduccion, agregar/mover canciones, aplicar metadata global y drag-and-drop ya viven en `app/ui/interaction_workflow.py`.
El ciclo de vida de ventana, menu, configuracion, tema, idioma y getters de controllers ya vive en `app/ui/app_lifecycle.py`.
`MetadataController` ya vive en `app/controllers/metadata_controller.py`.
Los modales de previsualizacion de cambios, creacion de presets, historial de respaldos, edicion por lotes, eliminacion de metadata y edicion de metadata ya viven en `app/views/modals/`.
El panel reutilizable de bibliotecas ya vive en `app/views/library_panel.py`; `app/ui/app.py` conserva la coordinacion de eventos.
El panel de metadata global y acciones rapidas ya vive en `app/views/metadata_panel.py`.
Los paneles de vista previa y reproductor ya viven en `app/views/preview_panel.py` y `app/views/player_panel.py`.
La lectura/escritura base de respaldos ya vive en `app/services/backup_service.py`.

El registro de migracion y limpieza de archivos viejos esta en `docs/architecture_migration_plan.md`.
El plan para automatizar insercion, renumerado y renombrado de playlists esta en `docs/playlist_workflow_plan.md`.
El procesamiento y busqueda automatica de portadas ya vive en `app/services/cover_service.py`.
Los filtros, ordenamientos, deteccion de duplicadas y reporte de calidad ya viven en `app/services/library_service.py`.
Las operaciones de archivo para agregar, mover, borrar, renombrar y sanitizar nombres ya viven en `app/services/file_service.py`.
La logica de acciones rapidas de limpieza ya vive en `app/controllers/cleanup_controller.py`; el estado y menu de presets vive en `app/controllers/cleanup_preset_controller.py`.
La renderizacion, conteo, colores, busqueda visible y ordenamiento visual de bibliotecas ya vive en `app/controllers/library_ui_controller.py`.
El flujo de portadas manuales y automaticas ya vive en `app/controllers/cover_controller.py`; `app/ui/metadata_workflow.py` coordina confirmaciones, mensajes y refrescos.
El historial, restauracion, previews de cambios y estado del ultimo respaldo ya viven en `app/controllers/backup_controller.py`.
La planeacion/ejecucion de renombrado desde metadata ya vive en `app/controllers/rename_controller.py`, y su previsualizacion vive en `app/views/modals/rename_metadata_modal.py`.
La aplicacion de metadata individual, por seleccion, por lote y a toda la biblioteca ya vive en `app/controllers/metadata_apply_controller.py`.
La clasificacion y procesamiento de archivos soltados por drag and drop ya vive en `app/controllers/drop_controller.py`.
La seleccion de pistas para reproducir, avanzar, retroceder y aleatorio ya vive en `app/controllers/playback_selection_controller.py`.
Los campos y accesos a modales de edicion, limpieza y batch de metadata ya viven en `app/controllers/metadata_dialog_controller.py`.
El refresco de textos traducibles, headings, combos de orden/filtro y paneles al cambiar idioma ya vive en `app/controllers/ui_text_controller.py`.
El estado y operaciones del reproductor ya viven en `app/controllers/playback_controller.py`; la vista y controles viven en `app/views/player_panel.py`.
El mapeo entre bibliotecas, paneles, trees y seleccion multiple ya vive en `app/controllers/selection_controller.py`.
La carga y guardado de `mokamusic_config.json` ya vive en `app/controllers/config_controller.py`.
La construccion del menu superior ya vive en `app/controllers/menu_controller.py`.
Los helpers de formato de UI, etiquetas, errores y nombres sugeridos ya viven en `app/utils/ui_formatting.py`.
`ActionResult`, `SortMode`, `FilterMode` y `TrackInfo` ya viven en `app/models/`.
La lectura de metadata vive en `app/services/song_info_service.py`; la escritura vive en `app/services/metadata_editor_service.py`.
El reproductor base y monitor viven en `app/services/playback/`.
La seleccion de archivos y dialogos vive en `app/ui_helpers/file_dialogs.py`.

## Pendientes recomendados

- Crear instalador o script `run.ps1` para abrir la app con un doble clic.
- Agregar pruebas automatizadas para los flujos visuales del reproductor.
- Explorar un visualizador real basado en audio, no solo animacion reactiva.
- Empaquetar con PyInstaller cuando el flujo principal quede estable.
>>>>>>> f6f447e (Update project files)
