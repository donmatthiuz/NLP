# Corpus inicial de ingesta del IGSS

**Corte local:** 14 de noviembre de 2026. **Empresa ficticia de prueba:** `empresa_demo`.

Los dos PDF se obtuvieron desde la [página Proveedores del IGSS](https://www.igssgt.org/proveedores/), se guardaron bajo `data/ingesta/originales/igss/` y se procesaron con el [módulo de ingesta](../../src/licigt/ingesta/README.md). `data/` está excluido de Git: este inventario registra la procedencia, pero los archivos y manifiestos permanecen en el entorno local. Los hashes SHA-256 se recalcularon sobre los originales guardados y coincidieron con sus manifiestos.

| Evento | PDF oficial | Código IGSS | `evento_id` | `doc_id` | SHA-256 | Páginas / fragmentos indexables |
|---|---|---:|---|---|---|---:|
| 399-IGSS-2026 | [Bases integradas](https://www.igssgt.org/wp-content/uploads/2026/11/LICITACION-PUBLICA-DA-No.-399-IGSS-2026.pdf) | 432 | `437a8435922652fbb78aea651114680e` | `4182413774fa4149a9a15f4ecd0ef466` | `1f9aa9fdf38e8ce7780a00f37b49a9edda4ec9ef9426a979b2962127ff740444` | 36 / 211 |
| 363-IGSS-2026 | [Bases integradas](https://www.igssgt.org/wp-content/uploads/2026/11/LICITACION-PUBLICA-DA-No.-363-IGSS-2026.pdf) | 345 | `7008db8420d85f7c932817d7868eae8a` | `f1cb15bfe200440891134b14683dcadf` | `953eab12d975d203d1d4f27aed8e14c39581095d67ac91efbcda7a8934cb9426` | 36 / 210 |

En ambos casos, `fecha_publicacion` es `2026-11-13` según la ficha del portal, `fecha_descarga` es `2026-11-14` y `fecha_documento` quedó sin dato porque no se verificó una fecha propia del archivo. El estado de ingesta es `completo`: las 36 páginas de cada PDF fueron legibles y el número de evento aparece en el texto. Esto **no** confirma que esté reunido el expediente completo. Hasta este corte, el inventario registra solo el tipo `bases`; no hay un par de modificación oficial para probar comparación documental.

Los manifiestos se regeneraron con la segmentación de la arquitectura vigente. El control de texto oculto no detectó capas adicionales ni patrones de inyección en estos dos PDF; este control es una señal auxiliar y no convierte el contenido recuperado en instrucciones confiables.

## Regenerar el corpus local

Con Python 3.11 o posterior y `poppler-utils` instalados, desde la raíz del repositorio:

```bash
PYTHONPATH=src python -m licigt.ingesta.automatic \
  --numero-evento 399-IGSS-2026 --tenant-id empresa_demo \
  --data-dir data/ingesta

PYTHONPATH=src python -m licigt.ingesta.automatic \
  --numero-evento 363-IGSS-2026 --tenant-id empresa_demo \
  --data-dir data/ingesta
```

El portal puede cambiar sus archivos. Si el SHA-256 descargado cambia, la ingesta conservará una nueva versión técnica; se debe revisar la causa antes de interpretar el cambio como modificación oficial. Los manifiestos se encuentran en `data/ingesta/manifiestos_igss/<doc_id>.json` y el registro en `data/ingesta/igss_ingesta.sqlite3`.
