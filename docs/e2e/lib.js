// Công cụ test giao diện: điều khiển Chrome headless qua DevTools Protocol.
// Dùng WebSocket có sẵn của Node 22 trở lên, không cần cài thêm thư viện.
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = process.env.WEBDOC_URL || 'http://localhost:5173';
const OUT = path.join(__dirname, 'shots');
fs.mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const getJson = (url) =>
  new Promise((res, rej) =>
    http
      .get(url, (r) => {
        let d = '';
        r.on('data', (c) => (d += c));
        r.on('end', () => res(JSON.parse(d)));
      })
      .on('error', rej),
  );

async function open() {
  const port = 9400 + Math.floor(Math.random() * 400);
  const proc = spawn(
    CHROME,
    [
      '--headless=new', '--disable-gpu', '--disable-extensions', '--no-first-run',
      '--window-size=1600,900', `--remote-debugging-port=${port}`,
      `--user-data-dir=${process.env.TEMP}/cdp-${Date.now()}`, 'about:blank',
    ],
    { stdio: 'ignore' },
  );
  let targets;
  for (let i = 0; i < 40; i++) {
    try { targets = await getJson(`http://127.0.0.1:${port}/json`); break; } catch { await sleep(500); }
  }
  const page = targets.find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r));

  let id = 0;
  const pending = {};
  const hooks = [];
  const log = { errors: [], net: [] };
  const reqs = {};
  const send = (method, params = {}) =>
    new Promise((res) => { const i = ++id; pending[i] = res; ws.send(JSON.stringify({ id: i, method, params })); });

  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending[msg.id]) { pending[msg.id](msg.result); return; }
    const p = msg.params || {};
    hooks.forEach((h) => h(msg));
    if (msg.method === 'Runtime.exceptionThrown')
      log.errors.push('EXC ' + (p.exceptionDetails.exception?.description || p.exceptionDetails.text).split('\n')[0].slice(0, 300));
    if (msg.method === 'Runtime.consoleAPICalled' && p.type === 'error')
      log.errors.push('console.error ' + p.args.map((a) => a.value || a.description || '').join(' ').split('\n')[0].slice(0, 300));
    if (msg.method === 'Network.requestWillBeSent') reqs[p.requestId] = { m: p.request.method, body: p.request.postData };
    if (msg.method === 'Network.responseReceived' && /localhost:(8098|8000|8001)/.test(p.response.url)) {
      const r = reqs[p.requestId] || {};
      log.net.push({ status: p.response.status, method: r.m, body: r.body, url: p.response.url.replace(/https?:\/\/localhost:/, ':') });
    }
  });

  await send('Runtime.enable'); await send('Network.enable'); await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 900, deviceScaleFactor: 1, mobile: false });

  const ev = async (expr) => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result?.value;
  const q = JSON.stringify;
  // Sự kiện click mức DOM: click chuột CDP không tới được trang sau đăng nhập trong headless.
  const fire = `for(const t of ['pointerdown','mousedown','pointerup','mouseup','click']){e.dispatchEvent(new (t.startsWith('pointer')?PointerEvent:MouseEvent)(t,{bubbles:true,cancelable:true,view:window,button:0}))}`;

  const api = {
    log, ev, sleep, send, hook: (fn) => hooks.push(fn),
    clear: () => { log.errors.length = 0; log.net.length = 0; },
    url: () => ev('location.href'),
    text: async () => (await ev('document.body.innerText')) || '',
    goto: async (p, wait = 3500) => { await send('Page.navigate', { url: p.startsWith('http') ? p : BASE + p }); await sleep(wait); },
    shot: async (name) => {
      const r = await send('Page.captureScreenshot', { format: 'png' });
      const f = path.join(OUT, name + '.png');
      fs.writeFileSync(f, Buffer.from(r.data, 'base64'));
      return f;
    },
    click: async (css, text = '', idx = 0) => {
      const ok = await ev(`(()=>{const els=[...document.querySelectorAll(${q(css)})].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(${q(text)}===''||(e.textContent||e.getAttribute('aria-label')||e.title||'').includes(${q(text)}))});const e=els[${idx}];if(!e)return false;e.scrollIntoView({block:'center'});${fire}return true})()`);
      await sleep(900);
      return !!ok;
    },
    clickWithin: async (containerCss, containerText, innerCss, innerText = '') => {
      const r = await ev(`(()=>{const c=[...document.querySelectorAll(${q(containerCss)})].find(e=>(e.textContent||'').includes(${q(containerText)}));if(!c)return 'no-container';const e=[...c.querySelectorAll(${q(innerCss)})].find(e=>${q(innerText)}===''||(e.textContent||'').includes(${q(innerText)}));if(!e)return 'no-inner';e.scrollIntoView({block:'center'});${fire}return 'ok'})()`);
      await sleep(900);
      return r;
    },
    type: (css, value) => ev(`(()=>{const el=document.querySelector(${q(css)});if(!el)return false;el.focus();const s=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el),'value').set;s.call(el,${q(value)});el.dispatchEvent(new Event('input',{bubbles:true}));return true})()`),
    modal: () => ev(`(()=>{const m=[...document.querySelectorAll('.ant-modal-wrap')].filter(w=>getComputedStyle(w).display!=='none');return m.map(w=>({title:(w.querySelector('.ant-modal-title')||{}).textContent,body:((w.querySelector('.ant-modal-body')||{}).textContent||'').slice(0,200),buttons:[...w.querySelectorAll('button')].map(b=>b.textContent.trim()).filter(Boolean)}))})()`),
    toasts: () => ev(`[...document.querySelectorAll('.ant-message-notice-content,.ant-notification-notice')].map(e=>e.textContent.trim()).join(' || ')`),
    login: async (email, pw = 'Demo@123') => {
      await api.goto('/login', 3500);
      await api.type('#loginForm_username', email);
      await api.type('#loginForm_password', pw);
      await api.click('button[type=submit]');
      await sleep(5000);
    },
    close: () => { try { ws.close(); } catch { /* đã đóng */ } proc.kill(); },
  };
  return api;
}

module.exports = { open, sleep };
