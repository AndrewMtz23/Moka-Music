# MokaMusic - Descripcion Del Proyecto

Este documento describe el estado actual de MokaMusic: que hace, como se usa, como esta organizado internamente y cuales son sus flujos principales.

## Resumen

MokaMusic es una aplicacion de escritorio hecha en Python y Tkinter para trabajar con musica local. Su objetivo principal es ayudar a revisar, reproducir, limpiar, editar y preparar archivos de audio antes de moverlos o dejarlos listos en una playlist.

La app trabaja con dos bibliotecas visibles al mismo tiempo:

- Biblioteca principal: normalmente la carpeta final o playlist ya curada.
- Biblioteca entrante: normalmente la carpeta donde llegan canciones nuevas antes de integrarlas.

Desde esas dos bibliotecas se pueden seleccionar canciones, revisar metadatos, editar datos en lote, aplicar portadas, renombrar archivos, ordenar canciones y reproducir audio.

## Lo Que Hace Actualmente

### Gestion De Bibliotecas

La aplicacion permite cargar carpetas locales con archivos de audio soportados. Al cargar una carpeta, lee los archivos, obtiene metadata, calcula duracion y arma una lista navegable.

Formatos de audio soportados:

- `.mp3`
- `.wav`
- `.ogg`
- `.flac`

Cada biblioteca permite:

- Seleccionar carpeta.
- Cerrar o limpiar la carpeta cargada.
- Ver archivos en tabla.
- Buscar por nombre o metadata.
- Filtrar canciones por problemas comunes.
- Ordenar por distintos criterios.
- Seleccionar una o varias canciones.
- Reordenar manualmente cuando la vista completa esta activa.

Filtros disponibles:

- Todas las canciones.
- Canciones sin artista.
- Canciones sin album.
- Canciones sin ano.
- Canciones sin numero de pista.
- Canciones sin portada.
- Duplicados por artista/titulo.

Ordenamientos disponibles:

- Manual.
- Nombre de archivo.
- Artista.
- Album.
- Numero de pista.
- Duracion.
- Fecha de agregado/modificacion del archivo.

### Vista Previa

Al seleccionar una cancion, el panel de vista previa muestra informacion de la pista activa:

- Portada.
- Nombre de archivo.
- Titulo.
- Artista.
- Artista del album.
- Album.
- Ano.
- Genero.
- Numero de pista.
- Comentario.

Desde esa vista se puede editar metadata de la cancion activa, cambiar portada, limpiar metadata o guardar cambios.

### Edicion De Metadatos

La app puede leer y escribir metadata usando `eyed3` para MP3 y `mutagen` para otros formatos compatibles.

Campos manejados:

- `artist`
- `album_artist`
- `album`
- `title`
- `genre`
- `year`
- `track_number`
- `comment`

La edicion puede aplicarse a:

- Una cancion activa desde la vista previa.
- Varias canciones seleccionadas.
- Todas las canciones de una biblioteca.
- Una carpeta completa desde los modales de edicion.

Antes de aplicar cambios masivos, la app muestra una previsualizacion con antes/despues cuando corresponde.

### Limpieza Rapida

MokaMusic incluye acciones rapidas para corregir metadata comunmente sucia:

- Quitar `feat`, `ft` y `featuring`.
- Quitar texto entre parentesis o corchetes.
- Conservar solo el titulo base.
- Crear titulo desde el nombre del archivo.
- Copiar artista hacia artista del album.

Tambien permite crear presets personalizados que agrupan varias acciones. Esos presets se guardan en la configuracion local.

### Preparacion De Playlists

Uno de los flujos mas importantes es preparar una playlist completa. La app puede tomar el orden visual actual de una biblioteca y aplicar dos cambios coordinados:

- Actualizar `track_number` segun el orden.
- Renombrar fisicamente los archivos con el formato:

```text
001 - Artista - Titulo.mp3
```

Tambien existe el flujo de insertar canciones en una posicion concreta. La app recalcula el orden final, actualiza numeros de pista y renombra los archivos necesarios.

Para evitar colisiones de nombres durante renombrados masivos, el flujo de playlist usa nombres temporales internos antes de asignar los nombres definitivos.

### Renombrado De Archivos

