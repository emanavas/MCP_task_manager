/**
 * MCP Task Manager — HTTP Server
 * Shared SQLite DB at tools/task-manager/tasks.db
 * Used by both this GUI and tools/mcp-tasks/server.mjs
 */
import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';
import { spawnSync } from 'node:child_process';

const __dir   = dirname(fileURLToPath(import.meta.url));
export const DB_PATH   = join(__dir, 'tasks.db');
const TASKS_JSON = join(__dir, '../mcp-tasks/tasks.json');
const PORT    = 5678;

// ── Database setup ─────────────────────────────────────────────────────────────
export const db = new DatabaseSync(DB_PATH);
db.exec('PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;');

db.exec(`
  CREATE TABLE IF NOT EXISTS groups (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT    NOT NULL,
    color     TEXT    NOT NULL DEFAULT '#6366f1',
    position  INTEGER NOT NULL DEFAULT 0,
    collapsed INTEGER NOT NULL DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS tasks (
    id        TEXT    PRIMARY KEY,
    group_id  INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    title     TEXT    NOT NULL,
    notes     TEXT    NOT NULL DEFAULT '',
    status    TEXT    NOT NULL DEFAULT 'pending',
    priority  TEXT    NOT NULL DEFAULT 'medium',
    position  INTEGER NOT NULL DEFAULT 0,
    created   TEXT    NOT NULL DEFAULT (datetime('now'))
  );
`);

