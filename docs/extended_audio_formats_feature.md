# MokaMusic - Soporte Extendido De Formatos De Audio

## Resumen

Este documento define el feature agregado a MokaMusic: ampliar los formatos de audio soportados mas alla de `.mp3`, `.wav`, `.ogg` y `.flac`.

El objetivo es que MokaMusic pueda trabajar mejor con bibliotecas musicales reales que incluyen archivos provenientes de iTunes, telefonos, descargas antiguas, podcasts o colecciones mixtas.

## Formatos Propuestos

Se agrega soporte inicial para:

- `.m4a`
- `.aac`
- `.opus`
- `.wma`

El soporte debe cubrir, en una primera fase:

- Deteccion de archivos al cargar carpetas.
- Drag-and-drop de archivos compatibles.
- Lectura de metadata basica.
- Edicion de metadata basica cuando la libreria lo permita.
- Analisis de duracion y calidad de audio.
- Exportacion en playlists y reportes.
- Reproduccion si `pygame`/SDL puede abrir el formato en el entorno actual.

## Motivacion

Actualmente `FileFormats.AUDIO` solo incluye:

```python
(".mp3", ".wav", ".ogg", ".flac")
```

Sin embargo, MokaMusic ya usa `mutagen` para manejar metadata de formatos no MP3. Eso permite ampliar compatibilidad sin cambiar toda la arquitectura.

El beneficio para usuarios es claro:

- Colecciones de iTunes suelen usar `.m4a`.
- Podcasts y audio moderno pueden usar `.opus`.
- Archivos viejos de Windows Media Player pueden usar `.wma`.
- Algunas descargas o conversiones usan `.aac`.

## Alcance Funcional

### Incluido

1. Actualizar la lista central de formatos soportados.
2. Ajustar validaciones que dependen de `FileFormats.AUDIO`.
3. Confirmar que los file dialogs muestren los nuevos formatos.
4. Leer metadata basica con `mutagen`.
5. Escribir metadata basica cuando sea seguro.
6. Agregar tests para deteccion y validacion de extensiones.
7. Documentar limitaciones conocidas.

### No Incluido En La Primera Fase

- Conversion automatica entre estos formatos.
- Garantizar reproduccion universal de todos los formatos.
- Soporte perfecto de portada embebida en todos los contenedores.
- Integracion con codecs externos instalables.
- Huella acustica o identificacion por audio.

## Campos De Metadata

MokaMusic intentara conservar el mismo modelo actual:

- `title`
- `artist`
- `album_artist`
- `album`
- `genre`
- `year`
- `track_number`
- `comment`

Para formatos basados en MP4, como `.m4a`, algunos campos pueden requerir claves internas distintas a las de `EasyMutagen`. La primera implementacion debe priorizar lectura/escritura basica y fallar de forma segura cuando un campo no sea compatible.

## Consideraciones Tecnicas

### Punto Central

El cambio principal debe comenzar en:

```text
app/constants.py
```

`FileFormats.AUDIO` debe convertirse en la fuente de verdad para los nuevos formatos.

### Servicios A Revisar

- `app/services/file_service.py`
- `app/services/song_info_service.py`
- `app/services/metadata_editor_service.py`
- `app/services/audio_quality_service.py`
- `app/services/playback/audio_player.py`
- `app/controllers/drop_controller.py`
- `app/controllers/metadata_controller.py`
- `app/ui_helpers/file_dialogs.py`

Muchos de estos ya dependen de `FileFormats.AUDIO`, por lo que el cambio deberia propagarse bien si se mantiene esa constante como fuente unica.

## Riesgos

### Reproduccion

`pygame` no garantiza que todos los formatos se puedan reproducir en todas las plataformas. La app debe permitir gestionar metadata aunque un archivo no pueda reproducirse.

### Metadata MP4/M4A

Los archivos `.m4a` pueden necesitar manejo especial para algunas etiquetas y portadas. Si `mutagen.File(..., easy=True)` no cubre un campo, la app debe ignorarlo o reportarlo sin romper la operacion completa.

### WMA

`.wma` puede tener compatibilidad parcial segun el archivo y el entorno. Se debe tratar como formato soportado con tolerancia a errores.

## Implementacion

1. Ampliar `FileFormats.AUDIO`.
2. Agregar tests para `is_supported_audio_file`, `list_audio_files` y drag-and-drop.
3. Mantener lectura/escritura de metadata basica con `mutagen`.
4. Agregar soporte de portada `covr` para archivos MP4/M4A.
5. Actualizar README con la nueva lista de formatos.
6. Ejecutar la suite completa de tests.

## Criterios De Aceptacion

- Los nuevos formatos aparecen al seleccionar archivos desde la UI.
- Las carpetas con `.m4a`, `.aac`, `.opus` o `.wma` los listan como canciones.
- Los filtros, busquedas y reportes no fallan con los nuevos formatos.
- La app muestra errores amigables si un archivo no puede reproducirse o editarse.
- Los tests existentes siguen pasando.
- Hay tests nuevos cubriendo al menos la deteccion de extensiones.

## Prioridad Recomendada

Prioridad: media-alta.

Es una mejora pequena en superficie, pero con impacto directo para usuarios con colecciones mixtas. Tambien es una buena forma de retomar el proyecto sin tocar flujos de alto riesgo como backups, renombrados masivos o preparacion de playlists.
