# Laboratorio 1 - Resultado de Ejecucion

**Curso:** CC3103 - Procesamiento de Lenguaje Natural
**Entrega:** Cordero, Mathew
**Comando ejecutado:**

```bash
python laboratorio_1_cordero_mathew.py
```

---

## Repositorio

[Repositorio](https://github.com/donmatthiuz/NLP/tree/lab1)

## Salida de la ejecucion

```text
================================================================================
DEMO: COMPARACION DE TOKENIZADORES
================================================================================
Texto:
Mi numero es +502 5555-1234 y mi correo es ana@example.com

Tokenizacion por espacios:
['Mi', 'numero', 'es', '+502', '5555-1234', 'y', 'mi', 'correo', 'es', 'ana@example.com']

Tokenizacion Regex basica:
['mi', 'numero', 'es', '502', '5555', '1234', 'y', 'mi', 'correo', 'es', 'ana', 'example', 'com']

Tokenizacion Regex mixta:
['Mi', 'numero', 'es', '+', '502', '5555', '-', '1234', 'y', 'mi', 'correo', 'es', 'ana@example.com']

================================================================================
DEMO: PIPELINE COMPLETO
================================================================================

================================================================================
TEXTO 1
================================================================================
Texto original:
Hola!!! necesito ayuda con mi cuenta :( mi correo es ana.lopez@example.com

Texto normalizado:
Hola!!! necesito ayuda con mi cuenta :( mi correo es ana.lopez@example.com

Datos sensibles detectados:
  - EMAIL: ana.lopez@example.com

Accion recomendada: REDACT

Texto seguro:
Hola!!! necesito ayuda con mi cuenta :( mi correo es [EMAIL_REDACTED]

Tokens:
['Hola', '!', '!', '!', 'necesito', 'ayuda', 'con', 'mi', 'cuenta', ':', '(', 'mi', 'correo', 'es', '[', 'EMAIL_REDACTED', ']']

Estadisticas:
Caracteres: 69
Tokens: 17
Tokens unicos: 14
Top 10 tokens:
  - !: 3
  - mi: 2
  - Hola: 1
  - necesito: 1
  - ayuda: 1
  - con: 1
  - cuenta: 1
  - :: 1
  - (: 1
  - correo: 1

================================================================================
TEXTO 2
================================================================================
Texto original:
Mi numero es +502 5555-1234 y mi sitio es https://uvg.edu.gt

Texto normalizado:
Mi numero es +502 5555-1234 y mi sitio es https://uvg.edu.gt

Datos sensibles detectados:
  - URL: https://uvg.edu.gt
  - PHONE: +502 5555-1234

Accion recomendada: REDACT

Texto seguro:
Mi numero es [PHONE_REDACTED] y mi sitio es https://uvg.edu.gt

Tokens:
['Mi', 'numero', 'es', '[', 'PHONE_REDACTED', ']', 'y', 'mi', 'sitio', 'es', 'https://uvg.edu.gt']

Estadisticas:
Caracteres: 62
Tokens: 11
Tokens unicos: 10
Top 10 tokens:
  - es: 2
  - Mi: 1
  - numero: 1
  - [: 1
  - PHONE_REDACTED: 1
  - ]: 1
  - y: 1
  - mi: 1
  - sitio: 1
  - https://uvg.edu.gt: 1

================================================================================
TEXTO 3
================================================================================
Texto original:
La documentacion esta en https://docs.example.com/nlp, revisenla antes de la clase.

Texto normalizado:
La documentacion esta en https://docs.example.com/nlp, revisenla antes de la clase.

Datos sensibles detectados:
  - URL: https://docs.example.com/nlp,

Accion recomendada: WARN

Texto seguro:
La documentacion esta en https://docs.example.com/nlp, revisenla antes de la clase.

Tokens:
['La', 'documentacion', 'esta', 'en', 'https://docs.example.com/nlp,', 'revisenla', 'antes', 'de', 'la', 'clase', '.']

Estadisticas:
Caracteres: 83
Tokens: 11
Tokens unicos: 11
Top 10 tokens:
  - La: 1
  - documentacion: 1
  - esta: 1
  - en: 1
  - https://docs.example.com/nlp,: 1
  - revisenla: 1
  - antes: 1
  - de: 1
  - la: 1
  - clase: 1

================================================================================
TEXTO 4
================================================================================
Texto original:
Mi password temporal es Cambiar123, no lo compartan con nadie.

Texto normalizado:
Mi password temporal es Cambiar123, no lo compartan con nadie.

Datos sensibles detectados:
  - SECRET_WORD: password

Accion recomendada: BLOCK

Texto seguro:
  [BLOQUEADO: no debe enviarse al modelo]

Tokens:
[]

Estadisticas:
  No se calcularon estadisticas porque el texto fue bloqueado.

================================================================================
TEXTO 5
================================================================================
Texto original:
Mi DPI simulado es 1234 56789 0101 para el tramite de la universidad.

Texto normalizado:
Mi DPI simulado es 1234 56789 0101 para el tramite de la universidad.

Datos sensibles detectados:
  - DPI: 1234 56789 0101

Accion recomendada: REDACT

Texto seguro:
Mi DPI simulado es [DPI_REDACTED] para el tramite de la universidad.

Tokens:
['Mi', 'DPI', 'simulado', 'es', '[', 'DPI_REDACTED', ']', 'para', 'el', 'tramite', 'de', 'la', 'universidad', '.']

Estadisticas:
Caracteres: 68
Tokens: 14
Tokens unicos: 14
Top 10 tokens:
  - Mi: 1
  - DPI: 1
  - simulado: 1
  - es: 1
  - [: 1
  - DPI_REDACTED: 1
  - ]: 1
  - para: 1
  - el: 1
  - tramite: 1

================================================================================
TEXTO 6
================================================================================
Texto original:
El codigo del curso es CC3103 y la clase inicia a las 17:20.

Texto normalizado:
El codigo del curso es CC3103 y la clase inicia a las 17:20.

Datos sensibles detectados:
  No se detectaron datos sensibles.

Accion recomendada: ALLOW

Texto seguro:
El codigo del curso es CC3103 y la clase inicia a las 17:20.

Tokens:
['El', 'codigo', 'del', 'curso', 'es', 'CC3103', 'y', 'la', 'clase', 'inicia', 'a', 'las', '17', ':', '20', '.']

Estadisticas:
Caracteres: 60
Tokens: 16
Tokens unicos: 16
Top 10 tokens:
  - El: 1
  - codigo: 1
  - del: 1
  - curso: 1
  - es: 1
  - CC3103: 1
  - y: 1
  - la: 1
  - clase: 1
  - inicia: 1

================================================================================
TEXTO 7
================================================================================
Texto original:
API_KEY=abc123-simulada no deberia compartirse con ningun modelo.

Texto normalizado:
API_KEY=abc123-simulada no deberia compartirse con ningun modelo.

Datos sensibles detectados:
  - SECRET_WORD: API_KEY

Accion recomendada: BLOCK

Texto seguro:
  [BLOQUEADO: no debe enviarse al modelo]

Tokens:
[]

Estadisticas:
  No se calcularon estadisticas porque el texto fue bloqueado.
```

---

## Reflexion (150-250 palabras)

Este laboratorio se creo con el proposito de parsear datos sensibles, para que a un agente se le logre pasar los tokens necesarios para construir el contexto completo a cualquier pregunta. Sin embargo, esto conlleva problemas: se dan falsos positivos como URLs con puntuacion pegada ("https://docs.example.com/nlp,") que no representan un riesgo real, sino que aparecen por lo codicioso del patron, o el simple hecho de mencionar la palabra "clave" o "contraseña", que bloquea el texto aunque no haya un secreto real. Tambien puede darse el caso contrario: falsos negativos como emails ofuscados donde no se escribe el correo pero si se menciona su estructura ("ana punto google punto com"), telefonos donde el separador no es "-" sino puntos o comas, secretos sin contexto (un token pegado sin decir que lo es), y variantes de "clave" como "pwd".

Aun asi, al descartar esto se pierden datos que, si bien no es bueno que el modelo reciba, tambien evita que realice su trabajo correctamente al no tener contexto. Por ello, usar solo Regex y descartar no es la mejor solucion para proteger datos de una empresa real, ya que es rigido y no entiende semantica. Como capa adicional agregaria un modelo local (tipo NER) que identifique estos patrones con contexto y los ofusque de forma reversible antes de enviarlos a un modelo en produccion, junto con revision humana para los casos ambiguos marcados como WARN.
