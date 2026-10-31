const main = document.querySelector('#main');
const headerActions = document.querySelector('#header-actions');
const toast = document.querySelector('#toast');
const PROJECTS = {
  incentiva: {name:'Incentiva en el Aula', course:'Metodología de la Investigación', short:'Innovación en salud aplicada al territorio', accent:'forest', kind:'Video-prototipo + Ficha de Evidencia', description:'Diseña una respuesta fundamentada a un desafío sociosanitario real.'},
  innova: {name:'Innova en el Aula', course:'Fundamentos de Diagnóstico Molecular', short:'Casos, prototipos y diagnóstico molecular', accent:'plum', kind:'Cápsula + prototipo 3D + matriz diagnóstica', description:'Explica cómo una alteración molecular se relaciona con un caso y su diagnóstico.'}
};
let user = null;
let activeProjects = [];
let pendingProjects = [];
let managedProjects = [];
let projectConfig = {};
let mySections = {};
let readerProjects = [];
let resourceCache = {};
let toastTimer;

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Written materials use a tiny format: "## " starts a heading, "- " a bullet, anything else is a paragraph.
function richText(value) {
  const out=[]; let list=[];
  const flush=()=>{if(list.length){out.push(`<ul class="detail-list">${list.join('')}</ul>`);list=[];}};
  String(value??'').split(/\n+/).map(l=>l.trim()).filter(Boolean).forEach(line=>{
    if(line.startsWith('- ')){list.push(`<li>${esc(line.slice(2))}</li>`);return;}
    flush(); out.push(line.startsWith('## ')?`<h3 class="detail-heading">${esc(line.slice(3))}</h3>`:`<p class="detail-content">${esc(line)}</p>`);});
  flush(); return out.join('');
}
const paragraphs = value => String(value ?? '').split(/\n+/).map(line=>line.trim()).filter(Boolean).map(line=>`<p class="detail-content">${esc(line)}</p>`).join('');
async function fileToBase64(file) {
  const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
  for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,i+0x8000));
  return btoa(binary);
}
function notify(message) {
  toast.textContent = message; toast.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('show'), 3400);
}
async function api(path, options={}) {
  const response = await fetch(path, {credentials:'same-origin', ...options, headers:{'Content-Type':'application/json', ...(options.headers||{})}});
  const data = await response.json().catch(()=>({}));
  if (!response.ok) { if (response.status===401) { user=null; render(); } throw new Error(data.error || 'Ocurrió un error.'); }
  return data;
}
function currentPath() { return location.pathname.replace(/\/$/,'') || '/'; }
function go(path) { history.pushState({},'',path); render(); window.scrollTo(0,0); }
function linkHandler(event) {
  const anchor=event.target.closest('a[data-route]');
  if (!anchor) return;
  event.preventDefault(); go(anchor.dataset.route);
}
document.addEventListener('click',linkHandler);
window.addEventListener('popstate',render);

const THEMES={auto:'Tema: automático',light:'Tema: claro',dark:'Tema: oscuro'};
function themeButton() {
  let theme='auto'; try{theme=localStorage.getItem('theme')||'auto';}catch{}
  return `<button class="text-button theme-toggle" type="button" data-theme-toggle aria-label="${THEMES[theme]}. Cambiar tema" title="${THEMES[theme]}"><span aria-hidden="true">${theme==='dark'?'☾':theme==='light'?'☀':'◐'}</span></button>`;
}
document.addEventListener('click',e=>{if(!e.target.closest('[data-theme-toggle]'))return;
  let theme='auto'; try{theme=localStorage.getItem('theme')||'auto';}catch{}
  const next={auto:'light',light:'dark',dark:'auto'}[theme]||'auto';
  try{localStorage.setItem('theme',next);}catch{}
  if(next==='auto')document.documentElement.removeAttribute('data-theme');else document.documentElement.setAttribute('data-theme',next);
  header(); notify(THEMES[next]);});
