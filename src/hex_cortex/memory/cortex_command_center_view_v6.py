"""V6 UI: opt-in real MobileSAM on photos, without replacing V5 modules."""
from __future__ import annotations

from hex_cortex.memory.cortex_command_center_view_v5 import (
    CSS as BASE_CSS, HTML as BASE_HTML,
)
from hex_cortex.memory.cortex_command_center_media_v4 import JS as MEDIA
from hex_cortex.memory.cortex_command_center_runtime_v4 import JS as RUNTIME
from hex_cortex.memory.cortex_command_center_view_v5 import (
    JS_KNOWLEDGE, RUNTIME_V5,
)


HTML = (
    BASE_HTML
    .replace("Command Center <em>HEX-CORTEX V5</em>",
             "Command Center <em>HEX-CORTEX V6</em>")
    .replace(
        '<button id="crop-export" type="button" disabled>Exporter le recadrage</button>',
        '<button id="crop-export" type="button" disabled>Exporter le recadrage</button>'
        '<button id="cpu-segment" type="button" disabled>Segmenter avec MobileSAM CPU</button>'
        '<button id="mask-export" type="button" disabled>Exporter le masque prédit</button>',
    )
    .replace(
        '<pre id="photo-status" aria-live="polite">Aucune image locale ouverte.</pre>',
        '<pre id="photo-status" aria-live="polite">Aucune image locale ouverte.</pre>'
        '<pre id="segmentation-status" aria-live="polite">'
        'Inférence CPU V36 disponible uniquement après autorisation, '
        'sans export ni écriture sur le serveur.</pre>',
    )
    .replace(
        "Ce rectangle n'est PAS un masque MobileSAM ;",
        "Ce rectangle définit le prompt MobileSAM. Le masque n'est calculé "
        "qu'après clic sur Segmenter. La photo sera alors envoyée UNIQUEMENT "
        "au serveur local 127.0.0.1:8777, sans stockage. "
        "La segmentation n'est pas une annotation humaine ;",
    )
)

CSS = BASE_CSS + r"""
#segmentation-status{overflow-wrap:anywhere;max-height:170px}
#cpu-segment{border-color:#39a9a1;background:#18525b}
#mask-export{background:#174158}
"""

