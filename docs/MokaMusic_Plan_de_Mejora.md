# MokaMusic — Plan de Mejora

> Este documento describe oportunidades concretas para llevar MokaMusic a un siguiente nivel, organizadas por área y prioridad.

---

## Estado Actual: Valoración General

MokaMusic es una app de escritorio bien pensada. Tiene separación clara de capas (services, controllers, views), soporte de respaldos, i18n, temas, reproductor integrado y flujos no triviales como preparación de playlists con renombrado sin colisiones. Es una base sólida.

Las oportunidades de mejora caen en cinco categorías:

1. Experiencia de usuario (UX)
2. Funcionalidades nuevas
3. Calidad técnica interna
4. Distribución y adopción
5. Extensibilidad futura

---

## 1. Experiencia de Usuario (UX)

### 1.1 Onboarding y primera ejecución

**Problema actual:** Un usuario nuevo que abre la app por primera vez ve dos paneles vacíos sin orientación.

**Mejora propuesta:**
- Pantalla de bienvenida la primera vez que se ejecuta la app.
- Estado vacío ilustrado en cada panel de biblioteca (imagen + texto corto + botón de acción).
- Tour guiado opcional: resaltar los pasos clave (cargar carpeta → revisar → reproducir → preparar playlist).

---

### 1.2 Feedback Visual Durante Operaciones Largas

**Problema actual:** Operaciones como preparar una playlist grande o aplicar portadas en lote pueden tardar sin mostrar progreso real.

**Mejora propuesta:**
- Barra de progreso con cancelación para operaciones masivas.
- Indicador de "procesando" por canción mientras se aplica metadata en lote.
- Notificaciones flotantes (toast) al terminar operaciones: éxito, errores parciales, cancelado.

---

### 1.3 Undo Global (Ctrl+Z)

**Problema actual:** Existe deshacer el último cambio de metadata de sesión, pero no un undo/redo general navegable.

**Mejora propuesta:**
- Pila de acciones por sesión con hasta N pasos atrás.
- Acciones que entran al historial: cambio de metadata, renombrado, aplicar portada, mover canciones.
- Menú Editar → Deshacer / Rehacer con descripción de la acción.

---

### 1.4 Vista de Tabla Mejorada

**Mejora propuesta:**
- Columnas redimensionables y reordenables por el usuario.
- Persistir el ancho de columnas en `mokamusic_config.json`.
- Resaltar visualmente canciones con problemas (sin portada, sin artista, duplicado) con colores o íconos en la fila.
- Mini waveform o barra de color como indicador visual de duración en la tabla.

---

### 1.5 Drag-and-Drop Extendido

**Problema actual:** Drag-and-drop existe para archivos, pero el reordenamiento manual solo funciona en vista completa.

**Mejora propuesta:**
- Drag-and-drop entre las dos bibliotecas para mover canciones.
- Drag-and-drop de una carpeta sobre el panel para abrirla directamente.
- Drag-and-drop de una imagen sobre cualquier canción seleccionada para aplicar portada.

---

## 2. Funcionalidades Nuevas

### 2.1 Búsqueda de Metadata Online (MusicBrainz / Last.fm)

**Descripción:** Permitir buscar y completar metadata desde servicios externos cuando la información local está incompleta o incorrecta.

**Flujo propuesto:**
1. El usuario selecciona una canción con metadata incompleta.
2. Presiona "Buscar online".
3. La app consulta MusicBrainz API (gratuita, sin API key) con artista + título.
4. Muestra resultados con preview de metadata encontrada.
5. El usuario confirma qué campos importar.

**APIs útiles:**
- MusicBrainz: `https://musicbrainz.org/ws/2/` — metadata, fechas, géneros, ISRCs.
- Cover Art Archive: portadas vinculadas a MusicBrainz.
- Last.fm API: géneros, tags, popularidad.

---

### 2.2 Detección de Duplicados Mejorada

**Problema actual:** La detección actual usa artista/título exacto.

**Mejora propuesta:**
- Comparación fonética o por similitud de strings (fuzzy matching con `rapidfuzz`).
- Detección por huella de audio usando `chromaprint` / AcoustID para identificar duplicados aunque tengan nombres distintos.
- Vista de duplicados lado a lado con opción de elegir cuál conservar.

---

### 2.3 Análisis de Calidad de Audio

**Descripción:** Mostrar información técnica de cada archivo de audio.

**Datos adicionales a mostrar:**
- Bitrate (kbps).
- Sample rate (Hz).
- Canales (mono / stereo).
- Formato de encoding (CBR / VBR para MP3).
- Tamaño del archivo.

**Filtros nuevos basados en esto:**
- Canciones con bitrate bajo (< 128 kbps).
- Archivos posiblemente dañados o truncados.

**Librería:** `mutagen` ya está disponible y expone estos datos.

---

### 2.4 Exportar Playlist a Formatos Estándar

