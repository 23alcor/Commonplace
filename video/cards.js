const {chromium} = require('/tmp/claude-1000/-home-ralph/61860cab-5b32-54bb-9cfa-abd6409b4040/scratchpad/node_modules/playwright');
const fs=require('fs'), V=__dirname, [,, src, card, secs] = process.argv;
(async()=>{const b=await chromium.launch();
 const ctx=await b.newContext({viewport:{width:1920,height:1080},recordVideo:{dir:`${V}/raw/tmp_${card}`,size:{width:1920,height:1080}}});
 const p=await ctx.newPage(); await p.goto(`file://${V}/${src}#${card}`); await p.waitForTimeout(secs*1000);
 const v=await p.video().path(); await ctx.close(); await b.close(); fs.renameSync(v,`${V}/raw/card_${card}.webm`);})();
