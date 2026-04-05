# TaskManager FastAPI (dev)

Rápida guía para levantar el servicio en desarrollo.

1. Crear y activar virtualenv:

```bash
python -m venv .venv
# .venv\Scripts\activate en Windows
```

2. Instalar dependencias (necesita `sqlmodel`, `aiosqlite`, `fastapi`, `uvicorn`, `requests`):

```bash
pip install -r requirements.txt
```

3. Variables de entorno (opcional):

```bash
set TASK_MANAGER_DB=tasks.db
```

4. Ejecutar:

```bash
uvicorn main:app --host 0.0.0.0 --port 6543 --reload
```

---

## MCP Workflow (Strict) 🛡️

Este servidor MCP impone un flujo de estados estricto ("Kanban-mode") para asegurar el seguimiento real del progreso por parte de los agentes:

### Comandos Principales
- **`task_create`**: Crea la tarea siempre en estado `pending`.
- **`tasks_push(id)`**: La única forma de avanzar.
  - `pending` ➡️ `in-progress`
  - `in-progress` ➡️ `done`
  - `blocked` ➡️ `pending` (para re-intentar)
- **`tasks_block(id, reason)`**: Si una tarea falla, debe marcarse como `blocked` explicando el motivo. Solo permitido desde `in-progress`.

### Por qué este cambio?
Para evitar que los agentes marquen tareas como `done` sin haber pasado por el estado de ejecución (`in-progress`), garantizando que siempre veas qué está haciendo el agente en tiempo real.

---

## Configuración MCP (Servidor y Cliente) ⚙️

Para que un agente (como Claude Desktop, Roo Code, etc.) pueda utilizar este Task Manager, sigue estas instrucciones:

### 1. Configuración del Servidor (Server-side)
El servidor MCP se comunica via `stdio`. No necesita estar "corriendo" como un proceso persistente si el cliente lo lanza directamente, pero **debe conocer la ruta de la base de datos** para estar sincronizado con la Web UI.

- **Variable Crítica**: `TASK_MANAGER_DB`
- **Ruta Recomendada**: Usa siempre una ruta absoluta para evitar que el cliente y el servidor miren archivos distintos.

### 2. Configuración del Cliente (Client-side)
Añade el servidor a tu archivo de configuración de MCP (ej: `claude_desktop_config.json` o la configuración de tu extensión IDE):

#### Ejemplo Claude Desktop:
```json
{
  "mcpServers": {
    "padelflow-tasks": {
      "command": "python",
      "args": ["C:/ruta/a/tu/proyecto/tools/mcp_taskmanager/task-manager/mcp_server.py"],
      "env": {
        "TASK_MANAGER_DB": "C:/ruta/a/tu/proyecto/tools/mcp-dev-remote/tasks.db"
      }
    }
  }
}
```

> [!IMPORTANT]
> Asegúrate de que la ruta en `env.TASK_MANAGER_DB` sea la misma que utiliza tu servidor FastAPI de la Web UI para que los cambios se reflejen en tiempo real en el Kanban.

---

## Validación de Estado
Puedes ejecutar los tests de workflow para verificar la máquina de estados localmente:
```bash
python tests/test_workflow.py
```
