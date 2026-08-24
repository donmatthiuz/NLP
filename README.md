# Laboratorio 2: búsqueda semántica

Este proyecto compara dos formas de buscar respuestas en un corpus de soporte para comercio electrónico:

- **Búsqueda semántica:** convierte cada texto en un embedding y ordena los resultados por similitud coseno.
- **Búsqueda por palabras clave:** cuenta cuántas palabras comparten la consulta y cada texto.

El notebook incluye 24 oraciones, 6 consultas de prueba, recuperación `top-k`, comparación de resultados y una función para escribir consultas propias.

## Ejecutar en Google Colab

Puedes [abrir el notebook en Google Colab](https://colab.research.google.com/github/donmatthiuz/NLP/blob/lab2/laboratorio_2_busqueda_semantica.ipynb) cuando esta rama esté publicada en GitHub.

También puedes abrirlo manualmente:

1. Entra a [Google Colab](https://colab.research.google.com/).
2. Selecciona **Archivo > Subir notebook**.
3. Sube `laboratorio_2_busqueda_semantica.ipynb`.
4. Selecciona **Entorno de ejecución > Ejecutar todas**.

La primera celda instala las dependencias. La primera ejecución descarga el modelo de Hugging Face y puede tardar unos minutos. No es necesario usar GPU.

## Cambiar los datos

En la celda **Configuración y datos** puedes:

- Editar `CORPUS` para agregar o reemplazar documentos.
- Editar `CONSULTAS` para cambiar los casos de prueba.
- Cambiar `TOP_K` para mostrar más o menos resultados.

Después de cualquier cambio, vuelve a ejecutar desde la celda **Generación de embeddings** hasta el final. Para probar una sola frase, usa:

```python
consultar("escribe aquí tu consulta", top_k=3)
```

La reflexión final se dejó sin responder para completarla después de observar los resultados.
