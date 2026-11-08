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