function header() {
  if (!user) { headerActions.innerHTML=themeButton(); return; }
  headerActions.innerHTML=themeButton()+`${['admin','editor'].includes(user.role)?'<a class="text-button" href="/admin" data-route="/admin">Revisión</a>':''}<span class="user-chip" aria-label="Sesión iniciada: ${esc(user.email)}"><i class="user-dot" aria-hidden="true"></i><span class="user-email">${esc(user.email)}</span></span><a class="text-button" href="/auth/logout">Salir</a>`;
}
function card(projectId) {
  const p=PROJECTS[projectId], innova=projectId==='innova';
  return `<article class="project-card ${innova?'innova':''}"><div class="card-inner">
    <span class="project-mark">${innova?'02 · INNOVA':'01 · INCENTIVA'}</span>
    <h2>${esc(p.name)}</h2><div class="course-label">${esc(p.course)}</div>
    <p>${esc(p.description)}</p>
    <div class="card-bottom"><span class="kind">${esc(p.kind)}</span><a class="button project-button" data-route="/${projectId}" href="/${projectId}">Entrar al proyecto <span aria-hidden="true">→</span></a></div>
  </div></article>`;
}
function accessCard(projectId) {
  const p=PROJECTS[projectId], innova=projectId==='innova', pending=pendingProjects.includes(projectId);
  return `<article class="access-request-card ${innova?'innova':''}"><span class="project-mark">${innova?'02 · INNOVA':'01 · INCENTIVA'}</span><h3>${esc(p.name)}</h3><p>${esc(p.course)}</p>${pending?'<span class="pending-label">Solicitud pendiente de aprobación</span>':`<button class="button secondary small" data-request-access="${projectId}">Solicitar acceso</button>`}</article>`;
}
function home() {
  const available=Object.keys(PROJECTS);
  const visible=activeProjects.filter(id=>PROJECTS[id]);
  const requests=available.filter(id=>!visible.includes(id));
  main.innerHTML=`<section class="hero"><div class="eyebrow">Escuela de Tecnología Médica · PUCV</div>
    <div class="hero-row"><div><h1>Proyectos de innovación<br><span>en Tecnología Médica.</span></h1>
      <p class="lead">Cada asignatura tiene su propio espacio, materiales y entregas. La docente autoriza qué cuentas pueden entrar.</p></div>
      <div class="access-note"><span class="lock-icon" aria-hidden="true">●</span>Acceso validado por asignatura</div></div>
    </section>
    ${visible.length?`<section aria-labelledby="projects-title"><div class="section-head"><div><div class="eyebrow">Asignaturas autorizadas</div><h2 id="projects-title">Tus proyectos</h2></div></div><div class="project-grid">${visible.map(card).join('')}</div></section>`:'<div class="empty-state">Tu correo ya fue verificado. Solicita acceso a tu asignatura; la docente revisará la solicitud antes de mostrarte los materiales.</div>'}
    ${readerProjects.length?`<section aria-labelledby="showcase-title"><div class="section-head"><div><div class="eyebrow">Abierto a la comunidad PUCV</div><h2 id="showcase-title">Vitrina de trabajos</h2></div></div><div class="project-grid">${readerProjects.map(id=>`<article class="project-card ${id==='innova'?'innova':''}"><div class="card-inner"><span class="project-mark">Modo lector</span><h2>${esc(PROJECTS[id].name)}</h2><div class="course-label">${esc(PROJECTS[id].course)}</div><p>Mira las cápsulas y videos que sus equipos autorizaron compartir con otros cursos.</p><div class="card-bottom"><span class="kind">Solo lectura</span><a class="button project-button" data-route="/${id}" href="/${id}">Ver la vitrina <span aria-hidden="true">→</span></a></div></div></article>`).join('')}</div></section>`:''}
    ${requests.length?`<section aria-labelledby="request-title"><div class="section-head"><div><div class="eyebrow">Acceso a cursos</div><h2 id="request-title">Solicitar acceso</h2></div></div>
      <form id="join-form" class="join-row"><div><strong>¿Tienes el código del curso?</strong><p class="helper">Si recibiste el código en clase, en el Aula Virtual o en una invitación, escríbelo aquí. Con él entras de inmediato, sin esperar aprobación.</p></div><label class="visually-hidden" for="join-code">Código del curso</label><input id="join-code" class="code-input" required maxlength="20" autocapitalize="characters" spellcheck="false" placeholder="XXXX-XXXX"><button class="button small" type="submit">Unirme →</button></form>
      <div class="access-request-grid">${requests.map(accessCard).join('')}</div></section>`:''}
    <section class="principles" aria-label="Características del repositorio">
      <article class="principle"><strong>Una entrada común</strong><p>El mismo enlace ofrece acceso a los dos portales independientes.</p></article>
      <article class="principle"><strong>Autorización por curso</strong><p>Cada docente aprueba quién puede consultar sus materiales.</p></article>
      <article class="principle"><strong>Contenido bajo revisión</strong><p>Las entregas y comentarios pasan por revisión antes de publicarse.</p></article>
    </section>`;
  main.querySelectorAll('[data-request-access]').forEach(button=>button.addEventListener('click',()=>requestAccess(button.dataset.requestAccess,button)));
  const joinForm=document.querySelector('#join-form');
  if(joinForm) joinForm.addEventListener('submit',async e=>{e.preventDefault();const button=joinForm.querySelector('button');button.disabled=true;
    try{const result=await api('/api/join',{method:'POST',body:JSON.stringify({code:document.querySelector('#join-code').value})});notify(result.message);await bootstrap();if(result.project_id)go(`/${result.project_id}`);}
    catch(ex){notify(ex.message);button.disabled=false;}});
}
async function requestAccess(projectId,button) {
  button.disabled=true;
  try {const result=await api('/api/access-requests',{method:'POST',body:JSON.stringify({project_id:projectId})});notify(result.message);await bootstrap();}
  catch(error){notify(error.message);button.disabled=false;}
}
function accessDeniedPage(projectId) {
  const p=PROJECTS[projectId], pending=pendingProjects.includes(projectId);
  main.innerHTML=`<section class="project-page ${projectId==='innova'?'innova-theme':''}"><a class="back-link" data-route="/" href="/">← Volver a los proyectos</a><div class="empty-state"><div class="eyebrow">${esc(p.name)}</div><h1>Acceso por validar</h1><p>${pending?'La docente recibió tu solicitud y aún no la ha aprobado.':'Solicita acceso a esta asignatura. Solo después de la aprobación podrás ver sus recursos.'}</p>${pending?'<span class="pending-label">Solicitud pendiente de aprobación</span>':`<button class="button" id="request-project">Solicitar acceso</button>`}</div></section>`;
  const button=document.querySelector('#request-project');if(button)button.addEventListener('click',()=>requestAccess(projectId,button));
}
// Same six blocks and times as the proposal and GUIA_VIDEO_PROTOTIPO.md; update the three together.
const STORYBOARD=[
  ['0:00–0:45','Problema y contexto territorial','Caso clínico simulado y pregunta'],
  ['0:45–1:25','Personas o comunidad afectada','Alteración y proceso molecular'],
  ['1:25–2:15','Solución propuesta','Propuesta diagnóstica o prototipo'],
  ['2:15–3:45','Simulación de su funcionamiento','Simulación: cómo funciona la técnica o el modelo 3D'],
  ['3:45–4:25','Resultado esperado e indicador','Resultado esperado y controles'],
  ['4:25–5:00','Limitación o condición necesaria','Limitación y cierre']
];
function videoToolkit(projectId) {
  const isInnova=projectId==='innova';
  return `<details class="toolkit" aria-labelledby="toolkit-title"><summary class="toolkit-summary"><span class="eyebrow">Taller audiovisual</span><strong>Guía para un video final · máximo 5 minutos</strong><span class="toolkit-summary-action">Ver guion y herramientas <span aria-hidden="true">＋</span></span></summary>
    <div class="toolkit-heading"><div><div class="eyebrow">Taller de producción · alternativas gratuitas</div><h2 id="toolkit-title">Un video final, hecho en equipo</h2></div><p>Elijan una ruta según el equipo y el tiempo disponible. Pueden dibujar, actuar, grabar una maqueta, modelar o animar; la IA es opcional.</p></div>
    <div class="storyboard-grid"><article><h3>Guion sugerido · 5 minutos</h3><ol>${STORYBOARD.map(([time,incentiva,innova])=>`<li><b>${time}</b> · ${esc(isInnova?innova:incentiva)}</li>`).join('')}</ol></article><article><h3>Enfoque de esta asignatura</h3><p>${isInnova?'Usen un caso clínico simulado. Conecten hallazgo, mecanismo o patología, evidencia y decisión diagnóstica; muestren cómo funcionaría su propuesta y qué control o dato permitiría evaluarla. La encuesta diagnóstica inicial/final sirve para explorar aprendizaje, no para afirmar eficacia clínica.':'Partan del desafío y la necesidad territorial. Expliquen a quién afecta, qué muestra la investigación, cómo se probaría la solución en una situación simulada y qué indicador usarían para comparar el diagnóstico inicial y final.'}</p><p class="helper">Pueden mover, combinar o renombrar los capítulos; no son seis entregas ni seis videos. Se evalúa un MP4 final por equipo.</p></article></div>
    <section class="tool-group"><div class="eyebrow">Editar, narrar y cerrar el video</div><div class="toolkit-grid">
      <article class="tool-card"><span class="tool-step">FÁCIL · NAVEGADOR</span><h3>Clipchamp</h3><p>Une grabaciones, dibujos y narración; incorpora títulos y subtítulos automáticos. La cuenta personal gratuita exporta hasta 1080p sin marca de agua; el contenido premium sí puede requerir pago.</p><a class="tool-link" href="https://clipchamp.com/en/pricing/" target="_blank" rel="noopener noreferrer">Ver plan gratis y abrir ↗</a></article>
      <article class="tool-card"><span class="tool-step">DIAGRAMAS Y ESCENAS</span><h3>Canva Video</h3><p>Arma un storyboard visual, anima textos y diagramas. Exporta MP4 sin costo usando elementos gratuitos; los recursos premium pueden exigir pago. Revisa cada recurso antes de exportar.</p><a class="tool-link" href="https://www.canva.com/help/download-video-as-separate-files/" target="_blank" rel="noopener noreferrer">Ver límites de Canva Free ↗</a></article>
      <article class="tool-card"><span class="tool-step">EDICIÓN EN COMPUTADOR</span><h3>Kdenlive</h3><p>Editor de escritorio gratuito y abierto para Windows, macOS y Linux: varias pistas, títulos, transiciones y subtítulos. Buena opción si quieren editar sin subir el material a un sitio web.</p><a class="tool-link" href="https://kdenlive.org/" target="_blank" rel="noopener noreferrer">Descargar Kdenlive ↗</a></article>
      <article class="tool-card"><span class="tool-step">VOZ Y SONIDO</span><h3>Audacity</h3><p>Graba y limpia la narración, nivela volúmenes y quita ruido. Es gratuito, funciona en el computador y no requiere cuenta para editar.</p><a class="tool-link" href="https://www.audacityteam.org/download/" target="_blank" rel="noopener noreferrer">Descargar Audacity ↗</a></article>
    </div></section>
    <section class="tool-group"><div class="eyebrow">Dibujar, animar o mostrar un prototipo</div><div class="toolkit-grid">
      <article class="tool-card"><span class="tool-step">3D · PARA EMPEZAR</span><h3>Tinkercad</h3><p>Modela formas 3D sencillas en el navegador. Sirve para representar una caja, una estación de toma de muestras, una pieza o el recorrido de una solución; no es necesario imprimirla.</p><a class="tool-link" href="https://www.tinkercad.com/" target="_blank" rel="noopener noreferrer">Probar Tinkercad ↗</a></article>
      <article class="tool-card"><span class="tool-step">3D Y ANIMACIÓN · MÁS AVANZADO</span><h3>Blender</h3><p>Herramienta abierta y gratuita para modelar, animar, iluminar y renderizar. Úsenla para visualizar una molécula o simular el prototipo; requiere más aprendizaje y un computador capaz.</p><a class="tool-link" href="https://www.blender.org/features/" target="_blank" rel="noopener noreferrer">Ver herramientas de Blender ↗</a></article>
      <article class="tool-card"><span class="tool-step">ANIMACIÓN 2D</span><h3>OpenToonz</h3><p>Animación cuadro a cuadro para dibujos propios, personajes o una secuencia científica. Gratuito; es más especializado, por lo que conviene probar primero una escena de pocos segundos.</p><a class="tool-link" href="https://opentoonz.github.io/e/" target="_blank" rel="noopener noreferrer">Explorar OpenToonz ↗</a></article>
      <article class="tool-card"><span class="tool-step">DIAGRAMA Y FLUJO</span><h3>diagrams.net</h3><p>Construye esquemas de proceso, recorrido del usuario, técnica y controles. Gratis; no requiere diseñar una animación: pueden grabar el cursor recorriendo el diagrama y narrarlo.</p><a class="tool-link" href="https://app.diagrams.net/" target="_blank" rel="noopener noreferrer">Abrir diagrams.net ↗</a></article>
      ${isInnova?'<article class="tool-card"><span class="tool-step">3D · MATERIAL DEL CURSO</span><h3>Fusion 360</h3><p>El curso ya cuenta con guía y videos. El acceso educativo de Autodesk depende de validar elegibilidad; Tinkercad o Blender son alternativas sin costo.</p><a class="tool-link" href="https://www.autodesk.com/education/edu-software/fusion" target="_blank" rel="noopener noreferrer">Revisar acceso educativo ↗</a></article>':''}
    </div></section>
    <section class="ai-tools"><div class="eyebrow">IA opcional · escenas e imágenes de apoyo</div><p class="helper">No necesitas pagar ni generar todo con IA. Prueba primero herramientas con uso gratuito; créditos y disponibilidad cambian. La IA puede ilustrar una escena breve, pero el razonamiento científico, la evidencia y la decisión deben ser del equipo.</p><div class="ai-tools-grid">
      <article class="tool-card"><span class="tool-step">USO GRATUITO LIMITADO</span><h3>Adobe Express</h3><p>Combina texto, imágenes y animación. El plan gratuito ofrece generaciones IA limitadas por día; el asistente es de escritorio, funciona en inglés y no está habilitado para todas las cuentas.</p><a class="tool-link" href="https://helpx.adobe.com/express/web/ai-assistant/adobe-express-ai-assistant-faq.html" target="_blank" rel="noopener noreferrer">Ver disponibilidad gratuita ↗</a></article>
      <article class="tool-card"><span class="tool-step">PRUEBA · CRÉDITOS ÚNICOS</span><h3>Runway</h3><p>El plan gratuito da 125 créditos una sola vez y exporta con marca de agua. Úsalo solo para probar un plano corto; no dependas de él para producir el trabajo completo.</p><a class="tool-link" href="https://help.runwayml.com/hc/en-us/articles/50404627334547-Free-plan-details" target="_blank" rel="noopener noreferrer">Revisar plan gratis ↗</a></article>
      <article class="tool-card"><span class="tool-step">PRUEBA · SIN CRÉDITOS MENSUALES</span><h3>Pika</h3><p>La cuenta gratuita actualmente tiene 0 créditos mensuales; permite explorar la plataforma, pero generar requiere comprar créditos. No es una ruta de costo cero sostenida.</p><a class="tool-link" href="https://pika.art/pricing" target="_blank" rel="noopener noreferrer">Comprobar plan y créditos ↗</a></article>
      <article class="tool-card"><span class="tool-step">PLAN GRATUITO MUY LIMITADO</span><h3>Luma Dream Machine</h3><p>Sirve para explorar generación visual y borradores; las exportaciones y usos completos pueden requerir pago. Comprueba el plan vigente antes de empezar.</p><a class="tool-link" href="https://lumalabs.ai/learning-hub/payments-subscriptions" target="_blank" rel="noopener noreferrer">Revisar límites actuales ↗</a></article>
      <article class="tool-card"><span class="tool-step">EDICIÓN CON IA · REVISAR REGIÓN</span><h3>CapCut</h3><p>Ofrece edición, subtítulos y herramientas automáticas. El costo, la exportación y las funciones de IA dependen de la cuenta, región y recurso elegido; comprueba antes y no lo uses como única opción.</p><a class="tool-link" href="https://www.capcut.com/tools" target="_blank" rel="noopener noreferrer">Revisar herramientas ↗</a></article>
    </div></section>
    <div class="toolkit-plan"><strong>Una ruta completa sin pagar</strong><p>1) Dibuja el storyboard en papel o diagrams.net · 2) muestra una maqueta, un diagrama animado, una escena actuada o un modelo Tinkercad/Blender · 3) graba con celular · 4) monta en Clipchamp o Kdenlive · 5) revisa subtítulos, audio, fuentes y duración. Una persona sube el único MP4; el equipo conserva una copia compartida y entrega la ficha.</p></div>
    <p class="toolkit-note"><a class="button secondary small" href="/kit/${projectId}" data-route="/kit/${projectId}">Abrir el kit imprimible (storyboard, grabación e IA) →</a></p>
    <p class="helper toolkit-note">No incorporen nombres, fichas ni datos de pacientes reales en herramientas externas. En trabajo en grupo, repartir investigación, diseño, prototipo, narración, edición y control científico; no hace falta que todas las personas aparezcan en cámara.</p>
  </details>`;
}
function projectPage(projectId, reader=false) {
  const p=PROJECTS[projectId], cls=projectId==='innova'?'innova-theme':'';
  main.innerHTML=`<div class="project-page ${cls}">
    <a class="back-link" data-route="/" href="/">← Volver a los proyectos</a>
    <section class="project-hero"><span class="project-mark">${projectId==='innova'?'Innova en el Aula':'Incentiva en el Aula'}</span>
      <h1>${esc(p.short)}</h1><p class="lead">${esc(p.description)}</p>
      <div class="project-meta"><span class="pill">${esc(p.course)}</span><span class="pill">${esc(p.kind)}</span></div>
    </section>
    ${reader?`<div class="notice">Estás en la vitrina abierta (modo lector): ves los trabajos que sus equipos autorizaron compartir. Para entregar o comentar necesitas el código del curso.</div>`:`<nav class="project-tabs" aria-label="Secciones de ${esc(p.name)}">
      <button class="tab" aria-pressed="true" data-tab="resources">${projectId==='innova'?'Casos y recursos':'Desafíos'}</button>
      <button class="tab" aria-pressed="false" data-tab="deliver">Entregar trabajo</button>
      <button class="tab" aria-pressed="false" data-tab="forum">Foro</button>
      <button class="tab" aria-pressed="false" data-tab="tickets">Tiquetes y encuestas</button>
    </nav>
    ${videoToolkit(projectId)}`}
    <section id="project-content" aria-live="polite"><div class="loading">Cargando recursos del proyecto…</div></section>
  </div>`;
  main.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>selectTab(projectId,button.dataset.tab,button)));
  loadResources(projectId).then(()=>showResources(projectId)).catch(err=>{document.querySelector('#project-content').innerHTML=`<div class="empty-state">${esc(err.message)}</div>`;});
}
async function loadResources(projectId) {
  if (!resourceCache[projectId]) resourceCache[projectId]=await api(`/api/resources?project=${projectId}`);
}
function selectTab(projectId, tab, button) {
  main.querySelectorAll('[data-tab]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
  if(tab==='resources') showResources(projectId);
  if(tab==='deliver') showDelivery(projectId);
  if(tab==='forum') showForum(projectId);
  if(tab==='tickets') showTickets(projectId);
}
const searchText=x=>`${x.title} ${x.summary} ${x.category} ${x.tags.join(' ')} ${x.team_name||''} ${(x.members||[]).join(' ')} ${(x.fields||[]).map(f=>f.value).join(' ')}`.toLowerCase();
function showResources(projectId) {
  const root=document.querySelector('#project-content'); if(!root)return;
  const items=resourceCache[projectId]||[];
  const cats=[...new Set(items.map(x=>x.category))];
  const sections=[...new Set(items.map(x=>x.section).filter(Boolean))], cohortsSeen=[...new Set(items.map(x=>x.cohort).filter(Boolean))].sort().reverse();
  const surprise=projectId==='incentiva'&&items.some(x=>/caso|desaf[ií]o/i.test(x.category));
  const empty=projectId==='incentiva'?'La docente publicará aquí los desafíos simulados. Cuando estén disponibles, podrán sacar uno de la caja sorpresa.':'Todavía no hay materiales publicados para esta asignatura.';
  root.innerHTML=`<div class="toolbar"><label class="search-wrap"><span class="visually-hidden">Buscar en este proyecto</span><input id="resource-search" type="search" placeholder="Buscar por tema, gen, técnica o equipo"></label>
      <label><span class="visually-hidden">Filtrar por tipo</span><select id="category-filter" class="select"><option value="">Todos los tipos</option>${cats.map(c=>`<option>${esc(c)}</option>`).join('')}</select></label>
      ${cohortsSeen.length>1?`<label><span class="visually-hidden">Filtrar por cohorte</span><select id="cohort-filter" class="select"><option value="">Todas las cohortes</option>${cohortsSeen.map(c=>`<option>${esc(c)}</option>`).join('')}</select></label>`:''}
      ${sections.length?`<label><span class="visually-hidden">Filtrar por paralelo</span><select id="section-filter" class="select"><option value="">Todos los paralelos</option>${sections.map(c=>`<option>${esc(c)}</option>`).join('')}</select></label>`:''}</div>
    ${surprise?'<div class="surprise-row"><div><strong>Caja sorpresa</strong><p class="helper">Sortea un desafío simulado para iniciar el trabajo del equipo.</p></div><button class="button secondary small" type="button" id="surprise-case">Sacar un desafío →</button></div>':''}
    <div class="resource-grid" id="resource-grid"></div>`;
  const search=root.querySelector('#resource-search'), select=root.querySelector('#category-filter'), sectionSelect=root.querySelector('#section-filter'), grid=root.querySelector('#resource-grid');
  const cohortSelect=root.querySelector('#cohort-filter');
  const update=()=>{const q=search.value.toLowerCase(), cat=select.value, section=sectionSelect?sectionSelect.value:'', cohort=cohortSelect?cohortSelect.value:'';
    const arr=items.filter(x=>searchText(x).includes(q)&&(!cat||x.category===cat)&&(!section||x.section===section)&&(!cohort||x.cohort===cohort));
    grid.innerHTML=arr.length?arr.map(x=>resourceCard(x,projectId)).join(''):`<div class="empty-state">${items.length?'No encontramos recursos con esa combinación. Prueba otra palabra o quita un filtro.':empty}</div>`;};
  update();
  search.addEventListener('input',update); select.addEventListener('change',update); if(sectionSelect)sectionSelect.addEventListener('change',update); if(cohortSelect)cohortSelect.addEventListener('change',update);
  const randomButton=root.querySelector('#surprise-case');if(randomButton)randomButton.addEventListener('click',()=>{const cases=items.filter(x=>/caso|desaf[ií]o/i.test(x.category));if(!cases.length){notify('La docente aún no ha publicado desafíos para sortear.');return;}const selected=cases[Math.floor(Math.random()*cases.length)];go(`/${projectId}/recurso/${encodeURIComponent(selected.slug)}`);});
  grid.addEventListener('click',e=>{const a=e.target.closest('[data-resource]');if(a){e.preventDefault();go(`/${projectId}/recurso/${a.dataset.resource}`);}});
}
function resourceCard(resource,projectId) {
  const team=resource.team_name?`<span class="resource-team">${esc(resource.team_name)}${resource.section?' · '+esc(resource.section):''}</span>`:'';
  return `<a class="resource-card" href="/${projectId}/recurso/${encodeURIComponent(resource.slug)}" data-resource="${esc(resource.slug)}">
    <div class="resource-top"><span class="resource-category">${esc(resource.category)}</span><span class="resource-arrow" aria-hidden="true">↗</span></div>
    <h3>${esc(resource.title)}</h3>${team}<p>${esc(resource.summary)}</p><div class="tags">${resource.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}${resource.has_file?'<span class="tag">Archivo descargable</span>':''}${resource.ai_declaration?'<span class="tag">IA declarada</span>':''}${resource.has_subtitles?'<span class="tag">Subtitulado</span>':''}${resource.quiz_count?'<span class="tag">Preguntas de control</span>':''}${resource.comment_count?`<span class="tag">Foro · ${resource.comment_count}</span>`:''}${resource.has_model?'<span class="tag">Modelo 3D</span>':''}${resource.alternatives?.items?.length?'<span class="tag">Alternativas comparadas</span>':''}</div>
  </a>`;
}
function fieldInput(spec) {
  const id=`f-${spec.key}`, label=`${esc(spec.label)}${spec.required?'':' (opcional)'}`;
  const control=spec.choices?`<select id="${id}" name="pf_${spec.key}" class="select"${spec.required?' required':''}><option value="">Elige una opción</option>${spec.choices.map(c=>`<option>${esc(c)}</option>`).join('')}</select>`
    :`<textarea id="${id}" name="pf_${spec.key}" rows="2" maxlength="1500"${spec.required?' required':''} placeholder="${esc(spec.placeholder||'')}"></textarea>`;
  return `<div class="field"><label for="${id}">${label}</label>${control}</div>`;
}
function showDelivery(projectId) {
  const isInnova=projectId==='innova', config=projectConfig[projectId]||{sections:[],fields:[]}, mine=mySections[projectId]||'';
  document.querySelector('#project-content').innerHTML=`<div class="resource-detail"><div class="eyebrow">Entrega de equipo</div><h2>${isInnova?'Publica tu cápsula y evidencia':'Entrega tu video-prototipo'}</h2>
    <p class="lead">Una persona del grupo envía el único video final y la ficha de evidencia. La entrega queda privada y pendiente de revisión docente.</p>
    <div id="my-submissions"></div>
    <form id="submission-form" class="detail-panel form-grid">
      <div class="field"><label for="s-team">Nombre del equipo</label><input id="s-team" name="team_name" required maxlength="160" placeholder="Ej.: Equipo 4"></div>
      ${config.sections.length?`<div class="field"><label for="s-section">Paralelo</label><select id="s-section" name="section" class="select" required><option value="">Elige el paralelo</option>${config.sections.map(c=>`<option${c===mine?' selected':''}>${esc(c)}</option>`).join('')}</select></div>`:''}
      <div class="field"><label for="s-members">Integrantes del equipo</label><textarea id="s-members" name="members" rows="4" required placeholder="Ana Pérez ana.perez@mail.pucv.cl&#10;Luis Soto luis.soto@mail.pucv.cl"></textarea><span class="helper">Un nombre por línea. Si agregan el correo PUCV, esa persona podrá responder en el foro como «Equipo autor» y ver la coevaluación de sus pares. Solo los nombres se muestran en la ficha.</span></div>
      <div class="field"><label for="s-title">Título del trabajo</label><input id="s-title" name="title" required maxlength="180"></div>
      <div class="field"><label for="s-summary">${isInnova?'Resumen del caso y de la cápsula':'Problema y solución propuesta'}</label><textarea id="s-summary" name="summary" required maxlength="5000"></textarea></div>
      <fieldset class="field-group"><legend>${isInnova?'Recorrido molecular: del hallazgo al diagnóstico':'Ficha del desafío'}</legend><p class="helper">${isInnova?'Sigan la cadena de la guía ABP: alteración, proceso, efecto molecular, cambio celular, patología, técnica y controles.':'Sigan los bloques del storyboard: problema, personas afectadas, solución, simulación, resultado e indicador, y limitación.'}</p>${config.fields.map(fieldInput).join('')}</fieldset>
      ${config.alternative_criteria?.length?alternativesFieldset(config.alternative_criteria):''}
      <div class="field"><label for="s-video">Enlace al único video final (MP4, máximo 5 minutos)</label><input id="s-video" name="video_url" type="url" required placeholder="https://"><span class="helper">Suban el MP4 a una carpeta compartida o plataforma de video y peguen aquí un enlace accesible para la docente. En Drive: Compartir → «Cualquier persona con el enlace».</span><div id="s-video-status" class="helper" role="status" aria-live="polite"></div></div>
      <div class="notice">La ${isInnova?'matriz diagnóstica':'Ficha de Evidencia'} se genera automáticamente con lo que escriban en este formulario: después de enviar, la pueden abrir, imprimir o guardar en PDF desde «Tus entregas». No hace falta llenar la plantilla Word.</div>
      ${isInnova?'<div class="field"><label for="s-model">Modelo 3D del prototipo (opcional)</label><input id="s-model" name="model_file" type="file" accept=".stl"><span class="helper">Archivo STL exportado desde Tinkercad, Fusion 360 o Blender; máximo 8 MB. Se verá en la ficha y se podrá girar.</span></div>':''}
      <div class="field"><label for="s-evidence-file">Material adicional (opcional)</label><input id="s-evidence-file" name="evidence_file" type="file" accept=".pdf,.docx,.pptx,.xlsx,.odt,.txt"><span class="helper">Si quieren sumar anexos, tablas o la <a href="/materiales/${isInnova?'matriz-diagnostica-innova':'ficha-evidencia-incentiva'}.docx" download>plantilla Word</a> completa: PDF, DOCX, PPTX, XLSX, ODT o TXT, máximo 8 MB. También pueden pegar el enlace HTTPS de una carpeta compartida:</span><input id="s-evidence" name="evidence_url" type="url" placeholder="https://"></div>
      <div class="field"><label for="s-ai">Declaración de uso de IA</label><textarea id="s-ai" name="ai_declaration" placeholder="Indica qué herramienta usó el equipo y para qué. Si no usaron IA, escríbanlo."></textarea></div>
      <label class="helper"><input name="has_subtitles" type="checkbox"> El video tiene subtítulos (o texto en pantalla que permite seguirlo sin audio).</label>
      <label class="helper"><input name="video_length_confirmed" type="checkbox" required> Confirmamos que este es el único video final del equipo y que dura máximo cinco minutos.</label>
      <label class="helper"><input name="consent" type="checkbox" required> Confirmamos que los recursos externos tienen permiso de uso y que quienes aparecen o se escuchan en forma identificable autorizaron su participación; también podemos hacer el video sin rostros ni voces identificables. Esta confirmación no autoriza usos posteriores (<a href="/consentimiento" data-route="/consentimiento">autorización opcional de imagen y voz</a>).</label>
      <label class="helper"><input name="showcase_consent" type="checkbox"> Opcional: autorizamos mostrar el trabajo en la vitrina abierta a otros cursos y cohortes de la PUCV (solo lectura).</label>
      <div class="error-text" id="submission-error" role="alert"></div><button class="button project-button" type="submit">Enviar a revisión →</button>
    </form></div>`;
  document.querySelector('#s-video').addEventListener('change',async e=>{const box=document.querySelector('#s-video-status'), url=e.target.value.trim();box.textContent='';
    if(!/^https:\/\/drive\.google\.com\/file\/d\//.test(url))return; box.textContent='Revisando si el video de Drive se puede ver…';
    try{const {status}=await api(`/api/video-check?url=${encodeURIComponent(url)}`);
      box.textContent={public:'✓ El video de Drive se puede ver con el enlace.',private:'⚠ Este video de Drive es privado: el curso no podrá verlo. En Drive, Compartir → «Cualquier persona con el enlace».',missing:'⚠ No encontramos ese archivo en Drive. Revisa el enlace.'}[status]||'';
      box.className=status==='public'?'helper':(status==='unknown'?'helper':'error-text');}catch{box.textContent='';}});
  document.querySelector('#submission-form').addEventListener('submit',async event=>{
    event.preventDefault(); const formElement=event.currentTarget, form=new FormData(formElement), error=document.querySelector('#submission-error'), button=formElement.querySelector('button[type="submit"]');
    try {
      const file=document.querySelector('#s-evidence-file').files[0], model=document.querySelector('#s-model')?.files[0];
      if(file&&file.size>8*1024*1024) throw new Error('El material adicional debe pesar como máximo 8 MB.');
      if(model&&model.size>8*1024*1024) throw new Error('El modelo 3D debe pesar como máximo 8 MB.');
      button.disabled=true;
      const evidence_file_base64=file?await fileToBase64(file):'', model_file_base64=model?await fileToBase64(model):'';
      const project_fields=Object.fromEntries(config.fields.map(f=>[f.key,form.get(`pf_${f.key}`)||'']));
      const res=await api('/api/submissions',{method:'POST',body:JSON.stringify({project_id:projectId,team_name:form.get('team_name'),section:form.get('section')||'',members:form.get('members'),title:form.get('title'),summary:form.get('summary'),video_url:form.get('video_url'),evidence_url:form.get('evidence_url'),evidence_file_base64,evidence_filename:file?.name||'',ai_declaration:form.get('ai_declaration'),project_fields,alternatives:readAlternatives(formElement,config.alternative_criteria||[]),model_file_base64,model_filename:model?.name||'',video_length_confirmed:form.get('video_length_confirmed')==='on',consent_confirmed:form.get('consent')==='on',has_subtitles:form.get('has_subtitles')==='on',showcase_consent:form.get('showcase_consent')==='on'})});
      notify(res.message); formElement.reset(); error.textContent=''; await loadMySubmissions(projectId);
      if(res.id) document.querySelector('#my-submissions').scrollIntoView({behavior:'smooth',block:'start'});
    }
    catch(err){error.textContent=err.message;}
    finally{button.disabled=false;}
  });
  loadMySubmissions(projectId);
}
function alternativesFieldset(criteria) {
  const select=(alt,i)=>`<select class="select score-select" name="alt${alt}_c${i}" aria-label="Alternativa ${alt+1}: ${esc(criteria[i])}"><option value="">–</option><option>1</option><option>2</option><option>3</option></select>`;
  return `<fieldset class="field-group"><legend>Comparación de alternativas (recomendada)</legend><p class="helper">Antes de elegir, la postulación pide comparar al menos dos ideas. Puntúen cada criterio de 1 (bajo) a 3 (alto) y marquen la elegida. Aparece en la ficha de evidencia.</p>
    <div class="table-scroll"><table class="code-table alternatives-table"><thead><tr><th>Criterio</th>${[0,1,2].map(a=>`<th><label class="visually-hidden" for="alt${a}-name">Nombre de la alternativa ${a+1}</label><input id="alt${a}-name" name="alt${a}_name" maxlength="160" placeholder="Alternativa ${String.fromCharCode(65+a)}"></th>`).join('')}</tr></thead>
    <tbody>${criteria.map((c,i)=>`<tr><td>${esc(c)}</td>${[0,1,2].map(a=>`<td>${select(a,i)}</td>`).join('')}</tr>`).join('')}
    <tr><td><b>Elegida</b></td>${[0,1,2].map(a=>`<td><label><input type="radio" name="alt_chosen" value="${a}"${a===0?' checked':''}> Esta</label></td>`).join('')}</tr></tbody></table></div></fieldset>`;
}
function readAlternatives(form, criteria) {
  if(!criteria.length) return null;
  const items=[]; let chosen=0;
  [0,1,2].forEach(a=>{const name=(form.elements[`alt${a}_name`]?.value||'').trim(); if(!name) return;
    const scores=criteria.map((_,i)=>Number(form.elements[`alt${a}_c${i}`].value)||0);
    if(scores.some(v=>!v)) throw new Error(`Puntúa todos los criterios de «${name}» o borra su nombre.`);
    if(form.elements.alt_chosen.value===String(a)) chosen=items.length;
    items.push({name,scores});});
  return items.length?{items,chosen}:null;
}
function alternativesTable(alt) {
  if(!alt?.items?.length) return '';
  return `<div class="table-scroll"><table class="code-table alternatives-table"><thead><tr><th>Criterio (1 a 3)</th>${alt.items.map((it,i)=>`<th>${esc(it.name)}${i===alt.chosen?' <span class="status-label">✓ elegida</span>':''}</th>`).join('')}</tr></thead>
    <tbody>${alt.criteria.map((c,ci)=>`<tr><td>${esc(c)}</td>${alt.items.map(it=>`<td>${it.scores[ci]}</td>`).join('')}</tr>`).join('')}<tr><td><b>Total</b></td>${alt.items.map(it=>`<td><b>${it.total}</b></td>`).join('')}</tr></tbody></table></div>`;
}
// Minimal STL viewer on a 2D canvas: flat-shaded triangles, painter's algorithm, drag or arrow keys to rotate.
async function mountStlViewer(canvas, url) {
  const ctx=canvas.getContext('2d'); let tris;
  try{const buffer=await (await fetch(url,{credentials:'same-origin'})).arrayBuffer(); tris=parseStl(buffer);}
  catch{canvas.replaceWith(Object.assign(document.createElement('p'),{className:'helper',textContent:'No se pudo abrir el modelo 3D.'}));return;}
  if(!tris.length) return;
  let min=[Infinity,Infinity,Infinity], max=[-Infinity,-Infinity,-Infinity];
  tris.forEach(t=>t.forEach(v=>v.forEach((c,i)=>{min[i]=Math.min(min[i],c);max[i]=Math.max(max[i],c);})));
  const center=min.map((m,i)=>(m+max[i])/2), size=Math.max(...max.map((m,i)=>m-min[i]))||1;
  let yaw=0.6, pitch=-0.5;
  const accent=getComputedStyle(canvas).color.match(/\d+/g).map(Number);
  const draw=()=>{const w=canvas.width=canvas.clientWidth*devicePixelRatio, h=canvas.height=canvas.clientHeight*devicePixelRatio, scale=Math.min(w,h)*0.8/size;
    const cy=Math.cos(yaw), sy=Math.sin(yaw), cp=Math.cos(pitch), sp=Math.sin(pitch);
    const tf=v=>{const x=v[0]-center[0], y=v[1]-center[1], z=v[2]-center[2]; const x1=cy*x+sy*y, y1=-sy*x+cy*y; return [x1, cp*z-sp*y1, sp*z+cp*y1];};
    const faces=[];
    for(const t of tris){const a=tf(t[0]), b=tf(t[1]), c=tf(t[2]);
      const u=[b[0]-a[0],b[1]-a[1],b[2]-a[2]], v=[c[0]-a[0],c[1]-a[1],c[2]-a[2]], n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
      const len=Math.hypot(...n)||1, light=Math.abs(n[2]/len)*0.75+0.25; faces.push([(a[2]+b[2]+c[2])/3,a,b,c,light]);}
    faces.sort((f,g)=>f[0]-g[0]);
    ctx.clearRect(0,0,w,h);
    for(const [,a,b,c,l] of faces){ctx.beginPath();ctx.moveTo(w/2+a[0]*scale,h/2-a[1]*scale);ctx.lineTo(w/2+b[0]*scale,h/2-b[1]*scale);ctx.lineTo(w/2+c[0]*scale,h/2-c[1]*scale);ctx.closePath();
      ctx.fillStyle=`rgb(${accent.slice(0,3).map(x=>Math.round(x*l+255*(1-l)*0.15)).join(',')})`;ctx.fill();}};
  let drag=null;
  canvas.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*0.01;pitch=Math.max(-1.5,Math.min(1.5,pitch+(e.clientY-drag[1])*0.01));drag=[e.clientX,e.clientY];draw();});
  canvas.addEventListener('pointerup',()=>{drag=null;});
  canvas.addEventListener('keydown',e=>{const k={ArrowLeft:[-0.2,0],ArrowRight:[0.2,0],ArrowUp:[0,-0.2],ArrowDown:[0,0.2]}[e.key];if(!k)return;e.preventDefault();yaw+=k[0];pitch=Math.max(-1.5,Math.min(1.5,pitch+k[1]));draw();});
  new ResizeObserver(draw).observe(canvas); draw();
}
function parseStl(buffer) {
  const view=new DataView(buffer), count=buffer.byteLength>=84?view.getUint32(80,true):0, tris=[];
  if(84+count*50===buffer.byteLength){
    for(let i=0;i<Math.min(count,60000);i++){const o=84+i*50+12;tris.push([0,1,2].map(k=>[0,1,2].map(j=>view.getFloat32(o+k*12+j*4,true))));}
    return tris;}
  const text=new TextDecoder().decode(buffer), nums=[...text.matchAll(/vertex\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)/g)].map(m=>[+m[1],+m[2],+m[3]]);
  for(let i=0;i+2<nums.length&&tris.length<60000;i+=3) tris.push([nums[i],nums[i+1],nums[i+2]]);
  return tris;
}
async function fichaPage(id) {
  main.innerHTML='<div class="resource-detail"><div class="loading">Generando ficha…</div></div>';
  let f;
  try{f=await api(`/api/submissions/${id}/ficha`);}
  catch(e){main.innerHTML=`<div class="empty-state"><h1>Ficha no disponible</h1><p>${esc(e.message)}</p><a class="button small" href="/" data-route="/">Ir a la portada</a></div>`;return;}
  const innova=f.project_id==='innova';
  main.innerHTML=`<article class="resource-detail ficha-page project-page ${innova?'innova-theme':''}"><a class="back-link no-print" href="/${f.project_id}" data-route="/${f.project_id}">← Volver a ${esc(f.project_name)}</a>
    <div class="eyebrow">${esc(f.project_name)} · ${esc(f.course)} · Cohorte ${esc(f.cohort)}</div><h1>${innova?'Matriz diagnóstica':'Ficha de Evidencia de la Innovación'}</h1>
    <p class="no-print"><button class="button small" type="button" id="print-ficha">Imprimir o guardar como PDF</button> <span class="helper">Generada a partir de la entrega del ${esc(f.created_at.slice(0,10))} · ${esc(SUBMISSION_STATUS[f.status]||f.status)}</span></p>
    <section class="detail-panel"><h2>Identificación</h2><dl class="field-list"><div><dt>Título</dt><dd>${esc(f.title)}</dd></div><div><dt>Equipo</dt><dd>${esc(f.team_name)}${f.section?' · Paralelo '+esc(f.section):''}</dd></div><div><dt>Integrantes</dt><dd>${f.members.map(esc).join(' · ')}</dd></div>
      <div><dt>Video final</dt><dd><a href="${esc(f.video_url)}" target="_blank" rel="noopener noreferrer">${esc(f.video_url)}</a>${f.has_subtitles?' · con subtítulos':''}</dd></div></dl></section>
    <section class="detail-panel"><h2>${innova?'Resumen del caso y de la cápsula':'Problema y solución propuesta'}</h2>${richText(f.summary)}</section>
    <section class="detail-panel"><h2>${innova?'Del hallazgo al diagnóstico':'Fundamentación'}</h2><dl class="field-list">${f.fields.map(x=>`<div><dt>${esc(x.label)}</dt><dd>${richText(x.value)}</dd></div>`).join('')}</dl></section>
    ${f.alternatives?.items?.length?`<section class="detail-panel"><h2>Alternativas evaluadas</h2>${alternativesTable(f.alternatives)}</section>`:(innova?'':'<section class="detail-panel"><h2>Alternativas evaluadas</h2><p class="helper">El equipo no registró la comparación de alternativas.</p></section>')}
    ${f.model_filename?`<section class="detail-panel"><h2>Prototipo 3D</h2><p class="detail-content">Modelo adjunto: ${esc(f.model_filename)} (se ve y se gira en la ficha del repositorio).</p></section>`:''}
    <section class="detail-panel"><h2>Declaración de uso de IA</h2><p class="detail-content">${esc(f.ai_declaration||'El equipo no declaró uso de IA.')}</p>
      <p class="detail-content">Declaramos que el problema, la evidencia, el análisis y las conclusiones son del equipo, y que revisamos todo lo producido con IA.</p></section>
    ${f.evidence_url||f.evidence_filename?`<section class="detail-panel"><h2>Material adicional</h2>${f.evidence_filename?`<p class="detail-content"><a href="/api/submissions/${f.id}/evidence">${esc(f.evidence_filename)}</a></p>`:''}${f.evidence_url?`<p class="detail-content"><a href="${esc(f.evidence_url)}" target="_blank" rel="noopener noreferrer">${esc(f.evidence_url)}</a></p>`:''}</section>`:''}
  </article>`;
  document.querySelector('#print-ficha').addEventListener('click',()=>window.print());
}
async function showTickets(projectId) {
  const root=document.querySelector('#project-content');
  root.innerHTML=`<div class="resource-detail"><div class="eyebrow">Cierre de cada sesión</div><h2>Tiquetes de salida</h2><p class="lead">Tres preguntas breves sin nombre al final de la clase. La docente agrupa las dudas y responde en la sesión siguiente o con un audio.</p><div id="ticket-items" class="detail-panel"><p class="helper">Cargando…</p></div>
    <h2>Encuestas</h2><p class="helper">Autoevaluación KPSI al inicio y al cierre, y encuesta de percepción. La respuesta no se vincula con tu nombre; se registra por separado que ya participaste.</p><div id="survey-items" class="detail-panel"><p class="helper">Cargando…</p></div></div>`;
  const box=root.querySelector('#ticket-items'), surveyBox=root.querySelector('#survey-items');
  api(`/api/my-surveys?project=${projectId}`).then(items=>{surveyBox.innerHTML=items.length?items.map(t=>`<article class="submission-status"><div><strong>${esc(t.title)}</strong><span class="helper"> · ${t.answered?'Respondida':t.open?'Abierta hasta '+new Date(t.closes_at*1000).toLocaleString('es-CL',{dateStyle:'short',timeStyle:'short'}):'Cerrada'}</span></div>${t.open&&!t.answered?`<a class="button small" href="/encuesta/${esc(t.code)}" data-route="/encuesta/${esc(t.code)}">Responder →</a>`:''}</article>`).join(''):'<p class="helper">No hay encuestas por ahora.</p>';}).catch(e=>{surveyBox.textContent=e.message;});
  try{const items=await api(`/api/my-tickets?project=${projectId}`);
    box.innerHTML=items.length?items.map(t=>`<article class="submission-status"><div><strong>${t.kind==='previa'?'Preguntas previas · ':''}${esc(t.title)}</strong><span class="helper"> · ${t.answered?'Respondido':t.open?'Abierto hasta '+new Date(t.closes_at*1000).toLocaleString('es-CL',{dateStyle:'short',timeStyle:'short'}):'Cerrado'}</span></div>
      <div class="moderation-actions">${t.open&&!t.answered?`<a class="button small" href="/tiquete/${esc(t.code)}" data-route="/tiquete/${esc(t.code)}">Responder →</a>`:''}${t.feedback_url?`<a class="button secondary small" href="${esc(t.feedback_url)}" target="_blank" rel="noopener noreferrer">Retroalimentación de la docente ↗</a>`:''}</div></article>`).join(''):'<p class="helper">La docente aún no abre tiquetes en esta asignatura.</p>';
  }catch(e){box.textContent=e.message;}
}
async function ticketPage(code) {
  main.innerHTML='<div class="resource-detail"><div class="loading">Cargando tiquete…</div></div>';
  let t;
  try{t=await api(`/api/tickets/${encodeURIComponent(code)}`);}
  catch(e){main.innerHTML=`<div class="empty-state"><h1>Tiquete no disponible</h1><p>${esc(e.message)} Si aún no entras a la asignatura, abre la invitación del curso o escribe el código que te dio la docente en la portada.</p><a class="button small" href="/" data-route="/">Ir a la portada</a></div>`;return;}
  const p=PROJECTS[t.project_id], feedback=t.feedback_url?`<a class="button secondary small" href="${esc(t.feedback_url)}" target="_blank" rel="noopener noreferrer">Escuchar la retroalimentación ↗</a>`:'';
  const head=`<div class="eyebrow">${esc(p.name)} · ${t.kind==='previa'?'Preguntas previas a la sesión':'Tiquete de salida'}</div><h1>${esc(t.title)}</h1>`;
  if(t.answered||!t.open){main.innerHTML=`<div class="resource-detail ${t.project_id==='innova'?'innova-theme':''}">${head}<div class="detail-panel"><p>${t.answered?'Ya respondiste este tiquete. ¡Gracias!':'Este tiquete ya cerró.'}</p>${feedback}<p><a class="text-button" href="/${t.project_id}" data-route="/${t.project_id}">Volver a ${esc(p.name)} →</a></p></div></div>`;return;}
  main.innerHTML=`<div class="resource-detail ${t.project_id==='innova'?'innova-theme':''}">${head}<p class="lead">Tu respuesta no lleva tu nombre ni correo. Basta con una o dos frases.</p>
    <form id="ticket-answer" class="detail-panel form-grid">${t.questions.map((q,i)=>`<div class="field"><label for="tq-${i}">${i+1}. ${esc(q)}</label><textarea id="tq-${i}" name="q${i}" maxlength="1500" rows="3" required></textarea></div>`).join('')}
    <div class="error-text" role="alert"></div><button class="button project-button" type="submit">Enviar respuestas →</button></form></div>`;
  const form=document.querySelector('#ticket-answer');
  form.addEventListener('submit',async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;
    try{const r=await api(`/api/tickets/${encodeURIComponent(code)}/answer`,{method:'POST',body:JSON.stringify({answers:t.questions.map((_,i)=>form.elements[`q${i}`].value)})});notify(r.message);ticketPage(code);}
    catch(ex){form.querySelector('.error-text').textContent=ex.message;button.disabled=false;}});
}
async function surveyPage(code) {
  main.innerHTML='<div class="resource-detail"><div class="loading">Cargando encuesta…</div></div>';
  let t;
  try{t=await api(`/api/surveys/${encodeURIComponent(code)}`);}
  catch(e){main.innerHTML=`<div class="empty-state"><h1>Encuesta no disponible</h1><p>${esc(e.message)}</p><a class="button small" href="/" data-route="/">Ir a la portada</a></div>`;return;}
  const p=PROJECTS[t.project_id], theme=t.project_id==='innova'?'innova-theme':'', head=`<div class="eyebrow">${esc(p.name)} · ${t.kind==='kpsi'?'Autoevaluación KPSI':'Encuesta de percepción'}</div><h1>${esc(t.title)}</h1>`;
  if(t.answered||!t.open){main.innerHTML=`<div class="resource-detail ${theme}">${head}<div class="detail-panel"><p>${t.answered?'Ya respondiste esta encuesta. ¡Gracias!':'Esta encuesta ya cerró.'}</p><a class="text-button" href="/${t.project_id}" data-route="/${t.project_id}">Volver a ${esc(p.name)} →</a></div></div>`;return;}
  let dimension=null;
  const rows=t.items.map((item,i)=>{const header=item.dimension!==dimension?`<h2 class="survey-dimension">${esc(item.dimension||'Enunciados')}</h2>`:'';dimension=item.dimension;
    return `${header}<fieldset class="rubric-row"><legend>${i+1}. ${esc(item.text)}</legend><div class="rubric-levels">${t.scale.map((level,j)=>`<label><input type="radio" name="i${i}" value="${j+1}" required> ${j+1} · ${esc(level)}</label>`).join('')}</div></fieldset>`;}).join('');
  main.innerHTML=`<div class="resource-detail ${theme}">${head}<p class="lead">${t.kind==='kpsi'?'Marca qué tan bien dominas hoy cada contenido. No es una evaluación: sirve para comparar el inicio con el cierre del proyecto.':'Cuéntanos cómo viviste la experiencia. Tus respuestas ayudan a mejorar el proyecto para la próxima cohorte.'} No se guarda tu nombre o correo junto a lo que respondes; para limitar duplicados, el sistema registra por separado quién participó.</p>
    <form id="survey-answer" class="detail-panel form-grid">${rows}<div class="field"><label for="sv-comment">Comentario (opcional)</label><textarea id="sv-comment" maxlength="1500" rows="3"></textarea></div><div class="error-text" role="alert"></div><button class="button project-button" type="submit">Enviar respuestas →</button></form></div>`;
  const form=document.querySelector('#survey-answer');
  form.addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(form), button=form.querySelector('button[type="submit"]');button.disabled=true;
    try{const r=await api(`/api/surveys/${encodeURIComponent(code)}/answer`,{method:'POST',body:JSON.stringify({values:t.items.map((_,i)=>Number(f.get(`i${i}`))),comment:document.querySelector('#sv-comment').value})});notify(r.message);surveyPage(code);}
    catch(ex){form.querySelector('.error-text').textContent=ex.message;button.disabled=false;}});
}
// Icons repeat the meaning of the color, which red/green color blindness can't tell apart.
const SUBMISSION_STATUS={review:'◷ En revisión docente',approved:'✓ Aprobada',published:'✓ Publicada en el repositorio',rejected:'↺ Devuelta para corregir'};
async function loadMySubmissions(projectId) {
  const box=document.querySelector('#my-submissions'); if(!box)return;
  try{const rows=await api(`/api/my-submissions?project=${projectId}`);
    box.innerHTML=rows.length?`<section class="detail-panel"><h2>Tus entregas</h2>${rows.map(s=>`<article class="submission-status status-${esc(s.status)}"><div><strong>${esc(s.title)}</strong><span class="helper"> · ${esc(s.team_name)}${s.section?' · '+esc(s.section):''} · ${esc(s.created_at)}</span></div><span class="status-label">${esc(SUBMISSION_STATUS[s.status]||s.status)}</span>${s.review_note?`<p class="helper">Comentario docente: ${esc(s.review_note)}</p>`:''}${s.status==='rejected'?'<p class="helper">Pueden corregir y volver a enviar con el mismo nombre de equipo.</p>':''}<a class="text-button" href="/ficha/${Number(s.id)}" data-route="/ficha/${Number(s.id)}">Ver la ficha de evidencia generada →</a></article>`).join('')}</section>`:'';
  }catch{box.innerHTML='';}
}
function showForum(projectId) {
  const root=document.querySelector('#project-content'), items=resourceCache[projectId]||[];
  root.innerHTML=`<div class="resource-detail"><div class="eyebrow">Conversación científica</div><h2>Foro</h2><p class="lead">Cada ficha tiene una pregunta guía. Respóndela o pregunta al equipo autor: sus respuestas aparecen destacadas. Los mensajes se revisan antes de publicarse.</p>
    ${items.length?`<div class="field"><label for="forum-resource">Elige una ficha</label><select id="forum-resource" class="select">${items.map(r=>`<option value="${esc(r.slug)}">${esc(r.title)}${r.comment_count?` (${r.comment_count})`:''}</option>`).join('')}</select></div><div id="forum-content" class="detail-panel"></div>`:'<div class="empty-state">Todavía no hay fichas publicadas.</div>'}</div>`;
  const select=root.querySelector('#forum-resource'); if(!select)return;
  const open=()=>mountDiscussion(root.querySelector('#forum-content'),projectId,items.find(r=>r.slug===select.value));
  select.addEventListener('change',open); open();
}
const BADGES={equipo:'Equipo autor',docente:'Docente'};
function commentThread(comments) {
  const top=comments.filter(c=>!c.parent_id);
  if(!top.length) return '<p class="helper">Todavía no hay comentarios publicados. Puedes empezar respondiendo la pregunta guía.</p>';
  const item=c=>`<article class="comment${c.badge?' badge-'+c.badge:''}"><strong>${esc(c.display_name)}</strong>${c.badge?`<span class="comment-badge">${BADGES[c.badge]||''}</span>`:''}<p>${esc(c.body)}</p></article>`;
  // Answers from the authoring team and teachers go first inside each thread.
  const replies=id=>comments.filter(c=>c.parent_id===id).sort((a,b)=>(b.badge?1:0)-(a.badge?1:0));
  return top.map(c=>`<div class="thread">${item(c)}${replies(c.id).map(r=>`<div class="reply">${item(r)}</div>`).join('')}<button class="text-button" type="button" data-reply="${c.id}" data-name="${esc(c.display_name)}">Responder</button></div>`).join('');
}
async function mountDiscussion(box, projectId, resource) {
  const draw=async()=>{
    const comments=await api(`/api/projects/${projectId}/resources/${encodeURIComponent(resource.slug)}/comments`);
    box.innerHTML=`<div class="guide-question"><span class="eyebrow">Pregunta guía</span><p>${esc(resource.guide_question)}</p></div><div class="comment-list">${commentThread(comments)}</div>
      <form class="form-grid discussion-form"><input type="hidden" name="parent_id" value=""><div class="reply-target helper" hidden></div><div class="field"><label for="comment-body-${resource.id}">Tu respuesta, pregunta o comentario</label><textarea id="comment-body-${resource.id}" name="body" maxlength="1200" required></textarea></div><div class="error-text" role="alert"></div><button class="button small" type="submit">Enviar</button></form>`;
    const form=box.querySelector('form'), target=form.querySelector('.reply-target');
    const clearReply=()=>{form.elements.parent_id.value='';target.hidden=true;};
    box.querySelectorAll('[data-reply]').forEach(b=>b.addEventListener('click',()=>{form.elements.parent_id.value=b.dataset.reply;target.hidden=false;
      target.innerHTML=`Respondiendo a ${esc(b.dataset.name)} · <button type="button" class="text-button">cancelar</button>`;target.querySelector('button').addEventListener('click',clearReply);form.elements.body.focus();}));
    form.addEventListener('submit',async e=>{e.preventDefault();const err=form.querySelector('.error-text'), button=form.querySelector('[type="submit"]');button.disabled=true;
      try{const result=await api('/api/comments',{method:'POST',body:JSON.stringify({project_id:projectId,slug:resource.slug,body:form.elements.body.value,parent_id:form.elements.parent_id.value||null})});
        notify(result.message);if(result.status==='published'){await draw();return;}form.elements.body.value='';clearReply();err.textContent='';}
      catch(ex){err.textContent=ex.message;}finally{button.disabled=false;}});
  };
  try{await draw();}catch(e){box.innerHTML=`<div class="notice">${esc(e.message)}</div>`;}
}
async function mountQuiz(box, resource) {
  const results=(answers,correct,explanations,score)=>`<p class="quiz-score">Obtuviste ${score} de ${correct.length}.</p>${state.questions.map((q,i)=>`<div class="quiz-question"><strong>${i+1}. ${esc(q.prompt)}</strong><ul class="quiz-options">${q.options.map((o,j)=>`<li class="${j===correct[i]?'is-correct':''}${j===answers[i]&&j!==correct[i]?' is-wrong':''}">${esc(o)}${j===correct[i]?' <span class="helper">· correcta</span>':''}${j===answers[i]?' <span class="helper">· tu respuesta</span>':''}</li>`).join('')}</ul>${explanations[i]?`<p class="helper">${esc(explanations[i])}</p>`:''}</div>`).join('')}`;
  let state;
  try{state=await api(`/api/quiz/${resource.id}`);}catch(e){box.textContent=e.message;return;}
  if(state.attempt){const a=state.attempt;box.innerHTML=results(a.answers,a.correct,a.explanations,a.score);return;}
  box.innerHTML=`<form class="form-grid">${state.questions.map((q,i)=>`<fieldset class="quiz-question"><legend>${i+1}. ${esc(q.prompt)}</legend>${q.options.map((o,j)=>`<label class="quiz-option"><input type="radio" name="q${i}" value="${j}" required> ${esc(o)}</label>`).join('')}</fieldset>`).join('')}<p class="helper">Solo cuenta el primer intento; después verás las respuestas y su explicación.</p><div class="error-text" role="alert"></div><button class="button small" type="submit">Revisar respuestas</button></form>`;
  const form=box.querySelector('form');
  form.addEventListener('submit',async e=>{e.preventDefault();const answers=state.questions.map((_,i)=>Number(new FormData(form).get(`q${i}`)));
    try{const r=await api(`/api/quiz/${resource.id}`,{method:'POST',body:JSON.stringify({answers})});box.innerHTML=results(answers,r.correct,r.explanations,r.score);}
    catch(ex){form.querySelector('.error-text').textContent=ex.message;}});
}
async function mountPeer(box, resource) {
  let data;
  try{data=await api(`/api/peer/${resource.id}`);}catch(e){box.closest('section').remove();return;}
  const summary=data.summary?`<div class="peer-summary"><h3>${data.is_author?'Lo que dicen sus pares':'Resultados de la coevaluación'}</h3>${data.summary.count?`<p class="helper">${data.summary.count} evaluaciones · promedio general ${data.summary.overall??'—'} de 4</p><table class="code-table"><tbody>${data.summary.averages.map(a=>`<tr><td>${esc(a.label)}</td><td><b>${a.average??'—'}</b></td></tr>`).join('')}</tbody></table>${(data.comments||[]).map(c=>`<article class="comment"><p><b>Fortaleza:</b> ${esc(c.strength)}</p><p><b>Sugerencia:</b> ${esc(c.suggestion)}</p></article>`).join('')}`:'<p class="helper">Aún no hay evaluaciones de pares.</p>'}</div>`:'';
  if(!data.can_review){box.innerHTML=summary||'<p class="helper">Esta ficha es de tu equipo.</p>';return;}
  const mine=data.mine||{scores:{},strength:'',suggestion:''};
  box.innerHTML=`${summary}<form class="form-grid peer-form"><p class="helper">Evalúa con la misma rúbrica que usa la docente. Tu evaluación llega al equipo sin tu nombre; la docente sí la ve.${data.mine?' Ya enviaste una evaluación: puedes corregirla.':''}</p>
    ${data.rubric.map(c=>`<fieldset class="rubric-row"><legend><b>${esc(c.label)}</b> <span class="helper">${esc(c.hint)}</span></legend><div class="rubric-levels">${data.levels.map((level,i)=>`<label><input type="radio" name="${esc(c.key)}" value="${i+1}" required${mine.scores[c.key]===i+1?' checked':''}> ${i+1} · ${esc(level)}</label>`).join('')}</div></fieldset>`).join('')}
    <div class="field"><label for="peer-strength-${resource.id}">Una fortaleza del trabajo</label><textarea id="peer-strength-${resource.id}" name="strength" maxlength="1000" required>${esc(mine.strength)}</textarea></div>
    <div class="field"><label for="peer-suggestion-${resource.id}">Una sugerencia concreta para mejorarlo</label><textarea id="peer-suggestion-${resource.id}" name="suggestion" maxlength="1000" required>${esc(mine.suggestion)}</textarea></div>
    <div class="error-text" role="alert"></div><button class="button small" type="submit">${data.mine?'Actualizar coevaluación':'Enviar coevaluación'}</button></form>`;
  const form=box.querySelector('form');
  form.addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(form);
    try{const r=await api(`/api/peer/${resource.id}`,{method:'POST',body:JSON.stringify({scores:Object.fromEntries(data.rubric.map(c=>[c.key,Number(f.get(c.key))])),strength:f.get('strength'),suggestion:f.get('suggestion')})});notify(r.message);mountPeer(box,resource);}
    catch(ex){form.querySelector('.error-text').textContent=ex.message;}});
}
function videoPanel(resource) {
  if(!resource.media_url) return '';
  const captions=resource.has_subtitles?'El equipo declara que el video tiene subtítulos: actívalos con el botón CC del reproductor.':'Este video no declara subtítulos. Si los necesitas, pídelos en el foro o a la docente.';
  return `<section class="detail-panel"><h2>Video del equipo</h2>${resource.embed_url?`<div class="video-frame"><iframe src="${esc(resource.embed_url)}" title="Video: ${esc(resource.title)}" allow="encrypted-media; picture-in-picture; fullscreen" loading="lazy" referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`:''}
    <p class="helper">${captions}</p><a class="text-button" href="${esc(resource.media_url)}" target="_blank" rel="noopener noreferrer">Abrir el video en una pestaña nueva ↗</a></section>`;
}
function detailPage(projectId, slug, reader=false) {
  const p=PROJECTS[projectId], cls=projectId==='innova'?'innova-theme':'';
  main.innerHTML=`<div class="project-page ${cls}"><a class="back-link" href="/${projectId}" data-route="/${projectId}">← Volver a ${esc(p.name)}</a><div id="detail-container" class="resource-detail"><div class="loading">Cargando ficha…</div></div></div>`;
  loadResources(projectId).then(()=>{
    const resource=resourceCache[projectId].find(r=>r.slug===slug), root=document.querySelector('#detail-container');
    if(!resource){root.innerHTML='<div class="empty-state">No encontramos esta ficha en este proyecto.</div>';return;}
    const isInnova=projectId==='innova', fields=resource.fields||[], student=Boolean(resource.source_submission_id);
    const credits=resource.team_name?`<p class="resource-credits">${esc(/^equipo\b/i.test(resource.team_name)?resource.team_name:'Equipo '+resource.team_name)}${resource.section?' · Paralelo '+esc(resource.section):''}${resource.members?.length?`<br><span class="helper">${resource.members.map(esc).join(' · ')}</span>`:''}</p>`:'';
    const body=fields.length?`<section class="detail-panel"><h2>${isInnova?'Del hallazgo al diagnóstico':'Ficha del desafío'}</h2><dl class="field-list">${fields.map(f=>`<div><dt>${esc(f.label)}</dt><dd>${paragraphs(f.value)}</dd></div>`).join('')}</dl>${resource.ai_declaration?`<p class="helper">Uso de IA declarado por el equipo: ${esc(resource.ai_declaration)}</p>`:''}</section>`
      :`<section class="detail-panel"><h2>${isInnova?'Caso clínico y antecedentes':'Sobre este desafío'}</h2>${richText(resource.content||resource.summary)}
      <p class="helper">${isInnova?'Integra alteración molecular, efecto funcional, manifestación clínica y decisión diagnóstica.':'Vincula la necesidad territorial, la evidencia y la viabilidad de la solución.'}</p></section>`;
    root.innerHTML=`<span class="resource-category">${esc(resource.category)}</span><h1>${esc(resource.title)}</h1>${credits}<p class="lead">${esc(resource.summary)}</p><div class="tags">${resource.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>
      ${videoPanel(resource)}
      ${body}
      ${resource.alternatives?.items?.length?`<section class="detail-panel"><h2>Alternativas evaluadas</h2>${alternativesTable(resource.alternatives)}</section>`:''}
      ${resource.has_model&&!reader?`<section class="detail-panel"><h2>Prototipo 3D</h2><canvas class="stl-viewer" tabindex="0" role="img" aria-label="Modelo 3D del prototipo. Arrastra o usa las flechas para girarlo."></canvas><p class="helper">Arrastra para girarlo (o usa las flechas del teclado). <a href="/api/submissions/${Number(resource.source_submission_id)}/model" download>Descargar STL ↧</a></p></section>`:''}
      ${reader?'':`
      ${resource.quiz_count?'<section class="detail-panel"><h2>Preguntas de control</h2><div id="detail-quiz"><p class="helper">Cargando…</p></div></section>':''}
      ${student?`<section class="detail-panel"><h2>Ficha de evidencia</h2><div class="moderation-actions"><a class="button small" href="/ficha/${Number(resource.source_submission_id)}" data-route="/ficha/${Number(resource.source_submission_id)}">Ver la ficha generada →</a>${resource.has_evidence?`<a class="button secondary small" href="/api/submissions/${Number(resource.source_submission_id)}/evidence">Material adicional ↧</a>`:''}</div></section>`:''}
      ${resource.has_file?`<section class="detail-panel"><h2>Archivo del material</h2><a class="button small" href="/api/projects/${projectId}/resources/${encodeURIComponent(resource.slug)}/file">Descargar ${esc(resource.file_filename||'archivo del curso')} ↧</a></section>`:''}
      <section class="detail-panel"><h2>Foro de esta ficha</h2><div id="detail-comments"><p class="helper">Cargando comentarios…</p></div></section>
      ${student?'<section class="detail-panel"><h2>Coevaluación entre pares</h2><div id="detail-peer"><p class="helper">Cargando…</p></div></section>':''}`}`;
    if(reader) return;
    mountDiscussion(document.querySelector('#detail-comments'),projectId,resource);
    if(resource.quiz_count) mountQuiz(document.querySelector('#detail-quiz'),resource);
    if(resource.has_model) mountStlViewer(root.querySelector('.stl-viewer'),`/api/submissions/${Number(resource.source_submission_id)}/model`);
    if(student) mountPeer(document.querySelector('#detail-peer'),resource);
  }).catch(e=>document.querySelector('#detail-container').innerHTML=`<div class="empty-state">${esc(e.message)}</div>`);
}
function login(error='') {
  const params=new URLSearchParams(location.search), reason=params.get('error');
  const err=error||(reason==='domain'?'Esta cuenta no está habilitada: usa tu cuenta institucional @mail.pucv.cl o @pucv.cl.':reason==='auth'?'No fue posible completar el acceso. Inténtalo de nuevo.':reason==='google_off'?'El ingreso con Google todavía no está configurado. Usa tu código de ingreso.':reason==='expired'?'El enlace venció o ya fue usado. Solicita uno nuevo.':'');
  const google=window.APP_GOOGLE_READY, email=window.APP_EMAIL_READY;
  main.innerHTML=`<section class="login-layout"><div class="login-intro"><div class="eyebrow">Tecnología Médica · PUCV</div><h1>Aprender, explicar y compartir.</h1><p>Accede a los dos proyectos de innovación docente desde un espacio común. Cada proyecto mantiene sus casos, trabajos y conversaciones por separado.</p>
    <div class="login-benefit"><div class="benefit"><span class="benefit-icon">✓</span><span>Entra con tu cuenta institucional o con el código que entrega la docente.</span></div><div class="benefit"><span class="benefit-icon">✓</span><span>Tus entregas quedan asociadas a tu correo.</span></div><div class="benefit"><span class="benefit-icon">✓</span><span>Los comentarios se revisan antes de hacerse visibles.</span></div></div></div>
    <div class="login-panel"><span class="eyebrow">Acceso privado</span><h2>Ingresa con PUCV</h2>
      ${params.has('unirse')?'<div class="notice">Tienes una invitación a una asignatura. Escribe tu correo institucional abajo y entra: el código del curso ya está puesto.</div>':''}
      ${err?`<div class="error-text" role="alert">${esc(err)}</div>`:''}
      ${google?`<p>Usa tu cuenta Google institucional <strong>@mail.pucv.cl</strong> o <strong>@pucv.cl</strong>.</p><a class="button google-button" href="/auth/google"><span class="google-g" aria-hidden="true">G</span>Continuar con Google PUCV</a>`:''}
      ${email?`${google?'<div class="login-separator"></div>':''}<form id="magic-form" class="form-grid"><div class="field"><label for="institutional-email">${google?'O recibe un enlace en tu correo':'Correo institucional'}</label><input id="institutional-email" type="email" autocomplete="email" required maxlength="254" placeholder="nombre@mail.pucv.cl"></div><div id="magic-status" class="helper" role="status" aria-live="polite"></div><button class="button ${google?'secondary':''}" type="submit">Enviar enlace de acceso →</button></form><p class="helper">El enlace vence en 15 minutos y solo se puede usar una vez.</p>`:''}
      <details class="code-panel" ${(google||email)&&!params.has('unirse')?'':'open'}><summary>Tengo un código de ingreso</summary><p class="helper">Escribe tu correo institucional y el código que entregó la docente: el <strong>código del curso</strong> (el mismo para todo el paralelo) o tu código personal. Sirve aunque no tengas acceso a Google o al correo en este momento.</p><form id="code-form" class="form-grid"><div class="field"><label for="code-email">Correo institucional</label><input id="code-email" type="email" autocomplete="email" required maxlength="254" placeholder="nombre@mail.pucv.cl"></div><div class="field"><label for="code-value">Código de ingreso</label><input id="code-value" class="code-input" required maxlength="20" autocomplete="one-time-code" autocapitalize="characters" spellcheck="false" placeholder="XXXX-XXXX" value="${esc(params.get('unirse')||'')}"></div><div class="error-text" id="code-error" role="alert"></div><button class="button ${google||email?'secondary':''}" type="submit">Entrar con código →</button></form></details>
      <div class="notice">El sitio acepta exclusivamente los dominios institucionales configurados.</div>
      ${window.APP_DEMO?`<div class="login-separator"></div><details class="demo-panel"><summary>Modo de demostración local</summary><div class="notice warning">Esta entrada solo sirve para revisar el prototipo en este computador. No verifica que la dirección pertenezca a una persona PUCV.</div><form id="demo-form" class="form-grid"><div class="field"><label for="demo-email">Correo institucional de ejemplo</label><input id="demo-email" type="email" placeholder="nombre@mail.pucv.cl" required></div><div class="error-text" id="demo-error" role="alert"></div><button class="button secondary" type="submit">Abrir demostración</button></form></details>`:''}
      <p class="helper spaced-top">Si tienes problemas con el acceso, contacta al equipo docente del curso. <a href="/privacidad" data-route="/privacidad">Aviso de privacidad</a>.</p></div></section>`;
  const form=document.querySelector('#demo-form'); if(form) form.addEventListener('submit',async e=>{e.preventDefault();const errorBox=document.querySelector('#demo-error');try{await api('/auth/demo',{method:'POST',body:JSON.stringify({email:document.querySelector('#demo-email').value})});await bootstrap();}catch(ex){errorBox.textContent=ex.message;}});
  const codeForm=document.querySelector('#code-form'); if(codeForm) codeForm.addEventListener('submit',async e=>{e.preventDefault();const errorBox=document.querySelector('#code-error');const button=codeForm.querySelector('button');button.disabled=true;errorBox.textContent='';try{await api('/auth/code',{method:'POST',body:JSON.stringify({email:document.querySelector('#code-email').value,code:document.querySelector('#code-value').value})});history.replaceState({},'','/');await bootstrap();}catch(ex){errorBox.textContent=ex.message;}finally{button.disabled=false;}});
  const magicForm=document.querySelector('#magic-form'); if(magicForm) magicForm.addEventListener('submit',async e=>{e.preventDefault();const status=document.querySelector('#magic-status');const button=magicForm.querySelector('button');button.disabled=true;status.textContent='Enviando…';try{const result=await api('/auth/request-link',{method:'POST',body:JSON.stringify({email:document.querySelector('#institutional-email').value})});status.textContent=result.message;magicForm.querySelector('input').value='';}catch(ex){status.textContent=ex.message;}finally{button.disabled=false;}});
}
async function moderatorPage() {
  if(!['admin','editor'].includes(user.role)){main.innerHTML='<div class="empty-state">No tienes permiso para abrir el panel de revisión.</div>';return;}
  main.innerHTML=`<div class="eyebrow">Gestión docente</div><h1>Materiales y revisión</h1><p class="lead">Carga casos, guías o fichas en el espacio de tu asignatura. Revisa sus accesos y entregas desde este panel.</p>
    <section class="detail-panel resource-detail"><h2>Agregar material al repositorio</h2><form id="resource-upload-form" class="form-grid">
      <div class="field"><label for="r-project">Asignatura</label><select id="r-project" class="select" required>${managedProjects.map(id=>`<option value="${id}">${esc(PROJECTS[id].name)} · ${esc(PROJECTS[id].course)}</option>`).join('')}</select></div>
      <div class="field"><label for="r-title">Título</label><input id="r-title" required maxlength="180"></div>
      <div class="field"><label for="r-category">Tipo de material</label><input id="r-category" required maxlength="100" placeholder="Desafío · Acceso rural, Caso clínico, Guía…"><span class="helper">Empieza con «Desafío» o «Caso» para que entre en la caja sorpresa.</span></div>
      <div class="field"><label for="r-summary">Descripción breve</label><textarea id="r-summary" required maxlength="2000"></textarea></div>
      <div class="field"><label for="r-tags">Palabras clave (separadas por coma)</label><input id="r-tags" maxlength="300"></div>
      <div class="field"><label for="r-content">Texto del material (opcional)</label><textarea id="r-content" rows="6" maxlength="20000" placeholder="## Problema sociosanitario&#10;Describe el caso o el desafío…&#10;## Barreras de acceso&#10;- Primera barrera&#10;- Segunda barrera"></textarea><span class="helper">Ideal para desafíos y casos escritos: «## » crea un título y «- » una viñeta.</span></div>
      <div class="field"><label for="r-file">Archivo (opcional si escribiste el texto)</label><input id="r-file" type="file" accept=".pdf,.docx,.pptx,.xlsx,.odt,.txt"><span class="helper">PDF, DOCX, PPTX, XLSX, ODT o TXT; máximo 8 MB. Lo verán solo integrantes autorizados de esta asignatura.</span></div>
      <label class="helper"><input id="r-draft" type="checkbox"> Guardar como borrador (no lo verán las y los estudiantes hasta publicarlo)</label>
      <div class="error-text" id="resource-upload-error" role="alert"></div><button class="button" type="submit">Guardar material →</button></form></section>
    <section class="detail-panel resource-detail"><div class="section-head"><h2>Materiales del repositorio</h2><span class="pill" id="materials-count"></span></div><p class="helper">Corrige títulos, descripciones o el archivo, y retira del catálogo lo que no deba verse. Un material retirado no se borra: se puede volver a publicar.</p><div id="materials-list" class="material-list">Cargando…</div></section>
    ${accessCodesPanel()}
    ${ticketsPanel()}
    ${surveysPanel()}
    <section class="detail-panel resource-detail"><div class="section-head"><h2>Indicadores para el informe</h2><label><span class="visually-hidden">Asignatura</span><select id="ind-project" class="select">${projectOptions()}</select></label></div><p class="helper">Lo que la propuesta promete medir, calculado con lo que ya registra la plataforma. El plazo de entrega se configura con PUCV_INCENTIVA_DEADLINE / PUCV_INNOVA_DEADLINE (AAAA-MM-DD).</p><label class="inline-field"><span>Cohorte</span><select id="ind-cohort" class="select cohort-select"></select></label><div id="indicators" class="helper">Cargando…</div><a class="button secondary small" id="ind-csv" href="#" download>Descargar indicadores (CSV) ↧</a></section>
    <section class="detail-panel resource-detail"><h2>Informe final y modo proyección</h2><p class="helper">El informe reúne indicadores y gráficos para los informes de Incentiva e Innova; se imprime o guarda en PDF. El modo proyección muestra los trabajos publicados uno tras otro, con temporizador y un QR para que el curso coevalúe en vivo.</p>
      <div class="join-row"><label class="visually-hidden" for="rp-project">Asignatura</label><select id="rp-project" class="select">${projectOptions()}</select><label class="visually-hidden" for="rp-cohort">Cohorte</label><select id="rp-cohort" class="select cohort-select"></select><div class="moderation-actions"><button class="button small" type="button" id="open-report">Abrir informe →</button><button class="button secondary small" type="button" id="open-projection">Modo proyección →</button></div></div></section>
    <section class="detail-panel resource-detail"><div class="section-head"><h2>Seguimiento por equipo</h2><div class="moderation-actions"><label class="visually-hidden" for="tr-project">Asignatura</label><select id="tr-project" class="select">${projectOptions()}</select><label class="visually-hidden" for="tr-cohort">Cohorte</label><select id="tr-cohort" class="select cohort-select"></select></div></div><p class="helper">Quién ya está ligado a una entrega (como quien la envió o con su correo en «Integrantes») y en qué estado está cada equipo.</p><div id="tracking" class="helper">Cargando…</div></section>
    <section class="detail-panel resource-detail"><h2>Cohortes</h2><p class="helper">Cada semestre es una cohorte. Abrir una nueva no borra nada: lo anterior queda archivado y visible en el catálogo (con filtro por cohorte), y los indicadores se calculan por cohorte. Los códigos del curso se desactivan para que crees los nuevos.</p><div id="cohorts" class="helper">Cargando…</div>
      ${user.role==='admin'?'<form id="cohort-open" class="join-row"><label for="co-name">Nueva cohorte</label><input id="co-name" maxlength="20" placeholder="2027-1" required><button class="button secondary small" type="submit">Abrir cohorte</button></form>':''}</section>
    <div id="moderation-content" class="loading">Cargando pendientes…</div>
    <section class="detail-panel resource-detail"><div class="section-head"><h2>Coevaluación entre pares</h2><a class="button secondary small" href="/api/admin/peer-reviews.csv" download>Descargar todo (CSV) ↧</a></div><p class="helper">Promedios por ficha (1 a 4) con la rúbrica de cada asignatura. El CSV incluye quién evaluó, para revisar la calidad de los comentarios.</p><div id="peer-summary" class="helper">Cargando…</div></section>
    <section class="detail-panel resource-detail"><div class="section-head"><h2>Integrantes con acceso</h2><span class="pill" id="members-count"></span></div><div id="members-list" class="helper">Cargando…</div></section>
    ${user.role==='admin'?staffPanel()+privacyPanel():''}
    ${user.role==='admin'?`<section class="detail-panel resource-detail"><h2>Respaldos</h2><div id="backup-info" class="helper">Cargando…</div><a class="button secondary small" href="/api/admin/backup" download>Descargar respaldo completo (.zip) ↧</a><p class="helper">Incluye la base de datos y todos los archivos subidos. Descárgalo una vez por semana y guárdalo fuera del hosting, por ejemplo en la unidad compartida del proyecto.</p></section>`:''}`;
  // Keep a long working panel navigable without presenting every tool as a competing action.
  const toc=document.createElement('nav'); toc.className='admin-toc'; toc.setAttribute('aria-label','Secciones del panel');
  const headings=[...main.querySelectorAll(':scope > section > h2, :scope > section > .section-head > h2')];
  const options=(start,end)=>headings.slice(start,end).map((h,i)=>`<option value="${start+i}">${esc(h.textContent)}</option>`).join('');
  toc.innerHTML=`<label for="admin-jump">Ir directamente a</label><select id="admin-jump" class="select"><option value="" selected>Elige una tarea del panel</option><optgroup label="Preparar la asignatura">${options(0,5)}</optgroup><optgroup label="Seguimiento del curso">${options(5,11)}<option value="moderation">Revisión pendiente</option></optgroup>${user.role==='admin'?`<optgroup label="Administración del sitio">${options(11,headings.length)}</optgroup>`:''}</select><button class="button secondary small" type="button" id="admin-jump-go">Ir</button>`;
  toc.addEventListener('click',e=>{if(e.target.id!=='admin-jump-go')return;const value=document.querySelector('#admin-jump').value;if(value==='')return;const target=value==='moderation'?document.querySelector('#moderation-content'):headings[Number(value)];target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});});
  main.querySelector('.lead').after(toc);
  bindAccessCodes();
  bindMembers();
  loadMembers();
  bindMaterials();
  loadMaterials();
  bindTickets();
  loadPeerSummary();
  bindSurveys();
  loadCohorts().then(()=>{bindIndicators();bindTracking();bindReportLinks();});
  if(user.role==='admin'){bindStaff();bindPrivacy();}
  if(user.role==='admin') loadBackups();
  const uploadForm=document.querySelector('#resource-upload-form');
  uploadForm.addEventListener('submit',async event=>{event.preventDefault();const button=uploadForm.querySelector('button');const error=document.querySelector('#resource-upload-error');const file=document.querySelector('#r-file').files[0], content=document.querySelector('#r-content').value;if(!file&&!content.trim()){error.textContent='Escribe el texto del material o adjunta un archivo.';return;}if(file&&file.size>8*1024*1024){error.textContent='El archivo debe pesar como máximo 8 MB.';return;}button.disabled=true;error.textContent='Guardando…';try{const result=await api('/api/admin/resources',{method:'POST',body:JSON.stringify({project_id:document.querySelector('#r-project').value,title:document.querySelector('#r-title').value,category:document.querySelector('#r-category').value,summary:document.querySelector('#r-summary').value,tags:document.querySelector('#r-tags').value,content,status:document.querySelector('#r-draft').checked?'draft':'published',filename:file?.name||'',file_base64:file?await fileToBase64(file):''})});notify(result.message);uploadForm.reset();error.textContent='';resourceCache={};loadMaterials();}catch(ex){error.textContent=ex.message;}finally{button.disabled=false;}});
  try {
    const pending=await api('/api/admin/pending'), root=document.querySelector('#moderation-content');
    const accessRequests=pending.access_requests.map(r=>`<article class="moderation-card"><div class="resource-top"><span class="resource-category ${r.project_id==='innova'?'plum-chip':'forest-chip'}">${esc(PROJECTS[r.project_id].name)}</span><span class="helper">${esc(r.email)}</span></div><h2>${esc(r.display_name)} solicita acceso</h2><div class="moderation-actions"><button class="button small" data-review="access_request" data-id="${r.id}" data-decision="approve">Autorizar</button><button class="button secondary small" data-review="access_request" data-id="${r.id}" data-decision="reject">Rechazar</button></div></article>`).join('');
    const submissions=pending.submissions.map(s=>`<article class="moderation-card"><div class="resource-top"><span class="resource-category ${s.project_id==='innova'?'plum-chip':'forest-chip'}">${esc(PROJECTS[s.project_id].name)}</span><span class="helper">${esc(s.team_name)}${s.section?' · '+esc(s.section):''} · ${esc(s.email)}</span></div><h2>${esc(s.title)}</h2>${s.members.length?`<p class="helper">Integrantes: ${s.members.map(esc).join(' · ')}</p>`:''}<p>${esc(s.summary)}</p>${s.fields.length?`<dl class="field-list compact">${s.fields.map(f=>`<div><dt>${esc(f.label)}</dt><dd>${esc(f.value)}</dd></div>`).join('')}</dl>`:''}${s.video_url?`<p class="helper">Video único (máx. 5 min): <a href="${esc(s.video_url)}" target="_blank" rel="noopener noreferrer">Abrir video ↗</a></p>`:''}${s.evidence_url?`<p class="helper">Ficha: <a href="${esc(s.evidence_url)}" target="_blank" rel="noopener noreferrer">Abrir ficha ↗</a></p>`:''}${s.evidence_storage_key?`<p><a class="button secondary small" href="/api/submissions/${Number(s.id)}/evidence">Descargar ficha adjunta ↧</a></p>`:''}${s.alternatives?.items?.length?`<h3>Alternativas evaluadas</h3>${alternativesTable(s.alternatives)}`:''}${s.has_model?`<p class="helper">Modelo 3D adjunto: <a href="/api/submissions/${Number(s.id)}/model" download>descargar STL</a></p>`:''}<p><a class="text-button" href="/ficha/${Number(s.id)}" data-route="/ficha/${Number(s.id)}">Ver la ficha de evidencia generada →</a></p><p class="helper">El equipo confirma que tiene permiso para los recursos y las imágenes o voces identificables que incluyó; la difusión posterior requiere autorización aparte.</p>${s.ai_declaration?`<p class="helper">Declaración de IA: ${esc(s.ai_declaration)}</p>`:'<p class="helper">Sin declaración de uso de IA.</p>'}<div class="field"><label for="note-${s.id}">Comentario para el equipo si se devuelve (opcional)</label><textarea id="note-${s.id}" maxlength="2000" rows="2"></textarea></div><div class="moderation-actions"><button class="button small" data-review="submission" data-id="${s.id}" data-decision="publish">Aprobar y publicar</button><button class="button secondary small" data-review="submission" data-id="${s.id}" data-decision="reject">Devolver</button></div></article>`).join('');
    const comments=pending.comments.map(c=>`<article class="moderation-card"><div class="resource-top"><span class="resource-category ${c.project_id==='innova'?'plum-chip':'forest-chip'}">${esc(PROJECTS[c.project_id].name)}</span><span class="helper">${esc(c.display_name)} · ${esc(c.email)}</span></div><h2>${c.parent_id?'Respuesta':'Comentario'} en: ${esc(c.resource_title)}${c.badge==='equipo'?' <span class="comment-badge">Equipo autor</span>':''}</h2><p>${esc(c.body)}</p><div class="moderation-actions"><button class="button small" data-review="comment" data-id="${c.id}" data-decision="publish">Publicar</button><button class="button secondary small" data-review="comment" data-id="${c.id}" data-decision="hide">Ocultar</button></div></article>`).join('');
    root.className='moderation-list';
    root.innerHTML=`<section><div class="section-head"><h2>Solicitudes de acceso</h2><span class="pill">${pending.access_requests.length} pendientes</span></div>${accessRequests||'<div class="empty-state">No hay solicitudes de acceso por revisar.</div>'}</section><section><div class="section-head"><h2>Entregas</h2><span class="pill">${pending.submissions.length} pendientes</span></div>${submissions||'<div class="empty-state">No hay entregas por revisar.</div>'}</section><section><div class="section-head"><h2>Comentarios</h2><span class="pill">${pending.comments.length} pendientes</span></div>${comments||'<div class="empty-state">No hay comentarios por revisar.</div>'}</section>`;
    root.addEventListener('click',async e=>{const button=e.target.closest('[data-review]');if(!button)return;button.disabled=true;try{await api('/api/admin/review',{method:'POST',body:JSON.stringify({kind:button.dataset.review,id:Number(button.dataset.id),decision:button.dataset.decision,note:document.querySelector(`#note-${button.dataset.id}`)?.value||''})});notify('Revisión guardada.');moderatorPage();}catch(ex){notify(ex.message);button.disabled=false;}});
  }catch(e){document.querySelector('#moderation-content').textContent=e.message;}
}
function projectOptions() { return managedProjects.map(id=>`<option value="${id}">${esc(PROJECTS[id].name)} · ${esc(PROJECTS[id].course)}</option>`).join(''); }
function accessCodesPanel() {
  return `<section class="detail-panel resource-detail"><h2>Acceso de estudiantes</h2><p class="helper">Crea un código por semestre o por fase y compártelo en clase o en Aula Virtual. Cada estudiante entra con su correo institucional y ese código, sin Google, y queda agregado al paralelo. Para que solo entre tu curso, pega la lista de correos. Los códigos personales quedan para casos puntuales.</p>
    <div class="code-columns">
      <form id="join-code-form" class="form-grid"><h3>Código del curso</h3>
        <div class="field"><label for="jc-project">Asignatura</label><select id="jc-project" class="select">${projectOptions()}</select></div>
        <div class="field" id="jc-section-field"><label for="jc-section">Paralelo que registra</label><select id="jc-section" class="select"></select></div>
        <div class="field"><label for="jc-label">Nombre de la invitación</label><input id="jc-label" maxlength="80" placeholder="Curso Bioanálisis"></div>
        <div class="field"><label for="jc-days">Vigencia (días)</label><input id="jc-days" type="number" min="1" max="180" value="14"></div>
        <div class="field"><label for="jc-max">Máximo de usos (opcional)</label><input id="jc-max" type="number" min="1" max="1000" placeholder="Ej.: 45"></div>
        <div class="field"><label for="jc-roster">Lista del curso (opcional)</label><textarea id="jc-roster" rows="3" placeholder="Pega los correos del paralelo, uno por línea"></textarea><p class="helper">Con lista, solo esos correos pueden entrar con el código. Sin lista, entra cualquier correo institucional que lo conozca.</p></div>
        <div class="error-text" id="jc-error" role="alert"></div><button class="button" type="submit">Crear código del curso</button>
        <div id="join-code-list" class="code-list"></div></form>
      <form id="access-code-form" class="form-grid"><h3>Códigos personales de ingreso</h3>
        <div class="field"><label for="ac-project">Asignatura que habilitan</label><select id="ac-project" class="select">${projectOptions()}</select></div>
        <div class="field"><label for="ac-emails">Correos institucionales (uno por línea o separados por coma)</label><textarea id="ac-emails" rows="4" placeholder="nombre.apellido@mail.pucv.cl"></textarea></div>
        <div class="field"><label for="ac-days">Vigencia (días)</label><input id="ac-days" type="number" min="1" max="180" value="30"></div>
        <div class="error-text" id="ac-error" role="alert"></div><button class="button" type="submit">Generar códigos</button>
        <div id="access-code-result"></div></form>
    </div></section>`;
}
function bindAccessCodes() {
  const joinForm=document.querySelector('#join-code-form'), accessForm=document.querySelector('#access-code-form');
  const projectSelect=document.querySelector('#jc-project');
  const fillSections=()=>{const sections=projectConfig[projectSelect.value]?.sections||[];document.querySelector('#jc-section-field').hidden=!sections.length;
    document.querySelector('#jc-section').innerHTML=`<option value="">Sin paralelo</option>${sections.map(c=>`<option>${esc(c)}</option>`).join('')}`;};
  projectSelect.addEventListener('change',fillSections); fillSections();
  loadJoinCodes();
  joinForm.addEventListener('submit',async e=>{e.preventDefault();const error=document.querySelector('#jc-error');error.textContent='';
    try{const result=await api('/api/admin/join-codes',{method:'POST',body:JSON.stringify({project_id:document.querySelector('#jc-project').value,section:document.querySelector('#jc-section').value,label:document.querySelector('#jc-label').value,days:document.querySelector('#jc-days').value,max_uses:document.querySelector('#jc-max').value,roster:document.querySelector('#jc-roster').value})});notify(`Código creado: ${result.code}${result.roster_size?` · lista de ${result.roster_size} correos`:''}`);document.querySelector('#jc-roster').value='';loadJoinCodes();}
    catch(ex){error.textContent=ex.message;}});
  joinForm.addEventListener('click',async e=>{const button=e.target.closest('[data-disable-code]');if(!button)return;button.disabled=true;
    try{await api('/api/admin/join-codes/disable',{method:'POST',body:JSON.stringify({id:Number(button.dataset.disableCode)})});loadJoinCodes();}catch(ex){notify(ex.message);button.disabled=false;}});
  joinForm.addEventListener('click',async e=>{const button=e.target.closest('[data-copy-invite]');if(!button)return;
    const link=`${location.origin}/?unirse=${encodeURIComponent(button.dataset.copyInvite)}`;
    try{await navigator.clipboard.writeText(link);notify('Invitación copiada. Pégala en el Aula Virtual o en un correo del curso.');}
    catch{window.prompt('Copia este enlace y compártelo solo con el curso:',link);}});
  accessForm.addEventListener('submit',async e=>{e.preventDefault();const error=document.querySelector('#ac-error'), box=document.querySelector('#access-code-result');error.textContent='';
    try{const result=await api('/api/admin/access-codes',{method:'POST',body:JSON.stringify({project_id:document.querySelector('#ac-project').value,emails:document.querySelector('#ac-emails').value,days:document.querySelector('#ac-days').value})});
      const csv='correo,codigo\n'+result.codes.map(c=>`${c.email},${c.code}`).join('\n');
      const href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
      box.innerHTML=`<div class="notice warning">Guarda o descarga estos códigos ahora: por seguridad no se vuelven a mostrar. Generar uno nuevo para un correo anula el anterior.</div><a class="button secondary small" href="${href}" download="codigos-ingreso.csv">Descargar CSV ↧</a><table class="code-table"><thead><tr><th>Correo</th><th>Código</th></tr></thead><tbody>${result.codes.map(c=>`<tr><td>${esc(c.email)}</td><td><code>${esc(c.code)}</code></td></tr>`).join('')}</tbody></table>${result.invalid.length?`<p class="helper">Omitidos (no son correos PUCV válidos): ${result.invalid.map(esc).join(', ')}</p>`:''}${result.refused?.length?`<p class="helper">No se generaron para ${result.refused.map(esc).join(', ')}: son cuentas docentes o participan en otra asignatura. La administración global puede emitirlos.</p>`:''}`;
      document.querySelector('#ac-emails').value='';}
    catch(ex){error.textContent=ex.message;}});
}
async function loadJoinCodes() {
  const box=document.querySelector('#join-code-list'); if(!box)return;
  try{const codes=await api('/api/admin/join-codes');
    box.innerHTML=codes.length?codes.map(c=>`<div class="code-item ${c.valid?'':'inactive'}"><code>${esc(c.code)}</code><span class="helper">${esc(PROJECTS[c.project_id].name)}${c.section?' · '+esc(c.section):''}${c.label?' · '+esc(c.label):''}${c.roster_size?` · lista de ${c.roster_size}`:' · sin lista'} · ${c.uses}${c.max_uses?'/'+c.max_uses:''} usos · ${c.valid?'vence '+new Date(c.expires_at*1000).toLocaleDateString('es-CL'):'inactivo'}</span>${c.valid?`<button class="button secondary small" type="button" data-copy-invite="${esc(c.code)}">Copiar invitación</button><button class="text-button" type="button" data-disable-code="${c.id}">Desactivar</button>`:''}</div>`).join(''):'<p class="helper">Aún no hay códigos del curso.</p>';
  }catch(ex){box.textContent=ex.message;}
}
async function loadMembers() {
  const box=document.querySelector('#members-list'); if(!box)return;
  try{const members=await api('/api/admin/members');
    document.querySelector('#members-count').textContent=`${members.length} activos`;
    box.innerHTML=members.length?`<table class="code-table"><thead><tr><th>Persona</th><th>Asignatura</th><th>Paralelo</th><th></th></tr></thead><tbody>${members.map(m=>`<tr><td>${esc(m.display_name)}<br><span class="helper">${esc(m.email)}</span></td><td>${esc(PROJECTS[m.project_id].name)}</td><td>${esc(m.section||'—')}</td><td><button class="text-button" type="button" data-revoke="${m.id}">Retirar acceso</button></td></tr>`).join('')}</tbody></table>`:'<p class="helper">Todavía no hay estudiantes con acceso.</p>';
  }catch(ex){box.textContent=ex.message;}
}
function bindMembers() {
  document.querySelector('#members-list').addEventListener('click',async e=>{const button=e.target.closest('[data-revoke]');if(!button||!confirm('¿Retirar el acceso de esta persona a la asignatura?'))return;button.disabled=true;
    try{await api('/api/admin/review',{method:'POST',body:JSON.stringify({kind:'membership',id:Number(button.dataset.revoke),decision:'revoke'})});notify('Acceso retirado.');loadMembers();}catch(ex){notify(ex.message);button.disabled=false;}});
}
async function loadMaterials() {
  const box=document.querySelector('#materials-list'); if(!box)return;
  try{const items=await api('/api/admin/resources');
    document.querySelector('#materials-count').textContent=`${items.filter(r=>r.status==='published').length} publicados · ${items.filter(r=>r.status!=='published').length} retirados`;
    box.innerHTML=items.length?items.map(r=>{const live=r.status==='published';return `<details class="material-item${live?'':' retired'}"><summary><span class="resource-category ${r.project_id==='innova'?'plum-chip':'forest-chip'}">${esc(PROJECTS[r.project_id].name)}</span><strong>${esc(r.title)}</strong><span class="status-label">${live?'Publicado':'Borrador o retirado'}</span></summary>
      <form class="form-grid" data-material="${r.id}" data-status="${esc(r.status)}">
        <div class="field"><label for="m-title-${r.id}">Título</label><input id="m-title-${r.id}" name="title" required maxlength="180" value="${esc(r.title)}"></div>
        <div class="field"><label for="m-category-${r.id}">Tipo de material</label><input id="m-category-${r.id}" name="category" required maxlength="100" value="${esc(r.category)}"></div>
        <div class="field"><label for="m-summary-${r.id}">Descripción breve</label><textarea id="m-summary-${r.id}" name="summary" required maxlength="2000">${esc(r.summary)}</textarea></div>
        ${r.source_submission_id?'':`<div class="field"><label for="m-content-${r.id}">Texto del material</label><textarea id="m-content-${r.id}" name="content" rows="8" maxlength="20000">${esc(r.content)}</textarea></div>`}
        <div class="field"><label for="m-tags-${r.id}">Palabras clave (separadas por coma)</label><input id="m-tags-${r.id}" name="tags" maxlength="300" value="${esc(r.tags.join(', '))}"></div>
        <div class="field"><label for="m-file-${r.id}">${r.has_file?`Reemplazar archivo (actual: ${esc(r.file_filename)})`:'Adjuntar archivo (opcional)'}</label><input id="m-file-${r.id}" name="file" type="file" accept=".pdf,.docx,.pptx,.xlsx,.odt,.txt"></div>
        <div class="field"><label for="m-guide-${r.id}">Pregunta guía del foro</label><textarea id="m-guide-${r.id}" name="guide_question" rows="2" maxlength="400" placeholder="${esc(r.default_guide_question)}">${esc(r.guide_question)}</textarea><span class="helper">Si la dejas vacía se usa la pregunta general de la asignatura.</span></div>
        <div class="field"><label for="m-quiz-${r.id}">Preguntas de control (hasta 3)</label><textarea id="m-quiz-${r.id}" name="quiz" rows="6" placeholder="¿Qué control descarta contaminación en la PCR?&#10;* Control negativo sin templado&#10;Control positivo&#10;Control de extracción&#10;Explicación: si el control sin templado amplifica, hay contaminación.&#10;&#10;(deja una línea en blanco entre preguntas)">${esc(r.quiz)}</textarea><span class="helper">Pregunta en la primera línea, una opción por línea, la correcta con *. «Explicación:» es opcional. Si cambias las preguntas se borran las respuestas anteriores.</span></div>
        ${r.quiz_stats?quizStatsBlock(r.quiz_stats):''}
        ${r.source_submission_id?'<p class="helper">Proviene de una entrega de estudiantes; la ficha y el video del equipo no cambian.</p>':''}
        <div class="error-text" role="alert"></div>
        <div class="moderation-actions"><button class="button small" type="submit">Guardar cambios</button><button class="button secondary small" type="submit" data-set-status="${live?'draft':'published'}">${live?'Retirar del catálogo':'Publicar'}</button></div>
      </form></details>`;}).join(''):'<p class="helper">Todavía no hay materiales.</p>';
  }catch(ex){box.textContent=ex.message;}
}
function bindMaterials() {
  document.querySelector('#materials-list').addEventListener('submit',async e=>{
    const form=e.target.closest('[data-material]'); if(!form)return; e.preventDefault();
    const status=e.submitter?.dataset.setStatus||form.dataset.status, error=form.querySelector('.error-text'), file=form.elements.file.files[0];
    if(status==='draft'&&!confirm('¿Retirar este material del catálogo? Las y los estudiantes dejarán de verlo; podrás volver a publicarlo.'))return;
    if(file&&file.size>8*1024*1024){error.textContent='El archivo debe pesar como máximo 8 MB.';return;}
    form.querySelectorAll('button').forEach(b=>b.disabled=true); error.textContent='';
    try{const result=await api('/api/admin/resources/update',{method:'POST',body:JSON.stringify({id:Number(form.dataset.material),title:form.elements.title.value,category:form.elements.category.value,summary:form.elements.summary.value,tags:form.elements.tags.value,guide_question:form.elements.guide_question.value,quiz:form.elements.quiz.value,...(form.elements.content?{content:form.elements.content.value}:{}),status,filename:file?.name||'',file_base64:file?await fileToBase64(file):''})});
      notify(result.message);resourceCache={};loadMaterials();}
    catch(ex){error.textContent=ex.message;form.querySelectorAll('button').forEach(b=>b.disabled=false);}
  });
}
function quizStatsBlock(stats) {
  return `<div class="quiz-stats"><strong>Resultados: ${stats.respondents} ${stats.respondents===1?'persona respondió':'personas respondieron'}</strong>${stats.questions.map((q,i)=>`<div><p>${i+1}. ${esc(q.prompt)} · <b>${q.correct_share===null?'—':Math.round(q.correct_share*100)+'% correcto'}</b></p><ul>${q.options.map(o=>`<li${o.correct?' class="is-correct"':''}>${esc(o.text)} · ${o.count}</li>`).join('')}</ul></div>`).join('')}</div>`;
}
function ticketsPanel() {
  const first=managedProjects[0], questions=projectConfig[first]?.ticket_questions||[];
  return `<section class="detail-panel resource-detail"><h2>Tiquetes de salida y preguntas previas</h2><p class="helper">Al cierre de cada sesión, proyecta el QR: el curso responde las tres preguntas estándar en 5 minutos sin escribir su nombre. Las preguntas previas se envían antes de la clase (aula invertida) para llegar con las dudas identificadas. En «Ver respuestas» puedes ponerle una categoría a cada duda: el panel calcula la duda dominante.</p>
    <form id="ticket-form" class="form-grid">
      <div class="code-columns"><div class="field"><label for="tk-project">Asignatura</label><select id="tk-project" class="select">${projectOptions()}</select></div>
      <div class="field"><label for="tk-kind">Tipo</label><select id="tk-kind" class="select"><option value="salida">Tiquete de salida (al cierre)</option><option value="previa">Preguntas previas (antes de la sesión)</option></select></div></div>
      <div class="field"><label for="tk-title">Sesión</label><input id="tk-title" maxlength="120" required placeholder="Fase 1 · sesión del 9 de noviembre"></div>
      <div class="field"><label for="tk-hours">Abierto durante (horas)</label><input id="tk-hours" type="number" min="1" max="336" value="24"></div>
      <details class="code-panel"><summary>Preguntas (las tres estándar del proyecto)</summary>${[0,1,2].map(i=>`<div class="field"><label for="tk-q${i}">Pregunta ${i+1}</label><textarea id="tk-q${i}" rows="2" maxlength="400">${esc(questions[i]||'')}</textarea></div>`).join('')}</details>
      <div class="error-text" id="tk-error" role="alert"></div><button class="button" type="submit">Crear tiquete y mostrar QR</button></form>
    <div id="ticket-list" class="material-list"></div></section>`;
}
function showQr(ticket) {
  const overlay=document.createElement('div');
  overlay.className='qr-overlay'; overlay.setAttribute('role','dialog'); overlay.setAttribute('aria-label','Código QR del tiquete');
  overlay.innerHTML=`<div class="qr-card"><div class="eyebrow">${esc(PROJECTS[ticket.project_id].name)} · ${esc(ticket.label||'Tiquete de salida')}</div><h2>${esc(ticket.title)}</h2><img src="${esc(ticket.qr||`/api/admin/tickets/${ticket.id}/qr.svg`)}" alt="Código QR para responder"><p class="qr-url">${esc(ticket.url)}</p><button class="button secondary small" type="button">Cerrar</button></div>`;
  const close=()=>{overlay.remove();document.removeEventListener('keydown',onKey);};
  const onKey=e=>{if(e.key==='Escape')close();};
  overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('button'))close();});
  document.addEventListener('keydown',onKey);
  document.body.append(overlay); overlay.querySelector('button').focus();
}
let ticketCache=[];
async function loadTickets() {
  const box=document.querySelector('#ticket-list'); if(!box)return;
  try{ticketCache=await api('/api/admin/tickets');
    box.innerHTML=ticketCache.length?ticketCache.map(t=>`<details class="material-item${t.open?'':' retired'}"><summary><span class="resource-category ${t.project_id==='innova'?'plum-chip':'forest-chip'}">${esc(PROJECTS[t.project_id].name)}</span><strong>${t.kind==='previa'?'Previas · ':''}${esc(t.title)}</strong><span class="status-label">${t.answers} respuestas · ${t.open?'abierto':'cerrado'}</span></summary>
      <div class="form-grid ticket-body"><p class="helper">Código <code>${esc(t.code)}</code> · ${esc(t.url)}</p>
        <div class="moderation-actions"><button class="button small" type="button" data-qr="${t.id}">Mostrar QR</button><button class="button secondary small" type="button" data-answers="${t.id}">Ver respuestas</button><a class="button secondary small" href="/api/admin/tickets/${t.id}/responses.csv" download>CSV ↧</a></div>
        <div class="ticket-answers" id="ticket-answers-${t.id}"></div>
        <form class="form-grid" data-ticket="${t.id}"><div class="field"><label for="tk-feedback-${t.id}">Enlace al audio o video de retroalimentación</label><input id="tk-feedback-${t.id}" name="feedback_url" type="url" placeholder="https://" value="${esc(t.feedback_url)}"></div>
          <div class="moderation-actions"><button class="button small" type="submit">Guardar enlace</button><button class="button secondary small" type="submit" data-active="${t.active?0:1}">${t.active?'Cerrar tiquete':'Reabrir'}</button></div></form></div></details>`).join(''):'<p class="helper">Aún no hay tiquetes.</p>';
  }catch(ex){box.textContent=ex.message;}
}
function bindTickets() {
  const form=document.querySelector('#ticket-form'), project=document.querySelector('#tk-project'), kind=document.querySelector('#tk-kind');
  const fillQuestions=()=>{const c=projectConfig[project.value]||{};(kind.value==='previa'?c.pre_questions:c.ticket_questions||[]).forEach((q,i)=>{document.querySelector(`#tk-q${i}`).value=q;});};
  project.addEventListener('change',fillQuestions); kind.addEventListener('change',fillQuestions);
  form.addEventListener('submit',async e=>{e.preventDefault();const error=document.querySelector('#tk-error');error.textContent='';
    try{const r=await api('/api/admin/tickets',{method:'POST',body:JSON.stringify({project_id:project.value,kind:kind.value,title:document.querySelector('#tk-title').value,hours:document.querySelector('#tk-hours').value,questions:[0,1,2].map(i=>document.querySelector(`#tk-q${i}`).value)})});
      document.querySelector('#tk-title').value='';await loadTickets();const created=ticketCache.find(t=>t.code===r.code);if(created)showQr(created);}
    catch(ex){error.textContent=ex.message;}});
  const list=document.querySelector('#ticket-list');
  list.addEventListener('click',async e=>{const qrButton=e.target.closest('[data-qr]'), answersButton=e.target.closest('[data-answers]');
    if(qrButton) showQr(ticketCache.find(t=>t.id===Number(qrButton.dataset.qr)));
    if(answersButton){const box=document.querySelector(`#ticket-answers-${answersButton.dataset.answers}`);
      loadTicketResponses(Number(answersButton.dataset.answers));}});
  list.addEventListener('change',async e=>{const input=e.target.closest('[data-tag-answer]');if(!input)return;
    try{await api(`/api/admin/tickets/${input.dataset.ticket}/tag`,{method:'POST',body:JSON.stringify({answer_id:input.dataset.tagAnswer,question:Number(input.dataset.q),tag:input.value})});
      loadTicketResponses(Number(input.dataset.ticket),{question:input.dataset.q,answer:input.dataset.tagAnswer});}
    catch(ex){notify(ex.message);}});
  list.addEventListener('submit',async e=>{const f=e.target.closest('[data-ticket]');if(!f)return;e.preventDefault();
    const ticket=ticketCache.find(t=>t.id===Number(f.dataset.ticket)), active=e.submitter?.dataset.active!==undefined?e.submitter.dataset.active==='1':Boolean(ticket.active);
    try{await api('/api/admin/tickets/update',{method:'POST',body:JSON.stringify({id:ticket.id,feedback_url:f.elements.feedback_url.value,active})});notify('Tiquete actualizado.');loadTickets();}
    catch(ex){notify(ex.message);}});
  loadTickets();
}
// Teacher-side binning of exit-ticket answers: a category per answer, counts, the dominant doubt and frequent words.
async function loadTicketResponses(ticketId, keepFocus) {
  const box=document.querySelector(`#ticket-answers-${ticketId}`); if(!box)return;
  try{const data=await api(`/api/admin/tickets/${ticketId}/responses`);
    if(!data.answers.length){box.innerHTML='<p class="helper">Todavía no hay respuestas.</p>';return;}
    box.innerHTML=data.questions.map((q,i)=>{const sum=data.summary[i]||{tags:[],keywords:[]};
      return `<div class="ticket-question"><strong>${i+1}. ${esc(q)}</strong>
        <p class="helper">${sum.dominant?`Duda dominante: <b>${esc(sum.dominant)}</b> · `:''}${sum.tags.length?sum.tags.map(t=>`${esc(t.tag)} (${t.count})`).join(' · '):'Aún sin categorías.'}</p>
        ${sum.keywords.length?`<p class="helper">Palabras frecuentes: ${sum.keywords.map(k=>`<span class="tag">${esc(k.word)} · ${k.count}</span>`).join(' ')}</p>`:''}
        <datalist id="tags-${ticketId}-${i}">${sum.tags.map(t=>`<option value="${esc(t.tag)}">`).join('')}</datalist>
        <ul class="tag-answers">${data.answers.map(a=>`<li><span>${esc(a.answers[i]||'')}</span><label class="visually-hidden" for="tag-${a.id}-${i}">Categoría</label><input id="tag-${a.id}-${i}" class="tag-input" list="tags-${ticketId}-${i}" maxlength="60" placeholder="Categoría" value="${esc(a.tags[i]||'')}" data-tag-answer="${esc(a.id)}" data-q="${i}" data-ticket="${ticketId}"></li>`).join('')}</ul></div>`;}).join('');
    if(keepFocus){const next=box.querySelector(`#tag-${CSS.escape(keepFocus.answer)}-${keepFocus.question}`)?.closest('li')?.nextElementSibling?.querySelector('input');if(next)next.focus();}
  }catch(ex){box.textContent=ex.message;}
}
let cohortList=[], currentCohortName='';
async function loadCohorts() {
  const box=document.querySelector('#cohorts');
  try{const d=await api('/api/admin/cohorts'); cohortList=d.cohorts; currentCohortName=d.current;
    document.querySelectorAll('.cohort-select').forEach(sel=>{sel.innerHTML=[...cohortList].reverse().map(c=>`<option value="${esc(c.name)}"${c.name===d.current?' selected':''}>${esc(c.name)}${c.name===d.current?' (actual)':''}</option>`).join('');});
    if(box) box.innerHTML=`<table class="code-table"><thead><tr><th>Cohorte</th><th>Desde</th><th>Estudiantes con acceso</th><th>Entregas</th></tr></thead><tbody>${[...cohortList].reverse().map(c=>`<tr><td>${esc(c.name)}${c.name===d.current?' <span class="status-label">actual</span>':''}</td><td>${c.started_at.startsWith('1970')?'inicio':esc(c.started_at.slice(0,10))}</td><td>${c.members}</td><td>${c.submissions}</td></tr>`).join('')}</tbody></table>`;
  }catch(ex){if(box)box.textContent=ex.message;}
  const form=document.querySelector('#cohort-open');
  if(form&&!form.dataset.bound){form.dataset.bound='1';form.addEventListener('submit',async e=>{e.preventDefault();const name=document.querySelector('#co-name').value.trim();
    if(!confirm(`¿Abrir la cohorte «${name}»? Los códigos del curso actuales se desactivarán; nada se borra.`))return;
    try{const r=await api('/api/admin/cohorts',{method:'POST',body:JSON.stringify({name})});notify(r.message);form.reset();await loadCohorts();}catch(ex){notify(ex.message);}});}
}
function bindTracking() {
  const project=document.querySelector('#tr-project'), cohort=document.querySelector('#tr-cohort'), box=document.querySelector('#tracking');
  const load=async()=>{try{const d=await api(`/api/admin/tracking?project=${project.value}&cohort=${encodeURIComponent(cohort.value)}`);
    const without=d.people.filter(x=>!x.status);
    box.innerHTML=`<table class="code-table"><thead><tr><th>Paralelo</th><th>Con acceso</th><th>Ligados a una entrega</th><th>Equipos</th><th>Publicados</th><th>Devueltos</th></tr></thead><tbody>${d.summary.map(r=>`<tr><td>${esc(r.section)}</td><td>${r.members}</td><td>${r.linked} de ${r.members}</td><td>${r.teams}</td><td>${r.published}</td><td>${r.returned}</td></tr>`).join('')||'<tr><td colspan="6">Sin datos en esta cohorte.</td></tr>'}</tbody></table>
      ${d.teams.length?`<h3>Equipos</h3><table class="code-table"><thead><tr><th>Equipo</th><th>Paralelo</th><th>Estado</th><th>Enviado</th></tr></thead><tbody>${d.teams.map(t=>`<tr class="status-${esc(t.status)}"><td>${esc(t.team)}</td><td>${esc(t.section||'—')}</td><td><span class="status-label">${esc(SUBMISSION_STATUS[t.status]||t.status)}</span></td><td>${esc(t.created_at.slice(0,10))}</td></tr>`).join('')}</tbody></table>`:''}
      <details class="code-panel"><summary>${without.length} ${without.length===1?'persona':'personas'} sin entrega asociada</summary><p class="helper">Puede que integren un equipo que no escribió su correo en «Integrantes».</p><ul>${without.map(x=>`<li>${esc(x.name)} · ${esc(x.email)}${x.section?' · '+esc(x.section):''}</li>`).join('')}</ul></details>`;}
    catch(ex){box.textContent=ex.message;}};
  project.addEventListener('change',load); cohort.addEventListener('change',load); load();
}
function bindReportLinks() {
  const project=document.querySelector('#rp-project'), cohort=document.querySelector('#rp-cohort');
  document.querySelector('#open-report').addEventListener('click',()=>go(`/informe/${project.value}?cohorte=${encodeURIComponent(cohort.value)}`));
  document.querySelector('#open-projection').addEventListener('click',()=>go(`/proyeccion/${project.value}?cohorte=${encodeURIComponent(cohort.value)}`));
}
// Horizontal bars, one or two series. Values are written on each bar (few bars), and the data stays available as a table.
function barChart(rows, {series, max, format=v=>String(v), label}) {
  const rowH=series.length*22+14, top=series.length>1?28:6, labelW=310, width=800, plotW=width-labelW-60, height=top+rows.length*rowH;
  const legend=series.length>1?series.map((s,i)=>`<rect x="${labelW+i*150}" y="4" width="12" height="12" rx="3" fill="var(${s.color})"/><text x="${labelW+18+i*150}" y="14" class="chart-legend">${esc(s.name)}</text>`).join(''):'';
  const bars=rows.map((r,i)=>{const y=top+i*rowH;
    const name=r.label.length>40?r.label.slice(0,39)+'…':r.label;
    return `<text x="${labelW-10}" y="${y+rowH/2+4}" text-anchor="end" class="chart-label"><title>${esc(r.label)}</title>${esc(name)}</text>`+r.values.map((v,j)=>{if(v===null||v===undefined)return '';
      const w=Math.max(2,plotW*v/max), by=y+7+j*22;
      return `<g><title>${esc(r.label)} · ${esc(series[j].name)}: ${esc(format(v))}</title><rect x="${labelW}" y="${by}" width="${w}" height="18" rx="4" fill="var(${series[j].color})"/><text x="${labelW+w+6}" y="${by+13}" class="chart-value">${esc(format(v))}</text></g>`;}).join('');}).join('');
  const table=`<details class="chart-data"><summary>Ver los datos en tabla</summary><table class="code-table"><thead><tr><th>${esc(label)}</th>${series.map(s=>`<th>${esc(s.name)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.label)}</td>${r.values.map(v=>`<td>${v===null||v===undefined?'—':esc(format(v))}</td>`).join('')}</tr>`).join('')}</tbody></table></details>`;
  return `<svg class="bar-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(label)}">${legend}${bars}</svg>${table}`;
}
async function reportPage(projectId) {
  const params=new URLSearchParams(location.search), cohort=params.get('cohorte')||'';
  main.innerHTML='<div class="resource-detail"><div class="loading">Preparando el informe…</div></div>';
  let r;
  try{r=await api(`/api/admin/report?project=${projectId}&cohort=${encodeURIComponent(cohort)}`);}
  catch(e){main.innerHTML=`<div class="empty-state"><h1>Informe no disponible</h1><p>${esc(e.message)}</p></div>`;return;}
  const innova=projectId==='innova', pct=v=>`${Math.round(v*100)}%`;
  const status=[['published','✓ Publicadas'],['review','◷ En revisión'],['rejected','↺ Devueltas']];
  let group='';
  main.innerHTML=`<article class="resource-detail report-page project-page ${innova?'innova-theme':''}"><a class="back-link no-print" href="/admin" data-route="/admin">← Volver al panel</a>
    <div class="eyebrow">${esc(r.name)} · Cohorte ${esc(r.cohort)}</div><h1>Informe del proyecto</h1>
    <p class="no-print"><button class="button small" type="button" id="print-report">Imprimir o guardar como PDF</button> <span class="helper">Generado el ${new Date().toLocaleDateString('es-CL')} con los datos del repositorio.</span></p>
    <section class="detail-panel"><h2>Entregas</h2><div class="stat-row">${status.map(([k,l])=>`<div class="stat"><span class="stat-value">${r.statuses[k]||0}</span><span class="stat-label">${l}</span></div>`).join('')}</div>
      ${r.by_section.length?barChart(r.by_section.map(x=>({label:x.section,values:[x.teams]})),{series:[{name:'Equipos con entrega',color:'--series-1'}],max:Math.max(...r.by_section.map(x=>x.teams),1),label:'Equipos con entrega por paralelo'}):''}</section>
    ${r.kpsi.length?`<section class="detail-panel"><h2>KPSI: entrada y salida</h2><p class="helper">Promedio de autoevaluación por enunciado (1 a 4). Es percepción de dominio, no una medida de aprendizaje ni de eficacia.</p>${barChart(r.kpsi.map(x=>({label:x.text,values:[x.before,x.after]})),{series:[{name:'Entrada',color:'--series-1'},{name:'Salida',color:'--series-2'}],max:4,format:v=>v.toFixed(1),label:'Enunciado del KPSI'})}</section>`:''}
    ${r.quiz.length?`<section class="detail-panel"><h2>Preguntas de control</h2>${barChart(r.quiz.map(x=>({label:`${x.title} (${x.respondents})`,values:[x.correct_share]})),{series:[{name:'Respuestas correctas',color:'--series-1'}],max:1,format:pct,label:'Ficha (personas que respondieron)'})}</section>`:''}
    ${r.peer?`<section class="detail-panel"><h2>Coevaluación entre pares</h2><p class="helper">${r.peer.count} evaluaciones · promedio general ${r.peer.overall} de 4.</p>${barChart(r.peer.averages.map(a=>({label:a.label,values:[a.average]})),{series:[{name:'Promedio',color:'--series-1'}],max:4,format:v=>v.toFixed(2),label:'Criterio'})}</section>`:''}
    ${r.doubts.length?`<section class="detail-panel"><h2>Dudas más frecuentes</h2><p class="helper">Categorías asignadas por la docente a las respuestas de tiquetes y preguntas previas.</p>${barChart(r.doubts.map(d=>({label:d.tag,values:[d.n]})),{series:[{name:'Respuestas',color:'--series-1'}],max:Math.max(...r.doubts.map(d=>d.n)),label:'Categoría'})}</section>`:''}
    <section class="detail-panel"><h2>Indicadores</h2><table class="code-table"><tbody>${r.indicators.map(x=>{const head=x.group!==group?`<tr><th colspan="2">${esc(x.group)}</th></tr>`:'';group=x.group;return `${head}<tr><td>${esc(x.label)}</td><td><b>${esc(x.value)}</b></td></tr>`;}).join('')}</tbody></table></section>
  </article>`;
  document.querySelector('#print-report').addEventListener('click',()=>window.print());
}
async function projectionPage(projectId) {
  const params=new URLSearchParams(location.search), cohort=params.get('cohorte')||'';
  let items=[], index=0, section=params.get('paralelo')||'', remaining=300, timer=null;
  const sections=projectConfig[projectId]?.sections||[];
  const load=async()=>{items=await api(`/api/admin/projection?project=${projectId}&cohort=${encodeURIComponent(cohort)}&section=${encodeURIComponent(section)}`);index=0;draw();};
  const tick=()=>{remaining=Math.max(0,remaining-1);const t=document.querySelector('#proj-timer');if(t){t.textContent=`${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')}`;t.classList.toggle('timer-ending',remaining<=30);}if(!remaining){clearInterval(timer);timer=null;}};
  const draw=()=>{clearInterval(timer);timer=null;remaining=300;const it=items[index];
    main.innerHTML=`<div class="projection project-page ${projectId==='innova'?'innova-theme':''}"><div class="projection-bar no-print"><a class="back-link" href="/admin" data-route="/admin">← Panel</a>
      ${sections.length?`<label><span class="visually-hidden">Paralelo</span><select id="proj-section" class="select"><option value="">Todos los paralelos</option>${sections.map(x=>`<option${x===section?' selected':''}>${esc(x)}</option>`).join('')}</select></label>`:''}
      <span class="helper">${items.length?`${index+1} de ${items.length}`:'Sin trabajos publicados'}</span><button class="button secondary small" type="button" id="proj-full">Pantalla completa</button></div>
      ${it?`<div class="projection-main"><div><div class="eyebrow">${esc(it.team_name)}${it.section?' · '+esc(it.section):''}</div><h1>${esc(it.title)}</h1>
        ${it.embed_url?`<div class="video-frame"><iframe src="${esc(it.embed_url)}" title="Video: ${esc(it.title)}" allow="encrypted-media; picture-in-picture; fullscreen"></iframe></div>`:`<p><a class="button" href="${esc(it.media_url)}" target="_blank" rel="noopener noreferrer">Abrir el video ↗</a></p>`}</div>
        <aside class="projection-side"><div class="timer" id="proj-timer" aria-live="off">5:00</div><div class="moderation-actions"><button class="button small" type="button" id="proj-start">Iniciar 5 min</button><button class="button secondary small" type="button" id="proj-reset">Reiniciar</button></div>
          <img src="/api/admin/qr.svg?path=${encodeURIComponent(it.path)}" alt="Código QR para coevaluar este trabajo"><p class="helper">Escanea para coevaluar este trabajo</p>
          <div class="moderation-actions"><button class="button secondary small" type="button" id="proj-prev"${index===0?' disabled':''}>← Anterior</button><button class="button small" type="button" id="proj-next"${index>=items.length-1?' disabled':''}>Siguiente →</button></div></aside></div>`
        :'<div class="empty-state">No hay trabajos publicados en esta cohorte o paralelo.</div>'}</div>`;
    document.querySelector('#proj-section')?.addEventListener('change',e=>{section=e.target.value;load();});
    document.querySelector('#proj-full')?.addEventListener('click',()=>document.documentElement.requestFullscreen?.());
    document.querySelector('#proj-start')?.addEventListener('click',()=>{if(!timer)timer=setInterval(tick,1000);});
    document.querySelector('#proj-reset')?.addEventListener('click',()=>{clearInterval(timer);timer=null;remaining=301;tick();});
    document.querySelector('#proj-prev')?.addEventListener('click',()=>{index--;draw();});
    document.querySelector('#proj-next')?.addEventListener('click',()=>{index++;draw();});};
  document.onkeydown=e=>{if(!location.pathname.startsWith('/proyeccion/'))return;if(e.target.closest('input,select,textarea'))return;if(e.key==='ArrowRight'&&index<items.length-1){index++;draw();}if(e.key==='ArrowLeft'&&index>0){index--;draw();}};
  try{await load();}catch(e){main.innerHTML=`<div class="empty-state"><h1>Modo proyección no disponible</h1><p>${esc(e.message)}</p></div>`;}
}
function surveysPanel() {
  const first=managedProjects[0];
  return `<section class="detail-panel resource-detail"><h2>Encuestas: KPSI y percepción</h2><p class="helper">Aplica el KPSI de entrada antes de las sesiones y el de salida al cierre: los resultados muestran el cambio por enunciado. La encuesta de percepción va al final. El contenido de las respuestas no lleva nombre o correo; la participación se registra por separado. Se responden con QR.</p>
    <form id="survey-form" class="form-grid">
      <div class="code-columns"><div class="field"><label for="sv-project">Asignatura</label><select id="sv-project" class="select">${projectOptions()}</select></div>
      <div class="field"><label for="sv-kind">Tipo</label><select id="sv-kind" class="select"><option value="kpsi">KPSI (autoevaluación 1 a 4)</option><option value="percepcion">Percepción (acuerdo 1 a 5)</option></select></div></div>
      <div class="code-columns"><div class="field"><label for="sv-moment">Momento</label><select id="sv-moment" class="select"><option value="entrada">Entrada</option><option value="salida">Salida</option><option value="cierre">Cierre</option></select></div>
      <div class="field"><label for="sv-hours">Abierta durante (horas)</label><input id="sv-hours" type="number" min="1" max="720" value="72"></div></div>
      <div class="field"><label for="sv-title">Título</label><input id="sv-title" maxlength="120" placeholder="KPSI de entrada · Fase 1"></div>
      <details class="code-panel"><summary>Enunciados (plantilla editable)</summary><p class="helper">Una línea por enunciado; las líneas que empiezan con # agrupan por dimensión. Para comparar entrada y salida, usa los mismos enunciados.<span id="sv-note"></span></p><textarea id="sv-items" rows="10">${esc(projectConfig[first]?.survey_templates?.kpsi||'')}</textarea></details>
      <div class="error-text" id="sv-error" role="alert"></div><button class="button" type="submit">Crear encuesta y mostrar QR</button></form>
    <div id="survey-list" class="material-list"></div></section>`;
}
let surveyCache=[];
async function loadSurveys() {
  const box=document.querySelector('#survey-list'); if(!box)return;
  try{surveyCache=await api('/api/admin/surveys');
    box.innerHTML=surveyCache.length?surveyCache.map(t=>`<details class="material-item${t.open?'':' retired'}"><summary><span class="resource-category ${t.project_id==='innova'?'plum-chip':'forest-chip'}">${esc(PROJECTS[t.project_id].name)}</span><strong>${esc(t.title)}</strong><span class="status-label">${t.answers} respuestas · ${t.open?'abierta':'cerrada'}</span></summary>
      <div class="form-grid ticket-body"><p class="helper">${t.kind==='kpsi'?'KPSI':'Percepción'} · ${esc(t.moment)} · código <code>${esc(t.code)}</code></p>
        <div class="moderation-actions"><button class="button small" type="button" data-survey-qr="${t.id}">Mostrar QR</button><button class="button secondary small" type="button" data-survey-results="${t.id}">Ver resultados</button><a class="button secondary small" href="/api/admin/surveys/${t.id}/responses.csv" download>CSV ↧</a><button class="button secondary small" type="button" data-survey-toggle="${t.id}" data-active="${t.active?0:1}">${t.active?'Cerrar':'Reabrir'}</button></div>
        <div id="survey-results-${t.id}"></div></div></details>`).join(''):'<p class="helper">Aún no hay encuestas.</p>';
  }catch(ex){box.textContent=ex.message;}
}
function bindSurveys() {
  const project=document.querySelector('#sv-project'), kind=document.querySelector('#sv-kind'), items=document.querySelector('#sv-items');
  const fill=()=>{items.value=projectConfig[project.value]?.survey_templates?.[kind.value]||'';
    document.querySelector('#sv-note').textContent=kind.value==='percepcion'?' Plantilla provisional: reemplázala por los ítems del instrumento de Bravo Cofré et al. (2024) cuando lo tengas.':project.value==='incentiva'?' No hay un KPSI de Incentiva en los archivos del curso: revisa estos enunciados antes de aplicarlo.':' Enunciados del KPSI de TEM 1133 (Certamen I).';};
  project.addEventListener('change',fill); kind.addEventListener('change',fill); fill();
  document.querySelector('#survey-form').addEventListener('submit',async e=>{e.preventDefault();const error=document.querySelector('#sv-error');error.textContent='';
    try{const r=await api('/api/admin/surveys',{method:'POST',body:JSON.stringify({project_id:project.value,kind:kind.value,moment:document.querySelector('#sv-moment').value,title:document.querySelector('#sv-title').value,hours:document.querySelector('#sv-hours').value,items:items.value})});
      document.querySelector('#sv-title').value='';await loadSurveys();const created=surveyCache.find(t=>t.code===r.code);if(created)showQr({...created,qr:`/api/admin/surveys/${created.id}/qr.svg`,label:'Encuesta'});}
    catch(ex){error.textContent=ex.message;}});
  document.querySelector('#survey-list').addEventListener('click',async e=>{const qrB=e.target.closest('[data-survey-qr]'), resB=e.target.closest('[data-survey-results]'), toggle=e.target.closest('[data-survey-toggle]');
    if(qrB){const t=surveyCache.find(x=>x.id===Number(qrB.dataset.surveyQr));showQr({...t,qr:`/api/admin/surveys/${t.id}/qr.svg`,label:'Encuesta'});}
    if(toggle){try{await api('/api/admin/surveys/update',{method:'POST',body:JSON.stringify({id:Number(toggle.dataset.surveyToggle),active:toggle.dataset.active==='1'})});loadSurveys();}catch(ex){notify(ex.message);}}
    if(resB){const box=document.querySelector(`#survey-results-${resB.dataset.surveyResults}`);
      try{const r=await api(`/api/admin/surveys/${resB.dataset.surveyResults}/results`);
        box.innerHTML=`<p class="helper">${r.respondents} respuestas${r.baseline?` · comparada con «${esc(r.baseline.title)}» (${r.baseline.respondents} respuestas)`:''} · escala 1 a ${r.scale.length}</p>
          <table class="code-table"><thead><tr><th>Enunciado</th><th>Promedio</th>${r.baseline?'<th>Entrada</th><th>Cambio</th>':''}<th>Niveles altos</th></tr></thead><tbody>${r.items.map(i=>`<tr><td>${esc(i.text)}<br><span class="helper">${esc(i.dimension)}</span></td><td><b>${i.mean??'—'}</b></td>${r.baseline?`<td>${i.baseline_mean??'—'}</td><td class="${i.delta>0?'delta-up':i.delta<0?'delta-down':''}">${i.delta===null||i.delta===undefined?'—':(i.delta>0?'+':'')+i.delta}</td>`:''}<td>${i.top_share===null?'—':Math.round(i.top_share*100)+'%'}</td></tr>`).join('')}</tbody></table>
          ${r.comments.length?`<div class="ticket-question"><strong>Comentarios</strong><ul>${r.comments.map(c=>`<li>${esc(c)}</li>`).join('')}</ul></div>`:''}`;}
      catch(ex){box.textContent=ex.message;}}});
  loadSurveys();
}
function bindIndicators() {
  const select=document.querySelector('#ind-project'), cohort=document.querySelector('#ind-cohort'), box=document.querySelector('#indicators'), link=document.querySelector('#ind-csv');
  const load=async()=>{const q=`project=${select.value}&cohort=${encodeURIComponent(cohort.value)}`;link.href=`/api/admin/indicators.csv?${q}`;
    try{const rows=await api(`/api/admin/indicators?${q}`);let group='';
      box.innerHTML=`<table class="code-table"><tbody>${rows.map(r=>{const head=r.group!==group?`<tr><th colspan="2">${esc(r.group)}</th></tr>`:'';group=r.group;return `${head}<tr><td>${esc(r.label)}</td><td><b>${esc(r.value)}</b></td></tr>`;}).join('')}</tbody></table>`;}
    catch(ex){box.textContent=ex.message;}};
  select.addEventListener('change',load); cohort.addEventListener('change',load); load();
}
function staffPanel() {
  return `<section class="detail-panel resource-detail"><h2>Equipo docente</h2><p class="helper">Asigna quién revisa cada asignatura sin tocar la configuración del servidor. El cambio rige de inmediato.</p>
    <form id="staff-form" class="join-row"><label class="visually-hidden" for="st-email">Correo</label><input id="st-email" type="email" required placeholder="nombre@pucv.cl"><label class="visually-hidden" for="st-project">Asignatura</label><select id="st-project" class="select">${Object.keys(PROJECTS).map(id=>`<option value="${id}">${esc(PROJECTS[id].name)}</option>`).join('')}</select><button class="button small" type="submit">Asignar</button></form>
    <div id="staff-list" class="helper">Cargando…</div></section>`;
}
async function loadStaff() {
  const box=document.querySelector('#staff-list');
  try{const d=await api('/api/admin/staff');
    const rows=[...d.admins.map(e=>`<tr><td>${esc(e)}</td><td>Administración global</td><td class="helper">servidor</td></tr>`),
      ...d.configured.map(r=>`<tr><td>${esc(r.email)}</td><td>${esc(PROJECTS[r.project_id].name)}</td><td class="helper">servidor</td></tr>`),
      ...d.assigned.map(r=>`<tr><td>${esc(r.email)}</td><td>${esc(PROJECTS[r.project_id].name)}</td><td><button class="text-button" type="button" data-staff-remove="${esc(r.email)}" data-project="${r.project_id}">Quitar</button></td></tr>`)];
    box.innerHTML=`<table class="code-table"><thead><tr><th>Correo</th><th>Rol</th><th></th></tr></thead><tbody>${rows.join('')}</tbody></table><p class="helper">Los marcados «servidor» se cambian en las variables PUCV_ADMIN_EMAILS y PUCV_*_ADMINS del hosting.</p>`;
  }catch(ex){box.textContent=ex.message;}
}
function bindStaff() {
  document.querySelector('#staff-form').addEventListener('submit',async e=>{e.preventDefault();
    try{const r=await api('/api/admin/staff',{method:'POST',body:JSON.stringify({email:document.querySelector('#st-email').value,project_id:document.querySelector('#st-project').value})});notify(r.message);document.querySelector('#st-email').value='';loadStaff();}catch(ex){notify(ex.message);}});
  document.querySelector('#staff-list').addEventListener('click',async e=>{const b=e.target.closest('[data-staff-remove]');if(!b)return;
    try{await api('/api/admin/staff',{method:'POST',body:JSON.stringify({email:b.dataset.staffRemove,project_id:b.dataset.project,action:'remove'})});loadStaff();}catch(ex){notify(ex.message);}});
  loadStaff();
}
function privacyPanel() {
  return `<section class="detail-panel resource-detail"><h2>Gestión de datos y solicitudes</h2>
    <div class="code-columns">
      <form id="person-form" class="form-grid"><h3>Solicitud de una persona</h3><div class="field"><label for="pp-email">Correo</label><input id="pp-email" type="email" required placeholder="nombre@mail.pucv.cl"></div>
        <div class="moderation-actions"><button class="button secondary small" type="submit" data-person="export">Descargar sus datos (JSON)</button><button class="button secondary small" type="submit" data-person="delete">Eliminar sus datos…</button></div>
        <p class="helper">Eliminar borra su cuenta, comentarios, coevaluaciones y entregas no publicadas, y quita su nombre de los trabajos publicados de su equipo. Las respuestas no incluyen el nombre o correo en el registro de contenido; la participación está en una tabla aparte.</p><div class="error-text" role="alert"></div></form>
      <form id="cohort-form" class="form-grid"><h3>Cierre de cohorte</h3><p class="helper">Al cerrar una cohorte, primero define la conservación y descarga el respaldo fuera del sitio. Esta acción anonimiza cuentas, borra entregas no publicadas, quita los nombres de integrantes y retira trabajos sin autorización de vitrina; los respaldos anteriores no se eliminan automáticamente.</p>
        <div class="field"><label for="cohort-confirm">Escribe CERRAR COHORTE</label><input id="cohort-confirm" autocomplete="off"></div><div class="error-text" role="alert"></div><button class="button secondary small" type="submit">Cerrar cohorte</button></form>
    </div></section>`;
}
function bindPrivacy() {
  const person=document.querySelector('#person-form');
  person.addEventListener('submit',async e=>{e.preventDefault();const email=document.querySelector('#pp-email').value.trim().toLowerCase(), error=person.querySelector('.error-text');error.textContent='';
    if(e.submitter?.dataset.person==='export'){location.href=`/api/admin/person?email=${encodeURIComponent(email)}`;return;}
    const confirmEmail=prompt(`Esto no se puede deshacer. Escribe de nuevo el correo para eliminar los datos de ${email}:`);if(confirmEmail===null)return;
    try{const r=await api('/api/admin/person/delete',{method:'POST',body:JSON.stringify({email,confirm:confirmEmail})});notify(r.message);person.reset();}catch(ex){error.textContent=ex.message;}});
  const cohort=document.querySelector('#cohort-form');
  cohort.addEventListener('submit',async e=>{e.preventDefault();const error=cohort.querySelector('.error-text');
    if(!confirm('¿Cerrar la cohorte? Las cuentas de estudiantes quedarán anonimizadas.'))return;
    try{const r=await api('/api/admin/cohort/close',{method:'POST',body:JSON.stringify({confirm:document.querySelector('#cohort-confirm').value})});notify(r.message);error.textContent=r.message;}catch(ex){error.textContent=ex.message;}});
}
async function loadPeerSummary() {
  const box=document.querySelector('#peer-summary'); if(!box)return;
  try{const rows=await api('/api/admin/peer-summary');
    box.innerHTML=rows.length?`<table class="code-table"><thead><tr><th>Ficha</th><th>Evaluaciones</th><th>Promedio</th><th>Por criterio</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.title)}<br><span class="helper">${esc(r.team_name)}${r.section?' · '+esc(r.section):''} · ${esc(PROJECTS[r.project_id].name)}</span></td><td>${r.count}</td><td><b>${r.overall??'—'}</b></td><td class="helper">${r.averages.map(a=>`${esc(a.label)}: ${a.average??'—'}`).join('<br>')}</td></tr>`).join('')}</tbody></table>`:'<p class="helper">Aún no hay coevaluaciones. Aparecen cuando el curso evalúa las fichas publicadas de otros equipos.</p>';
  }catch(ex){box.textContent=ex.message;}
}
async function loadBackups() {
  const box=document.querySelector('#backup-info'); if(!box)return;
  try{const info=await api('/api/admin/backups'), last=info.backups[0];
    box.innerHTML=info.enabled?`Copia automática de la base cada ${info.every_hours} h (se guardan las últimas ${info.keep}). ${last?`Última: ${new Date(last.created_at*1000).toLocaleString('es-CL')} · ${(last.size/1024).toFixed(0)} KB.`:'Aún no se genera la primera.'}`:'Las copias automáticas están desactivadas (APP_BACKUP_HOURS=0).';
  }catch(ex){box.textContent=ex.message;}
}
const HELP=[
  ['Entrar',[
    ['¿Cómo entro?','Abre el enlace de invitación de tu curso y continúa con tu cuenta Google @mail.pucv.cl o @pucv.cl. Si Google no funciona, pide a la docente un código personal y escríbelo en «Tengo un código de ingreso».'],
    ['Entré, pero no veo mi asignatura','Abre la invitación que compartió la docente. Si ya iniciaste sesión, se activa al instante; si todavía no, entra con tu cuenta Google PUCV y luego se agregará automáticamente. Si tienes un código personal, úsalo en «Tengo un código de ingreso».'],
    ['¿Puedo usar mi Gmail personal?','No. Solo se aceptan cuentas institucionales @mail.pucv.cl o @pucv.cl.']]],
  ['Trabajar',[
    ['¿Dónde está nuestro desafío o caso?','En la pestaña «Desafíos» (Incentiva) o «Casos y recursos» (Innova). En Incentiva, «Sacar un desafío» sortea uno.'],
    ['¿Cómo hacemos el video?','Abre «Guía para un video final» en tu asignatura o el kit imprimible: storyboard de seis bloques, herramientas gratuitas y uso ético de IA.'],
    ['¿Qué son los tiquetes de salida y las encuestas?','Preguntas breves al cierre de una sesión o del proyecto. El nombre y correo no se guardan junto a la respuesta; sí se registra por separado quién ya participó. Se responden con el QR o desde «Tiquetes y encuestas».']]],
  ['Entregar',[
    ['¿Quién entrega?','Una persona por equipo, en «Entregar trabajo». Si escriben el correo PUCV de cada integrante junto a su nombre, todo el equipo puede responder en el foro como «Equipo autor».'],
    ['¿Qué se entrega?','El enlace al único video final (MP4, máximo 5 minutos), la ficha de evidencia (archivo o enlace), los campos de la asignatura, la declaración de IA y la declaración sobre recursos y personas identificables.'],
    ['Nos devolvieron la entrega','Lean el comentario de la docente en «Tus entregas», corrijan y vuelvan a enviarla con el mismo nombre de equipo.']]],
  ['Después de publicar',[
    ['¿Qué hacemos cuando nuestra ficha se publica?','Respondan las preguntas del foro: sus respuestas aparecen destacadas como «Equipo autor». También verán la coevaluación de sus pares, sin nombres.'],
    ['¿Cómo coevalúo?','Abre la ficha de otro equipo y completa «Coevaluación entre pares»: cinco criterios de 1 a 4, una fortaleza y una sugerencia. Puedes corregirla después.']]],
  ['Datos y privacidad',[
    ['¿Quién ve lo que publicamos?','Solo las cuentas autorizadas de la asignatura. Si el equipo marca la vitrina, también otros cursos PUCV en modo lectura.'],
    ['Quiero que borren mis datos','Pídelo a la docente: puede descargarte todo lo que hay sobre ti o eliminarlo. Más detalle en el aviso de privacidad.']]],
];
function helpPage() {
  main.innerHTML=`<article class="resource-detail legal-page"><a class="back-link" data-route="/" href="/">← Volver al inicio</a><div class="eyebrow">Ayuda</div><h1>Cómo usar el repositorio</h1>
    <p class="lead">Respuestas cortas a lo que más se pregunta. Si algo no funciona, escribe en el foro de tu asignatura o a la docente.</p>
    ${HELP.map(([group,items])=>`<section class="detail-panel"><h2>${esc(group)}</h2>${items.map(([q,a])=>`<details class="help-item"><summary>${esc(q)}</summary><p class="detail-content">${esc(a)}</p></details>`).join('')}</section>`).join('')}
    <p class="helper">Materiales: <a href="/kit" data-route="/kit">kit de producción</a> · <a href="/materiales/ficha-evidencia-incentiva.docx" download>Ficha de Evidencia (Word)</a> · <a href="/materiales/matriz-diagnostica-innova.docx" download>matriz diagnóstica (Word)</a> · <a href="/consentimiento" data-route="/consentimiento">autorización de imagen y voz</a> · <a href="/privacidad" data-route="/privacidad">aviso de privacidad</a>.</p></article>`;
}
function kitPage(projectId) {
  const p=PROJECTS[projectId], innova=projectId==='innova';
  const boxes=STORYBOARD.map(([time,incentiva,innovaLabel],i)=>`<article class="kit-block"><div class="kit-block-head"><b>${i+1}. ${esc(innova?innovaLabel:incentiva)}</b><span>${time}</span></div><div class="kit-frame" aria-hidden="true"></div><p class="kit-lines">Qué se ve: ________________________________<br>Qué se escucha o se lee: _____________________</p></article>`).join('');
  main.innerHTML=`<article class="resource-detail kit-page project-page ${innova?'innova-theme':''}"><a class="back-link no-print" data-route="/" href="/">← Volver al inicio</a>
    <div class="eyebrow">${esc(p.name)} · Kit de producción</div><h1>Un video final de máximo 5 minutos</h1>
    <p class="lead">Storyboard, especificaciones, guía de grabación con celular y uso ético de IA. Imprímelo o guárdalo como PDF para el equipo.</p>
    <p class="no-print"><button class="button small" type="button" id="print-kit">Imprimir</button> <a class="button secondary small" href="/materiales/kit-${projectId}.pdf" download>Descargar PDF ↧</a> <a class="button secondary small" href="/materiales/${innova?'matriz-diagnostica-innova':'ficha-evidencia-incentiva'}.docx" download>Plantilla de ${innova?'matriz diagnóstica':'Ficha de Evidencia'} (Word) ↧</a> <a class="text-button" href="/kit/${innova?'incentiva':'innova'}" data-route="/kit/${innova?'incentiva':'innova'}">Ver el kit de ${innova?'Incentiva':'Innova'}</a></p>
    <section class="detail-panel"><h2>1. Storyboard en 6 bloques</h2><p class="helper">Equipo: ____________________ · Título: ________________________________ · Bloques y tiempos de la propuesta del proyecto (puede moverse ±15 s por bloque).</p><div class="kit-grid">${boxes}</div></section>
    <section class="detail-panel kit-break"><h2>2. Especificaciones del archivo final</h2><ul class="legal-list">
      <li><b>Un solo archivo MP4</b> (H.264) por equipo, <b>horizontal 16:9</b>, 1080p (mínimo 720p), <b>máximo 5:00</b>.</li>
      <li><b>Audio limpio:</b> la voz se entiende sin subir el volumen; música de fondo muy baja o ninguna mientras se habla.</li>
      <li><b>Subtítulos</b> incrustados o en archivo .srt. Los automáticos de YouTube, CapCut o Clipchamp sirven si el equipo los revisa entero.</li>
      <li><b>Créditos al final:</b> integrantes, fuentes de imágenes y música (con su licencia) y la declaración de IA.</li>
      <li>Compartir desde Drive con acceso limitado a las cuentas PUCV autorizadas, cuando sea posible. Un video de YouTube «no listado» lo puede ver cualquiera que reciba el enlace; no usen esa opción para material sensible. Prueben el enlace en una ventana privada.</li>
    </ul></section>
    <section class="detail-panel"><h2>3. Grabar con el celular</h2><ol class="legal-list">
      <li>Celular en <b>horizontal</b> y lente limpio.</li>
      <li>Luz de frente a quien habla (una ventana sirve); nunca una ventana detrás.</li>
      <li>Apoyar el celular o usar trípode; si se mueve, que sea lento.</li>
      <li>Planos cortos (10–20 s). Grabar 3 segundos antes y después de cada toma para editar cómodo.</li>
      <li>Voz en un lugar silencioso y con el micrófono a un palmo; la narración se puede grabar aparte.</li>
      <li>Revisar el resultado con audífonos antes de editar.</li>
      <li>${innova?'Mostrar el modelo 3D o el prototipo de cerca y en movimiento, con una mano o un objeto que dé escala.':'Simular la solución con personas, maqueta o pantallas: que se vea a alguien usándola.'}</li>
    </ol></section>
    <section class="detail-panel"><h2>4. Uso ético de la IA</h2>
      <div class="kit-columns"><div><h3>Se puede</h3><ul class="legal-list"><li>Fondos, íconos, transiciones o una escena ilustrativa breve.</li><li>Subtítulos o transcripción automática, revisados.</li><li>Ordenar ideas o mejorar la redacción del guion, revisada por el equipo.</li></ul></div>
      <div><h3>No se puede</h3><ul class="legal-list"><li>Generar la evidencia, los datos, las citas o las conclusiones.</li><li>Usar datos, fotos o voces de pacientes o personas reales sin autorización.</li><li>Presentar como propio lo que hizo la herramienta.</li></ul></div></div>
      <p class="detail-content">Verifiquen cada cita y cada dato con la fuente original: la IA inventa referencias con frecuencia.</p>
      <h3>Declaración del equipo (va en los créditos y en el formulario de entrega)</h3>
      <table class="consent-table"><thead><tr><th>Herramienta</th><th>Para qué la usamos</th><th>Qué revisamos o corregimos</th></tr></thead><tbody>${'<tr><td></td><td></td><td></td></tr>'.repeat(3)}</tbody></table>
      <p class="detail-content">Declaramos que el problema, la evidencia, el análisis y las conclusiones son del equipo, y que revisamos todo lo producido con IA. Firmas: ____________________________________________</p></section>
    <section class="detail-panel"><h2>5. Antes de entregar</h2><ul class="check-list">
      <li>☐ Un solo video, de máximo 5 minutos, que abre en una ventana privada.</li><li>☐ Subtítulos revisados.</li><li>☐ ${innova?'Alteración, proceso, efecto, técnica y controles explicados.':'Problema, personas afectadas, solución, simulación, indicador y limitación.'}</li>
      <li>☐ Ficha de evidencia lista (archivo o enlace).</li><li>☐ Declaración de IA completa.</li><li>☐ Si aparecen personas identificables, cada una autorizó ese uso o se editó una versión sin elementos que la identifiquen.</li><li>☐ Sin datos de pacientes ni de personas reales identificables sin permiso.</li></ul></section>
  </article>`;
  document.querySelector('#print-kit').addEventListener('click',()=>window.print());
}
function privacyPage() {
  main.innerHTML=`<article class="resource-detail legal-page"><a class="back-link" data-route="/" href="/">← Volver al inicio</a><div class="eyebrow">Datos personales</div><h1>Aviso de privacidad</h1>
    <div class="notice warning">Borrador operativo para revisar con las docentes antes de abrir el sitio. La Ley 21.719 entra en vigencia el 1 de diciembre de 2026; este texto no declara cumplimiento legal. Antes de usar datos reales, deben confirmar responsable, contacto, finalidad, base de tratamiento, proveedores, conservación y procedimiento de solicitudes.</div>
    <section class="detail-panel"><h2>Quién es responsable</h2><p class="detail-content">El equipo docente de los proyectos Incentiva en el Aula e Innova en el Aula de la Escuela de Tecnología Médica PUCV administra este repositorio. Las consultas y solicitudes sobre tus datos se dirigen a la docente de tu asignatura, por el Aula Virtual o por correo institucional.</p></section>
    <section class="detail-panel"><h2>Qué datos se usan y para qué</h2><ul class="legal-list">
      <li><b>Cuenta:</b> correo institucional y nombre (el que entrega Google o el que se deduce del correo). Sirven para darte acceso a tu asignatura.</li>
      <li><b>Asignatura y paralelo:</b> para mostrarte solo los materiales de tu curso y ordenar las entregas.</li>
      <li><b>Entregas:</b> equipo, integrantes, título, resumen, campos del proyecto, enlaces al video y a la ficha, archivos adjuntos y declaración de uso de IA. Se usan para la revisión y retroalimentación docente.</li>
      <li><b>Comentarios del foro:</b> se revisan antes de publicarse.</li>
      <li><b>Preguntas de control y coevaluación:</b> la docente ve tus respuestas agregadas y quién hizo cada coevaluación; el equipo evaluado recibe los puntajes y comentarios sin tu nombre.</li>
      <li><b>Tiquetes de salida y encuestas (KPSI y percepción):</b> la respuesta no se guarda con tu correo o nombre. Para permitir una respuesta por persona, el sistema guarda la participación en una tabla separada; los informes no muestran quién respondió. No se debe presentar este mecanismo como anonimato certificado para investigación.</li>
      <li><b>Registros técnicos:</b> la aplicación conserva por hasta 24 horas la IP usada en intentos fallidos, solo para limitar abuso. La sesión usa una cookie técnica por 12 horas. El hosting puede mantener registros técnicos según su propia política; el sitio no usa publicidad ni analítica de terceros.</li>
    </ul><p class="detail-content">Los informes de los proyectos usan solo cifras agregadas, sin identificar a personas.</p></section>
    <section class="detail-panel"><h2>Quién puede verlos</h2><ul class="legal-list">
      <li>La docente y el equipo de apoyo de cada asignatura ven las entregas y los integrantes de su curso.</li>
      <li>Una entrega aprobada aparece en el catálogo para las cuentas con acceso a esa asignatura. El permiso de la vitrina para otras cohortes es opcional.</li>
      <li>Si todas las personas del equipo dieron su autorización expresa, su trabajo puede aparecer en la vitrina de solo lectura para otras cuentas PUCV (otros cursos y cohortes). La casilla no comprueba por sí sola esas autorizaciones.</li>
      <li>Si el video está en YouTube, se reproduce con el modo de privacidad mejorada (youtube-nocookie.com).</li>
      <li>Proveedores: el servicio de hosting y, si ingresas con Google, Google. El sitio guarda enlaces, no el video final; el almacenamiento y los permisos dependen de YouTube, Google Drive u otro servicio que el equipo elija.</li>
    </ul><p class="detail-content">Un enlace de YouTube «no listado» lo puede ver cualquier persona que lo reciba. Para controlar el acceso, prefieran Drive restringido a cuentas PUCV autorizadas y verifiquen el enlace antes de entregarlo. No suban datos de pacientes reales ni información identificable a herramientas externas de edición o IA.</p></section>
    <section class="detail-panel"><h2>Cuánto tiempo se guardan</h2><p class="detail-content">El plazo está pendiente de definición por las docentes y deberá publicarse antes de iniciar la recolección. La función de cierre de cohorte anonimiza cuentas, retira ciertos materiales y desactiva formularios, pero no reemplaza una política de conservación aprobada ni elimina los respaldos históricos automáticamente.</p></section>
    <section class="detail-panel"><h2>Tus derechos</h2><p class="detail-content">Puedes pedir que el equipo docente revise tus datos, corrija información o retire una entrega; el procedimiento se confirmará con las docentes antes de abrir el sitio. Si retiras la autorización de uso de tu imagen o voz, el video se retira del catálogo; la evaluación ya realizada no cambia.</p><p class="detail-content">Para incluir imágenes o voces identificables en un video, el equipo usa el <a href="/consentimiento" data-route="/consentimiento">formulario de autorización de imagen y voz</a>.</p></section>
  </article>`;
}
function consentPage() {
  const rows=Array.from({length:7},()=>'<tr><td></td><td></td><td></td><td></td></tr>').join('');
  main.innerHTML=`<article class="resource-detail legal-page consent-form"><a class="back-link no-print" data-route="/" href="/">← Volver al inicio</a>
    <div class="eyebrow">Tecnología Médica · PUCV</div><h1>Autorización opcional de imagen y voz</h1><p class="lead">Video final del equipo · Incentiva en el Aula / Innova en el Aula</p>
    <p class="no-print"><button class="button small" type="button" id="print-consent">Imprimir</button> <a class="button secondary small" href="/materiales/consentimiento.pdf" download>Descargar PDF ↧</a></p>
    <section class="detail-panel"><p class="consent-line">Asignatura: ☐ Incentiva en el Aula (Metodología de la Investigación) &nbsp; ☐ Innova en el Aula (Fundamentos de Diagnóstico Molecular)</p>
      <p class="consent-line">Equipo: ______________________ &nbsp; Paralelo: ______________ &nbsp; Título del trabajo: ________________________________</p></section>
    <section class="detail-panel"><h2>Autorizo que mi imagen o mi voz identificable, tal como aparecen en el video del equipo, se use para:</h2><ul class="check-list">
      <li>☐ Su publicación en el repositorio del curso, visible solo para cuentas PUCV autorizadas de la asignatura.</li>
      <li>☐ Su uso como ejemplo con futuras cohortes del mismo curso.</li>
      <li>☐ La difusión académica del proyecto (presentaciones e informes), sin datos de contacto.</li>
    </ul><p class="detail-content">La autorización de imagen o voz identificable es opcional y no condiciona la entrega ni la evaluación. El equipo puede presentar el prototipo, una maqueta, diapositivas, manos, animación, subtítulos o narración sin identificar a nadie. Puedo marcar solo algunas opciones y retirar esta autorización escribiendo a la docente; el retiro no cambia la evaluación ya realizada.</p>
    <p class="detail-content">Si en el video aparecen personas que no integran el equipo (por ejemplo, en un role-play), cada una firma este formulario. No se incluyen datos de pacientes reales.</p></section>
    <p class="helper">El equipo conserva el formulario firmado y entrega una copia a la docente. Para más firmas, adjunta otra hoja.</p>
    <table class="consent-table"><thead><tr><th>Nombre completo</th><th>Correo institucional</th><th>Opciones autorizadas</th><th>Firma y fecha</th></tr></thead><tbody>${rows}</tbody></table>
  </article>`;
  document.querySelector('#print-consent').addEventListener('click',()=>window.print());
}
async function render() {
  header();
  const path=currentPath();
  // Privacy and consent pages are readable before signing in.
  if(path==='/privacidad') return privacyPage();
  if(path==='/consentimiento') return consentPage();
  if(path==='/ayuda') return helpPage();
  const kit=path.match(/^\/kit(?:\/(incentiva|innova))?$/);
  if(kit) return kitPage(kit[1]||'incentiva');
  const ticket=path.match(/^\/(tiquete|encuesta)\/([A-Za-z0-9-]{4,12})$/), ficha=path.match(/^\/ficha\/(\d+)$/);
  if(!user){ if(ticket){try{sessionStorage.setItem('afterLogin',path);}catch{}} return login(); }
  if(ticket) return ticket[1]==='tiquete'?ticketPage(ticket[2]):surveyPage(ticket[2]);
  if(ficha) return fichaPage(Number(ficha[1]));
  const managerPage=path.match(/^\/(informe|proyeccion)\/(incentiva|innova)$/);
  if(managerPage) return managerPage[1]==='informe'?reportPage(managerPage[2]):projectionPage(managerPage[2]);
  if(path==='/') return home();
  if(path==='/admin') return moderatorPage();
  const detail=path.match(/^\/(incentiva|innova)\/recurso\/([^/]+)$/);
  if(detail&&!activeProjects.includes(detail[1])&&readerProjects.includes(detail[1])) return detailPage(detail[1],decodeURIComponent(detail[2]),true);
  if(detail&&!activeProjects.includes(detail[1])&&user.role!=='admin') return accessDeniedPage(detail[1]);
  if(detail) return detailPage(detail[1],decodeURIComponent(detail[2]));
  const project=path.match(/^\/(incentiva|innova)(?:\/.*)?$/);
  if(project&&!activeProjects.includes(project[1])&&readerProjects.includes(project[1])) return projectPage(project[1],true);
  if(project&&!activeProjects.includes(project[1])&&user.role!=='admin') return accessDeniedPage(project[1]);
  if(project) return projectPage(project[1]);
  return home();
}
async function bootstrap() {
  try { const state=await api('/api/me'); user=state.user; activeProjects=state.active_projects||[]; pendingProjects=state.pending_projects||[]; managedProjects=state.managed_projects||[]; projectConfig=state.project_config||{}; mySections=state.my_sections||{}; readerProjects=state.reader_projects||[]; window.APP_DEMO=state.demo; window.APP_EMAIL_READY=state.email_ready; window.APP_GOOGLE_READY=state.google_ready; }
  catch { user=null; }
  // Keep project invitations and QR forms through the full-page Google/email sign-in round trip.
  if(!user){const invite=new URLSearchParams(location.search).get('unirse');if(invite){try{sessionStorage.setItem('afterLogin',`/?unirse=${encodeURIComponent(invite)}`);}catch{}}}
  if(user){
    try{const next=sessionStorage.getItem('afterLogin');if(next){sessionStorage.removeItem('afterLogin');if(currentPath()==='/'&&next.startsWith('/')&&!next.startsWith('//'))history.replaceState({},'',next);}}catch{}
    const invite=new URLSearchParams(location.search).get('unirse');
    if(invite){history.replaceState({},'','/');try{await api('/api/join',{method:'POST',body:JSON.stringify({code:invite})});const state=await api('/api/me');activeProjects=state.active_projects||[];pendingProjects=state.pending_projects||[];mySections=state.my_sections||{};notify('Listo: ya tienes acceso a la asignatura.');}catch(ex){notify(ex.message);}}
  }
  render();
}
bootstrap();