**Descripción:** Generar archivos de playlist que otras apps puedan consumir.

**Formatos propuestos:**
- `.m3u` / `.m3u8` — el más universal.
- `.pls` — compatible con Winamp y muchos reproductores.
- `.json` — útil para integraciones propias.

**Flujo:**
- Desde el menú o botón en la biblioteca → "Exportar playlist" → elegir formato → guardar archivo.

---

### 2.5 Estadísticas de la Biblioteca

**Descripción:** Panel o modal con un resumen de la biblioteca cargada.

**Datos útiles:**
- Total de canciones y duración acumulada.
- Distribución por género (gráfico de torta simple).
- Distribución por año (gráfico de barras).
- Porcentaje de canciones con metadata completa.
- Top artistas y albums.

**Librería:** se puede hacer con `tkinter.Canvas` o embebiendo `matplotlib`.

---

### 2.6 Modo Comparación Entre Bibliotecas

**Descripción:** Vista especial para cruzar canciones entre la biblioteca principal y la entrante.

**Funciones:**
- Detectar canciones de la entrante que ya están en la principal (por artista+título o huella de audio).
- Marcar duplicados cruzados antes de mover.
- Resaltar canciones nuevas que no existen en la principal.

---

### 2.7 Historial de Reproducción

**Descripción:** Llevar registro de qué se ha reproducido en sesiones previas.

**Funciones:**
- Guardar historial en `mokamusic_config.json` o archivo separado.
- Filtro "No reproducidas" en la biblioteca.
- Ordenar por "última vez reproducida".
- Estadísticas simples: canciones más reproducidas.

---

### 2.8 Convertidor de Formato de Audio

**Descripción:** Convertir archivos entre formatos soportados sin salir de la app.

**Casos de uso:**
- Convertir WAV a MP3 para reducir espacio.
- Convertir FLAC a MP3 para compatibilidad.

**Librería:** `pydub` (wrapper de ffmpeg) o llamada directa a `ffmpeg` si está disponible.

---

## 3. Calidad Técnica Interna

### 3.1 Cache Persistente de Metadata

**Problema actual:** Al cerrar y reabrir la app, se relee toda la metadata desde disco.

**Mejora propuesta:**
- Guardar un índice de metadata por carpeta en un archivo SQLite o JSON con hash de archivo.
- Al cargar una carpeta, comparar hash/fecha de modificación para saber qué archivos releer.
- Reducción drástica del tiempo de carga en bibliotecas grandes.

**Librería sugerida:** `sqlite3` (incluida en Python stdlib).

---

### 3.2 Operaciones en Hilo Separado

**Problema actual:** Operaciones de I/O en el hilo principal pueden congelar la UI.

**Mejora propuesta:**
- Mover lectura de bibliotecas, escritura de metadata en lote y renombrado masivo a hilos separados con `threading` o `concurrent.futures`.
- Comunicar progreso y resultados de vuelta al hilo de UI usando la cola de eventos de Tkinter (`after()`).

---

### 3.3 Logging Mejorado y Panel de Errores

**Mejora propuesta:**
- Niveles de log configurables (DEBUG / INFO / WARNING / ERROR).
- Panel de log interno accesible desde el menú (últimas N líneas del log).
- Notificación visible cuando ocurre un error no fatal durante operaciones en lote, con opción de ver detalle.

---

### 3.4 Cobertura de Tests Ampliada

**Áreas a cubrir que probablemente tienen menos tests:**
- `file_service.py` (operaciones de sistema de archivos).
- `cover_controller.py` con imágenes reales.
- Flujo completo de drag-and-drop.
- Persistencia y restauración de configuración.

**Agregar:**
- Tests de integración end-to-end con carpetas temporales reales.
- Fixtures compartidas para no repetir setup de archivos de audio de prueba.

---

### 3.5 Validación de Metadata Más Rica

**Mejora propuesta:**
- Validar que el año sea razonable (entre 1900 y el año actual).
- Validar que el número de pista sea positivo y no mayor a 999.
- Detectar y advertir sobre títulos o artistas con caracteres extraños o encoding incorrecto (problema común en MP3 viejos con latin-1).
- Mostrar advertencias en la vista previa antes de guardar.

---

## 4. Distribución y Adopción

### 4.1 Instalador para Windows

**Problema actual:** El ejecutable queda en una carpeta `dist/MokaMusic/` y el usuario debe mover todo.

