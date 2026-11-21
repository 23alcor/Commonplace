// Records /stage while one capture runs through the live pipeline; logs when each step lights up.
const {chromium} = require('/tmp/claude-1000/-home-ralph/61860cab-5b32-54bb-9cfa-abd6409b4040/scratchpad/node_modules/playwright');
const fs = require('fs'), path = require('path');
const [,, file, name] = process.argv, V = path.dirname(__filename), BASE = 'http://127.0.0.1:8010';
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1,
    recordVideo: {dir: `${V}/raw/${name}`, size: {width: 1920, height: 1080}}});
  const p = await ctx.newPage(); const t0 = Date.now(); const log = [];
  p.on('pageerror', e => console.log('PAGEERR', e.message));
    log.push({ev: 'submit', t: (Date.now() - t0) / 1000});
  const r = await p.request.post(`${BASE}/capture`, {multipart: {file: {name: path.basename(file),
    mimeType: file.endsWith('.jpg') ? 'image/jpeg' : file.endsWith('.wav') ? 'audio/wav' : 'application/pdf',
    buffer: fs.readFileSync(file)}, agent_verify: 'true'}});
  const {job} = await r.json(); console.log('job', job);
  await p.goto(`${BASE}/stage?job=${job}`);
  const seen = new Set();
  for (let i = 0; i < 1800; i++) {           // up to 3 minutes
    const st = await p.evaluate(() => ({on: [...document.querySelectorAll('.step.on')].map(s => s.id),
      res: document.getElementById('result').innerText}));
    for (const id of st.on) if (!seen.has(id)) { seen.add(id); log.push({ev: id, t: (Date.now() - t0) / 1000}); }
    if (st.res && !seen.has('result')) { seen.add('result'); log.push({ev: 'result', t: (Date.now() - t0) / 1000, text: st.res}); }
    if (seen.has('result')) break;
    await p.waitForTimeout(100);
  }
  await p.waitForTimeout(4500);              // let the graph settle with the new note
  log.push({ev: 'end', t: (Date.now() - t0) / 1000});
  const vid = await p.video().path(); await ctx.close(); await b.close();
  fs.renameSync(vid, `${V}/raw/${name}.webm`);
  fs.writeFileSync(`${V}/raw/${name}.json`, JSON.stringify(log, null, 1));
  console.log(JSON.stringify(log));
})();