La app puede renombrar canciones a partir de su metadata. El renombrado sanitiza caracteres invalidos de Windows y evita duplicados dentro de la biblioteca.

Cuando falta metadata, algunos flujos intentan inferir artista o titulo desde nombres existentes.

### Portadas

MokaMusic puede aplicar portadas manualmente o buscarlas automaticamente desde la carpeta.

Formatos de imagen soportados:

- `.jpg`
- `.jpeg`
- `.png`
- `.bmp`
- `.gif`

Funciones actuales de portada:

- Seleccionar una imagen desde dialogo.
- Arrastrar una imagen sobre la portada activa.
- Aplicar una portada a canciones objetivo.
- Buscar una portada existente dentro de la carpeta.
- Procesar la imagen con Pillow y guardarla como JPEG embebido.
- Restaurar portada desde respaldo cuando existe.

### Reproductor Integrado

La app incluye un reproductor con `pygame`.

Funciones disponibles:

- Reproducir y pausar.
- Detener.
- Cancion anterior y siguiente.
- Repetir.
- Aleatorio.
- Saltar posicion.
- Control de volumen.
- Barra de progreso.
- Tiempo de reproduccion.
- Deteccion de fin de pista.

### Movimiento, Agregado Y Borrado De Canciones

Desde los controladores de acciones se pueden:

- Agregar canciones a una biblioteca copiandolas a la carpeta destino.
- Mover canciones entre biblioteca entrante y biblioteca principal.
- Renombrar archivos.
- Eliminar canciones.

El borrado intenta usar `Send2Trash` para mandar archivos a la papelera. Si no esta disponible o falla, usa borrado directo como respaldo.

### Respaldos

Antes de cambios importantes, MokaMusic genera respaldos JSON en la carpeta `backups/`.

Los respaldos guardan:

- Fecha de creacion.
- Carpeta afectada.
- Metadata aplicada.
- Cantidad de canciones.
- Metadata anterior por cancion.
- Ruta y nombre del archivo.
- Portada embebida en base64 cuando existe.

La app permite:

- Ver historial de respaldos.
- Restaurar respaldos.
- Deshacer el ultimo cambio de metadata de la sesion.

### Configuracion

La configuracion local se guarda en `mokamusic_config.json`.

Actualmente conserva:

- Tema.
- Idioma.
- Volumen.
- Estado de repetir/aleatorio.
- Carpeta principal.
- Carpeta entrante.
- Presets de limpieza.

### Temas E Idiomas

La interfaz soporta:

- Tema claro.
- Tema oscuro.
- Espanol.
- Ingles.

Los textos viven en `app/i18n.py` y se acceden con claves de traduccion.

### Icono Y Assets

Los assets principales estan en `assets/`.

Archivos actuales relevantes:

- `assets/logo.png`: logo principal.
- `assets/Moka.ico`: icono usado para la ventana y para empaquetar el ejecutable.

La ventana carga el icono desde la ruta absoluta del proyecto para que funcione aunque la app se ejecute desde otra carpeta.

## Como Se Ejecuta

Instalacion recomendada:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Ejecucion:

```powershell
python main.py
```

O usando el Python del entorno:

```powershell
.\.venv\Scripts\python.exe main.py
```

## Como Crear El Ejecutable

La forma recomendada es usar PyInstaller en modo carpeta:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\pyinstaller.exe `
  --noconfirm `
  --clean `
  --windowed `
  --name MokaMusic `
  --icon assets\Moka.ico `
  --add-data "assets;assets" `
  --collect-all tkinterdnd2 `
  main.py
```

El ejecutable queda en:

```text
dist/MokaMusic/MokaMusic.exe
```

## Organizacion Del Proyecto

Estructura principal:

```text
MokaMusic/
  app/
    controllers/
    models/
    services/
    services/playback/
    ui/
    ui_helpers/
    utils/
    views/
    views/modals/
    constants.py
    i18n.py
  assets/
  backups/
  docs/
  tests/
  main.py
  requirements.txt
  mokamusic_config.json
  mokamusic.log
