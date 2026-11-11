import fs from 'node:fs/promises';
import sharp from 'file:///C:/Users/Utkarsh%20Jaiswal/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp/dist/index.cjs';
const source='.studenthub-build/gcet-logo.jpeg';const target='.studenthub-build/gcet-logo-transparent.png';
const {data,info}=await sharp(source).ensureAlpha().raw().toBuffer({resolveWithObject:true});
for(let i=0;i<data.length;i+=4){const m=Math.min(data[i],data[i+1],data[i+2]);const M=Math.max(data[i],data[i+1],data[i+2]);if(m>160&&M-m<40){data[i+3]=0;data[i]=data[i+1]=data[i+2]=0;}else if(m>220){const a=255-m;data[i+3]=a;for(let c=0;c<3;c++)data[i+c]=a?Math.max(0,Math.min(255,Math.round((data[i+c]-m)*255/a))):0;}}
await sharp(data,{raw:{width:info.width,height:info.height,channels:4}}).png().toFile(target);console.log(target,info.width,info.height);


