#!/bin/bash
# Video workshop: three steps and three tools in view (Tinkercad only in Innova); the rest folded under «Más opciones».
set -u
APP="$(cd "$(dirname "$0")/.." && pwd)"
check() { if echo "$2" | grep -q -- "$3"; then echo "OK   $1"; else echo "FAIL $1 -> $(echo "$2" | head -c 300)"; fi; }
nocheck() { if echo "$2" | grep -q -- "$3"; then echo "FAIL $1 -> $(echo "$2" | head -c 300)"; else echo "OK   $1"; fi; }
cd "$APP"
# Render the workshop as each subject sees it, with the browser-only globals stubbed, and split main view / «Más opciones».
render() { node -e "
const src=require('fs').readFileSync('static/app.js','utf8');
const start=src.indexOf('function videoToolkit('); if(start<0){console.log('SIN-FUNCION');process.exit(0);}
let depth=0,i=src.indexOf('{',start);for(;i<src.length;i++){if(src[i]==='{')depth++;else if(src[i]==='}'&&--depth===0)break;}
const esc=s=>String(s);const STORYBOARD=(src.match(/const STORYBOARD=\[[\s\S]*?\];/)||['const STORYBOARD=[];'])[0];
const fn=new Function('esc',STORYBOARD+src.slice(start,i+1)+';return videoToolkit;')(esc);
const html=fn('$1');const cut=html.indexOf('class=\"more-tools\"');
console.log(process.argv[1]==='main'?(cut<0?html:html.slice(0,cut)):(cut<0?'':html.slice(cut)));" "$2"; }
mi=$(render incentiva main); [ "$mi" = "SIN-FUNCION" ] && { echo "FAIL no se encontró videoToolkit"; exit 0; }; mn=$(render innova main); more=$(render incentiva more); moren=$(render innova more)
check "tres pasos en la vista principal" "$(echo "$mi" | tr -d '\n')" "Graba con el celular.*Edita.*Sube y pega el enlace"
check "Clipchamp visible" "$mi" "<h3>Clipchamp</h3>"
check "CapCut visible" "$mi" "<h3>CapCut</h3>"
check "Tinkercad visible en Innova" "$mn" "<h3>Tinkercad</h3>"
nocheck "Tinkercad no está en la vista principal de Incentiva" "$mi" "<h3>Tinkercad</h3>"
for tool in "Canva Video" Kdenlive Audacity Blender OpenToonz diagrams.net Runway Pika "Luma Dream Machine" "Adobe Express"; do
  nocheck "$tool fuera de la vista principal" "$mi" "<h3>$tool</h3>"; done
check "«Más opciones» cerrado por defecto" "$more" 'class="more-tools"><summary>Más opciones'
nocheck "«Más opciones» no se abre solo" "$more" 'class="more-tools" open'
check "las demás herramientas siguen disponibles" "$more" "<h3>Blender</h3>"
check "Fusion 360 en «Más opciones» de Innova" "$moren" "<h3>Fusion 360</h3>"
check "guion de 5 minutos en la vista principal" "$mi" "Guion sugerido · 5 minutos"
check "cómo compartir: YouTube no listado o Drive con enlace" "$mi" "YouTube «No listado».*Drive «Cualquier persona con el enlace»"
check "campo del video con la misma indicación" "$(cat static/app.js)" 'YouTube «No listado» o Drive «Cualquier persona con el enlace»'
check "la guía escrita también va en 3 pasos" "$(cat GUIA_VIDEO_PROTOTIPO.md)" "## En 3 pasos"
