'use strict';
document.addEventListener('DOMContentLoaded',()=>{
 const input=document.querySelector('input[type="file"]');
 if(input)input.addEventListener('change',()=>{const chosen=document.querySelector('.dropzone');if(chosen&&input.files.length)chosen.firstChild.textContent=input.files[0].name+' — selected ';});
 const upload=document.querySelector('form[action="/upload"]');
 if(upload)upload.addEventListener('submit',()=>{const button=upload.querySelector('button[type="submit"]');if(button){button.disabled=true;button.textContent='Extracting and indexing…';}});
 // Query suggestions use a local same-origin endpoint and textContent only.
 const inputs=document.querySelectorAll('input[name="q"],input[data-suggest]');
 inputs.forEach(el=>{
   const list=document.createElement('datalist');list.id='suggestions-'+Math.random().toString(36).slice(2);
   document.body.appendChild(list);el.setAttribute('list',list.id);
   let sequence=0;
   el.addEventListener('input',async()=>{
     const q=el.value.trim();const mine=++sequence;
     if(q.length<2){list.replaceChildren();return;}
     try{
       const r=await fetch('/api/suggest?q='+encodeURIComponent(q),{credentials:'same-origin'});
       if(!r.ok)return;const data=await r.json();if(mine!==sequence)return;
       list.replaceChildren();(data.suggestions||[]).forEach(v=>{const o=document.createElement('option');o.value=v;list.appendChild(o);});
     }catch(e){list.replaceChildren();}
   });
 });
});
document.addEventListener('DOMContentLoaded',()=>{
 const btn=document.getElementById('present-toggle');
 if(!btn)return;
 const root=document.documentElement;
 const apply=on=>{root.classList.toggle('presenter',on);btn.setAttribute('aria-pressed',String(on));btn.textContent=on?'Exit presenter mode':'Presenter mode';};
 let on=false;
 try{on=localStorage.getItem('presenter')==='1';}catch(e){}
 apply(on);
 btn.addEventListener('click',()=>{on=!on;apply(on);try{localStorage.setItem('presenter',on?'1':'0');}catch(e){}});
});
document.addEventListener('DOMContentLoaded',()=>{
 // While a file is still being indexed in the background, reload the library every 3 seconds.
 if(document.querySelector('[data-busy]'))setTimeout(()=>location.reload(),3000);
});
document.addEventListener('DOMContentLoaded',()=>{
 // System page: run one small ELSER search without leaving the page, and copy the diagnostics report.
 const test=document.getElementById('semantic-test');
 const out=document.getElementById('semantic-test-result');
 if(test&&out)test.addEventListener('click',async()=>{
   test.disabled=true;out.textContent='Testing... the first call after idle can take about 30 seconds.';
   try{const r=await fetch('/api/semantic-test',{credentials:'same-origin'});const d=await r.json();
     out.textContent=(d.ok?'OK: ':'Problem: ')+d.message;}
   catch(e){out.textContent='Problem: the test request failed.';}
   test.disabled=false;
 });
 const copy=document.getElementById('copy-report');
 const box=document.getElementById('diag-report');
 if(copy&&box)copy.addEventListener('click',async()=>{
   try{await navigator.clipboard.writeText(box.value);copy.textContent='Copied';}
   catch(e){box.select();try{document.execCommand('copy');copy.textContent='Copied';}catch(e2){copy.textContent='Press Ctrl+C to copy';}}
 });
});