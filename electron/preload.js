const { contextBridge } = require('electron');

// Puente seguro entre el renderer (React) y Electron.
// Por ahora solo expone metadatos; aquí se añadirán APIs nativas si se necesitan
// (notificaciones de escritorio, guardado de archivos, etc.).
contextBridge.exposeInMainWorld('cryptoSniper', {
  isElectron: true,
  platform: process.platform,
  version: process.versions.electron,
});
