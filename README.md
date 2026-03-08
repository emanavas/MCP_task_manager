# MCP Task Manager

A lightweight, self-hosted task manager with a web GUI and an MCP (Model Context Protocol) server so AI coding agents (GitHub Copilot, Claude Desktop, Cursor…) can read and write your tasks in real time.

No external services. No npm dependencies. Runs on Node.js built-ins.

---

## Requirements

| Requirement | Version |
|---|---|
| Node.js | **22.5 or higher** (uses built-in `node:sqlite`) |

---

## Directory structure

```
MCP_task_manager/
├── task-manager/          ← GUI HTTP server
│   ├── server.mjs
│   ├── package.json
│   └── public/
│       └── index.html
└── mcp-server/            ← MCP stdio server for AI agents
    └── server.mjs
```

---

## Installation

```bash
git clone https://github.com/emanavas/MCP_task_manager.git
cd MCP_task_manager
```

No `npm install` needed — zero external dependencies.

---

## Usage

### 1 · Start the GUI server

```bash
node task-manager/server.mjs
```

Open **http://localhost:5678** in your browser.

The server creates `task-manager/tasks.db` (SQLite, WAL mode) on first run. The database is excluded from git.

#### Features
- Create groups (phases, categories) with custom colors
- Add tasks with title, notes, priority (`high / medium / low`) and status (`pending / in-progress / done`)
- Drag-and-drop reorder (groups and tasks)
- Filter by status or search by keyword — empty groups are hidden automatically
- Count badge shows `matched/total` when filtering
- Live SSE refresh — any changes made by an AI agent appear instantly in the browser

---

### 2 · Connect the MCP server to your AI agent

The MCP server communicates with the same `tasks.db` that the GUI uses, so changes from the agent show up in the browser immediately.

#### VS Code (GitHub Copilot / Claude)

Add to your `.vscode/mcp.json` (or create it):

```json
{
  "servers": {
    "mcp-task-manager": {
      "type": "stdio",
      "command": "node",
      "args": ["${workspaceFolder}/../MCP_task_manager/mcp-server/server.mjs"]
    }
  }
}
```

Adjust the path to match wherever you cloned the repo.

#### Custom DB path (use with any project)

By default the MCP server looks for `../task-manager/tasks.db` relative to `mcp-server/server.mjs`. You can point it at any database file with an environment variable:

```json
{
  "servers": {
    "mcp-task-manager": {
      "type": "stdio",
      "command": "node",
      "args": ["/absolute/path/to/mcp-server/server.mjs"],
      "env": {
        "MCP_TASKS_DB": "/absolute/path/to/your/tasks.db",
        "MCP_TASKS_NAME": "my-project-tasks"
      }
    }
  }
}
```

#### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-task-manager": {
      "command": "node",
      "args": ["/absolute/path/to/MCP_task_manager/mcp-server/server.mjs"]
    }
  }
}
```

---

## Available MCP tools

| Tool | Description |
|---|---|
| `tasks_pending` | List all pending tasks. Optional `priority` filter. Call at session start. |
| `tasks_list` | List tasks with optional `phase`, `status`, `priority` filters. |
| `tasks_add` | Add a new task. Params: `title` (required), `id`, `phase`, `priority`, `notes`. |
| `tasks_update` | Update `status`, `priority`, or `notes` of an existing task by `id`. |
| `tasks_complete` | Mark a task as done by `id`. |
| `tasks_stats` | Summary count: total, done, in-progress, pending, high-priority pending. |

### Recommended agent workflow

```
Session start  → tasks_pending()           # see what needs doing
Before task    → tasks_update(in-progress) # signal you're working on it
After task     → tasks_complete(id)        # mark done immediately
New task found → tasks_add(...)            # add to backlog
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MCP_TASKS_DB` | `../task-manager/tasks.db` | Absolute path to a custom `tasks.db` |
| `MCP_TASKS_NAME` | `mcp-task-manager` | Server name reported in MCP `initialize` response |

---

## Tech stack

- **Node.js built-ins only** — `node:http`, `node:sqlite`, `node:path`, `node:fs`, `node:readline`
- **SQLite WAL mode** — concurrent reads from GUI + MCP server without locks
- **Server-Sent Events** — browser auto-refreshes when agent writes tasks
- **MCP protocol 2024-11-05** — JSON-RPC over stdio

---

## License

MIT
