#!/usr/bin/env node
/**
 * mcp-task-manager — MCP server backed by a SQLite database.
 *
 * Portable: set MCP_TASKS_DB env var to point at any project's tasks.db.
 * Default  : <this-file>/../task-manager/tasks.db
 *
 * Tools: tasks_list, tasks_pending, tasks_complete, tasks_add, tasks_update, tasks_stats
 *
 * Requires Node.js 22.5+ (built-in node:sqlite).
 */

import { join, dirname }    from 'node:path';
import { fileURLToPath }    from 'node:url';
import { existsSync }       from 'node:fs';
import * as readline        from 'node:readline';
import { DatabaseSync }     from 'node:sqlite';

const __dirname    = dirname(fileURLToPath(import.meta.url));
const DEFAULT_DB   = join(__dirname, '../task-manager/tasks.db');
const DB_PATH      = process.env.MCP_TASKS_DB ?? DEFAULT_DB;
const SERVER_NAME  = process.env.MCP_TASKS_NAME ?? 'mcp-task-manager';

if (!existsSync(DB_PATH)) {
  process.stderr.write(
    `[mcp-task-manager] ERROR: tasks.db not found at ${DB_PATH}.\n` +
    `  Set MCP_TASKS_DB env var or start the Task Manager GUI first (it runs the migration).\n`
  );
}

const db = new DatabaseSync(DB_PATH);
db.exec('PRAGMA journal_mode = WAL;');

// ── Helpers ────────────────────────────────────────────────────────────────────
function prioIcon(p)   { return p === 'high' ? '🔴' : p === 'medium' ? '🟡' : '🟢'; }
function statusIcon(s) { return s === 'done' ? '✅' : s === 'in-progress' ? '🔄' : '⬜'; }

function groupName(groupId) {
  if (!groupId) return 'Ungrouped';
  const g = db.prepare('SELECT name FROM groups WHERE id=?').get(groupId);
  return g?.name ?? 'Ungrouped';
}

function formatTask(t) {
  let line = `${statusIcon(t.status)} ${prioIcon(t.priority)} **[${t.id}]** ${t.title}\n`;
  if (t.notes) line += `   > ${t.notes}\n`;
  return line;
}

// ── Tool implementations ───────────────────────────────────────────────────────
function tasksList({ phase, status, priority } = {}) {
  let tasks = db.prepare(`
    SELECT t.* FROM tasks t
    LEFT JOIN groups g ON t.group_id = g.id
    ORDER BY
      COALESCE(g.position, 999999),
      CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
      t.position
  `).all();

  if (status)   tasks = tasks.filter(t => t.status === status);
  if (priority) tasks = tasks.filter(t => t.priority === priority);
  if (phase)    tasks = tasks.filter(t => groupName(t.group_id).toLowerCase().includes(phase.toLowerCase()));

  const total = tasks.length;
  const byGroup = {};
  for (const t of tasks) {
    const gname = groupName(t.group_id);
    (byGroup[gname] ??= []).push(t);
  }

  let out = `📋 **${total} task(s)**\n\n`;
  for (const [gname, items] of Object.entries(byGroup)) {
    out += `### ${gname}\n`;
    for (const t of items) out += formatTask(t);
    out += '\n';
  }
  return out;
}

function tasksPending({ priority } = {}) {
  return tasksList({ status: 'pending', priority });
}

function tasksComplete({ id } = {}) {
  if (!id) return '❌ id is required';
  const task = db.prepare('SELECT * FROM tasks WHERE id=?').get(id);
  if (!task) return `❌ Task not found: ${id}`;
  db.prepare("UPDATE tasks SET status='done' WHERE id=?").run(id);
  return `✅ Marked done: [${id}] ${task.title} (was: ${task.status})`;
}

function tasksAdd({ id, phase, title, priority = 'medium', notes = '' } = {}) {
  if (!title) return '❌ title is required';
  const newId = id || title.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 40);
  const exists = db.prepare('SELECT id FROM tasks WHERE id=?').get(newId);
  if (exists) return `❌ Task id already exists: ${newId}`;

  let groupId = null;
  if (phase) {
    const g = db.prepare('SELECT id FROM groups WHERE name=?').get(phase);
    if (g) {
      groupId = g.id;
    } else {
      const maxPos = db.prepare('SELECT COALESCE(MAX(position),0) as m FROM groups').get().m;
      const r = db.prepare('INSERT INTO groups (name, position) VALUES (?,?)').run(phase, maxPos + 1);
      groupId = r.lastInsertRowid;
    }
  }

  const maxPos = db.prepare('SELECT COALESCE(MAX(position),0) as m FROM tasks WHERE group_id IS ?').get(groupId).m;
  db.prepare(`
    INSERT INTO tasks (id, group_id, title, notes, status, priority, position)
    VALUES (?, ?, ?, ?, 'pending', ?, ?)
  `).run(newId, groupId, title, notes, priority, maxPos + 1);

  return `✅ Added task [${newId}]: ${title}`;
}

function tasksUpdate({ id, status, priority, notes } = {}) {
  if (!id) return '❌ id is required';
  const task = db.prepare('SELECT * FROM tasks WHERE id=?').get(id);
  if (!task) return `❌ Task not found: ${id}`;
  db.prepare('UPDATE tasks SET status=?, priority=?, notes=? WHERE id=?').run(
    status   ?? task.status,
    priority ?? task.priority,
    notes !== undefined ? notes : task.notes,
    id
  );
  const updated = db.prepare('SELECT * FROM tasks WHERE id=?').get(id);
  return `✅ Updated [${id}]: status=${updated.status}, priority=${updated.priority}`;
}