// ── Migrate from tasks.json (runs once if DB is empty) ───────────────────────
const taskCount = db.prepare('SELECT COUNT(*) as c FROM tasks').get().c;
if (taskCount === 0 && existsSync(TASKS_JSON)) {
  const raw = JSON.parse(readFileSync(TASKS_JSON, 'utf8'));
  const phases = [...new Set(raw.map(t => t.phase).filter(Boolean))];

  const phaseColors = {
    'Phase 1':    '#10b981',
    'Phase 2':    '#3b82f6',
    'Phase 3':    '#8b5cf6',
    'Phase 4':    '#f59e0b',
    'Phase 5':    '#ef4444',
    'Phase 6':    '#06b6d4',
    'Deployment': '#f97316',
    'UI/UX':      '#ec4899',
    'Templates':  '#84cc16',
    'Manual':     '#94a3b8',
  };

  const insertGroup = db.prepare(
    'INSERT INTO groups (name, color, position) VALUES (?, ?, ?)'
  );
  const groupMap = {};
  phases.forEach((phase, i) => {
    const color = Object.entries(phaseColors).find(([k]) => phase.includes(k))?.[1] ?? '#6366f1';
    const r = insertGroup.run(phase, color, i);
    groupMap[phase] = r.lastInsertRowid;
  });

  const insertTask = db.prepare(`
    INSERT INTO tasks (id, group_id, title, notes, status, priority, position)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  const posCounters = {};
  raw.forEach(t => {
    const gid = groupMap[t.phase] ?? null;
    const key = String(gid);
    if (!posCounters[key]) posCounters[key] = 0;
    const rawStatus = (t.status === 'done' || t.status === 'in-progress') ? t.status : 'pending';
    insertTask.run(
      t.id, gid, t.title, t.notes ?? '',
      rawStatus, t.priority ?? 'medium', posCounters[key]++
    );
  });

  console.log(`✅  Migrated ${raw.length} tasks from tasks.json → tasks.db`);
}

// ── Utility helpers ────────────────────────────────────────────────────────────
function json(res, data, status = 200) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
  });
  res.end(JSON.stringify(data));
}

// ── SSE live-push ─────────────────────────────────────────────────────────────
const sseClients = new Set();

function broadcastRefresh() {
  for (const res of sseClients) {
    try { res.write('event: refresh\ndata: 1\n\n'); } catch { sseClients.delete(res); }
  }
}

// Poll DB mtime every 500ms — fs.watch is unreliable on Windows + SQLite WAL
// (WAL writes don't always update the main file, so watch events never fire)
let _lastMtime = 0;
let _watchTimer = null;
function scheduleRefresh() {
  clearTimeout(_watchTimer);
  _watchTimer = setTimeout(broadcastRefresh, 120);
}

function parseBody(req) {
  return new Promise(resolve => {
    let buf = '';
    req.on('data', c => (buf += c));
    req.on('end', () => {
      try { resolve(JSON.parse(buf)); } catch { resolve({}); }
    });
  });
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'text/javascript',
  '.css':  'text/css',
  '.svg':  'image/svg+xml',
  '.ico':  'image/x-icon',
  '.png':  'image/png',
};

// ── HTTP Server ────────────────────────────────────────────────────────────────
const server = createServer(async (req, res) => {
  const url    = new URL(req.url, `http://localhost:${PORT}`);
  const path   = url.pathname;
  const method = req.method;

  // CORS preflight
  if (method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin':  '*',
      'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    res.end();
    return;
  }

  // ── GET /api/events — SSE live push ─────────────────────────────────────────
  if (path === '/api/events' && method === 'GET') {
    res.writeHead(200, {
      'Content-Type':  'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection':    'keep-alive',
      'Access-Control-Allow-Origin': '*',
    });
    res.write(':ok\n\n'); // initial handshake
    sseClients.add(res);
    req.on('close', () => sseClients.delete(res));
    return;
  }

  // ── Static files ─────────────────────────────────────────────────────────────
  if (!path.startsWith('/api')) {
    const filePath = join(__dir, 'public', path === '/' ? 'index.html' : path);
    if (existsSync(filePath) && statSync(filePath).isFile()) {
      const ext = extname(filePath);
      res.writeHead(200, { 'Content-Type': MIME[ext] ?? 'text/plain' });
      res.end(readFileSync(filePath));
    } else {
      res.writeHead(302, { Location: '/' });
      res.end();
    }
    return;
  }

  // ── GET /api/data — bulk load ─────────────────────────────────────────────────
  if (path === '/api/data' && method === 'GET') {
    const groups = db.prepare('SELECT * FROM groups ORDER BY position').all();
    const tasks  = db.prepare(`
      SELECT t.* FROM tasks t
      LEFT JOIN groups g ON t.group_id = g.id
      ORDER BY
        COALESCE(g.position, 999999),
        CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
        t.position
    `).all();
    return json(res, { groups, tasks });
  }

  // ── GET /api/stats ────────────────────────────────────────────────────────────
  if (path === '/api/stats' && method === 'GET') {
    const total      = db.prepare("SELECT COUNT(*) as c FROM tasks").get().c;
    const done       = db.prepare("SELECT COUNT(*) as c FROM tasks WHERE status='done'").get().c;
    const inProgress = db.prepare("SELECT COUNT(*) as c FROM tasks WHERE status='in-progress'").get().c;
    const pending    = db.prepare("SELECT COUNT(*) as c FROM tasks WHERE status='pending'").get().c;
    const high       = db.prepare("SELECT COUNT(*) as c FROM tasks WHERE priority='high' AND status!='done'").get().c;
    return json(res, { total, done, inProgress, pending, high });
  }

  // ── POST /api/groups ──────────────────────────────────────────────────────────
  if (path === '/api/groups' && method === 'POST') {
    const body   = await parseBody(req);
    const maxPos = db.prepare('SELECT COALESCE(MAX(position),0) as m FROM groups').get().m;
    const r = db.prepare(
      'INSERT INTO groups (name, color, position) VALUES (?,?,?)'
    ).run(body.name ?? 'New Group', body.color ?? '#6366f1', maxPos + 1);
    return json(res, db.prepare('SELECT * FROM groups WHERE id=?').get(r.lastInsertRowid), 201);
  }

  // ── PUT /api/groups/:id ───────────────────────────────────────────────────────
  const groupMatch = path.match(/^\/api\/groups\/(\d+)$/);
  if (groupMatch && method === 'PUT') {
    const body = await parseBody(req);
    const g    = db.prepare('SELECT * FROM groups WHERE id=?').get(+groupMatch[1]);
    if (!g) return json(res, { error: 'Not found' }, 404);
    db.prepare('UPDATE groups SET name=?,color=?,collapsed=? WHERE id=?').run(
      body.name      ?? g.name,
      body.color     ?? g.color,
      body.collapsed ?? g.collapsed,
      g.id
    );
    return json(res, db.prepare('SELECT * FROM groups WHERE id=?').get(g.id));
  }

  // ── DELETE /api/groups/:id ────────────────────────────────────────────────────
  if (groupMatch && method === 'DELETE') {
    const id = +groupMatch[1];
    db.prepare('UPDATE tasks SET group_id=NULL WHERE group_id=?').run(id);
    db.prepare('DELETE FROM groups WHERE id=?').run(id);
    return json(res, { ok: true });
  }

  // ── POST /api/tasks ───────────────────────────────────────────────────────────
  if (path === '/api/tasks' && method === 'POST') {
    const body = await parseBody(req);
    const id   = body.id ?? `task-${Date.now()}`;
    const gid  = body.group_id ?? null;
    const maxPos = db.prepare(
      'SELECT COALESCE(MAX(position),0) as m FROM tasks WHERE group_id IS ?'
    ).get(gid).m;
    db.prepare(`
      INSERT INTO tasks (id, group_id, title, notes, status, priority, position)
      VALUES (?,?,?,?,?,?,?)
    `).run(id, gid, body.title ?? 'New task', body.notes ?? '',
           body.status ?? 'pending', body.priority ?? 'medium', maxPos + 1);
    return json(res, db.prepare('SELECT * FROM tasks WHERE id=?').get(id), 201);
  }

  // ── PUT /api/tasks/:id ────────────────────────────────────────────────────────
  const taskMatch = path.match(/^\/api\/tasks\/([^/]+)$/);
  if (taskMatch && method === 'PUT') {
    const body = await parseBody(req);
    const t    = db.prepare('SELECT * FROM tasks WHERE id=?').get(taskMatch[1]);
    if (!t) return json(res, { error: 'Not found' }, 404);
    db.prepare(`
      UPDATE tasks SET title=?,notes=?,status=?,priority=?,group_id=? WHERE id=?
    `).run(
      body.title    ?? t.title,
      body.notes    ?? t.notes,
      body.status   ?? t.status,
      body.priority ?? t.priority,
      'group_id' in body ? body.group_id : t.group_id,
      t.id
    );
    return json(res, db.prepare('SELECT * FROM tasks WHERE id=?').get(t.id));
  }

  // ── DELETE /api/tasks/:id ─────────────────────────────────────────────────────
  if (taskMatch && method === 'DELETE') {
    db.prepare('DELETE FROM tasks WHERE id=?').run(taskMatch[1]);
    return json(res, { ok: true });
  }

  // ── POST /api/reorder/tasks ───────────────────────────────────────────────────
  if (path === '/api/reorder/tasks' && method === 'POST') {
    const body   = await parseBody(req);
    const update = db.prepare('UPDATE tasks SET group_id=?,position=? WHERE id=?');
    db.exec('BEGIN');
    try {
      body.items.forEach(i => update.run(i.group_id, i.position, i.id));
      db.exec('COMMIT');
    } catch (e) {
      db.exec('ROLLBACK');
      return json(res, { error: e.message }, 500);
    }
    return json(res, { ok: true });
  }

  // ── POST /api/reorder/groups ──────────────────────────────────────────────────
  if (path === '/api/reorder/groups' && method === 'POST') {
    const body   = await parseBody(req);
    const update = db.prepare('UPDATE groups SET position=? WHERE id=?');
    db.exec('BEGIN');
    try {
      body.items.forEach(i => update.run(i.position, i.id));
      db.exec('COMMIT');
    } catch (e) {
      db.exec('ROLLBACK');
      return json(res, { error: e.message }, 500);
    }
    return json(res, { ok: true });
  }

  json(res, { error: `${method} ${path} not found` }, 404);
});

server.listen(PORT, () => {
  console.log(`\n┌─────────────────────────────────────────────┐`);
  console.log(`│  🚀  MCP Task Manager                       │`);
  console.log(`│      http://localhost:${PORT}                  │`);
  console.log(`└─────────────────────────────────────────────┘\n`);

  // Poll DB + WAL mtime every 500ms — WAL mode writes go to .db-wal first,
  // so we must watch both files to catch MCP writes before checkpoint.
  _lastMtime = existsSync(DB_PATH) ? statSync(DB_PATH).mtimeMs : 0;
  let _lastWalMtime = existsSync(DB_PATH + '-wal') ? statSync(DB_PATH + '-wal').mtimeMs : 0;
  setInterval(() => {
    try {
      const mtime    = existsSync(DB_PATH)         ? statSync(DB_PATH).mtimeMs         : 0;
      const walMtime = existsSync(DB_PATH + '-wal') ? statSync(DB_PATH + '-wal').mtimeMs : 0;
      if (mtime !== _lastMtime || walMtime !== _lastWalMtime) {
        _lastMtime    = mtime;
        _lastWalMtime = walMtime;
        scheduleRefresh();
      }
    } catch { /* DB not ready */ }
  }, 500);
});
