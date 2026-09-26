# pdf-extractext-extraction

Servicio de extracción de texto de archivos PDF. Expone una API FastAPI para extraer el contenido de documentos PDF.

## Instalación

Instalar las dependencias:

```bash
pip install -r requirements.txt
```

Para desarrollo también hacen falta `pytest` y `ruff`, que no van en la imagen de producción:

```bash
pip install -r requirements-dev.txt
```

`requirements-dev.txt` ya incluye `requirements.txt`, así que alcanza con ese comando para trabajar localmente.

## Ejecución

Levantar el servidor en modo desarrollo:

```bash
uvicorn main:app --reload --port 8002
```

## Tests

Correr los tests:

```bash
pytest tests/ -v
```

## Lint

Verificar estilo y errores con ruff:

```bash
ruff check .
```

Ambos comandos se ejecutan en cada push y PR mediante GitHub Actions (`.github/workflows/ci.yml`).

## Variables de entorno

| Variable                  | Descripción                                  | Valor por defecto        |
| ------------------------- | -------------------------------------------- | ------------------------ |
| `PERSISTENCE_SERVICE_URL` | URL base del servicio de persistencia        | `http://persistence-service:8000` |