**Mejora propuesta:**
- Crear un instalador `.exe` con [NSIS](https://nsis.sourceforge.io/) o [Inno Setup](https://jrsoftware.org/isinfo.php).
- El instalador crea acceso directo en el escritorio y en el menú inicio.
- Incluye opción de desinstalar desde Agregar/Quitar programas.

---

### 4.2 Auto-actualización

**Descripción:** Notificar al usuario cuando hay una versión nueva disponible.

**Flujo simple:**
- Al iniciar la app, consultar un JSON de versión en GitHub releases.
- Si hay versión nueva, mostrar banner discreto con link de descarga.
- No actualizar automáticamente sin confirmación del usuario.

---

### 4.3 Soporte macOS y Linux

**Estado actual:** La app es Python/Tkinter y teóricamente es cross-platform, pero el icono `.ico`, algunos paths y `Send2Trash` pueden tener diferencias.

**Mejora propuesta:**
- Probar en macOS y Linux.
- Adaptar el empaquetado con PyInstaller para generar `.app` en macOS y AppImage en Linux.
- Documentar los pasos específicos por plataforma.

---

### 4.4 Sitio Web o README Más Visual

**Mejora propuesta:**
- README con capturas de pantalla o GIF animado mostrando el flujo principal.
- Sección de instalación rápida con un comando.
- Badge de versión y de tests pasando.

---

## 5. Extensibilidad Futura

### 5.1 Sistema de Plugins

**Descripción:** Permitir que terceros (o el mismo desarrollador) agreguen acciones de limpieza, exportadores o integraciones sin modificar el núcleo.

**Diseño mínimo:**
- Carpeta `plugins/` en la raíz del proyecto.
- Cada plugin es un módulo Python con una interfaz simple: `name`, `description`, `apply(songs)`.
- La app descubre plugins al arrancar y los expone en el menú o como acciones rápidas.

---

### 5.2 Integración con Servicios de Streaming (Solo Lectura)

**Descripción:** Conectar con Last.fm o Spotify para enriquecer metadata sin depender de edición manual.

**Casos de uso:**
- Autocompletar género desde Last.fm tags.
- Ver si una canción local existe en Spotify y tomar su metadata como referencia.
- Marcar canciones "no disponibles en streaming" para conservar versiones locales.

---

### 5.3 Soporte de Más Formatos

**Formatos a considerar:**
- `.aac` — muy común en archivos descargados.
- `.m4a` — contenedor AAC de Apple, popular en colecciones de iTunes.
- `.opus` — creciente en plataformas de podcast y streaming alternativo.
- `.wma` — presente en colecciones viejas de Windows Media Player.

**`mutagen` ya soporta la mayoría de estos**, solo habría que agregar las extensiones al listado de formatos y verificar los campos de metadata disponibles por formato.

---

### 5.4 Modo Headless / CLI

**Descripción:** Permitir usar las funciones principales desde línea de comandos para automatización.

**Comandos útiles:**
```bash
mokamusic clean-metadata ./mi-musica/
mokamusic prepare-playlist ./mi-musica/
mokamusic apply-cover ./mi-musica/ --cover cover.jpg
mokamusic export-playlist ./mi-musica/ --format m3u
```

**Beneficio:** Permite integrar MokaMusic en scripts de procesamiento por lotes sin abrir la UI.

---

## Resumen de Prioridades

| Prioridad | Área | Mejora |
|-----------|------|--------|
| 🔴 Alta | UX | Feedback visual en operaciones largas (progreso + toast) |
| 🔴 Alta | Técnica | Operaciones en hilo separado para no congelar UI |
| 🔴 Alta | UX | Estado vacío y onboarding básico |
| 🟡 Media | Funcionalidad | Búsqueda de metadata online (MusicBrainz) |
| 🟡 Media | Funcionalidad | Exportar playlist a M3U |
| 🟡 Media | Funcionalidad | Análisis de calidad de audio (bitrate, sample rate) |
| 🟡 Media | Técnica | Cache persistente de metadata |
| 🟡 Media | UX | Resaltar problemas en tabla con colores/íconos |
| 🟢 Baja | Funcionalidad | Estadísticas de la biblioteca |
| 🟢 Baja | Funcionalidad | Historial de reproducción |
| 🟢 Baja | Distribución | Instalador para Windows |
| 🟢 Baja | Extensibilidad | Soporte de más formatos (.aac, .m4a, .opus) |
| 🟢 Baja | Extensibilidad | Modo CLI / headless |

---

## Siguiente Paso Recomendado

El impacto más inmediato y visible para cualquier usuario vendría de atacar en este orden:

1. **Hilo separado para carga de biblioteca y escritura masiva** — evita que la UI se congele, que es el problema más frustrante en apps de escritorio.
2. **Feedback visual (barra de progreso + toasts)** — hace que las operaciones largas sean tolerables y dan confianza de que algo está pasando.
3. **Resaltado de problemas en tabla** — mejora enormemente el flujo de revisión de metadata sin requerir que el usuario filtre activamente.
4. **Búsqueda online en MusicBrainz** — añade valor real de forma rápida; la API es gratuita y bien documentada.

---

*Documento generado como referencia de desarrollo. Las áreas no son excluyentes; pueden atacarse en paralelo según el tiempo disponible.*
