const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');

const isDev = process.env.NODE_ENV === 'development';
const BACKEND_PORT = 8001;
const BACKEND_HEALTH = `http://127.0.0.1:${BACKEND_PORT}/api/health`;

let mainWindow = null;
let backendProcess = null;
let staticServer = null;

// ─── Backend ───
function startBackend() {
  if (isDev) {
    // En desarrollo el backend se lanza con `npm run dev:backend`. No lo duplicamos.
    log('Modo desarrollo: backend gestionado externamente');
    return;
  }

  // En producción: ejecutable empaquetado con PyInstaller (sin Python instalado).
  const resourcesPath = process.resourcesPath;
  const exeName = process.platform === 'win32' ? 'crypto_sniper_backend.exe' : 'crypto_sniper_backend';
  const backendExe = path.join(resourcesPath, 'backend', exeName);

  if (fs.existsSync(backendExe)) {
    log(`Iniciando backend empaquetado: ${backendExe}`);
    backendProcess = spawn(backendExe, [], {
      cwd: path.join(resourcesPath, 'backend'),
      env: { ...process.env, PORT: String(BACKEND_PORT) },
    });
  } else {
    // Fallback: Python del sistema (útil si el usuario tiene Python 3.11).
    log('Backend empaquetado no encontrado, intentando Python del sistema');
    const backendDir = path.join(app.getAppPath(), '..', 'backend');
    backendProcess = spawn('py', ['-3.11', '-m', 'uvicorn', 'server:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)], {
      cwd: backendDir,
      shell: true,
    });
  }

  backendProcess.stdout?.on('data', (d) => log(`[backend] ${d}`));
  backendProcess.stderr?.on('data', (d) => log(`[backend] ${d}`));
  backendProcess.on('error', (e) => log(`[backend error] ${e.message}`));
}

// ─── Servidor estático para el frontend en producción ───
function startStaticServer() {
  return new Promise((resolve) => {
    if (isDev) {
      resolve('http://localhost:3000');
      return;
    }
    const distDir = path.join(app.getAppPath(), 'frontend', 'dist');
    const mime = {
      '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
      '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
      '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2',
    };
    staticServer = http.createServer((req, res) => {
      let urlPath = decodeURIComponent(req.url.split('?')[0]);
      let filePath = path.join(distDir, urlPath === '/' ? 'index.html' : urlPath);
      // SPA fallback: rutas desconocidas → index.html (BrowserRouter)
      if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        filePath = path.join(distDir, 'index.html');
      }
      const ext = path.extname(filePath);
      fs.readFile(filePath, (err, data) => {
        if (err) { res.writeHead(404); res.end('Not found'); return; }
        res.writeHead(200, { 'Content-Type': mime[ext] || 'application/octet-stream' });
        res.end(data);
      });
    });
    staticServer.listen(8002, '127.0.0.1', () => resolve('http://127.0.0.1:8002'));
  });
}

// ─── Espera a que el backend responda ───
function waitForBackend(retries = 60) {
  return new Promise((resolve) => {
    const check = () => {
      http.get(BACKEND_HEALTH, (res) => {
        if (res.statusCode === 200) resolve(true);
        else retry();
      }).on('error', retry);
    };
    const retry = () => {
      if (--retries <= 0) { resolve(false); return; }
      setTimeout(check, 500);
    };
    check();
  });
}

function log(msg) {
  console.log(`[main] ${msg}`);
}

// ─── Ventana ───
async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 950,
    minWidth: 1200,
    minHeight: 700,
    backgroundColor: '#09090b',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Pantalla de carga mientras arranca el backend
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));
  mainWindow.show();

  startBackend();
  const frontendUrl = await startStaticServer();
  const backendOk = await waitForBackend();

  if (!backendOk) {
    log('El backend no respondió a tiempo');
  }

  await mainWindow.loadURL(frontendUrl);

  // Abrir enlaces externos en el navegador del sistema
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on('before-quit', () => {
  if (backendProcess) {
    try { backendProcess.kill(); } catch (_) {}
  }
  if (staticServer) {
    try { staticServer.close(); } catch (_) {}
  }
});
