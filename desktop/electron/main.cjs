const { app, BrowserWindow, protocol, net, shell, screen } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const url = require('node:url');

const WWW = path.join(__dirname, '..', 'www');

// milon.html טוען את הנתונים ב-fetch עם נתיבים יחסיים. תחת file://
// הדפדפן חוסם fetch (CORS), ולכן מגישים את התוכן דרך סכמה משלנו
// שמתנהגת כמו מקור רגיל — כך אותו קוד בדיוק עובד גם באתר וגם כאן.
protocol.registerSchemesAsPrivileged([{
  scheme: 'milon',
  privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true },
}]);

// ── שמירת מיקום וגודל החלון בין הרצות ──
const boundsFile = () => path.join(app.getPath('userData'), 'window-bounds.json');
function loadBounds(){
  try { return JSON.parse(fs.readFileSync(boundsFile(), 'utf-8')); } catch { return null; }
}
function saveBounds(b){
  try { fs.writeFileSync(boundsFile(), JSON.stringify(b), 'utf-8'); } catch {}
}

function createWindow(){
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const saved = loadBounds();
  const w = saved?.width  || Math.min(1280, Math.round(width * 0.78));
  const h = saved?.height || Math.round(height * 0.88);

  const win = new BrowserWindow({
    width: w,
    height: h,
    x: saved?.x,
    y: saved?.y,
    minWidth: 380,
    minHeight: 480,
    title: 'מילון מונחים בפנימיות התורה',
    icon: path.join(__dirname, '..', 'build', 'icon.ico'),
    backgroundColor: '#4a2f17',
    autoHideMenuBar: true,
    show: false,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });

  win.once('ready-to-show', () => win.show());

  // בדיקה אוטומטית: MILON_QUERY=<שאילתה> מריץ חיפוש בתוך האפליקציה
  // הארוזה ומדפיס את התוצאות — כך אפשר לאמת שהמנוע עובד גם אחרי אריזה.
  // MILON_SUGGEST=<שאילתה> פותח את לשונית ההצעות ומצלם אותה
  if (process.env.MILON_SUGGEST) {
    win.webContents.once('did-finish-load', () => {
      setTimeout(async () => {
        try {
          await win.webContents.executeJavaScript(
            `(async () => { await ensureSearchIndex();
               runSearch(${JSON.stringify(process.env.MILON_SUGGEST)});
               await new Promise(r => setTimeout(r, 400));
               openSuggestTab(${JSON.stringify(process.env.MILON_SUGGEST)}); })()`);
          await new Promise(r => setTimeout(r, 900));
          const img = await win.webContents.capturePage();
          fs.writeFileSync(process.env.MILON_SHOT || 'suggest.png', img.toPNG());
          console.log('SUGGEST_OK');
        } catch (e) { console.log('SUGGEST_FAIL ' + e.message); }
        app.quit();
      }, 3500);
    });
  }

  if (process.env.MILON_QUERY) {
    win.webContents.once('did-finish-load', () => {
      setTimeout(async () => {
        try {
          const q = JSON.stringify(process.env.MILON_QUERY);
          const r = await win.webContents.executeJavaScript(
            `(async () => { await ensureSearchIndex();
               const t0 = performance.now();
               const r = runEngine(searchIx, ${q}, true);
               return { n: r.results.length, ms: +(performance.now() - t0).toFixed(2),
                 top: r.results.slice(0,5).map(x => searchData.entries[x.ei].t),
                 entries: searchData.entries.length }; })()`);
          console.log('QUERY_OK ' + JSON.stringify(r));
        } catch (e) { console.log('QUERY_FAIL ' + e.message); }
        app.quit();
      }, 3000);
    });
  }

  // בדיקה אוטומטית: MILON_SHOT=<קובץ> מצלם את החלון אחרי הטעינה ויוצא.
  // מאפשר לאמת רינדור בלי צילום מסך של מערכת ההפעלה.
  if (process.env.MILON_SHOT) {
    win.webContents.once('did-finish-load', () => {
      setTimeout(async () => {
        try {
          const img = await win.webContents.capturePage();
          fs.writeFileSync(process.env.MILON_SHOT, img.toPNG());
          console.log('SHOT_OK ' + process.env.MILON_SHOT);
        } catch (e) { console.error('SHOT_FAIL ' + e.message); }
        app.quit();
      }, Number(process.env.MILON_SHOT_DELAY || 4000));
    });
  }
  win.loadURL('milon://app/index.html');

  let t;
  const persist = () => {
    clearTimeout(t);
    t = setTimeout(() => {
      if (!win.isMinimized() && !win.isMaximized()) saveBounds(win.getBounds());
    }, 400);
  };
  win.on('move', persist);
  win.on('resize', persist);

  // קישורים חיצוניים (mailto וכד') ייפתחו בתוכנה של המערכת, לא בחלון האפליקציה
  win.webContents.setWindowOpenHandler(({ url: u }) => { shell.openExternal(u); return { action: 'deny' }; });
  win.webContents.on('will-navigate', (e, u) => {
    if (!u.startsWith('milon://')) { e.preventDefault(); shell.openExternal(u); }
  });

  win.webContents.on('before-input-event', (_e, input) => {
    if (input.type === 'keyDown' &&
        (input.key === 'F12' || (input.control && input.shift && input.key.toLowerCase() === 'i'))) {
      win.webContents.toggleDevTools();
    }
  });
}

app.whenReady().then(() => {
  protocol.handle('milon', (req) => {
    // milon://app/<path> -> www/<path>, עם חסימת יציאה מהתיקייה
    const p = decodeURIComponent(new URL(req.url).pathname);
    const target = path.normalize(path.join(WWW, p));
    if (!target.startsWith(WWW)) return new Response('forbidden', { status: 403 });
    return net.fetch(url.pathToFileURL(target).toString());
  });
  createWindow();
});

app.on('window-all-closed', () => app.quit());
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
