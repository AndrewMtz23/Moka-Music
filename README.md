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
