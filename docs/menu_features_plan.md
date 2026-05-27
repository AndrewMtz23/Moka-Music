# Menu Features Plan

Fecha de revision: 2026-05-27

## Objetivo

Convertir los menus principales de MokaMusic en centros de trabajo mas claros y utiles:

- Archivo: entrada, salida, importacion, exportacion y respaldos.
- Editar: acciones rapidas sobre seleccion y metadata.
- Tema: apariencia, temas personalizados y modos visuales.
- Herramientas: analisis, mantenimiento, conversion y organizacion.
- Idioma: seleccion y administracion de traducciones.
- Ayuda: guias, diagnostico y soporte.

La meta no es llenar los menus de opciones por llenar, sino ordenar funciones reales por flujo de uso, con atajos, confirmaciones y pruebas donde aplique.

## Principios De Diseno

- Mantener menus cortos en el primer nivel.
- Usar submenus cuando un menu crezca demasiado.
- Priorizar acciones frecuentes y de bajo riesgo antes que automatizaciones destructivas.
- Toda accion masiva debe tener preview, confirmacion o respaldo.
- Las funciones nuevas deben respetar i18n, configuracion persistente y los controladores existentes.
- Las opciones que dependan de una biblioteca cargada deben mostrar mensajes claros si no hay datos.

## Fase 1: Ordenar La Base Del Menu

Estado: completada el 2026-05-27.

Objetivo: mejorar la estructura sin cambiar comportamiento profundo.

### Archivo

- Agregar submenu `Abrir recientes`.
- Guardar las ultimas carpetas abiertas en configuracion.
- Permitir limpiar la lista de recientes.
- Mantener `Abrir carpeta principal` y `Abrir carpeta entrante` como acciones directas.

### Editar

- Agregar acciones basicas:
  - `Seleccionar todo`
  - `Deseleccionar todo`
  - `Invertir seleccion`
- Conectar estas acciones con la biblioteca activa.
- Mantener `Deshacer` y `Rehacer` visibles.

### Tema

- Mantener `Personalizar apariencia...`.
- Agregar `Pantalla completa` como opcion directa del menu Tema.
- Agregar atajo `F11` a nivel app si es viable.

### Criterio De Salida

- Los menus quedan mas ordenados.
- Las acciones nuevas no modifican archivos.
- Hay tests para menu/controller cuando aplique.

## Fase 2: Exportaciones E Importaciones Utiles

Estado: completada el 2026-05-27.

Objetivo: hacer mas poderosa la salida de datos y preparar importacion controlada.

### Archivo

- `Exportar seleccionadas...`
  - JSON con canciones seleccionadas.
  - M3U/M3U8 con canciones seleccionadas.
- `Exportar reporte de biblioteca...`
  - JSON o CSV con metadata faltante, calidad, duplicados y rutas.
- `Importar metadata desde JSON...`
  - Leer un JSON compatible.
  - Mostrar preview antes de aplicar.
  - Aplicar solo campos seleccionados.

### Criterio De Salida

- Se puede exportar una vista completa o una seleccion.
- La importacion nunca aplica cambios sin preview.
- Las funciones reutilizan `playlist_export_service` o servicios nuevos pequenos.

## Fase 3: Tema Y Personalizacion Avanzada

Estado: completada el 2026-05-27.

Objetivo: hacer que la apariencia sea realmente personalizable sin obligar al usuario a editar codigo.

### Tema

- `Guardar tema actual como...`
  - Nombre personalizado.
  - Tema base.
  - Color de acento.
  - Tamano de fuente.
  - Densidad.
  - Estado: completado el 2026-05-27.
- `Administrar mis temas...`
  - Renombrar tema.
  - Duplicar tema.
  - Eliminar tema.
  - Restaurar tema de fabrica.
  - Estado: completado el 2026-05-27.
- `Importar tema...`
  - JSON con paleta y opciones.
  - Estado: completado el 2026-05-27.
- `Exportar tema...`
  - JSON reutilizable.
  - Estado: completado el 2026-05-27.

### Consideraciones Tecnicas

- Crear un modelo simple de tema personalizado en config.
- Mantener presets base en `app/ui/theme.py`.
- Validar colores hex y valores permitidos.
- Evitar que un tema importado rompa contraste minimo.

### Criterio De Salida

- El usuario puede crear, guardar y reutilizar temas propios.
- Los temas personalizados persisten en `mokamusic_config.json`.
- El modal de apariencia permite elegir entre presets y temas propios.

## Fase 4: Herramientas De Metadata

Estado: completada el 2026-05-27.

Objetivo: acelerar limpieza y correccion de bibliotecas grandes.

### Herramientas > Metadata

- `Completar metadata online`
  - Usar resultados de MusicBrainz u otro proveedor ya integrado.
  - Aplicar a seleccion o biblioteca activa.
  - Mostrar preview por cancion.
  - Estado: completado el 2026-05-27.
- `Buscar portadas faltantes`
  - Detectar canciones sin portada.
  - Sugerir portada por album/artista.
  - Estado: completado el 2026-05-27.
