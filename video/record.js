// Records /stage while one capture runs through the live pipeline; logs when each step lights up.
const {chromium} = require('playwright');
const fs = require('fs'), path = require('path');
const [,, file, name] = process.argv, V = path.dirname(__filename), BASE = 'http://127.0.0.1:8010';
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1,
    recordVideo: {dir: `${V}/raw/${name}`, size: {width: 1920, height: 1080}}});
  // phone preview: the real capture page at iPhone size, recorded on the same clock as /stage
  const pctx = await b.newContext({viewport: {width: 390, height: 844}, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    recordVideo: {dir: `${V}/raw/${name}_phone`, size: {width: 390, height: 844}}});
  const p = await ctx.newPage(), ph = await pctx.newPage(); const t0 = Date.now(); const log = [];
  p.on('pageerror', e => console.log('PAGEERR', e.message));
  await ph.goto(`${BASE}/`); await ph.waitForTimeout(800);
  log.push({ev: 'submit', t: (Date.now() - t0) / 1000});
  const resp = ph.waitForResponse(r => r.url().endsWith('/capture') && r.request().method() === 'POST');
  await ph.setInputFiles('#snap', file);
  const {job} = await (await resp).json(); console.log('job', job);
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
  const vid = await p.video().path(), pvid = await ph.video().path();
  await ctx.close(); await pctx.close(); await b.close();
  fs.renameSync(pvid, `${V}/raw/${name}_phone.webm`);
  fs.renameSync(vid, `${V}/raw/${name}.webm`);
  fs.writeFileSync(`${V}/raw/${name}.json`, JSON.stringify(log, null, 1));
  console.log(JSON.stringify(log));
})();