# Keep all V4 media workflows; only opt into the V36 backend when explicitly
# requested by the user. The browser is the sole source of image bytes.
MEDIA_V6 = MEDIA.replace(
    "  let original=null,dragStart=null,dragEnd=null,dragging=false;",
    """  let original=null,dragStart=null,dragEnd=null,dragging=false;
  let predictedOverlay=null,predictedMaskBlob=null;
  let segmentEnabled=false,segmentBusy=false;
  function clearPredictedMask(){
    predictedOverlay?.close?.();predictedOverlay=null;predictedMaskBlob=null;
    $('mask-export').disabled=true;
  }
  function segmentButton(){
    $('cpu-segment').disabled=!(segmentEnabled && !segmentBusy && selection());
  }
""",
).replace(
    "    if(original)ctx.drawImage(original,0,0,canvas.width,canvas.height);",
    """    if(original)ctx.drawImage(original,0,0,canvas.width,canvas.height);
    if(predictedOverlay){
      ctx.drawImage(predictedOverlay,0,0,canvas.width,canvas.height);
    }""",
).replace(
    "    $('photo-export').disabled=!original;",
    """    $('photo-export').disabled=!original;
    segmentButton();""",
).replace(
    "    original=bitmap;\n    dragStart=null;",
    """    original=bitmap;
    clearPredictedMask();
    dragStart=null;""",
).replace(
    "    dragging=true;dragStart=coords(e);dragEnd=dragStart;",
    """    clearPredictedMask();
    dragging=true;dragStart=coords(e);dragEnd=dragStart;""",
).replace(
    "  const video=$('camera-stream');",
    r"""
  async function dataUrl(blob){
    return await new Promise((resolve,reject)=>{
      const reader=new FileReader();
      reader.onload=()=>resolve(String(reader.result).split(',')[1]||'');
      reader.onerror=()=>reject(Error('Lecture locale impossible'));
      reader.readAsDataURL(blob);
    });
  }
  function binaryFromBase64(encoded){
    const raw=atob(encoded);
    const bytes=new Uint8Array(raw.length);
    for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
    return new Blob([bytes],{type:'image/png'});
  }
  async function enabledVision(){
    try{
      const r=await fetch('/api/vision/cpu/availability',{cache:'no-store'});
      const state=await r.json();
      segmentEnabled=r.ok && state.enabled_at_server_launch===true;
      message('segmentation-status',segmentEnabled?
        'MobileSAM CPU autorisé au lancement. Choisis une zone puis clique '
        +'sur Segmenter : la photo sera envoyée à ce serveur local seulement.':
        'MobileSAM non activé : relancer le serveur avec --enable-cpu-vision.');
    }catch(e){
      segmentEnabled=false;
      message('segmentation-status','Vision CPU non disponible dans ce serveur.');
    }
    segmentButton();
  }
  $('cpu-segment').addEventListener('click',async()=>{
    const bbox=selection();
    if(!segmentEnabled || !bbox || !original || segmentBusy)return;
    let name;
    try{name=objectName();}catch(error){
      message('segmentation-status',error.message);return;
    }
    segmentBusy=true;segmentButton();
    message('segmentation-status','Encodage local · aucun transfert avant ce clic...');
    try{
      const c=document.createElement('canvas');
      c.width=original.width;c.height=original.height;
      const g=c.getContext('2d');
      g.fillStyle='#fff';g.fillRect(0,0,c.width,c.height);
      g.drawImage(original,0,0);
      const jpg=await new Promise(resolve=>c.toBlob(resolve,'image/jpeg',.86));
      if(!jpg || jpg.size>7800000)throw Error(
        'Photo JPEG trop volumineuse : choisir une image plus petite (<7,8 Mo).');
      const encoded=await dataUrl(jpg);
      message('segmentation-status',
        'MobileSAM réel en cours sur CPU · cette opération peut prendre plusieurs secondes.');
      const r=await fetch('/api/vision/cpu/segment',{
        method:'POST',
        headers:{
          'Content-Type':'application/json',
          'X-HEX-Vision-Approval':'upload-one-image-and-load-pinned-cpu-model'
        },
        body:JSON.stringify({
          image_b64:encoded,
          bbox:[bbox.x0,bbox.y0,bbox.x1,bbox.y1],
          object_id:name
        })
      });
      const result=await r.json();
      if(!r.ok || result.status!=='one_shot_mobile_sam_mask_ready'){
        throw Error(result.reason||'Inférence CPU impossible');
      }
      const mask=binaryFromBase64(result.mask_png_b64);
      const overlay=binaryFromBase64(result.overlay_png_b64);
      const rendered=await createImageBitmap(overlay);
      clearPredictedMask();
      predictedOverlay=rendered;
      predictedMaskBlob=mask;
      $('mask-export').disabled=false;
      draw();
      message('segmentation-status',
        'Prédiction MobileSAM CPU prête · '+result.mask_visible_pixels+
        ' pixels · '+result.inference_ms_including_load+' ms (modèle inclus). '
        +'Empreinte masque : '+result.mask_binary_sha256+
        '. Pas de vérité terrain humaine, ni fichier conservé sur le serveur.');
    }catch(error){
      message('segmentation-status','Segmentation refusée/échouée : '+error.message);
    }finally{segmentBusy=false;segmentButton();}
  });
  $('mask-export').addEventListener('click',()=>{
    if(!predictedMaskBlob)return;
    try{download(predictedMaskBlob,objectName()+'.mobilesam-predicted-mask.png');}
    catch(error){message('segmentation-status',error.message);}
  });
  enabledVision();

  const video=$('camera-stream');""",
)

JS = RUNTIME_V5 + "\n" + MEDIA_V6 + "\n" + JS_KNOWLEDGE