function tasksStats() {
  const total   = db.prepare('SELECT COUNT(*) as c FROM tasks').get().c;
  const done    = db.prepare("SELECT COUNT(*) as c FROM tasks WHERE status='done'").get().c;
  const pending = db.prepare("SELECT COUNT(*) as c FROM tasks WHERE status='pending'").get().c;
  const inprog  = db.prepare("SELECT COUNT(*) as c FROM tasks WHERE status='in-progress'").get().c;
  const high    = db.prepare("SELECT COUNT(*) as c FROM tasks WHERE priority='high' AND status!='done'").get().c;
  return `📊 **Task stats**\n- Total: ${total}\n- ✅ Done: ${done}\n- 🔄 In Progress: ${inprog}\n- ⬜ Pending: ${pending}\n- 🔴 High-priority pending: ${high}`;
}

// ── Tool definitions ───────────────────────────────────────────────────────────
const TOOLS = [
  {
    name: 'tasks_pending',
    description: 'List all pending/unresolved tasks. Optionally filter by priority ("high", "medium", "low"). Call this at the START of every session to review what needs doing.',
    inputSchema: {
      type: 'object',
      properties: {
        priority: { type: 'string', enum: ['high', 'medium', 'low'], description: 'Filter by priority' },
      },
    },
  },
  {
    name: 'tasks_list',
    description: 'List tasks with optional filters. Use to browse all tasks or filter by phase/status/priority.',
    inputSchema: {
      type: 'object',
      properties: {
        phase:    { type: 'string', description: 'Filter by phase name (partial match)' },
        status:   { type: 'string', enum: ['pending', 'in-progress', 'done'], description: 'Filter by status' },
        priority: { type: 'string', enum: ['high', 'medium', 'low'], description: 'Filter by priority' },
      },
    },
  },
  {
    name: 'tasks_complete',
    description: 'Mark a task as done. Call this immediately after finishing a task.',
    inputSchema: {
      type: 'object',
      required: ['id'],
      properties: {
        id: { type: 'string', description: 'The task id to mark as done' },
      },
    },
  },
  {
    name: 'tasks_add',
    description: 'Add a new task to the backlog.',
    inputSchema: {
      type: 'object',
      required: ['title'],
      properties: {
        id:       { type: 'string',  description: 'Optional slug id (auto-generated from title if omitted)' },
        phase:    { type: 'string',  description: 'Phase or category label' },
        title:    { type: 'string',  description: 'Task description' },
        priority: { type: 'string',  enum: ['high', 'medium', 'low'], description: 'Priority level' },
        notes:    { type: 'string',  description: 'Additional context or acceptance criteria' },
      },
    },
  },
  {
    name: 'tasks_update',
    description: 'Update a task status, priority, or notes.',
    inputSchema: {
      type: 'object',
      required: ['id'],
      properties: {
        id:       { type: 'string', description: 'Task id to update' },
        status:   { type: 'string', enum: ['pending', 'in-progress', 'done'], description: 'New status' },
        priority: { type: 'string', enum: ['high', 'medium', 'low'], description: 'New priority' },
        notes:    { type: 'string', description: 'Updated notes' },
      },
    },
  },
  {
    name: 'tasks_stats',
    description: 'Get a summary count of tasks by status and high-priority pending count.',
    inputSchema: { type: 'object', properties: {} },
  },
];

// ── JSON-RPC stdio server ─────────────────────────────────────────────────────
const rl = readline.createInterface({ input: process.stdin, terminal: false });

function send(obj)           { process.stdout.write(JSON.stringify(obj) + '\n'); }
function respond(id, result) { send({ jsonrpc: '2.0', id, result }); }
function rpcError(id, code, message) { send({ jsonrpc: '2.0', id, error: { code, message } }); }
function textResult(text)    { return { content: [{ type: 'text', text }] }; }

rl.on('line', (line) => {
  line = line.trim();
  if (!line) return;
  let msg;
  try { msg = JSON.parse(line); }
  catch { return; }

  const { id, method, params } = msg;

  switch (method) {
    case 'initialize':
      respond(id, {
        protocolVersion: '2024-11-05',
        capabilities: { tools: {} },
        serverInfo: { name: SERVER_NAME, version: '2.0.0' },
      });
      break;

    case 'notifications/initialized':
      break;

    case 'tools/list':
      respond(id, { tools: TOOLS });
      break;

    case 'tools/call': {
      const { name, arguments: args } = params ?? {};
      try {
        let text;
        switch (name) {
          case 'tasks_pending':   text = tasksPending(args);   break;
          case 'tasks_list':      text = tasksList(args);      break;
          case 'tasks_complete':  text = tasksComplete(args);  break;
          case 'tasks_add':       text = tasksAdd(args);       break;
          case 'tasks_update':    text = tasksUpdate(args);    break;
          case 'tasks_stats':     text = tasksStats();         break;
          default: rpcError(id, -32601, `Unknown tool: ${name}`); return;
        }
        respond(id, textResult(text));
      } catch (e) {
        respond(id, textResult(`❌ Error: ${e.message}`));
      }
      break;
    }

    default:
      if (id !== undefined) rpcError(id, -32601, `Method not found: ${method}`);
  }
});
