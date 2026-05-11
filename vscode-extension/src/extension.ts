/**
 * builder-bridge — a thin localhost HTTP shim that lets the builder Python CLI use
 * GitHub Copilot models via vscode.lm.
 *
 * Binds 127.0.0.1 only. Writes its port to ~/.builder/bridge.port so the CLI can
 * discover it. Triggers VS Code's vscode.lm consent dialog the first time a
 * model is requested.
 *
 * Endpoints:
 *   GET  /healthz             → {"ok": true, "version": "0.1.0"}
 *   GET  /v1/models           → list available copilot models
 *   POST /v1/chat             → {model, messages, max_tokens, temperature} → {text}
 */

import * as vscode from 'vscode';
import * as http from 'node:http';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { spawn } from 'node:child_process';

const VERSION    = '0.1.0';
const PORT_FILE  = path.join(os.homedir(), '.builder', 'bridge.port');

let server: http.Server | undefined;
let statusBar: vscode.StatusBarItem | undefined;


export function activate(context: vscode.ExtensionContext): void {
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBar.command = 'builderBridge.showStatus';
  context.subscriptions.push(statusBar);

  context.subscriptions.push(
    vscode.commands.registerCommand('builderBridge.showStatus', showStatus),
    vscode.commands.registerCommand('builderBridge.restart', () => {
      stopServer();
      startServer();
    }),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('builderBridge.port')) {
        stopServer();
        startServer();
      }
    }),
  );

  startServer();
}


export function deactivate(): void {
  runSignalCollector();
  stopServer();
}


/**
 * Best-effort: invoke the builder signal_collector when the bridge shuts down.
 * Acts as a backstop for chat.hooks.postSession (which only fires on chat
 * session end, not on full VS Code shutdown).
 *
 * Looks for the collector relative to the active workspace folder. Silent on
 * failure — collector is allowed to be absent (unbuilt shadow/) or to error.
 */
function runSignalCollector(): void {
  try {
    const folder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (!folder) return;

    const collector = path.join(
      folder,
      'shadow', 'signal_collector', 'artifacts', 'signal_collector', 'skill', 'main.py',
    );
    if (!fs.existsSync(collector)) return;

    const py = process.platform === 'win32'
      ? path.join(folder, '.venv', 'Scripts', 'python.exe')
      : path.join(folder, '.venv', 'bin', 'python');
    const pyCmd = fs.existsSync(py) ? py : 'python';

    const env = {
      ...process.env,
      AGENTS_SHADOW_ROOT: process.env.AGENTS_SHADOW_ROOT || path.join(folder, 'shadow'),
    };

    // Detached + unref'd: don't block VS Code shutdown waiting for the collector.
    const child = spawn(pyCmd, [collector], { detached: true, stdio: 'ignore', env });
    child.unref();
  } catch {
    // Best-effort — swallow.
  }
}


function startServer(): void {
  const port = vscode.workspace.getConfiguration('builderBridge').get<number>('port', 21847);

  server = http.createServer(handleRequest);
  server.on('error', (err: NodeJS.ErrnoException) => {
    if (err.code === 'EADDRINUSE') {
      vscode.window.showErrorMessage(
        `builder bridge: port ${port} already in use. Change builderBridge.port in settings.`,
      );
    } else {
      vscode.window.showErrorMessage(`builder bridge error: ${err.message}`);
    }
    setStatus('error', `:${port}`);
  });
  server.listen(port, '127.0.0.1', () => {
    writePortFile(port);
    setStatus('ok', `:${port}`);
  });
}


function stopServer(): void {
  if (server) {
    server.close();
    server = undefined;
  }
  try { fs.unlinkSync(PORT_FILE); } catch { /* ignore */ }
  setStatus('off', '');
}


function setStatus(state: 'ok' | 'off' | 'error', detail: string): void {
  if (!statusBar) return;
  const icon = state === 'ok' ? '$(plug)' : state === 'error' ? '$(error)' : '$(circle-slash)';
  statusBar.text = `${icon} builder ${detail}`;
  statusBar.tooltip = `builder-bridge ${VERSION} — ${state}${detail}`;
  statusBar.show();
}


