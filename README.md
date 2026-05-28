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

## Ejecutable Windows

El proyecto incluye una configuracion de PyInstaller para generar una version ejecutable de escritorio.

```powershell
.\.venv\Scripts\pyinstaller.exe MokaMusic.spec --noconfirm
```

El resultado queda en:

```text
dist/MokaMusic/MokaMusic.exe
```

## Flujo principal

1. Abre una carpeta en `Biblioteca principal` y, si hace falta, otra en `Biblioteca entrante`.
2. Selecciona una o varias canciones para previsualizar portada y metadatos.
3. Usa `Editar metadata...` para modificar una cancion o aplicar campos seleccionados a varias.
4. En `Biblioteca entrante`, usa `Metadatos globales` para preparar musica nueva antes de moverla a la playlist principal.
5. Usa `Preparar playlist` para numerar pistas y renombrar archivos con el formato `001 - Artista - Titulo`.
6. Revisa calidad, duplicados, portadas faltantes y metadata desde los reportes de `Herramientas`.
7. Reproduce la seleccion con el reproductor inferior redisenado, con portada tipo vinilo, progreso, volumen y controles principales.
8. Antes de cambios masivos, la app genera respaldos que puedes restaurar desde `Herramientas`.

## Preparar playlist

El flujo de playlist esta pensado para evitar renumerar y renombrar a mano:

1. Carga tu playlist curada en `Biblioteca principal` o canciones nuevas en `Biblioteca entrante`.
2. Acomoda el orden visual de las canciones.
3. Usa `Insertar en posicion...` si quieres mover una o varias canciones a una posicion concreta.
4. Usa `Preparar playlist` para aplicar el orden completo.

`Preparar playlist` hace todo junto: crea respaldo, actualiza `track_number`, renombra archivos y refresca la biblioteca. El nombre final queda:

```text
001 - Artista - Titulo.mp3
```

Si falta metadata de artista o titulo, la app intenta inferirla desde nombres existentes como `Artista - Titulo.mp3`.

## Funciones principales

- Dos bibliotecas lado a lado: principal y entrante.
- Busqueda por nombre o metadata y filtros por campos faltantes, canciones sin portada y duplicadas.
- Filtros y orden por calidad de audio: 128 kbps o menos, 256 kbps aprox. y 320 kbps o mas.
- Lista organizada con seleccion multiple y orden manual.
- Reordenar canciones con drag and drop y numerar pistas segun el orden actual.
- Preparar playlist con preview: orden actual, `track_number` y renombrado fisico a `001 - Artista - Titulo`.
- Insertar canciones en una posicion concreta y recorrer automaticamente las demas.
- Ordenar por nombre, artista, album, numero de pista, duracion, calidad, fecha o ultima reproduccion.
- Vista previa compacta con portada, titulo, artista, artista album, album, ano, genero, pista y comentario.
- Edicion individual y edicion por lotes con previsualizacion antes/despues.
- Importar metadata desde JSON con preview y seleccion de campos.
- Exportar seleccionadas, vista actual JSON, playlist M3U8 y reporte completo de biblioteca.
- Acciones rapidas de limpieza:
  - Quitar `feat`, `ft` y `featuring`.
  - Quitar texto entre parentesis o corchetes.
  - Conservar solo titulo.
  - Crear titulo desde nombre de archivo.
  - Preparar playlist segun el orden visible.
  - Insertar canciones en una posicion.
  - Copiar artista a artista album.
  - Renombrar archivos desde metadata.
  - Buscar portada automaticamente desde la carpeta.
- Presets personalizados para guardar varias acciones de limpieza y aplicarlas juntas.
- Eliminar metadata con modal para elegir que campos conservar.
- Gestion de caratulas: arrastra una imagen JPG o PNG sobre la portada para guardarla como `PORTADA.jpg` y aplicarla a la carpeta de la cancion activa.
- Mover canciones entre carpetas, agregar canciones, renombrar y eliminar con envio seguro a papelera cuando esta disponible.
- Reproductor integrado redisenado con tarjeta premium, portada circular tipo vinilo, play/pausa centrado, anterior, siguiente, controles secundarios, progreso minimalista y modal de volumen.
- Temas claro/oscuro, presets visuales, temas personalizados, pantalla completa, tamanos de fuente y densidad.
- Menus y modales principales adaptados al tema activo, incluyendo `Acerca de`, guia rapida, atajos, diagnostico y reportes informativos.
- Idioma Espanol/Ingles, deteccion de idioma del sistema y reporte de traducciones faltantes.
- Logs en `mokamusic.log`.

## Herramientas De Audio Y Biblioteca

Desde `Herramientas` puedes revisar y corregir bibliotecas grandes:

- Reporte de calidad con metadata faltante, duplicados, bitrate bajo y posibles archivos danados.
- Estadisticas de biblioteca: duracion total, completitud, generos, anos, artistas y albumes principales.
- Comparacion entre biblioteca principal y entrante para detectar canciones nuevas o duplicadas.
- Historial de reproduccion con canciones escuchadas, conteos y ultima reproduccion.
- Analisis de calidad de audio con bitrate, duracion, formato, frecuencia y canales.
- Duplicados avanzados por metadata, nombre normalizado y duracion aproximada.
- Validacion de archivos para detectar rutas rotas, extensiones no soportadas y archivos posiblemente corruptos.
- Conversion de audio con presets MP3 320/256/128 kbps, WAV y FLAC, con opcion de conservar estructura de carpetas.

## Organizacion Y Playlists Inteligentes

MokaMusic tambien puede ordenar archivos fisicamente, siempre con preview antes de aplicar:

- Renombrar archivos por plantilla, por ejemplo `{track_number:03d} - {artist} - {title}`.
- Organizar archivos en carpetas con plantillas como `{artist}/{album}/{track_number:02d} - {title}`.
- Validar playlists para detectar canciones repetidas, numeracion faltante y rutas rotas.
- Generar playlists inteligentes con criterios:
  - `low_bitrate`
  - `unplayed`
  - `missing_cover`
  - `artist:Nombre`
  - `genre:Genero`
  - `duration:60`

## Personalizacion

El menu `Tema` permite ajustar MokaMusic al gusto del usuario:

- Temas base claro, oscuro y sistema.
- Presets visuales como clasico, azul nocturno, bosque, rose, alto contraste y OLED black.
- Guardar tema actual como tema personalizado.
- Administrar temas propios: renombrar, duplicar, eliminar y restaurar.
- Importar y exportar temas en JSON.
- Ajustar color de acento, tamano de fuente y densidad.
- Pantalla completa con `F11`.

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
