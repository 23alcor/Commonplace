const {chromium} = require('playwright');
const fs=require('fs'), V=__dirname, [,, src, card, secs] = process.argv;
(async()=>{const b=await chromium.launch();
 const ctx=await b.newContext({viewport:{width:1920,height:1080},recordVideo:{dir:`${V}/raw/tmp_${card}`,size:{width:1920,height:1080}}});
 const p=await ctx.newPage(); await p.goto(`file://${V}/${src}#${card}`); await p.waitForTimeout(secs*1000);
 const v=await p.video().path(); await ctx.close(); await b.close(); fs.renameSync(v,`${V}/raw/card_${card}.webm`);})();
