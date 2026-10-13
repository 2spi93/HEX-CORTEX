"""New V4 browser runtime: single bootstrap (no versioned JS concatenation)."""

JS = r"""
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const show = (id, value) => { const e=$(id);if(e)e.textContent=String(value); };
  const report = (text, error=false) => {
    const b=$('banner');if(!b)return;
    b.textContent=text;b.classList.toggle('error',error);
  };
  window.addEventListener('error', e => report(
    'Erreur interface JS : '+(e.message || 'inconnue')+'. Vérifier la console Edge.', true
  ));
  window.addEventListener('unhandledrejection', e => report(
    'Erreur asynchrone interface : '+String(e.reason).slice(0,180), true
  ));
  // Establish navigation immediately, before any network requests.
  const nav=Array.from(document.querySelectorAll('.sidebar .nav a[href^="#"]'));
  const sections=Array.from(document.querySelectorAll('.main section[id]'));
  function tab(id){
    const selected=sections.find(s=>s.id===id)||sections[0];
    if(!selected)return;
    sections.forEach(s=>s.hidden=s!==selected);
    nav.forEach(a=>{
      const yes=a.getAttribute('href')==='#'+selected.id;
      a.classList.toggle('current',yes);
      if(yes)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');
    });
    window.scrollTo(0,0);
  }
  nav.forEach(a=>a.addEventListener('click',e=>{
    e.preventDefault();
    const target=a.getAttribute('href').slice(1);
    tab(target);
    history.replaceState(null,'','#'+target);
  }));
  window.addEventListener('hashchange',()=>tab(location.hash.slice(1)));
  tab(location.hash.slice(1)||'overview');
  report('Command Center V4 actif · Synchronisation des registres locaux…');

  async function getJson(url){
    const response=await fetch(url,{cache:'no-store'});
    const data=await response.json();
    if(!response.ok)throw new Error(data.reason||'HTTP '+response.status);
    return data;
  }
  function element(name,kind='div',cls=''){
    const x=document.createElement(kind);x.textContent=name;if(cls)x.className=cls;return x;
  }
  // V40/Spine/Cockpit are observed; no new model call or file access is triggered.
  function renderVision(data){
    const target=$('vision-list');target.replaceChildren();
    if(data.status!=='operator_receipt_loaded'){
      target.append(element('Aucune inspection V40 exploitable.','p','muted'));return;
    }
    for(const scene of data.scenes||[]){
      for(const obj of scene.objects||[]){
        const card=element('', 'article','vision-card');
        if(obj.preview_url){
          const image=document.createElement('img');
          image.src=obj.preview_url;image.loading='lazy';
          image.alt='Masque prédit : '+scene.scene_id+' / '+obj.object_id;
          card.append(image);
        }
        card.append(element(obj.object_id,'strong'));
        card.append(element(scene.scene_id+' · non annoté','small'));
        target.append(card);
      }
    }
  }
  async function snapshot(){
    $('refresh').disabled=true;
    try{
      const data=await getJson('/api/snapshot');
      show('mode',data.mode==='local_cpu_safe_readonly'?'CPU SAFE':data.mode);
      show('scenes',data.vision.scenes?.length??'—');
      show('masks',data.vision.mask_count??'—');
      show('events',data.spine.events??'—');
      show('spine-status',data.spine.integrity===true?'Chaîne vérifiée':data.spine.status);
      show('spine-visual',data.spine.visual_predictions??'—');
      show('cockpit-status',data.cockpit.latest_status??data.cockpit.status);
      const chips=$('event-types');chips.replaceChildren();
      for(const item of data.spine.types||[]){
        chips.append(element(item.type+' · '+item.count,'span','event-tag'));
      }
      renderVision(data.vision);
      const err=['vision','spine','cockpit'].filter(k=>data[k].status==='error');
      report(err.length?
        'Certaines preuves locales sont invalides : '+err.join(', '):
        'Interface chargée · CPU sûr · chat sur demande · aucune commande externe autorisée',
        err.length>0);
    }catch(e){report('Impossible de charger les registres : '+e.message,true);}
    finally{$('refresh').disabled=false;}
  }
  $('refresh').addEventListener('click',snapshot);

  async function probe(){
    const b=$('probe');b.disabled=true;show('probe-result','Probe du dépôt via LocalHarness…');
    try{
      const response=await fetch('/api/harness/probe',{
        method:'POST',headers:{'X-HEX-Read-Probe':'explicit'},body:''
      });
      const data=await response.json();
      show('probe-result',JSON.stringify(data,null,2));
    }catch(e){show('probe-result','Probe indisponible : '+e.message);}
    finally{b.disabled=false;}
  }
  $('probe').addEventListener('click',probe);

  let modules=[];
  function renderCatalog(){
    const target=$('catalog-list');target.replaceChildren();
    const q=$('catalog-search').value.toLowerCase().trim();
    for(const info of modules.filter(r=>(r.name+' '+r.id+' '+r.status).toLowerCase().includes(q))){
      const card=element('','article','catalog-card');
      card.append(element(info.name,'strong'));
      const state=element(info.status.replaceAll('_',' '),'span','state');
      if(!/^(enabled|connected)/.test(info.status))state.classList.add('off');
      card.append(state,element('Accès : '+info.action.replaceAll('_',' '),'p'));
      target.append(card);
    }
    if(!target.childElementCount)target.append(element('Aucun module correspondant.','p','muted'));
  }
  async function catalog(){
    try{modules=(await getJson('/api/capabilities')).features||[];renderCatalog();}
    catch(e){$('catalog-list').textContent='Catalogue indisponible : '+e.message;}
  }
  $('catalog-refresh').addEventListener('click',catalog);
  $('catalog-search').addEventListener('input',renderCatalog);

  const selector=$('chat-model'), log=$('chat-log'), form=$('chat-form');
  let conversationalContext=[],busy=false,lastReply='';
  function clearChat(reason){
    if(busy)return;
    conversationalContext=[];lastReply='';
    log.replaceChildren();log.append(element(reason,'p','muted'));
    $('chat-prompt').value='';
    show('chat-state','Contexte remis à zéro · non enregistré');
  }
  $('new-conversation').addEventListener('click',()=>
    clearChat('Nouvelle conversation ; aucun échange précédent réutilisé.'));
  selector.addEventListener('change',()=>clearChat('Modèle changé : contexte effacé.'));
  function appendMessage(role,text){
    const box=element('','div','chat-entry '+(role==='Vous'?'from-user':'from-assistant'));
    box.append(element(role,'small'),element(text,'div'));log.append(box);
    log.scrollTop=log.scrollHeight;
  }
  $('load-models').addEventListener('click',async()=>{
    if(busy)return;
    clearChat('Inventaire des modèles renouvelé : contexte effacé.');
    const button=$('load-models');button.disabled=true;show('chat-state','Recherche des modèles Ollama…');
    try{
      const data=await getJson('/api/ollama/models');
      selector.replaceChildren();
      for(const model of data.models){
        const option=document.createElement('option');
        option.value=model;option.textContent=model;selector.append(option);
      }
      $('send-chat').disabled=!data.models.length;
      show('chat-state',data.models.length+' modèle(s) Ollama détecté(s). Envoi CPU sur demande.');
    }catch(e){
      $('send-chat').disabled=true;
      show('chat-state','Ollama indisponible : '+e.message);
    }finally{button.disabled=false;}
  });
  form.addEventListener('submit',async e=>{
    e.preventDefault();
    if(busy)return;
    const prompt=$('chat-prompt').value.trim(),model=selector.value;
    if(!prompt||!model)return;
    busy=true;
    const buttons=[$('send-chat'),selector,$('load-models'),$('new-conversation')];
    buttons.forEach(b=>b.disabled=true);
    form.setAttribute('aria-busy','true');
    const context=conversationalContext.slice(-6);
    appendMessage('Vous',prompt);
    show('chat-state','Calcul CPU… '+(context.length/2)+' échange(s) en contexte');
    const started=performance.now();
    try{
      const response=await fetch('/api/ollama/conversation',{
        method:'POST',
        headers:{'Content-Type':'application/json','X-HEX-Chat-Approval':'single-cpu-request'},
        body:JSON.stringify({prompt,model,history:context})
      });
      const data=await response.json();
      if(!response.ok||data.status!=='completed')
        throw new Error(data.reason||'Modèle non disponible');
      appendMessage('HEX-CORTEX · '+data.model_used,data.reply);
      lastReply=data.reply;
      conversationalContext.push(
        {role:'user',content:prompt.slice(0,600)},
        {role:'assistant',content:data.reply.slice(0,600)}
      );
      conversationalContext=conversationalContext.slice(-6);
      $('chat-prompt').value='';
      show('chat-state',
        'Réponse CPU · '+Math.round(performance.now()-started)+
        ' ms aller-retour · '+(data.history_items_used/2)+' échange(s) réutilisé(s)');
    }catch(error){
      appendMessage('Erreur',error.message);
      show('chat-state','Échec du modèle · contexte précédent conservé');
    }finally{
      busy=false;buttons.forEach(b=>b.disabled=false);
      if(!selector.value)$('send-chat').disabled=true;
      form.setAttribute('aria-busy','false');
    }
  });
  // V4 voice only reads current answer; it never submits prompts automatically.
  window.HEX_GET_LAST_REPLY=()=>lastReply;
  window.HEX_TAB=tab;

  async function codeInventory(){
    try{
      const inv=await getJson('/api/code/inventory');
      const target=$('code-files');target.replaceChildren();
      for(const row of inv.entries){
        const option=document.createElement('option');
        option.value=row.id;option.textContent=row.path;target.append(option);
      }
    }catch(e){show('code-source','Inventaire indisponible : '+e.message);}
  }
  $('code-open').addEventListener('click',async()=>{
    const id=$('code-files').value;if(!id)return;
    try{
      const data=await getJson('/api/code/source?name='+encodeURIComponent(id));
      show('code-source',data.contents);
      $('code-copy').disabled=false;
    }catch(e){show('code-source','Source non disponible : '+e.message);
      $('code-copy').disabled=true;}
  });
  $('code-copy').addEventListener('click',async()=>{
    try{
      await navigator.clipboard.writeText($('code-source').textContent);
      $('code-copy').textContent='Copié';
    }catch(e){$('code-copy').textContent='Copie refusée';}
  });
  async function devices(){
    const target=$('device-list');target.replaceChildren();
    try{
      const info=await getJson('/api/devices/capabilities');
      for(const device of info.device_types){
        const card=element('','article','catalog-card');
        card.append(element(device.name,'strong'),element(device.state,'span','state'));
        card.append(element('Actions réelles : '+(device.actions.join(', ')||'aucune'),'p'));
        target.append(card);
      }
    }catch(e){target.append(element('Registre indisponible : '+e.message,'p','muted'));}
  }
  let simArmed=false,simX=0,simY=0;
  function simStatus(status){
    show('sim-status',
      status+' · cible fictive : '+$('sim-target').value+
      ' · position fictive : ('+simX+', '+simY+') · '+(simArmed?'ARMÉE':'DÉSARMÉE')+
      ' · aucun message envoyé à un appareil');
  }
  $('sim-arm').addEventListener('click',()=>{
    simArmed=true;simX=0;simY=0;simStatus('Simulation activée en mémoire');
  });
  for(const [id,dx,dy] of [['sim-left',-1,0],['sim-forward',0,1],['sim-right',1,0]]){
    $(id).addEventListener('click',()=>{
      if(!simArmed){simStatus('Action refusée : simulation non armée');return;}
      simX=Math.max(-10,Math.min(10,simX+dx));
      simY=Math.max(-10,Math.min(10,simY+dy));
      simStatus('Mouvement fictif appliqué');
    });
  }
  $('sim-stop').addEventListener('click',()=>{
    simArmed=false;simX=0;simY=0;simStatus("ARRÊT D'URGENCE SIMULÉ");
  });
  $('sim-target').addEventListener('change',()=>{
    simArmed=false;simX=0;simY=0;simStatus('Changement de cible, désarmé');
  });
  // Always show a useful boot status even if later requests fail.
  snapshot();
  catalog();
  devices();
  codeInventory();
})();
"""
