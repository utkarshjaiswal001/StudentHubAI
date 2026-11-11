import fs from 'node:fs/promises';
import path from 'node:path';
import { Presentation, PresentationFile } from 'file:///C:/Users/Utkarsh%20Jaiswal/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
import { pathToFileURL } from 'node:url';
const workspaceDir = 'D:/Student Hub ( PROJECT )';
const buildDir = path.join(workspaceDir,'tools');
const finalPath = path.join(workspaceDir,'docs','submission','StudentHub_Project_Presentation.pptx');
const W=1280,H=720;
const C={navy:'#102A43',teal:'#087E8B',mint:'#D9F3EE',paper:'#F7F8F5',white:'#FFFFFF',ink:'#183B56',muted:'#526777',gold:'#F2B544',light:'#E8F0F2'};
const p=Presentation.create({slideSize:{width:W,height:H}});
function box(s,x,y,w,h,fill,geometry='rect',lineFill='none') { return s.shapes.add({geometry,position:{left:x,top:y,width:w,height:h},fill,line:{style:'solid',fill:lineFill,width:lineFill==='none'?0:1}}); }
function txt(s,str,x,y,w,h,size,color,bold=false){let t=box(s,x,y,w,h,'none','textbox');t.text=str;t.text.style={fontFamily:'Aptos',fontSize:size,color,bold};return t;}
function base(kicker,title,sub='') { const s=p.slides.add(); s.background.fill=C.paper; box(s,0,0,W,16,C.teal); txt(s,kicker.toUpperCase(),72,48,700,26,15,C.teal,true); txt(s,title,72,84,1120,70,38,C.navy,true); if(sub)txt(s,sub,72,157,1100,54,20,C.muted,false); return s; }
function footer(s,n){txt(s,'STUDENTHUB AI  •  UTKARSH JAISWAL',72,676,680,18,12,C.muted,true);txt(s,String(n).padStart(2,'0'),1170,674,40,20,13,C.teal,true);}
function bullet(s,title,body,x,y,w){txt(s,title,x,y,w,32,24,C.navy,true);txt(s,body,x,y+38,w,64,18,C.muted,false);}
// 1
{const s=p.slides.add();s.background.fill=C.navy;box(s,840,0,440,H,C.teal);box(s,840,0,22,H,C.gold);txt(s,'STUDENT PROJECT  /  2026',78,85,680,25,16,C.mint,true);txt(s,'StudentHub AI',78,160,700,82,56,C.white,true);txt(s,'An overview of the current web application',82,265,685,118,29,C.mint,false);box(s,82,442,74,6,C.gold);txt(s,'College project presentation',82,480,720,50,23,C.white,false);txt(s,'Presented by Utkarsh Jaiswal',82,620,600,30,18,C.mint,false);txt(s,'01',1190,665,40,20,13,C.white,true);}
// 2
{const s=base('Project overview','Problem statement','Students need a practical way to find subject notes and get initial career guidance.');box(s,72,250,1136,2,C.teal);bullet(s,'Study materials','Notes can be hard to find when they are shared across different places.',72,292,500);bullet(s,'Career questions','Students may need help deciding what to learn or how to prepare.',680,292,500);bullet(s,'Project objective','Build one web app with a notes library and a career guidance tool.',72,440,500);txt(s,'Objective',680,446,460,24,16,C.teal,true);txt(s,'Make common study resources and basic guidance easier to access.',680,479,500,86,25,C.navy,true);footer(s,2);}
// 3
{const s=base('What it does','Main modules','The working version includes these features.');txt(s,'01',80,255,70,48,32,C.teal,true);bullet(s,'Course notes library','Browse by year, branch and subject; preview or download PDFs.',170,246,900);box(s,72,355,1136,1,'#C7D8DD');txt(s,'02',80,390,70,48,32,C.teal,true);bullet(s,'AI Career Mentor','Save conversations locally; request an AI reply when configured.',170,381,900);box(s,72,492,1136,1,'#C7D8DD');txt(s,'03',80,530,70,48,32,C.teal,true);bullet(s,'Quick Help','Get local answers to common subject questions or find notes.',170,521,900);footer(s,3);}
// 4
{const s=base('Product flow','How the application works','Users register and sign in before accessing the notes library and Mentor.');const steps=[['1','Register','Create a student account'],['2','Choose','Browse notes by course'],['3','Study','Preview or download PDFs'],['4','Ask','Use Quick Help or Mentor']];for(let i=0;i<4;i++){let x=74+i*292;txt(s,steps[i][0],x,290,60,64,42,C.teal,true);box(s,x,367,215,4,i===0?C.gold:C.teal);txt(s,steps[i][1],x,395,225,36,24,C.navy,true);txt(s,steps[i][2],x,440,230,70,18,C.muted,false);}txt(s,'Built with Flask • SQLite • HTML/CSS/JavaScript',74,575,900,30,18,C.ink,true);footer(s,4);}
// 5
{const s=base('AI approach','AI Career Mentor','Students can save a question locally and choose whether to request an AI response.');bullet(s,'Quick Help stays local','Common subject answers and note search run inside the app.',80,270,490);bullet(s,'Mentor replies are optional','AI replies require an API key and an explicit sharing choice.',680,270,510);box(s,72,414,1136,2,C.teal);txt(s,'Technical details',80,452,430,38,25,C.navy,true);txt(s,'The app uses Flask and SQLite. AI responses need an API key. Quick Help uses local answers and does not call the AI service.',80,503,1050,92,19,C.muted,false);footer(s,5);}
// 6
{const s=base('Roadmap','Future scope','These are ideas for a later version, not completed features.');const items=[['Resume analyzer','Review resumes and improve role fit'],['Mock interviews','Practice technical and HR questions'],['Internships','Discover relevant opportunities'],['Progress tracking','Track preparation over time'],['Company prep','Prepare for target employers'],['Coding practice','Build technical problem solving']];for(let i=0;i<6;i++){let col=i%2,row=Math.floor(i/2),x=78+col*570,y=262+row*112;txt(s,items[i][0],x,y,480,31,22,C.navy,true);txt(s,items[i][1],x,y+38,490,46,17,C.muted,false);if(row<2)box(s,x,y+88,500,1,'#CCD9DC');}footer(s,6);}
{const s=base('Summary','What the current version delivers','A student can find course PDFs and get a starting point for career questions.');txt(s,'Working features',78,274,420,30,22,C.teal,true);txt(s,'Student accounts, course notes, PDF preview and download, Quick Help, and saved Mentor conversations.',78,324,1060,65,23,C.navy,false);box(s,78,433,1120,2,C.teal);txt(s,'Next development',78,470,420,30,22,C.teal,true);txt(s,'Add the planned career preparation tools as the project grows.',78,520,1060,45,23,C.navy,false);txt(s,'Thank you',78,610,500,35,20,C.muted,true);footer(s,7);}await fs.mkdir(buildDir,{recursive:true});await fs.mkdir(path.dirname(finalPath),{recursive:true});
const draft=path.join(buildDir,'draft.pptx');await (await PresentationFile.exportPptx(p)).save(draft);
const skillDir='C:/Users/Utkarsh Jaiswal/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations';
await fs.copyFile(draft,finalPath); for(let i=0;i<p.slides.items.length;i++){const png=await p.export({slide:p.slides.items[i],format:'png',scale:0.5});await fs.writeFile(path.join(buildDir,'slide-'+(i+1)+'.png'),new Uint8Array(await png.arrayBuffer()));} console.log(JSON.stringify({finalPath,slides:p.slides.items.length}));