function showStatus(): void {
  const port = vscode.workspace.getConfiguration('builderBridge').get<number>('port', 21847);
  const url  = `http://127.0.0.1:${port}`;
  vscode.window.showInformationMessage(`builder bridge ${VERSION} listening at ${url}`);
}


function writePortFile(port: number): void {
  try {
    fs.mkdirSync(path.dirname(PORT_FILE), { recursive: true });
    fs.writeFileSync(PORT_FILE, String(port), { mode: 0o600 });
  } catch (e) {
    console.warn('builder bridge: could not write port file:', e);
  }
}


// --- HTTP handler ---------------------------------------------------------

function handleRequest(req: http.IncomingMessage, res: http.ServerResponse): void {
  // Localhost-only is enforced by listen('127.0.0.1') above, but double-check
  // remoteAddress for paranoia.
  const remote = req.socket.remoteAddress;
  if (remote !== '127.0.0.1' && remote !== '::1' && remote !== '::ffff:127.0.0.1') {
    res.writeHead(403, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'forbidden: non-localhost' }));
    return;
  }

  const url = req.url ?? '/';

  if (req.method === 'GET' && url === '/healthz') {
    return json(res, 200, { ok: true, version: VERSION });
  }

  if (req.method === 'GET' && url === '/v1/models') {
    Promise.resolve(vscode.lm.selectChatModels({ vendor: 'copilot' }))
      .then((models) => json(res, 200, {
        models: models.map((m) => ({
          vendor: m.vendor,
          family: m.family,
          name: m.name,
          maxInputTokens: m.maxInputTokens,
        })),
      }))
      .catch((e: Error) => json(res, 500, { error: e.message }));
    return;
  }

  if (req.method === 'POST' && url === '/v1/chat') {
    readBody(req).then(async (body) => {
      try {
        const payload = JSON.parse(body || '{}');
        const text = await runChat(payload);
        json(res, 200, { text });
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        json(res, 500, { error: msg });
      }
    });
    return;
  }

  json(res, 404, { error: `unknown route ${req.method} ${url}` });
}


function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let buf = '';
    req.setEncoding('utf-8');
    req.on('data', (chunk) => { buf += chunk; });
    req.on('end', () => resolve(buf));
    req.on('error', reject);
  });
}


function json(res: http.ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}


// --- chat dispatch -------------------------------------------------------

interface ChatRequest {
  model?:       string;
  messages:     { role: string; content: string }[];
  max_tokens?:  number;
  temperature?: number;
}

async function runChat(req: ChatRequest): Promise<string> {
  if (!Array.isArray(req.messages) || req.messages.length === 0) {
    throw new Error('messages array is required and must not be empty');
  }

  const defaultFamily = vscode.workspace
    .getConfiguration('builderBridge')
    .get<string>('defaultFamily', 'claude-sonnet-4.6');
  const family = req.model || defaultFamily;

  const [model] = await vscode.lm.selectChatModels({ vendor: 'copilot', family });
  if (!model) {
    const available = await vscode.lm.selectChatModels({ vendor: 'copilot' });
    const familyList = available.map((m) => m.family).join(', ') || '(none)';
    throw new Error(
      `no copilot model matched family=${family}. Available families: ${familyList}`,
    );
  }

  const lmMessages = req.messages.map((m) => {
    if (m.role === 'user') {
      return vscode.LanguageModelChatMessage.User(m.content);
    }
    // Treat everything else as assistant. vscode.lm has only User and Assistant.
    return vscode.LanguageModelChatMessage.Assistant(m.content);
  });

  const cts = new vscode.CancellationTokenSource();
  try {
    const response = await model.sendRequest(lmMessages, {}, cts.token);
    let text = '';
    for await (const fragment of response.text) {
      text += fragment;
    }
    return text;
  } finally {
    cts.dispose();
  }
}