```

## Punto De Entrada

### `main.py`

Es el arranque de la aplicacion.

Responsabilidades:

- Configurar logging.
- Asegurar que el directorio actual este en `sys.path`.
- Verificar dependencias principales.
- Importar `app.ui.iniciar_app`.
- Iniciar la interfaz.
- Capturar errores de importacion o errores inesperados.

## Capa UI

### `app/ui/app.py`

Define `MokaMusicApp`, la clase principal de la aplicacion Tkinter.

Responsabilidades:

- Crear estado global de la app.
- Crear controladores.
- Crear servicios compartidos.
- Montar los paneles principales.
- Conectar callbacks entre UI y logica.
- Registrar eventos de teclado y drag-and-drop.

La UI se divide en:

- Panel superior con dos bibliotecas.
- Vista global de metadata.
- Panel inferior con vista previa y reproductor.

### `app/ui/app_lifecycle.py`

Contiene comportamiento de ciclo de vida:

- Tamano minimo y tamano inicial de ventana.
- Carga del icono.
- Menu principal.
- Carga y guardado de configuracion.
- Cambio de tema.
- Cambio de idioma.
- Refresco de textos traducidos.
- Cierre limpio de la app.

### `app/ui/metadata_workflow.py`

Coordina los flujos de metadata, portadas, limpieza, respaldos, renombrado y playlists.

Aqui se conectan muchos botones de la interfaz con los controladores:

- Guardar metadata desde preview.
- Cambiar portada.
- Aplicar portada a carpetas o selecciones.
- Editar metadata individual o por lote.
- Limpiar metadata.
- Crear y aplicar respaldos.
- Aplicar acciones rapidas.
- Crear, aplicar y borrar presets.
- Preparar playlist.
- Insertar seleccion en posicion.
- Renombrar desde metadata.

### `app/ui/library_workflow.py`

Coordina flujos de biblioteca:

- Cargar carpetas.
- Refrescar tablas.
- Aplicar busqueda y filtros.
- Cambiar ordenamiento.
- Seleccionar canciones.
- Mantener vista previa sincronizada.

### `app/ui/interaction_workflow.py`

Coordina interacciones directas del usuario:

- Drag-and-drop de archivos.
- Acciones contextuales.
- Reordenamiento manual.
- Acciones sobre canciones seleccionadas.

### `app/ui/theme.py`

Define estilos visuales para Tkinter/ttk:

- Colores por tema.
- Estilos de botones.
- Estilos de tablas.
- Estilos de paneles.
- Adaptacion a modo claro/oscuro.

## Vistas

La carpeta `app/views/` contiene componentes visuales reutilizables.

### `library_panel.py`

Construye el panel de biblioteca:

- Contenedor con titulo.
- Botones de abrir/cerrar carpeta.
- Campo de busqueda.
- Filtro.
- Selector de orden.
- Tabla de canciones.
- Botones de acciones principales.

### `metadata_panel.py`

Construye el panel de metadata global:

- Entradas para artista, artista album, album, genero, ano y comentario.
- Botones para aplicar a seleccion o a todo.
- Acciones rapidas.
- Selector de presets.

### `preview_panel.py`

Construye la vista previa de cancion activa:

- Portada.
- Metadata editable.
- Botones de editar, limpiar, guardar y seleccionar portada.

### `player_panel.py`

Construye el reproductor:

- Play/pausa.
- Stop.
- Anterior/siguiente.
- Repetir/aleatorio.
- Volumen.
- Progreso.
- Tiempo.

### `views/modals/`

Contiene ventanas emergentes para flujos especificos:

- Edicion individual.
- Edicion por lote.
- Limpiar metadata.
- Preview de cambios.
- Preview de renombrado.
- Preview de insertar/preparar playlist.
- Crear presets.
- Historial de respaldos.
- Guia de carpeta entrante.

## Controladores

La carpeta `app/controllers/` contiene coordinadores entre UI y servicios.

### `metadata_controller.py`

Administra una biblioteca cargada.

Responsabilidades:

- Cargar archivos de audio de una carpeta.
- Cachear metadata y duracion.
- Aplicar metadata a archivos.
- Crear y restaurar respaldos.
- Validar ano y numero de pista.
- Filtrar y ordenar archivos.
- Reordenar archivos.
- Actualizar numeros de pista segun orden.
- Detectar portadas faltantes.
- Generar reporte de calidad.

Cada biblioteca visible tiene su propio `MetadataController`.

### `metadata_apply_controller.py`

Centraliza la aplicacion de metadata a una o varias canciones y reporta que bibliotecas necesitan refrescarse.

### `metadata_dialog_controller.py`

Administra los modales de edicion de metadata, edicion por lote y limpieza.

### `cleanup_controller.py`

Construye y ejecuta planes de limpieza rapida.

Responsabilidades:

- Normalizar presets.
- Crear plan de cambios.
- Generar preview antes/despues.
- Ejecutar cambios sobre controladores.
- Invalidar cache de canciones modificadas.

### `playlist_workflow_controller.py`

Construye y ejecuta planes de playlist.

Responsabilidades:

- Insertar canciones en una posicion.
- Recalcular orden final.
- Generar numeros de pista.
- Generar nombres finales de playlist.
- Crear respaldo.
- Aplicar track numbers.
- Renombrar archivos evitando colisiones.
- Mantener la cancion activa sincronizada despues del renombrado.

### `rename_controller.py`

Construye planes de renombrado a partir de metadata y ejecuta cambios de nombre fisicos.

### `cover_controller.py`

Determina objetivos de portada y aplica portadas manuales o automaticas.

### `backup_controller.py`

Envuelve operaciones de respaldo:

- Crear respaldos para grupos de canciones.
- Listar historial.
- Restaurar respaldos.
- Recordar el ultimo respaldo de la sesion.

### Otros Controladores

- `add_music_controller.py`: agregar canciones.
- `song_actions_controller.py`: acciones sobre canciones.
- `selection_controller.py`: seleccion cruzada entre bibliotecas.
- `library_ui_controller.py`: refresco de tablas y datos visibles.
- `drop_controller.py`: interpretar payloads de drag-and-drop.
- `playback_controller.py`: coordinar reproductor y UI.
- `playback_selection_controller.py`: elegir canciones para reproducir.
- `menu_controller.py`: construir menu principal.
- `config_controller.py`: cargar y guardar configuracion.
- `cleanup_preset_controller.py`: manejar presets en UI.
- `ui_text_controller.py`: refrescar textos traducidos.

## Servicios

La carpeta `app/services/` contiene logica reutilizable sin depender directamente de widgets.

### `metadata_editor_service.py`

Lee y escribe metadata real en los archivos.

Usa:

- `eyed3` para MP3.
- `mutagen` para otros formatos.
- `Pillow` indirectamente para procesar portadas.

Puede:

- Leer metadata.
- Escribir metadata en lote.
- Aplicar portada desde archivo.
- Aplicar/restaurar portada desde bytes.
- Limpiar portada.
- Leer portada embebida.

### `song_info_service.py`

Funciona como inspector/cache de canciones. Evita releer metadata y portada de disco innecesariamente.

### `file_service.py`

Funciones de sistema de archivos:

- Validar formatos.
- Listar audio.
- Acortar nombres largos.
- Agregar canciones a bibliotecas.
- Mover canciones entre bibliotecas.
- Eliminar canciones.
- Renombrar canciones.
- Sanitizar nombres.

### `library_service.py`

Funciones puras para biblioteca:

- Ordenamiento natural por nombre.
- Ordenamiento por metadata.
- Ordenamiento por duracion o fecha.
- Busqueda por nombre/metadata.
- Filtros de calidad.
- Deteccion de duplicados.
- Reporte de calidad.

### `backup_service.py`

Funciones puras de respaldo:

- Crear payloads de respaldo.
- Codificar portadas en base64.
- Guardar JSON.
- Leer JSON.
- Iterar respaldos existentes.

### `cover_service.py`

Procesa imagenes de portada para dejarlas listas para metadata embebida.

### `playlist_order_service.py`

Contiene operaciones puras de orden:

- Insertar seleccion en una posicion.
- Renumerar canciones.

### `playlist_naming_service.py`

Construye nombres de archivo para playlists usando numero de pista, artista y titulo.

### `services/playback/`

Contiene el reproductor.

- `audio_player.py`: wrapper de `pygame.mixer`.
- `audio_thread.py`: soporte para ejecucion/polling relacionado con audio.

## Modelos

La carpeta `app/models/` contiene estructuras compartidas.

### `TrackInfo`

Representa informacion cacheada de una cancion:

- Nombre de archivo.
- Ruta completa.
- Metadata.
- Duracion.
- Portada.

### `ActionResult`

Resultado estandar para operaciones:

- `success`
- `message`
- `data`
- `errors`

### Enums

`SortMode` define modos de ordenamiento.

`FilterMode` define filtros de biblioteca.

## Utilidades

La carpeta `app/utils/` contiene funciones auxiliares.

### `audio_utils.py`

Obtiene duracion, metadata basica y utilidades relacionadas con audio e imagenes.

### `text_cleanup.py`

Implementa transformaciones de limpieza:

- Quitar colaboraciones.
- Quitar parentesis/corchetes.
- Extraer titulo.
- Crear titulo desde archivo.
- Copiar artista.

### `ui_formatting.py`

Formatea datos para la UI, incluyendo etiquetas de metadata y representaciones visibles.

## Internacionalizacion

`app/i18n.py` contiene un diccionario de traducciones para Espanol e Ingles.

La app usa claves como:

```text
app.window_title
button.apply_selected
quick_actions.remove_feat
message.no_song_selected
```

Cada componente recibe una funcion `t(...)` para traducir textos. Cuando el idioma cambia, `UiTextController` refresca widgets registrados.

## Datos En Disco

Archivos/carpetas generados durante uso:

- `mokamusic_config.json`: configuracion local.
- `mokamusic.log`: log de ejecucion.
- `backups/*.json`: respaldos de metadata y portadas.
- `dist/` y `build/`: salidas de PyInstaller si se crea ejecutable.

## Dependencias

Las dependencias estan en `requirements.txt`.

Uso principal de cada una:

- `eyed3`: lectura/escritura ID3 en MP3.
- `mutagen`: metadata en otros formatos.
- `Pillow`: procesamiento de portadas.
- `pygame`: reproduccion de audio.
- `Send2Trash`: envio seguro a papelera.
- `tkinterdnd2`: drag-and-drop en Tkinter.

## Pruebas

El proyecto tiene pruebas unitarias en `tests/`.

Ejecutar todas:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```

Compilar modulos principales:

```powershell
.\.venv\Scripts\python.exe -m py_compile main.py app\ui\app.py app\ui\metadata_workflow.py app\ui\app_lifecycle.py app\services\metadata_editor_service.py app\services\playback\audio_player.py
```

Las pruebas cubren areas como:

- Backups.
- Limpieza de texto.
- Servicios de biblioteca.
- Controladores de metadata.
- Flujos de playlist.
- Renombrado.
- Portadas.
- Reproduccion.
- Refresco de UI.

## Flujo Interno Tipico

Ejemplo: aplicar metadata a varias canciones.

1. El usuario selecciona canciones en una o ambas bibliotecas.
2. `SelectionController` obtiene los nombres seleccionados.
3. `MetadataWorkflowMixin` pide metadata al modal correspondiente.
4. `BackupController` crea respaldo antes del cambio.
5. `MetadataApplyController` aplica los cambios a cada controlador.
6. `MetadataController` valida y llama a `MetadataEditor`.
7. `MetadataEditor` escribe en disco con `eyed3` o `mutagen`.
8. Se invalidan caches.
9. La biblioteca y preview se refrescan.
10. La UI muestra resultado o errores.

Ejemplo: preparar playlist.

1. El usuario ordena la lista visualmente.
2. Pulsa `Preparar playlist`.
3. `PlaylistWorkflowController` crea un plan desde el orden actual.
4. El modal muestra preview de posiciones, numeros y nombres.
5. Al confirmar, se crea respaldo.
6. Se aplican `track_number`.
7. Se renombran archivos usando nombres temporales para evitar choques.
8. Se refresca la biblioteca y se mantiene la seleccion activa.

## Notas De Mantenimiento

- La app esta organizada por capas, pero la coordinacion de flujos grandes todavia vive principalmente en mixins de `app/ui/`.
- Los servicios y controladores ya separan bastante logica testeable de la UI.
- Los cambios mas riesgosos suelen estar en metadata real, renombrado fisico y respaldos; deben probarse con copias de musica.
- Para nuevas funciones, conviene poner logica pura en `services/` o `utils/`, coordinacion en `controllers/` y solo construccion visual en `views/`.
- Cuando se agreguen textos visibles, hay que actualizar `app/i18n.py` para Espanol e Ingles.

