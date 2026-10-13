"""Browser-only capture, rectangular annotation, voice and CPU wireframe tools."""

JS = r"""
'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const message=(id,s)=>{$(id).textContent=String(s);};
  const canvas=$('photo-canvas'),ctx=canvas.getContext('2d');
  let original=null,dragStart=null,dragEnd=null,dragging=false;
  let stream=null;
  const maxImagePixels=16_000_000,maxFileBytes=8_000_000;

  function coords(e){
    const bounds=canvas.getBoundingClientRect();
    return {
      x:Math.max(0,Math.min(canvas.width,(e.clientX-bounds.left)*canvas.width/bounds.width)),
      y:Math.max(0,Math.min(canvas.height,(e.clientY-bounds.top)*canvas.height/bounds.height))
    };
  }
  function selection(){
    if(!dragStart||!dragEnd||!original)return null;
    const x0=Math.min(dragStart.x,dragEnd.x);
    const x1=Math.max(dragStart.x,dragEnd.x);
    const y0=Math.min(dragStart.y,dragEnd.y);
    const y1=Math.max(dragStart.y,dragEnd.y);
    if(x1-x0<4||y1-y0<4)return null;
    const sx=original.width/canvas.width,sy=original.height/canvas.height;
    return {
      x0:Math.floor(x0*sx),y0:Math.floor(y0*sy),
      x1:Math.min(original.width,Math.ceil(x1*sx)),
      y1:Math.min(original.height,Math.ceil(y1*sy))
    };
  }
  function draw(){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    if(original)ctx.drawImage(original,0,0,canvas.width,canvas.height);
    const box=selection();
    if(box){
      const x=box.x0*canvas.width/original.width;
      const y=box.y0*canvas.height/original.height;
      const w=(box.x1-box.x0)*canvas.width/original.width;
      const h=(box.y1-box.y0)*canvas.height/original.height;
      ctx.strokeStyle='#4effe4';ctx.lineWidth=2;ctx.strokeRect(x,y,w,h);
      ctx.fillStyle='rgba(35,180,180,.16)';ctx.fillRect(x,y,w,h);
      message('photo-status',
        'Sélection manuelle : ['+[box.x0,box.y0,box.x1,box.y1].join(', ')+
        '] sur image '+original.width+' × '+original.height+
        ' · aucun masque IA ni interprétation sémantique');
    }
    $('bbox-export').disabled=!box;$('crop-export').disabled=!box;
    $('photo-export').disabled=!original;
  }
  async function acceptBitmap(bitmap,source){
    if(bitmap.width*bitmap.height>maxImagePixels){
      bitmap.close?.();throw new Error('Image dépassant 16 millions de pixels');
    }
    original?.close?.();
    original=bitmap;
    dragStart=null;dragEnd=null;
    draw();
    message('photo-status',
      source+' : '+bitmap.width+' × '+bitmap.height+
      ' · glisser pour sélectionner un rectangle.');
  }
  $('photo-file').addEventListener('change',async e=>{
    const file=e.target.files?.[0];if(!file)return;
    if(!['image/png','image/jpeg','image/webp'].includes(file.type)||
        file.size>maxFileBytes){
      message('photo-status','Format refusé ou taille > 8 Mo : PNG/JPEG/WebP uniquement.');return;
    }
    try{
      stopCamera();
      await acceptBitmap(await createImageBitmap(file),'Photo locale');
    }catch(error){message('photo-status','Impossible de lire la photo : '+error.message);}
  });
  canvas.addEventListener('pointerdown',e=>{
    if(!original)return;
    dragging=true;dragStart=coords(e);dragEnd=dragStart;
    canvas.setPointerCapture(e.pointerId);draw();
  });
  canvas.addEventListener('pointermove',e=>{
    if(!dragging)return;
    dragEnd=coords(e);draw();
  });
  canvas.addEventListener('pointerup',e=>{
    if(!dragging)return;
    dragEnd=coords(e);dragging=false;
    canvas.releasePointerCapture(e.pointerId);draw();
  });
  canvas.addEventListener('pointercancel',()=>{dragging=false;draw();});
  function download(blob,name){
    const url=URL.createObjectURL(blob);
    const link=document.createElement('a');
    link.href=url;link.download=name;link.click();
    setTimeout(()=>URL.revokeObjectURL(url),2000);
  }
  function objectName(){
    const name=$('object-label').value.trim();
    if(!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(name))throw Error(
      'Nom invalide (lettre puis caractères ASCII, chiffres, _ ou -)');
    return name;
  }
  $('bbox-export').addEventListener('click',()=>{
    try{
      const box=selection(),name=objectName();if(!box)return;
      const record={
        schema:'hex.operator_manual_bbox.v4',
        label_source:'operator_manually_selected_not_model_recognized',
        object_id:name, bbox_xyxy:[box.x0,box.y0,box.x1,box.y1],
        image_width:original.width,image_height:original.height,
        mask_exists:false,verified_by_model:false,
        exported_by_operator:true
      };
      download(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}),
        name+'.bbox.json');
    }catch(e){message('photo-status',e.message);}
  });
  function toPng(c,name){
    c.toBlob(blob=>{
      if(blob)download(blob,name);
      else message('photo-status','Export PNG indisponible.');
    },'image/png');
  }
  $('crop-export').addEventListener('click',()=>{
    try{
      const box=selection(),name=objectName();if(!box)return;
      const c=document.createElement('canvas');
      c.width=box.x1-box.x0;c.height=box.y1-box.y0;
      c.getContext('2d').drawImage(
        original,box.x0,box.y0,c.width,c.height,
        0,0,c.width,c.height
      );
      toPng(c,name+'.crop.png');
    }catch(e){message('photo-status',e.message);}
  });
  $('photo-export').addEventListener('click',()=>{
    if(!original)return;
    const c=document.createElement('canvas');
    c.width=original.width;c.height=original.height;
    c.getContext('2d').drawImage(original,0,0);
    toPng(c,'hex-local-photo.png');
  });
  const video=$('camera-stream');
  async function startCamera(){
    if(!navigator.mediaDevices?.getUserMedia){
      message('photo-status','Caméra non disponible dans ce navigateur.');return;
    }
    try{
      stream=await navigator.mediaDevices.getUserMedia({
        video:{width:{ideal:960},height:{ideal:540}},audio:false
      });
      video.srcObject=stream;video.hidden=false;
      $('camera-start').disabled=true;
      $('camera-stop').disabled=false;
      $('camera-snap').disabled=false;
      await video.play();
      message('photo-status','Caméra locale activée avec consentement · aucun flux transmis au serveur.');
    }catch(error){
      stopCamera();message('photo-status','Caméra refusée ou indisponible : '+error.name);
    }
  }
  function stopCamera(){
    if(stream){for(const track of stream.getTracks())track.stop();}
    stream=null;video.pause();video.srcObject=null;video.hidden=true;
    $('camera-start').disabled=false;
    $('camera-stop').disabled=true;
    $('camera-snap').disabled=true;
  }
  $('camera-start').addEventListener('click',startCamera);
  $('camera-stop').addEventListener('click',()=>{
    stopCamera();message('photo-status','Caméra arrêtée, pistes média libérées.');
  });
  $('camera-snap').addEventListener('click',async()=>{
    if(!stream||!video.videoWidth)return;
    try{
      const c=document.createElement('canvas');
      c.width=video.videoWidth;c.height=video.videoHeight;
      c.getContext('2d').drawImage(video,0,0);
      await acceptBitmap(await createImageBitmap(c),'Capture caméra locale');
      stopCamera();
    }catch(e){message('photo-status','Capture impossible : '+e.message);}
  });
  // Revoke camera if the tab becomes hidden; no background monitoring.
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden&&stream)stopCamera();
  });
  window.addEventListener('pagehide',stopCamera);

  // Native browser speech: explicit opt-in and potentially CLOUD-transcribed.
  const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
  let recognition=null;
  if(!Speech)message('voice-status',
    'SpeechRecognition indisponible ; utiliser un navigateur compatible ou futurs STT locaux.');
  $('voice-start').addEventListener('click',()=>{
    if(!Speech){message('voice-status','Dictée non disponible dans ce navigateur.');return;}
    if(recognition)return;
    recognition=new Speech();recognition.lang='fr-FR';
    recognition.continuous=false;recognition.interimResults=false;
    recognition.onresult=e=>{
      const transcript=e.results?.[0]?.[0]?.transcript||'';
      $('voice-text').value=transcript.slice(0,1600);
      message('voice-status',
        'Dictée terminée · la reconnaissance du navigateur peut utiliser le cloud. Aucun envoi au modèle.');
    };
    recognition.onerror=e=>message('voice-status','Micro ou reconnaissance : '+e.error);
    recognition.onend=()=>{
      recognition=null;
      $('voice-stop').disabled=true;$('voice-start').disabled=false;
    };
    $('voice-stop').disabled=false;$('voice-start').disabled=true;
    try{
      recognition.start();
      message('voice-status','Écoute ponctuelle autorisée · arrêter à tout moment.');
    }catch(error){
      recognition=null;
      $('voice-stop').disabled=true;$('voice-start').disabled=false;
      message('voice-status','Impossible de démarrer la dictée : '+error.message);
    }
  });
  $('voice-stop').addEventListener('click',()=>{
    recognition?.abort();
    recognition=null;
    $('voice-start').disabled=false;$('voice-stop').disabled=true;
    message('voice-status','Écoute arrêtée.');
  });
  $('voice-to-chat').addEventListener('click',()=>{
    const s=$('voice-text').value.trim();
    if(!s)return;
    $('chat-prompt').value=s.slice(0,1600);
    window.HEX_TAB?.('chat');
    message('voice-status','Texte copié vers Chat, non envoyé au modèle.');
  });
  $('voice-speak').addEventListener('click',()=>{
    if(!('speechSynthesis' in window))return;
    const words=$('voice-text').value.trim()||window.HEX_GET_LAST_REPLY?.()||'';
    if(!words)return;
    speechSynthesis.cancel();
    const utterance=new SpeechSynthesisUtterance(words.slice(0,1000));
    utterance.lang='fr-FR';
    speechSynthesis.speak(utterance);
    message('voice-status','Lecture TTS navigateur à la demande. Localité de la voix non garantie.');
  });
  $('voice-silence').addEventListener('click',()=>{
    if('speechSynthesis' in window)speechSynthesis.cancel();
    message('voice-status','Lecture audio stoppée.');
  });
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden&&recognition){recognition.abort();recognition=null;}
  });

  // True 3D coordinates projected by CPU Canvas2D, not WebGL nor 3D inference.
  const c3=$('scene-canvas'),g=c3.getContext('2d');
  const verts=[
    [-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
    [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]
  ];
  const edges=[
    [0,1],[1,2],[2,3],[3,0],
    [4,5],[5,6],[6,7],[7,4],
    [0,4],[1,5],[2,6],[3,7]
  ];
  function render3D(){
    const rx=Number($('angle-x').value)*Math.PI/180;
    const ry=Number($('angle-y').value)*Math.PI/180;
    const sx=Math.sin(rx),cx=Math.cos(rx),sy=Math.sin(ry),cy=Math.cos(ry);
    const project=verts.map(([x,y,z])=>{
      const x1=x*cy+z*sy,z1=-x*sy+z*cy;
      const y1=y*cx-z1*sx,z2=y*sx+z1*cx;
      const k=150/(4+z2);
      return [c3.width/2+x1*k,c3.height/2+y1*k];
    });
    g.clearRect(0,0,c3.width,c3.height);
    g.fillStyle='#071320';g.fillRect(0,0,c3.width,c3.height);
    g.strokeStyle='#45dfcb';g.lineWidth=2;
    for(const [a,b] of edges){
      g.beginPath();g.moveTo(...project[a]);g.lineTo(...project[b]);g.stroke();
    }
    g.fillStyle='#e0faff';g.font='14px Segoe UI';
    g.fillText('Cube synthétique 3D · projection CPU 2D',18,28);
    g.fillText('X : '+$('angle-x').value+'° · Y : '+$('angle-y').value+'°',18,50);
  }
  $('angle-x').addEventListener('input',render3D);
  $('angle-y').addEventListener('input',render3D);
  $('scene-reset').addEventListener('click',()=>{
    $('angle-x').value=-20;$('angle-y').value=28;render3D();
  });
  render3D();
})();