- `Normalizar metadata`
  - Limpiar espacios dobles.
  - Normalizar mayusculas/minusculas.
  - Corregir guiones raros.
  - Opcional: quitar texto basura comun.
  - Estado: completado el 2026-05-27.
- `Buscar y reemplazar metadata...`
  - Campo objetivo.
  - Texto a buscar.
  - Texto de reemplazo.
  - Preview antes/despues.
  - Estado: completado el 2026-05-27.

### Criterio De Salida

- Toda accion masiva tiene preview.
- Los cambios crean respaldo antes de aplicar.
- Hay tests para reglas puras de normalizacion.

## Fase 5: Herramientas De Audio Y Calidad

Objetivo: convertir el menu Herramientas en un panel serio de auditoria de audio.

### Herramientas > Audio

- `Analizar calidad de audio`
  - Bitrate.
  - Duracion.
  - Formato.
  - Posibles corruptos.
- `Detectar duplicados avanzado`
  - Por metadata.
  - Por duracion aproximada.
  - Por nombre normalizado.
- `Validar archivos`
  - Rutas rotas.
  - Archivos no reproducibles.
  - Extensiones no soportadas.
- Mejorar `Convertir audio...`
  - Presets:
    - MP3 320 kbps
    - MP3 256 kbps
    - MP3 128 kbps
    - WAV
    - FLAC si ffmpeg lo soporta
  - Opcion de conservar estructura de carpetas.

### Criterio De Salida

- El reporte de calidad puede convertirse en accion.
- El usuario puede filtrar, seleccionar y corregir desde los resultados.
- Conversion mantiene confirmaciones claras para no sobrescribir sin permiso.

## Fase 6: Organizacion De Archivos Y Playlist

Objetivo: ayudar a dejar la biblioteca ordenada fisicamente, no solo dentro de la app.

### Archivo / Herramientas

- `Renombrar archivos por plantilla...`
  - Plantillas como:

```text
{track_number:03d} - {artist} - {title}
{artist}/{album}/{track_number:02d} - {title}
```

- `Organizar archivos en carpetas...`
  - Por artista.
  - Por album.
  - Por ano.
- `Validar playlist`
  - Canciones repetidas.
  - Numeracion faltante.
  - Rutas rotas.
- `Generar playlist inteligente`
  - Por calidad.
  - Por canciones no reproducidas.
  - Por artista/genero.
  - Por duracion objetivo.

### Criterio De Salida

- Las operaciones muestran preview de rutas antes/despues.
- Se evita colision de nombres.
- Se crea respaldo antes de renombrar o mover archivos.

## Fase 7: Idioma Y Ayuda

Objetivo: que el usuario entienda mejor la app y que el proyecto sea mas facil de mantener.

### Idioma

- Mostrar una marca en el idioma activo.
- `Detectar idioma del sistema`.
- `Reportar textos sin traducir`.
- Preparar soporte para traducciones externas si el proyecto crece.

### Ayuda

- `Guia rapida`
  - Cargar carpeta.
  - Revisar metadata.
  - Filtrar por calidad.
  - Exportar listas.
  - Preparar playlist.
- `Atajos de teclado`.
- `Ver logs`.
- `Abrir carpeta de respaldos`.
- `Diagnostico del sistema`
  - Verificar ffmpeg.
  - Verificar permisos.
  - Verificar dependencias opcionales.
- `Acerca de MokaMusic`.

### Criterio De Salida

- El menu Ayuda sirve tanto a usuarios como a desarrollo.
- El diagnostico reduce dudas cuando algo falla.

## Orden Recomendado De Implementacion

1. Fase 1: bajo riesgo y mejora inmediata de UX.
2. Fase 3: continua el trabajo actual de apariencia.
3. Fase 2: exportaciones seleccionadas y reportes.
4. Fase 5: calidad/audio, porque conecta con filtros ya existentes.
5. Fase 4: metadata avanzada.
6. Fase 6: organizacion fisica, por ser mas delicada.
7. Fase 7: ayuda/diagnostico para cerrar la experiencia.

## Primer Sprint Propuesto

### Punto 1

Agregar `Abrir recientes` en Archivo:

- Guardar carpetas recientes.
- Separar recientes por principal/entrante si hace falta.
- Permitir abrir una carpeta reciente en la biblioteca activa.

### Punto 2

Agregar acciones de seleccion en Editar:

- Seleccionar todo.
- Deseleccionar todo.
- Invertir seleccion.

### Punto 3

Agregar pantalla completa al menu Tema:

- Alternar pantalla completa de toda la app.
- Mostrar estado correcto en menu.
- Mantener `F11` como atajo.

### Punto 4

Exportar seleccion actual:

- JSON.
- M3U8.
- Incluir posicion visible y posicion de biblioteca.

## Riesgos Y Cuidados

- No mezclar funciones destructivas con acciones sin confirmacion.
- No guardar rutas inexistentes como recientes permanentes.
- No hacer importaciones de metadata sin preview.
- No bloquear la UI en analisis grandes; usar progreso donde aplique.
- Mantener traducciones en espanol e ingles desde el inicio.
