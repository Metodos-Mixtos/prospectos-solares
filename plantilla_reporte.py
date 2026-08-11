# -*- coding: utf-8 -*-
"""
Plantilla del reporte HTML. Vive aparte de reporte_html.py para que la lógica de datos
y el marcado no se estorben. Los marcadores __ASI__ los sustituye reporte_html.py.
"""

PLANTILLA = r"""<title>Grillas candidatas para granjas solares</title>
<style>
/* ---------------------------------------------------------------------------
   Paleta tomada del logotipo de Métodos Mixtos.

   El teal de la marca es #18919C exacto, medido sobre el archivo. Da 3,6:1 sobre
   papel blanco, que basta para gráficos pero no para texto pequeño, así que el
   acento tipográfico es el mismo tono oscurecido hasta 4,55:1. La marca conserva
   su color literal en el isotipo y en los elementos gráficos.

   Los neutrales no son grises puros: llevan el mismo matiz (h=0.514) del teal en
   saturación muy baja, de modo que la página se lea como una sola familia.

   La rampa ámbar es deliberadamente ajena a la marca. Codifica un dato, la
   irradiación, y tiene que distinguirse del color corporativo a primera vista.
   --------------------------------------------------------------------------- */
:root{
  --brand:#18919C;
  --ground:#F9FBFB; --surface:#FFFFFF; --surface-2:#F2F4F5; --surface-3:#E9ECEC;
  --ink:#1E2829; --ink-2:#49585A; --ink-3:#7F8E90;
  --line:#DFE2E2; --line-2:#C8CFD0;
  --accent:#157F88; --accent-2:#0F5E65; --accent-soft:#E2F0F1;
  --good:#3D7A5A; --warn:#B0761E; --bad:#A8492F;
  --good-bg:#E7F1EB; --warn-bg:#F8EFDC; --bad-bg:#F7E6E1;
  --rad1:#F4E3C1; --rad2:#EDC988; --rad3:#E3A44E; --rad4:#D17B2C; --rad5:#B44E18;
  --map-land:#EDF0F0; --map-line:#CFD6D6;
  --on-accent:#FFFFFF;
  --shadow:0 1px 2px rgba(30,40,41,.06),0 4px 14px rgba(30,40,41,.05);
}
@media (prefers-color-scheme:dark){
  :root{
    --brand:#22A4B0;
    --ground:#131818; --surface:#1C2323; --surface-2:#262E2E; --surface-3:#313A3A;
    --ink:#E6EAEA; --ink-2:#ADB7B8; --ink-3:#7D8B8C;
    --line:#303A3B; --line-2:#404D4F;
    --accent:#35AAB5; --accent-2:#5EC4CE; --accent-soft:#123539;
    --good:#71B593; --warn:#DCA950; --bad:#D87F66;
    --good-bg:#183028; --warn-bg:#2E2617; --bad-bg:#33201C;
    --rad1:#4A4433; --rad2:#7A6334; --rad3:#A87C36; --rad4:#C7853A; --rad5:#DE8B45;
    --map-land:#1F2727; --map-line:#374242;
    --on-accent:#0C1213;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 18px rgba(0,0,0,.28);
  }
}
:root[data-theme="dark"]{
  --brand:#22A4B0;
  --ground:#131818; --surface:#1C2323; --surface-2:#262E2E; --surface-3:#313A3A;
  --ink:#E6EAEA; --ink-2:#ADB7B8; --ink-3:#7D8B8C;
  --line:#303A3B; --line-2:#404D4F;
  --accent:#35AAB5; --accent-2:#5EC4CE; --accent-soft:#123539;
  --good:#71B593; --warn:#DCA950; --bad:#D87F66;
  --good-bg:#183028; --warn-bg:#2E2617; --bad-bg:#33201C;
  --rad1:#4A4433; --rad2:#7A6334; --rad3:#A87C36; --rad4:#C7853A; --rad5:#DE8B45;
  --map-land:#1F2727; --map-line:#374242;
  --on-accent:#0C1213;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 18px rgba(0,0,0,.28);
}
:root[data-theme="light"]{
  --brand:#18919C;
  --ground:#F9FBFB; --surface:#FFFFFF; --surface-2:#F2F4F5; --surface-3:#E9ECEC;
  --ink:#1E2829; --ink-2:#49585A; --ink-3:#7F8E90;
  --line:#DFE2E2; --line-2:#C8CFD0;
  --accent:#157F88; --accent-2:#0F5E65; --accent-soft:#E2F0F1;
  --good:#3D7A5A; --warn:#B0761E; --bad:#A8492F;
  --good-bg:#E7F1EB; --warn-bg:#F8EFDC; --bad-bg:#F7E6E1;
  --rad1:#F4E3C1; --rad2:#EDC988; --rad3:#E3A44E; --rad4:#D17B2C; --rad5:#B44E18;
  --map-land:#EDF0F0; --map-line:#CFD6D6;
  --on-accent:#FFFFFF;
  --shadow:0 1px 2px rgba(30,40,41,.06),0 4px 14px rgba(30,40,41,.05);
}

*{box-sizing:border-box}
body{margin:0; background:var(--ground); color:var(--ink);
  font-family:"Segoe UI",-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif;
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased}
.mono{font-family:"Cascadia Mono","SF Mono",Consolas,"Liberation Mono",monospace;
  font-variant-numeric:tabular-nums}
.wrap{max-width:1240px; margin:0 auto; padding:0 22px 80px}

header{border-bottom:1px solid var(--line); background:var(--surface); margin-bottom:26px}
.head{max-width:1240px; margin:0 auto; padding:26px 22px 24px}
.eyebrow{font-size:11.5px; letter-spacing:.13em; text-transform:uppercase;
  color:var(--accent); font-weight:600; margin-bottom:7px}
h1{font-family:"Bahnschrift","DIN Alternate","Avenir Next Condensed",system-ui,sans-serif;
  font-weight:600; font-size:clamp(27px,3.6vw,40px); line-height:1.08; margin:0;
  text-wrap:balance; letter-spacing:-.005em}
/* Justificado y a todo el ancho, como se pidió. hyphens e inter-word evitan que el
   justificado abra ríos de espacio en las líneas más cortas. */
.sub{color:var(--ink-2); font-size:15px; line-height:1.6; margin:11px 0 0;
  text-align:justify; text-justify:inter-word; hyphens:auto;
  -webkit-hyphens:auto; max-width:none}
@media(max-width:640px){ .sub{text-align:left; hyphens:manual} }

/* Marca. El gris del wordmark original es #909090; aquí se usa --ink-2, que es el
   mismo valor de claridad pero con el matiz de la casa, para que no chirríe contra
   los neutrales de la página. */
.brand{display:flex; align-items:center; gap:11px; margin-bottom:16px}
.brand-mark{width:29px; height:32px; flex:none; display:block}
.brand-text{display:flex; flex-direction:column; line-height:1.05}
.brand-name{font-family:"Bahnschrift","DIN Alternate",system-ui,sans-serif; font-weight:600;
  font-size:16px; letter-spacing:.055em; text-transform:uppercase; color:var(--ink-2)}
.brand-sub{font-size:9px; letter-spacing:.42em; text-transform:uppercase; color:var(--brand);
  margin-top:3px; font-weight:600}

.kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(172px,1fr)); gap:12px; margin-bottom:28px}
.kpi{background:var(--surface); border:1px solid var(--line); border-radius:3px;
  padding:15px 16px 14px; box-shadow:var(--shadow); position:relative; overflow:hidden}
.kpi::before{content:""; position:absolute; left:0; top:0; bottom:0; width:2px; background:var(--accent)}
.kpi.g::before{background:var(--good)} .kpi.w::before{background:var(--warn)}
.kpi.b::before{background:var(--bad)} .kpi.n::before{background:var(--ink-3)}
.kpi.n .kpi-val{color:var(--ink-3)}
.kpi-lab{font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3); font-weight:600}
.kpi-val{font-family:"Bahnschrift","DIN Alternate",system-ui,sans-serif; font-weight:600;
  font-size:31px; line-height:1.12; margin-top:5px; font-variant-numeric:tabular-nums}
.kpi-note{font-size:12px; color:var(--ink-2); margin-top:2px}

section{margin-bottom:34px}
.sec-head{display:flex; align-items:baseline; gap:12px; margin-bottom:14px;
  padding-bottom:9px; border-bottom:1px solid var(--line); flex-wrap:wrap}
h2{font-family:"Bahnschrift","DIN Alternate",system-ui,sans-serif; font-weight:600;
  font-size:20px; margin:0; letter-spacing:.005em}
.sec-note{font-size:13px; color:var(--ink-3)}

.mapgrid{display:grid; grid-template-columns:minmax(0,1.25fr) minmax(285px,.75fr); gap:22px; align-items:start}
@media(max-width:920px){.mapgrid{grid-template-columns:1fr}}
.mapbox{background:var(--surface); border:1px solid var(--line); border-radius:3px;
  padding:10px; box-shadow:var(--shadow)}
.mapa-wrap{position:relative}
svg.mapa{width:100%; height:auto; display:block; max-height:78vh; touch-action:none;
  cursor:grab}
svg.mapa.arrastrando{cursor:grabbing}
.mapa-zoom{position:absolute; top:8px; right:8px; display:flex; flex-direction:column; gap:4px}
.mapa-zoom button{width:28px; height:28px; padding:0; font-size:15px; line-height:1;
  border:1px solid var(--line-2); background:var(--surface); color:var(--ink-2);
  border-radius:2px; cursor:pointer; font-family:inherit}
.mapa-zoom button:hover{border-color:var(--accent); color:var(--accent)}
.mapa-nivel{position:absolute; bottom:8px; right:8px; font-size:11px; color:var(--ink-3);
  background:var(--surface); border:1px solid var(--line); border-radius:2px;
  padding:2px 7px; font-variant-numeric:tabular-nums}
.mapa-ayuda{font-size:11.5px; color:var(--ink-3); margin:8px 2px 2px; text-align:center}
/* Los vecinos van detrás y apagados, para que Colombia destaque sin perder el contexto
   de las líneas que cruzan la frontera. El contorno nacional va en trazo grueso. */
.vecinos{fill:var(--surface-2); stroke:var(--map-line); stroke-width:.6; opacity:.55}
.pais{fill:var(--map-land); stroke:var(--ink-2); stroke-width:2}
.dep{fill:none; stroke:var(--map-line); stroke-width:.7; opacity:.85}
/* capas conmutables */
#subs, #lineas, .divs{display:none}
#subs.on, #lineas.on, .divs.on{display:inline}
.divs path{fill:none; vector-effect:non-scaling-stroke}
#div-departamento path{stroke:var(--ink-3); stroke-width:1; opacity:.8}
#div-municipio path{stroke:var(--ink-3); stroke-width:.55; opacity:.55}
#div-vereda path{stroke:var(--accent); stroke-width:.5; opacity:.6}
#div-grilla path{stroke:var(--brand); stroke-width:.9; opacity:.85}
.sub-pt{fill:var(--accent); fill-opacity:.75; stroke:var(--surface); stroke-width:.5}
.lin{fill:none; stroke:var(--accent-2); stroke-opacity:.55; stroke-width:1}
.lin.alta{stroke:var(--bad); stroke-opacity:.6; stroke-width:1.4}
.pt{cursor:pointer; stroke:var(--surface); stroke-width:1.1}
.pt:hover{stroke:var(--ink); stroke-width:1.6}
.pt.sel{stroke:var(--ink); stroke-width:2.4}
.pt.off{opacity:.12; pointer-events:none}

.side{display:flex; flex-direction:column; gap:14px; position:sticky; top:14px}
.card{background:var(--surface); border:1px solid var(--line); border-radius:3px;
  padding:15px 16px; box-shadow:var(--shadow)}
.card h3{font-family:"Bahnschrift","DIN Alternate",system-ui,sans-serif; font-weight:600;
  font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3); margin:0 0 11px}
.ramp{display:flex; height:9px; border-radius:2px; overflow:hidden; margin:8px 0 5px}
.ramp span{flex:1}
.ramp-lab{display:flex; justify-content:space-between; font-size:11px; color:var(--ink-3)}
.legend-row{display:flex; align-items:center; gap:9px; font-size:13px; margin-bottom:6px}
.sw{width:11px; height:11px; border-radius:50%; flex:none}
.ln{width:15px; height:3px; border-radius:1px; flex:none; opacity:.7}

/* buscador */
.buscador input[type="search"]{width:100%; font-family:inherit; font-size:13px;
  padding:7px 10px; border:1px solid var(--line-2); border-radius:2px;
  background:var(--surface); color:var(--ink)}
.buscador input:focus{border-color:var(--accent); outline:none;
  box-shadow:0 0 0 2px var(--accent-soft)}
/* filtros encadenados */
.filtros{display:grid; grid-template-columns:1fr 1fr; gap:8px 10px; margin-top:10px}
.filtros label{display:flex; flex-direction:column; gap:3px; font-size:10px;
  letter-spacing:.08em; text-transform:uppercase; color:var(--ink-3); font-weight:600}
.filtros label:nth-child(1), .filtros label:nth-child(2){grid-column:span 2}
.filtros select{width:100%; max-width:none; font-size:12.5px; padding:5px 7px;
  text-transform:none; letter-spacing:0; font-weight:400; color:var(--ink)}
.filtros select:disabled{opacity:.45; cursor:not-allowed}
.busca-cuenta{font-size:12px; color:var(--ink-2); margin-top:10px;
  padding-top:8px; border-top:1px solid var(--line); font-variant-numeric:tabular-nums}
.busca-cuenta b{color:var(--ink); font-weight:600}
#bLimpiar{font-size:11.5px; padding:2px 7px}

.resultados{margin-top:9px; max-height:230px; overflow-y:auto}
.resultados:empty{display:none}
.res{display:flex; align-items:baseline; gap:8px; padding:6px 7px; cursor:pointer;
  border-radius:2px; font-size:12.5px; border-bottom:1px solid var(--line)}
.res:hover, .res.marcado{background:var(--accent-soft)}
.res-pos{font-variant-numeric:tabular-nums; font-size:11px; font-weight:700; color:var(--accent);
  min-width:26px; text-align:right}
.res-id{font-family:"Cascadia Mono",Consolas,monospace; font-size:11.5px; color:var(--ink-2)}
.res-loc{color:var(--ink-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1}
.res-idx{margin-left:auto; font-variant-numeric:tabular-nums; font-size:11.5px; color:var(--ink-3)}
.res mark{background:var(--accent-soft); color:var(--accent); font-weight:600; padding:0 1px}
.res-vacio{font-size:12.5px; color:var(--ink-3); font-style:italic; padding:6px 2px}

/* cerrar la ficha */
.f-head{display:flex; align-items:center; justify-content:space-between; gap:8px}
.f-cerrar{background:none; border:none; color:var(--ink-3); cursor:pointer; font-size:17px;
  line-height:1; padding:2px 5px; border-radius:2px; font-family:inherit}
.f-cerrar:hover{background:var(--surface-2); color:var(--ink)}

#ficha .empty{color:var(--ink-3); font-size:13px; font-style:italic}
.f-top{display:flex; align-items:baseline; justify-content:space-between; gap:10px}
.f-id{font-family:"Bahnschrift",system-ui,sans-serif; font-size:22px; font-weight:600}
.f-rank{font-size:11.5px; color:var(--ink-3); letter-spacing:.06em; text-transform:uppercase}
.f-loc{font-size:13px; color:var(--ink-2); margin:2px 0 10px}
.f-motivo{font-size:12.5px; color:var(--ink-2); line-height:1.45; margin:9px 0 0;
  padding-left:9px; border-left:2px solid var(--line-2)}
.f-idx-row{display:flex; align-items:center; justify-content:space-between; gap:10px}
.f-idx{font-family:"Bahnschrift",system-ui,sans-serif; font-variant-numeric:tabular-nums}
.f-idx b{font-size:22px; font-weight:600; color:var(--accent)}
.f-idx small{font-size:10.5px; color:var(--ink-3); margin-left:3px}
.f-sec{font-family:"Bahnschrift","DIN Alternate",system-ui,sans-serif; font-weight:600;
  font-size:10px; letter-spacing:.11em; text-transform:uppercase; color:var(--accent);
  margin:15px 0 -2px; display:flex; align-items:baseline; gap:7px}
.f-sec span{font-family:inherit; font-weight:400; letter-spacing:.04em; color:var(--ink-3);
  text-transform:none; font-size:10.5px; font-style:italic}
.f-grid{display:grid; grid-template-columns:1fr 1fr; gap:9px 14px; margin-top:9px}
.f-v.sm{font-size:12.5px; line-height:1.35}
.f-nota{font-size:11px; color:var(--ink-3); font-style:italic; line-height:1.45;
  margin:8px 0 0; text-align:justify}
/* zonas: prioritarias visibles y barra con su etiqueta */
.zona-pri{border-top:1px solid var(--line); margin-top:8px; padding-top:7px}
.zona-pri.sin{font-size:11.5px; color:var(--ink-3); font-style:italic}
.zona-pri-t{font-size:10.5px; letter-spacing:.05em; text-transform:uppercase;
  color:var(--good); font-weight:600; margin-bottom:5px}
.zona-chips{display:flex; flex-wrap:wrap; gap:4px}
.zchip{border:1px solid var(--line-2); background:var(--surface-2); color:var(--ink-2);
  border-radius:3px; padding:2px 6px; font:inherit; font-size:11px; cursor:pointer;
  font-variant-numeric:tabular-nums; line-height:1.3}
.zchip:hover{border-color:var(--accent); color:var(--accent)}
.zchip small{color:var(--ink-3); margin-left:3px; font-size:9.5px}
.zchip-mas{font-size:11px; color:var(--ink-3); align-self:center}
.zona-bar-lab{font-size:9px; color:var(--ink-3); letter-spacing:.04em; margin-top:3px;
  text-transform:uppercase}
.zona-sueltas{border-style:dashed}
.zona-nota{font-size:11px; color:var(--ink-3); line-height:1.45; margin:8px 0 0;
  font-style:italic}

/* competencia por barra: veredicto legible en vez de cifras sueltas */
.sub-mun{display:block; font-size:10.5px; color:var(--ink-3); font-weight:400}
.veredicto{font-size:11.5px; padding:2px 8px; border-radius:10px; white-space:nowrap;
  font-weight:600}
.v-si{background:var(--good-bg); color:var(--good)}
.v-justo{background:var(--warn-bg); color:var(--warn)}
.v-no{background:var(--bad-bg); color:var(--bad)}
.v-nd{background:var(--surface-3); color:var(--ink-3); font-weight:400; font-style:italic}
tr.est-no td{background:color-mix(in srgb, var(--bad-bg) 45%, transparent)}
.hol{font-size:11px; cursor:help; border-bottom:1px dotted var(--ink-3)}
.h-alta{color:var(--good)} .h-media{color:var(--warn)} .h-baja{color:var(--bad)}
.h-nd{color:var(--ink-3); font-style:italic; border-bottom:0}

/* lote de grillas para la busqueda de predios */
.ctrls.lote{margin-top:9px; padding-top:9px; border-top:1px dashed var(--line-2);
  align-items:center}
.lote-lab{font-size:10.5px; letter-spacing:.07em; text-transform:uppercase;
  color:var(--ink-3); font-weight:600}
.lote-n{font-size:12px; color:var(--ink-3); font-style:italic}
.lote-n.hay{color:var(--accent); font-style:normal; font-weight:600}
.th-chk, .td-chk{width:30px; text-align:center; padding-left:8px; padding-right:2px}
.td-chk input{cursor:pointer; accent-color:var(--accent); width:14px; height:14px;
  vertical-align:middle}
.ctrls.lote .btn[disabled]{opacity:.4; cursor:not-allowed}

/* foto satelital con el contorno de la grilla superpuesto */
.sat-caja{position:relative; margin-top:9px; border-radius:4px; overflow:hidden;
  border:1px solid var(--line); line-height:0}
.sat-img{width:100%; height:auto; display:block}
.sat-svg{position:absolute; inset:0; width:100%; height:100%; pointer-events:none}
.sat-cred{position:absolute; right:5px; bottom:4px; font-size:8.5px; line-height:1.3;
  color:#fff; background:rgba(0,0,0,.42); padding:1.5px 5px; border-radius:2px;
  letter-spacing:.02em}
.f-k small{font-weight:400; text-transform:none; letter-spacing:0; opacity:.8}
.f-item{border-top:1px solid var(--line); padding-top:6px}
/* La reserva de Ley 2a condiciona pero rara vez impide, asi que avisa sin gritar.
   Solo cuando cubre casi toda la grilla pasa al tono de alerta. */
.f-item.f-aviso, .f-item.f-alerta{border-top:0; border-left:3px solid var(--warn);
  background:var(--warn-bg); padding:7px 10px; border-radius:0 5px 5px 0}
.f-item.f-alerta{border-left-color:var(--bad); background:var(--bad-bg)}
.f-k{font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--ink-3); font-weight:600}
.f-v{font-size:14.5px; font-variant-numeric:tabular-nums; margin-top:1px}
.f-v small{font-size:11px; color:var(--ink-3); font-weight:400}
.f-full{grid-column:1/-1}
.f-full .f-v{font-size:13px; line-height:1.4}
.f-links{display:flex; gap:8px; margin-top:12px; flex-wrap:wrap}
.f-links a{font-size:12px; padding:5px 10px; border:1px solid var(--line-2); border-radius:2px;
  text-decoration:none; color:var(--accent); background:var(--surface)}
.f-links a:hover{border-color:var(--accent); background:var(--accent-soft)}

.pill{display:inline-block; font-size:11px; font-weight:600; padding:2.5px 8px;
  border-radius:2px; letter-spacing:.03em; white-space:nowrap}
.p-pre{background:var(--good-bg); color:var(--good)}
.p-via{background:var(--warn-bg); color:var(--warn)}
.p-rep{background:var(--bad-bg); color:var(--bad)}
.p-des{background:var(--surface-3); color:var(--ink-3); text-decoration:line-through}

/* criterios y simulador */
.crit-intro{font-size:12.5px; color:var(--ink-2); margin:0 0 12px}
.crit{border-top:1px solid var(--line); padding:10px 0 9px; position:relative}
.crit p{margin:6px 0 0; font-size:12.5px; color:var(--ink-2); line-height:1.45}
.crit p b{color:var(--ink); font-weight:600}
.crit-n{position:absolute; top:11px; right:0; font-size:11.5px; color:var(--ink-3);
  font-variant-numeric:tabular-nums}
.crit-pie{font-size:12px; color:var(--ink-3); line-height:1.45; margin:12px 0 0;
  padding-top:10px; border-top:1px solid var(--line); font-style:italic}
/* conmutador de perfil: cambia los umbrales sin regenerar el reporte */
.perfil-row{display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:13px}
.perfil-lab{font-size:10.5px; letter-spacing:.07em; text-transform:uppercase;
  color:var(--ink-3); font-weight:600}
.selperfil{display:inline-flex; border:1px solid var(--line); border-radius:5px;
  overflow:hidden}
.selperfil button{border:0; background:var(--surface); color:var(--ink-2); cursor:pointer;
  font:inherit; font-size:12.5px; padding:6px 13px; border-right:1px solid var(--line)}
.selperfil button:last-child{border-right:0}
.selperfil button:hover{background:var(--surface-2)}
.selperfil button.on{background:var(--accent); color:#fff; font-weight:600}
.perfil-nota{font-size:11.5px; color:var(--ink-3); font-style:italic}

/* aviso del perfil: solo aparece cuando el perfil tiene una salvedad que declarar */
.aviso-p{margin-top:15px; padding:13px 16px; background:var(--warn-bg);
  border-left:3px solid var(--warn); border-radius:0 4px 4px 0; font-size:12.5px;
  color:var(--ink-2); line-height:1.55; text-align:justify}
.aviso-p b{color:var(--warn)}

/* nota metodologica: se lee como aparte, no como continuacion de la tabla */
.nota-met{margin-top:16px; padding:15px 17px; background:var(--surface-2);
  border-left:2px solid var(--accent); border-radius:0 4px 4px 0}
.nota-met h3{margin:0 0 9px; font-size:12px; letter-spacing:.07em; text-transform:uppercase;
  color:var(--accent)}
.nota-met p{margin:0 0 9px; font-size:12.5px; color:var(--ink-2); line-height:1.55;
  text-align:justify}
.nota-met p:last-child{margin-bottom:0}
.nota-met b{color:var(--ink-1)}
.nota-met-pie{font-style:italic; padding-top:9px; border-top:1px solid var(--line);
  color:var(--ink-3)!important}
/* los tres puntos de la escala, en lista para no gastar un parrafo en enumerarlos */
ul.nm-puntos{list-style:none; margin:0 0 10px; padding:0}
ul.nm-puntos li{font-size:12.5px; color:var(--ink-2); line-height:1.5; padding:2px 0 2px 13px;
  position:relative}
ul.nm-puntos li::before{content:""; position:absolute; left:0; top:9px; width:5px; height:5px;
  border-radius:50%; background:var(--accent)}
ul.nm-puntos b{color:var(--ink-1)}

/* desglose del calculo, plegado para no alargar la nota */
details.calc{margin:4px 0 11px}
details.calc summary{cursor:pointer; font-size:12.5px; color:var(--accent);
  font-weight:600; padding:4px 0; user-select:none}
details.calc summary:hover{text-decoration:underline}
.calc-cab{margin:9px 0 8px!important; font-size:12.5px}
.calc-pie{margin:8px 0 0!important; font-size:12px; color:var(--ink-3)!important;
  font-style:italic}
table.calc-t{width:100%; border-collapse:collapse; font-size:12px}
table.calc-t th{text-align:left; padding:5px 8px; border-bottom:1px solid var(--line);
  font-size:10.5px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-3);
  font-weight:600; vertical-align:bottom}
table.calc-t th small{font-weight:400; text-transform:none; letter-spacing:0;
  font-size:9.5px; opacity:.75}
table.calc-t td{padding:5px 8px; border-bottom:1px solid var(--line)}
table.calc-t .num{text-align:right; font-variant-numeric:tabular-nums}
table.calc-t .esc{color:var(--ink-3)}
table.calc-t .sinval{color:var(--ink-3); font-style:italic}
table.calc-t tfoot td{border-bottom:0; border-top:2px solid var(--line);
  text-align:right; font-weight:600; padding-top:7px}

/* lista de exclusiones: se lee de corrido, sin la vineta que corta el renglon */
ul.exclus{list-style:none; margin:0; padding:0}
ul.exclus li{border-top:1px solid var(--line); padding:9px 0 8px; font-size:12.5px;
  color:var(--ink-2); line-height:1.45}
ul.exclus li b{color:var(--ink-1)}
/* matriz de criterios: umbrales editables y distribución a la vista */
table.criterios{min-width:880px}
table.criterios th{position:static; cursor:default}
table.criterios th:hover{color:var(--ink-3)}
table.criterios td{vertical-align:middle; padding:11px}
.cr-nom{font-weight:600; font-size:13.5px}
.cr-uni{font-size:11.5px; color:var(--ink-3); font-weight:400}
.cr-efecto{display:flex; align-items:center; gap:8px; min-width:118px}
.cr-efecto .track{flex:1; height:6px; background:var(--surface-3); border-radius:1px; overflow:hidden}
.cr-efecto .fill{display:block; height:100%; background:var(--brand)}
.cr-efecto .val{font-family:"Cascadia Mono",Consolas,monospace; font-size:11.5px;
  color:var(--ink-2); font-variant-numeric:tabular-nums}
input.umbral{width:74px; text-align:right; font-family:"Cascadia Mono",Consolas,monospace;
  font-size:12.5px; padding:4px 7px; border:1px solid var(--line-2); border-radius:2px;
  background:var(--surface); color:var(--ink); font-variant-numeric:tabular-nums}
input.umbral:focus{border-color:var(--accent); outline:none;
  box-shadow:0 0 0 2px var(--accent-soft)}
input.umbral.lim{border-left:2px solid var(--bad)}
input.umbral.obj{border-left:2px solid var(--good)}
.hist{display:block}
.hist .bar{fill:var(--ink-3); opacity:.5}
.hist .bar.ok{fill:var(--good); opacity:.75}
.hist .bar.no{fill:var(--bad); opacity:.6}
.hist .marca-obj{stroke:var(--good); stroke-width:1.5}
.hist .marca-lim{stroke:var(--bad); stroke-width:1.5; stroke-dasharray:2 2}
.cr-cumplen{font-family:"Cascadia Mono",Consolas,monospace; font-size:13px; font-weight:600;
  font-variant-numeric:tabular-nums}
/* comparador de dos grillas */
.comp-sel{display:flex; align-items:flex-end; gap:12px; margin-bottom:13px; flex-wrap:wrap}
.comp-campo{display:flex; flex-direction:column; gap:4px}
.comp-campo label{font-size:10.5px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--ink-3); font-weight:600}
.comp-campo select{min-width:220px; max-width:none}
#cmpSwap{padding:5px 11px; font-size:15px; line-height:1.3}
.comp-ayuda{font-size:12px; color:var(--ink-3); margin-left:auto; max-width:36ch; line-height:1.4}
table.comp{width:100%; min-width:640px; border-collapse:collapse; font-size:13px}
table.comp th{position:static; cursor:default; padding:12px 14px}
table.comp th:hover{color:var(--ink-3)}
table.comp th.lado{font-family:"Bahnschrift","DIN Alternate",system-ui,sans-serif;
  font-size:15px; letter-spacing:.01em; text-transform:none; color:var(--ink); text-align:center}
table.comp th.lado small{display:block; font-size:11px; font-weight:400; color:var(--ink-3);
  letter-spacing:.02em; margin-top:2px}
table.comp td{padding:9px 14px; border-bottom:1px solid var(--line)}
table.comp td.var{color:var(--ink-2); width:32%}
table.comp td.var small{display:block; font-size:11px; color:var(--ink-3)}
table.comp td.dato{text-align:center; font-variant-numeric:tabular-nums;
  font-family:"Cascadia Mono","SF Mono",Consolas,monospace; width:34%; position:relative}
table.comp td.dato.gana{background:var(--good-bg); color:var(--good); font-weight:600}
table.comp td.dato.gana::after{content:"▲"; font-size:8px; margin-left:5px; vertical-align:2px}
table.comp tr.sep td{background:var(--surface-2); font-family:"Bahnschrift",system-ui,sans-serif;
  font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3);
  font-weight:600; padding:7px 14px}
table.comp tr.total td{border-top:2px solid var(--line-2); font-size:15px}
table.comp td.texto{font-family:inherit; font-size:12px; line-height:1.4; text-align:center}
.comp-vs{display:flex; align-items:center; justify-content:center; gap:5px}
.comp-bar{height:5px; background:var(--surface-3); border-radius:1px; overflow:hidden;
  margin-top:5px; width:100%}
.comp-bar span{display:block; height:100%; background:var(--brand)}
.comp-empate{color:var(--ink-3)}

.crit-pie-row{display:flex; gap:18px; align-items:flex-start; margin-top:13px; flex-wrap:wrap}
.crit-nota{flex:1; min-width:340px; font-size:12.5px; color:var(--ink-2); line-height:1.5; margin:0}
.crit-nota b{color:var(--ink)}

/* reparto apilado */
.apilada{display:flex; height:26px; border-radius:2px; overflow:hidden; margin-bottom:9px}
.apilada span{display:flex; align-items:center; justify-content:center; font-size:11px;
  font-weight:600; color:#fff; min-width:0}
.apilada-leg{display:flex; flex-wrap:wrap; gap:11px; font-size:12px; color:var(--ink-2)}
.apilada-leg span{display:flex; align-items:center; gap:6px}
.apilada-leg i{width:9px; height:9px; border-radius:2px; display:block}
/* las dos varas, una al lado de la otra para que se vea que no son lo mismo */
.dosvaras{display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:12px}
.dosvaras h4{margin:0 0 7px; font-size:11px; letter-spacing:.04em; text-transform:uppercase;
  color:var(--ink-2); font-weight:600; line-height:1.35}
.dosvaras h4 small{display:block; font-weight:400; text-transform:none; letter-spacing:0;
  font-size:10.5px; color:var(--ink-3); font-style:italic}
@media (max-width:720px){.dosvaras{grid-template-columns:1fr}}

.cd-row{display:grid; grid-template-columns:74px 1fr 34px; align-items:center; gap:10px;
  font-size:12.5px; padding:2.5px 0}
.cd-row .t{background:var(--surface-3); height:8px; border-radius:1px; overflow:hidden}
.cd-row .t span{display:block; height:100%; background:var(--brand)}
.cd-row .n{text-align:right; font-variant-numeric:tabular-nums; font-size:12px}

/* zonas */
.zonas{display:grid; grid-template-columns:repeat(auto-fit,minmax(238px,1fr)); gap:12px}
.zona{background:var(--surface); border:1px solid var(--line); border-radius:3px;
  padding:14px 15px 12px; box-shadow:var(--shadow)}
.zona-top{display:flex; justify-content:space-between; align-items:baseline; gap:8px}
.zona-id{font-family:"Bahnschrift",system-ui,sans-serif; font-weight:600; font-size:17px;
  letter-spacing:.05em; color:var(--accent)}
.zona-mwp{font-family:"Bahnschrift",system-ui,sans-serif; font-weight:600; font-size:19px;
  font-variant-numeric:tabular-nums}
.zona-mwp small{font-size:11px; color:var(--ink-3); font-weight:400}
.zona-dep{font-size:12.5px; color:var(--ink-2); margin:1px 0 9px}
.zona-datos{display:grid; grid-template-columns:1fr 1fr; gap:3px 10px; font-size:12px;
  color:var(--ink-3); border-top:1px solid var(--line); padding-top:8px}
.zona-datos b{color:var(--ink); font-weight:600; font-variant-numeric:tabular-nums}
.zona-op{font-size:11px; color:var(--ink-3); margin-top:8px; overflow:hidden;
  text-overflow:ellipsis; white-space:nowrap}
.zona-bar{height:3px; background:var(--surface-3); margin-top:9px; border-radius:1px; overflow:hidden}
.zona-bar span{display:block; height:100%; background:var(--brand)}
.vacio{color:var(--ink-3); font-style:italic; font-size:13px}

.cols2{display:grid; grid-template-columns:1fr 1fr; gap:22px}
@media(max-width:820px){.cols2{grid-template-columns:1fr}}
.bar-row{display:grid; grid-template-columns:1fr 90px 30px; align-items:center; gap:11px;
  font-size:13px; padding:3.5px 0}
.bar-lab{overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--ink-2)}
.bar-track{background:var(--surface-3); height:7px; border-radius:1px; overflow:hidden}
.bar-fill{display:block; height:100%; background:var(--brand)}
.bar-fill.alt{background:var(--ink-3)}
.bar-num{text-align:right; font-variant-numeric:tabular-nums; font-size:12.5px}
.bar-rest .bar-lab{color:var(--ink-3); font-style:italic}

.ctrls{display:flex; flex-wrap:wrap; gap:9px; align-items:center; margin-bottom:13px}
.chip{font-size:12.5px; padding:5px 12px; border:1px solid var(--line-2); background:var(--surface);
  color:var(--ink-2); border-radius:2px; cursor:pointer; font-family:inherit}
.chip:hover{border-color:var(--accent); color:var(--accent)}
.chip[aria-pressed="true"]{background:var(--accent); border-color:var(--accent); color:var(--on-accent)}
select{font-family:inherit; font-size:13px; padding:5px 9px; border:1px solid var(--line-2);
  background:var(--surface); color:var(--ink); border-radius:2px; max-width:230px}
.count{margin-left:auto; font-size:12.5px; color:var(--ink-3); font-variant-numeric:tabular-nums}
.btn{font-size:12.5px; padding:5px 12px; border:1px solid var(--accent); background:var(--accent);
  color:var(--on-accent); border-radius:2px; cursor:pointer; font-family:inherit; font-weight:600}
.btn:hover{background:var(--accent-2); border-color:var(--accent-2)}
.btn.ghost{background:var(--surface); color:var(--accent)}
.btn.ghost:hover{background:var(--accent-soft)}

.tablebox{overflow-x:auto; border:1px solid var(--line); border-radius:3px; background:var(--surface);
  box-shadow:var(--shadow)}
/* La tabla larga se recorta a unas diez filas y el resto se ve bajando dentro de ella.
   La cabecera ya es sticky, así que al desplazarse sigue diciendo qué es cada columna. */
.tabla-scroll{max-height:436px; overflow-y:auto}
table{border-collapse:collapse; width:100%; font-size:13px; min-width:1020px}
th{text-align:left; font-family:"Bahnschrift","DIN Alternate",system-ui,sans-serif; font-weight:600;
  font-size:11px; letter-spacing:.07em; text-transform:uppercase; color:var(--ink-3);
  padding:10px 11px; border-bottom:1px solid var(--line-2); background:var(--surface-2);
  position:sticky; top:0; cursor:pointer; white-space:nowrap; user-select:none}
th:hover{color:var(--accent)}
th[data-dir]::after{content:" ↑"; color:var(--accent)}
th[data-dir="desc"]::after{content:" ↓"}
td{padding:8px 11px; border-bottom:1px solid var(--line); vertical-align:middle}
tbody tr{cursor:pointer}
tbody tr:hover{background:var(--surface-2)}
tbody tr.sel{background:var(--accent-soft)}
td.num{text-align:right; font-variant-numeric:tabular-nums;
  font-family:"Cascadia Mono","SF Mono",Consolas,monospace; font-size:12px}
td.id{font-family:"Cascadia Mono",Consolas,monospace; font-size:12px; color:var(--ink-2)}
.radcell{display:flex; align-items:center; gap:7px; justify-content:flex-end}
.radbar{width:32px; height:6px; border-radius:1px; flex:none}
.trunc{max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:block}
.trunc.motivo{max-width:250px; color:var(--ink-2); font-size:12.5px}
.zt{font-family:"Cascadia Mono",Consolas,monospace; font-size:11.5px; color:var(--accent)}
.idx{display:flex; align-items:center; gap:7px; justify-content:flex-end}
.idx-t{width:38px; height:6px; background:var(--surface-3); border-radius:1px; overflow:hidden; flex:none}
.idx-t span{display:block; height:100%; background:var(--brand)}

table.proc{min-width:760px}
table.proc th{position:static; cursor:default}
table.proc th:hover{color:var(--ink-3)}
table.proc td{font-size:12.5px; color:var(--ink-2); vertical-align:top; line-height:1.45}
table.proc td b{color:var(--ink); font-weight:600}
table.proc .mono{font-size:11.5px; background:var(--surface-2); padding:1px 4px; border-radius:2px}
.warn-cell{color:var(--warn)!important; font-weight:600}
th.tr{text-align:right}
td.tr{text-align:right}
#tbarras td.num{font-family:"Cascadia Mono",Consolas,monospace; font-variant-numeric:tabular-nums}
#tbarras tbody tr:hover{background:var(--surface-2)}
#tbarras tr.apretada{background:var(--bad-bg)}
#tbarras tr.apretada:hover{background:var(--bad-bg); filter:brightness(.97)}
#tbarras td.pend{color:var(--ink-3); font-style:italic; font-size:11px}
.flag{display:inline-block; font-size:10px; font-weight:600; letter-spacing:.04em;
  text-transform:uppercase; color:var(--bad); border:1px solid var(--bad);
  border-radius:2px; padding:0 5px; margin-left:6px; vertical-align:1px}
.aviso{font-size:13px; color:var(--ink-2); line-height:1.55; margin:13px 0 0;
  padding:12px 15px; background:var(--warn-bg); border-left:2px solid var(--warn); border-radius:2px}
.aviso b{color:var(--ink)}

.gaps{display:grid; grid-template-columns:repeat(auto-fit,minmax(262px,1fr)); gap:13px}
.gap{background:var(--surface); border:1px solid var(--line); border-left:2px solid var(--warn);
  border-radius:3px; padding:14px 16px}
.gap.done{border-left-color:var(--good)}
.gap-t{font-family:"Bahnschrift",system-ui,sans-serif; font-weight:600; font-size:15px; margin-bottom:5px}
.gap-s{font-size:10.5px; letter-spacing:.09em; text-transform:uppercase; font-weight:600;
  color:var(--warn); margin-bottom:7px}
.gap.done .gap-s{color:var(--good)}
.gap p{margin:0; font-size:13px; color:var(--ink-2); line-height:1.5}

footer{border-top:1px solid var(--line); padding-top:16px; font-size:12.5px; color:var(--ink-3)}
footer b{color:var(--ink-2); font-weight:600}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<header>
  <div class="head">
    <div>
      <div class="brand">
        <!-- Isotipo de Métodos Mixtos redibujado en vectorial: siete barras de altura
             creciente, con extremos redondeados y alineadas por su eje central. -->
        <svg class="brand-mark" viewBox="0 0 92 100" aria-hidden="true">
          <g fill="var(--brand)">
            <rect x="0"  y="27.0" width="8.4" height="46.0" rx="4.2"></rect>
            <rect x="14" y="21.5" width="8.4" height="57.0" rx="4.2"></rect>
            <rect x="28" y="16.0" width="8.4" height="68.0" rx="4.2"></rect>
            <rect x="42" y="11.0" width="8.4" height="78.0" rx="4.2"></rect>
            <rect x="56" y="6.0"  width="8.4" height="88.0" rx="4.2"></rect>
            <rect x="70" y="2.5"  width="8.4" height="95.0" rx="4.2"></rect>
            <rect x="83.6" y="0"  width="8.4" height="100"  rx="4.2"></rect>
          </g>
        </svg>
        <span class="brand-text">
          <span class="brand-name">Métodos Mixtos</span>
          <span class="brand-sub">Consultores</span>
        </span>
      </div>
      <div class="eyebrow">Prospectos solares · <span id="eyebrow-perfil"></span></div>
      <h1>Priorización de áreas para generación solar en suelo</h1>
      <p class="sub">Grillas de 25&nbsp;km² seleccionadas por su afinidad con las zonas donde
      ya opera generación solar en Colombia. Cada una se evalúa contra criterios ponderados y
      se ordena por un índice de aptitud de 0 a 100. El resultado define la lista con la que
      arranca la identificación de lotes.</p>
    </div>
  </div>
</header>

<div class="wrap">

  <section>
    <div class="sec-head"><h2>Tipos de clasificación</h2>
      <span class="sec-note">Cuatro niveles en los que puede caer una grilla.</span></div>
    <div class="cols2">
      <div class="card">
        <h3>Cómo se clasifica</h3>
        <p class="crit-intro">Cada grilla lleva escrito su motivo concreto, en la ficha y en
        la tabla.</p>
        <div class="crit"><span class="pill p-des">Excluida</span>
          <p>Tiene una o más restricciones que impiden el desarrollo.</p>
          <div class="crit-n" id="c-des">__DES__</div></div>
        <div class="crit"><span class="pill p-rep">Condicionada</span>
          <p>Algún criterio queda <b>fuera de su límite</b>. El índice puede
          ser alto, pero un solo criterio en rojo exige gestión adicional y no se deja
          promediar con los demás.</p>
          <div class="crit-n" id="c-rep">__REP__</div></div>
        <div class="crit"><span class="pill p-pre">Prioritaria</span>
          <p><b>Ningún criterio en rojo</b> y un índice de <b>__UMBRAL__ o más</b>. No se le
          pide alcanzar el objetivo en todos los criterios, que es una vara mucho más alta:
          se le pide no tener problemas y sumar buen puntaje.</p>
          <div class="crit-n" id="c-pre">__PRE__</div></div>
        <div class="crit"><span class="pill p-via">Elegible</span>
          <p>Ningún criterio en rojo tampoco, pero el índice queda por debajo del corte.
          Sigue en juego y puede subir si cambian los umbrales o llega mejor información.</p>
          <div class="crit-n" id="c-via">__VIA__</div></div>
      </div>
      <div class="card">
        <h3>Criterios para excluir una grilla</h3>
        <p class="crit-intro">Las exclusiones se aplican antes de puntuar nada.</p>
        <ul class="exclus">
          <li><b>Figura jurídica.</b> Parque nacional, resguardo indígena, consejo comunitario
            o área protegida del RUNAP. Cualquiera basta.</li>
          <li><b>Altitud sobre 3.000 m.</b> Páramo, donde la Ley 1930 de 2018 prohíbe las
            actividades de alto impacto.</li>
          <li><b>Cultivos de coca.</b> Por riesgo operativo. Ninguna planta de escala utility
            del país está en una grilla con coca.</li>
          <li><b>Conflicto armado.</b> Municipio con tres o más acciones bélicas desde 2022
            y al menos tres por cada mil km². Ninguna de las diez plantas de 50&nbsp;MW o más
            del país está en un municipio así.</li>
          <li><b>Reserva de Ley 2ª.</b> Solo si cubre el 90% o más de la grilla. Por debajo
            condiciona pero no impide, porque el lote se ubica fuera del polígono.</li>
        </ul>
      </div>
    </div>
  </section>

  <section>
    <div class="sec-head"><h2>Matriz de criterios</h2>
      <span class="sec-note">Aquí se decide todo lo demás. Cambia un umbral y las 100 grillas se reclasifican al instante, arriba y abajo.</span></div>
    <div class="perfil-row">
      <span class="perfil-lab">Tamaño de proyecto</span>
      <div class="selperfil" id="selperfil"></div>
      <span class="perfil-nota" id="perfil-nota"></span>
    </div>
    <div class="tablebox">
      <table class="criterios">
        <thead><tr>
          <th>Criterio de aptitud</th>
          <th title="d de Cohen: cuánto separa esta variable las grillas con planta de escala utility del resto">Efecto medido</th>
          <th class="tr">Objetivo</th>
          <th class="tr">Límite</th>
          <th>Distribución de las 100 grillas</th>
          <th class="tr">Cumplen</th>
        </tr></thead>
        <tbody id="tcrit"></tbody>
      </table>
    </div>
    <div class="crit-pie-row">
      <p class="crit-nota">El <b>efecto medido</b> es cuánto separa esa variable a las grillas
      con planta del resto, en desviaciones estándar. Cuanto más separa, más pesa: el peso es
      el efecto dividido por la suma de los seis. Se compara contra las 7.239 grillas que están
      dentro del radio de una subestación, no contra el país entero, porque medido contra todo
      el territorio la cercanía a la red se contaba dos veces y su efecto subía de 0,52 a 0,79.
      Quedaron fuera variables de mayor efecto, como la privación relativa o la densidad de
      población, porque describen el entorno de las plantas y no la aptitud del terreno:
      usarlas como criterio sería replicar una decisión de mercado. Van en la ficha de cada
      grilla, como caracterización.</p>
      <button class="btn ghost" id="reset">Restablecer umbrales</button>
    </div>

    <div id="aviso-perfil"></div>

    <div class="nota-met">
      <h3>Nota metodológica</h3>
      <p>Los umbrales no se pusieron a criterio propio. Se leen de las <b>__NREF__ grillas del
      país que ya contienen una planta de 10&nbsp;MW o más</b>, que es la escala que se
      prospecta:</p>
      <ul class="nm-puntos">
        <li><b>Límite</b>, vale 0. Su percentil 90: más allá casi nadie ha construido.</li>
        <li><b>Objetivo</b>, vale 70. Su mediana: aquí está la mitad de lo construido.</li>
        <li><b>Tope</b>, vale 100. Su percentil 10: el decil mejor de lo existente.</li>
      </ul>
      <p>La nota de cada criterio se interpola entre esos tres puntos, y el índice es la suma
      de las seis notas por su peso. <b>No es un cumple o no cumple</b>: una grilla con la
      subestación a 15&nbsp;km saca 49 sobre 100, no cero ni todo. Y como los tres puntos no
      dependen de las grillas que se evalúen, <b>un índice de 78 significa lo mismo en
      cualquier corrida</b>.</p>
      <p>Lo que es convención y no dato: los tres <i>puntos</i> salen de las plantas, pero los
      <i>valores</i> 0, 70 y 100 son una escala elegida. Se probó puntuar por percentil directo,
      sin ningún valor elegido, y el orden de las grillas salía prácticamente igual.</p>
      <details class="calc">
        <summary>Ver el cálculo completo de una grilla</summary>
        <div id="calc-ejemplo"></div>
      </details>
      <p class="nota-met-pie">El método describe dónde se ha construido, no dónde conviene
      construir. Si el sector se equivocó de forma sistemática, el índice reproduce el error.
      A cambio, se puede auditar y recalcular cuando entren plantas nuevas.</p>
    </div>
  </section>

  <div class="kpis">
    <div class="kpi"><div class="kpi-lab">Grillas</div><div class="kpi-val">__N__</div>
      <div class="kpi-note">de 7.168 candidatas puntuadas</div></div>
    <div class="kpi g"><div class="kpi-lab">Prioritarias</div><div class="kpi-val" id="k-pre">__PRE__</div>
      <div class="kpi-note">lista corta, índice __UMBRAL__ o más</div></div>
    <div class="kpi w"><div class="kpi-lab">Elegibles</div><div class="kpi-val" id="k-via">__VIA__</div>
      <div class="kpi-note">en juego, por debajo del corte</div></div>
    <div class="kpi b"><div class="kpi-lab">Condicionadas</div><div class="kpi-val" id="k-rep">__REP__</div>
      <div class="kpi-note">exigen gestión adicional</div></div>
    <div class="kpi n"><div class="kpi-lab">Excluidas</div><div class="kpi-val" id="k-des">__DES__</div>
      <div class="kpi-note">restricción que impide el desarrollo</div></div>
    <div class="kpi"><div class="kpi-lab">Zonas</div><div class="kpi-val">__NZONAS__</div>
      <div class="kpi-note">agrupaciones de trabajo</div></div>
  </div>

  <section>
    <div class="sec-head"><h2>Resultado de la clasificación</h2>
      <span class="sec-note">Cómo queda repartida la cartera con los umbrales actuales.</span></div>
    <div class="cols2">
      <div class="card">
        <h3>Reparto</h3>
        <div class="apilada" id="apilada"></div>
        <div class="apilada-leg" id="apilada-leg"></div>
      </div>
      <div class="card">
        <h3>Las dos varas, que no son la misma</h3>
        <p class="crit-intro">Cada criterio tiene un <b>límite</b> y un <b>objetivo</b>, y
        conviene no confundirlos. Estar dentro del límite es no tener nada en rojo. Alcanzar
        el objetivo es igualar a la planta mediana ya construida, que es bastante más difícil.
        Lo que decide la clasificación es el primero; el segundo solo informa.</p>
        <div class="dosvaras">
          <div>
            <h4>Criterios fuera de límite <small>decide la clase</small></h4>
            <div id="rojo-dist"></div>
          </div>
          <div>
            <h4>Criterios que alcanzan el objetivo <small>solo informa</small></h4>
            <div id="cumplen-dist"></div>
          </div>
        </div>
        <p class="crit-pie">Por eso una grilla puede ser Prioritaria sin alcanzar ningún
        objetivo: le basta con no tener nada en rojo y sumar 70 de índice. Y una con cuatro
        objetivos alcanzados cae a Condicionada si el quinto criterio se le fue del límite.</p>
      </div>
    </div>
  </section>

  <section>
    <div class="sec-head"><h2>Las 100 grillas</h2>
      <span class="sec-note">Ordenadas de más a menos apta. Se ven las diez primeras; baja
      con la rueda dentro de la tabla para el resto. Los filtros afectan también al mapa.</span></div>
    <div class="ctrls">
      <button class="chip" data-f="todas" aria-pressed="true">Todas</button>
      <button class="chip" data-f="Prioritaria" aria-pressed="false">Prioritarias</button>
      <button class="chip" data-f="Elegible" aria-pressed="false">Elegibles</button>
      <button class="chip" data-f="Condicionada" aria-pressed="false">Condicionadas</button>
      <button class="chip" data-f="Excluida" aria-pressed="false">Excluidas</button>
      <select id="fdep"><option value="">Todos los departamentos</option></select>
      <select id="fop"><option value="">Todos los operadores</option></select>
      <select id="fzona"><option value="">Todas las zonas</option></select>
      <button class="btn ghost" id="exportar">Descargar selección en CSV</button>
      <span class="count" id="count"></span>
    </div>
    <div class="ctrls lote">
      <span class="lote-lab">Lote para búsqueda de predios</span>
      <span class="lote-n" id="loteN">ninguna marcada</span>
      <button class="btn ghost" id="loteVisibles">Marcar las visibles</button>
      <button class="btn ghost" id="loteTop10">Marcar las 10 primeras</button>
      <button class="btn ghost" id="loteLimpiar">Quitar marcas</button>
      <button class="btn" id="loteGeojson">GeoJSON</button>
      <button class="btn" id="loteCsv">CSV</button>
    </div>
    <div class="tablebox tabla-scroll">
      <table>
        <thead><tr>
          <th class="th-chk" title="Marcar para el lote de búsqueda de predios">✓</th>
          <th data-k="ranking" data-t="n">#</th>
          <th data-k="id">Grilla</th>
          <th data-k="zona">Zona</th>
          <th data-k="clase">Clasificación</th>
          <th data-k="motivo">Motivo</th>
          <th data-k="depto">Departamento</th>
          <th data-k="indice" data-t="n" title="Índice ponderado de aptitud, de 0 a 100">Índice</th>
          <th data-k="cumple" data-t="n" title="Criterios de aptitud que alcanzan su objetivo">Cumple</th>
          <th data-k="pvout" data-t="n">Producción FV</th>
          <th data-k="cobertura" data-t="n">Cobertura apta</th>
          <th data-k="mwp" data-t="n">MWp</th>
          <th data-k="pendiente" data-t="n">Pendiente</th>
          <th data-k="dist_sub" data-t="n">A subestación</th>
          <th data-k="via" data-t="n">A vía</th>
          <th data-k="operador">Operador</th>
        </tr></thead>
        <tbody id="tb"></tbody>
      </table>
    </div>
  </section>

  <section>
    <div class="sec-head"><h2>Dónde están</h2>
      <span class="sec-note">Toca un punto para ver su ficha.</span></div>
    <div class="ctrls" style="margin-bottom:11px">
      <span class="sec-note" style="margin-right:2px">Colorear por</span>
      <button class="chip" data-color="rad" aria-pressed="true">Recurso solar</button>
      <button class="chip" data-color="clase" aria-pressed="false">Clasificación</button>
      <button class="chip" data-color="zona" aria-pressed="false">Zona</button>
      <span class="sec-note" style="margin-left:14px; margin-right:2px">Red</span>
      <button class="chip" data-capa="subs" aria-pressed="false">Subestaciones</button>
      <button class="chip" data-capa="lineas" aria-pressed="false">Líneas</button>
    </div>
    <div class="ctrls" style="margin-bottom:11px">
      <span class="sec-note" style="margin-right:2px">Límites</span>
      <button class="chip" data-div="departamento" aria-pressed="false">Departamento</button>
      <button class="chip" data-div="municipio" aria-pressed="false">Municipio</button>
      <button class="chip" data-div="vereda" aria-pressed="false">Vereda</button>
      <button class="chip" data-div="grilla" aria-pressed="false">Grilla de 5 km</button>
      <span class="comp-ayuda" style="margin-left:auto">Municipio y vereda se distinguen mejor con el mapa acercado.</span>
    </div>
    <div class="mapgrid">
      <div class="mapbox">
        <div class="mapa-wrap">
          <svg class="mapa" id="svgmapa" viewBox="__VIEWBOX__" role="img"
               aria-label="Mapa de Colombia con las grillas candidatas">
            <g id="vp">
              <path class="vecinos" d="__VECINOS__" vector-effect="non-scaling-stroke"></path>
              <path class="pais" d="__PAIS__" vector-effect="non-scaling-stroke"></path>
              <g id="deps"></g>
              <g id="div-departamento" class="divs"></g>
              <g id="div-municipio" class="divs"></g>
              <g id="div-vereda" class="divs"></g>
              <g id="div-grilla" class="divs"></g>
              <g id="lineas"></g>
              <g id="subs"></g>
              <g id="pts"></g>
            </g>
          </svg>
          <div class="mapa-zoom">
            <button id="zIn"  title="Acercar">+</button>
            <button id="zOut" title="Alejar">−</button>
            <button id="zRes" title="Volver a la vista completa">⤢</button>
          </div>
          <div class="mapa-nivel" id="zNivel">1,0×</div>
        </div>
        <p class="mapa-ayuda">Rueda del ratón para acercar, arrastra para desplazar,
        doble clic para volver.</p>
      </div>
      <div class="side">
        <div class="card buscador">
          <div class="f-head"><h3 style="margin:0">Buscar grilla</h3>
            <button class="f-cerrar" id="bLimpiar" title="Limpiar todos los filtros">Limpiar</button></div>
          <input type="search" id="busca" autocomplete="off" spellcheck="false"
                 placeholder="Código, subestación, operador…" aria-label="Buscar por texto">
          <div class="filtros">
            <label>Departamento<select id="fbDepto"></select></label>
            <label>Municipio<select id="fbMpio"></select></label>
            <label>Vereda<select id="fbVer"></select></label>
            <label>Clasificación<select id="fbClase"></select></label>
            <label>Zona<select id="fbZona"></select></label>
          </div>
          <div class="busca-cuenta" id="bCuenta"></div>
          <div id="resultados" class="resultados"></div>
        </div>
        <div class="card" id="ficha"><h3>Ficha de la grilla</h3>
          <p class="empty">Búscala arriba, o toca un punto del mapa o una fila de la tabla.</p></div>
        <div class="card" id="leyenda"></div>
      </div>
    </div>
  </section>

  <section>
    <div class="sec-head"><h2>Zonas de prospección</h2>
      <span class="sec-note">Grillas a menos de 20 km entre sí. Cien puntos sueltos no son una
      hoja de ruta; estas zonas sí, porque la salida de campo, el trámite municipal y la
      conversación con el operador se hacen por zona.</span></div>
    <div class="zonas" id="zonasCards"></div>
    <div class="cols2" style="margin-top:18px">
      <div class="card"><h3>Concentración por departamento</h3>
        <p class="crit-intro">Dónde está la cartera. Un departamento con muchas grillas
        permite repartir el costo de la prospección; también concentra el riesgo regulatorio
        y el de orden público.</p>
        __BARRAS_DEP__</div>
      <div class="card"><h3>Concentración por operador de red</h3>
        <p class="crit-intro">Con quién hay que negociar la conexión. Si la mitad de la
        cartera cuelga de un solo operador, su respuesta condiciona medio portafolio.</p>
        __BARRAS_OP__</div>
    </div>
  </section>


  <section>
    <div class="sec-head"><h2>Comparar dos grillas</h2>
      <span class="sec-note">Enfrenta cualquier par y mira dónde gana cada una.</span></div>
    <div class="comp-sel">
      <div class="comp-campo"><label for="cmpA">Grilla A</label><select id="cmpA"></select></div>
      <button class="btn ghost" id="cmpSwap" title="Intercambiar">⇄</button>
      <div class="comp-campo"><label for="cmpB">Grilla B</label><select id="cmpB"></select></div>
      <span class="comp-ayuda">También puedes fijar una grilla desde el mapa o la tabla con el botón de la ficha.</span>
    </div>
    <div class="tablebox"><div id="comparador"></div></div>
  </section>

  <section>
    <div class="sec-head"><h2>Competencia por el punto de conexión</h2>
      <span class="sec-note">¿Cabe el proyecto en esa barra, y con quién habría que competir
      por el cupo?</span></div>
    <p class="crit-intro">La columna que decide es <b>¿cabe?</b>: cuántos proyectos de
    <b><span id="barrasProy">20</span>&nbsp;MW</b>, que es el tamaño del perfil activo, admite
    la barra antes de llenarse. Si caben menos de los que la apuntan, esas candidatas
    compiten entre sí por el mismo cupo. Cambia el perfil arriba y la respuesta cambia.</p>
    <div class="tablebox">
      <table class="proc" id="tbarras">
        <thead><tr>
          <th>Subestación</th>
          <th class="tr">kV</th>
          <th class="tr" title="Capacidad de la barra según la UPME">MW libres</th>
          <th>¿Cabe?</th>
          <th class="tr">Candidatas</th>
          <th class="tr" title="Distancia media de esas candidatas a la subestación">Km</th>
          <th title="Qué tan flexible es el patio para colgar una conexión nueva">Configuración</th>
        </tr></thead>
        <tbody id="tbb"></tbody>
      </table>
    </div>
    <div class="cols2" style="margin-top:14px">
      <div class="card">
        <h3>Qué es la configuración de barras</h3>
        <p class="crit-intro">Es el esquema eléctrico del patio de la subestación. Determina
        cuánta holgura hay para colgar una conexión nueva y si hacerlo obliga a dejar sin
        servicio a las que ya están.</p>
        <ul class="exclus">
          <li><b>Holgura alta.</b> Interruptor y medio, o en anillo. La energía llega por más
            de un camino y se pueden añadir salidas sin cortar el servicio del resto.</li>
          <li><b>Holgura media.</b> Doble barra, o principal con transferencia. Hay una barra
            de reserva para mover una salida mientras se le hace mantenimiento.</li>
          <li><b>Holgura baja.</b> Barra sencilla: una sola barra y un interruptor por salida.
            Ampliarla suele exigir obra en el patio, y una falla afecta a todas.</li>
        </ul>
      </div>
      <div class="card">
        <h3>De dónde sale el cupo, y qué no dice</h3>
        <p class="crit-intro">Los megavatios libres salen de los catorce informes de capacidad
        por barra de la UPME, ciclo 2023-2024, publicados por la Circular 077 de 2024, con la
        capacidad de cada barra año por año hasta 2037. La tabla usa la del año en curso.</p>
        <p class="crit-pie"><b>Es el techo físico del nodo, no el cupo libre de hoy.</b> Mide
        cuánta generación admite la barra según los límites de red, antes de descontar lo
        asignado después en el propio ciclo, y una barra puede pasar de 0,2&nbsp;MW un año a 80
        al siguiente cuando entra una obra de expansión. Sirve para descartar nodos saturados
        y ordenar candidatas; para comprometer una conexión hay que radicar el estudio ante el
        operador de red. El régimen además cambió: la Resolución CREG 101&nbsp;094 de 2025
        movió esta información al Repositorio de Transportadores de la Ventanilla Única, que
        exige registro, así que el ciclo 2023-2024 es el último dato abierto.</p>
      </div>
    </div>
  </section>


  <section>
    <div class="sec-head"><h2>De dónde sale cada dato</h2>
      <span class="sec-note">Con su fecha, porque no todos están igual de frescos.</span></div>
    <div class="tablebox">
      <table class="proc">
        <thead><tr><th>Dato</th><th>Fuente</th><th>Cómo se asigna a la grilla</th><th>Vigencia</th></tr></thead>
        <tbody>
          <tr><td><b>Operador de red</b></td>
            <td>Capa <span class="mono">Subestaciones.geojson</span>, 499 subestaciones del SIN, bucket <span class="mono">geoinfo</span></td>
            <td>Subestación más cercana al centroide. Se usa <span class="mono">nombre_organizacion</span>, y donde falta se toma <span class="mono">nombre_propietario</span></td>
            <td class="warn-cell">Mezcla de 2017 a 2021, y 159 registros sin fecha</td></tr>
          <tr><td><b>Tensión y barras</b></td>
            <td>Misma capa, campos <span class="mono">tension</span> y <span class="mono">configuracion</span></td>
            <td>De la misma subestación más cercana</td>
            <td class="warn-cell">Igual que arriba</td></tr>
          <tr><td><b>Recurso solar</b></td>
            <td>Global Solar Atlas, siete capas ya agregadas al panel</td>
            <td>Media de la grilla, sin valores faltantes</td>
            <td>Serie climatológica de largo plazo</td></tr>
          <tr><td><b>Figuras jurídicas</b></td>
            <td>RUNAP, Parques Nacionales, resguardos indígenas y consejos comunitarios</td>
            <td>Marca de sí o no por intersección, no porcentaje de área</td>
            <td>RUNAP con corte de febrero de 2026</td></tr>
          <tr><td><b>Conflicto armado</b></td>
            <td>SIEVCAC del Centro Nacional de Memoria Histórica, datos.gov.co</td>
            <td>Hechos del municipio desde 2022, en conteo y por mil km²</td>
            <td class="warn-cell">La fuente geocodifica al municipio, no al sitio</td></tr>
          <tr><td><b>Reserva de Ley 2ª</b></td>
            <td>FeatureServer del MinAmbiente, SIAC datos abiertos</td>
            <td>Superficie de la grilla dentro de la reserva, en hectáreas y porcentaje</td>
            <td>Se cruza en vivo contra la geometría de cada grilla</td></tr>
          <tr><td><b>Distancia a vía</b></td>
            <td>OpenStreetMap vía Overpass</td>
            <td>Del centroide al tramo más cercano, en dos jerarquías</td>
            <td>Consulta en vivo</td></tr>
          <tr><td><b>Pendiente y elevación</b></td>
            <td>NASADEM, ya agregado al panel</td>
            <td>Media de la grilla, más su desviación como medida de rugosidad</td>
            <td>Estable</td></tr>
          <tr><td><b>Cobertura del suelo</b></td>
            <td>ESRI Sentinel-2 Land Cover, nueve clases</td>
            <td>Porcentaje de cada clase, ponderado por su aptitud y normalizado sobre lo
              observado, descontando lo que tapó la nube</td>
            <td>Anual</td></tr>
          <tr><td><b>Capacidad en barra</b></td>
            <td>Catorce informes de capacidad por barra de la UPME, Circular 077 de 2024</td>
            <td>Se cruza la subestación asignada por nombre base, tomando la barra de alta o de
              media tensión según el perfil de proyecto</td>
            <td class="warn-cell">Ciclo 2023-2024, el último abierto. Cubre 67% de las
              subestaciones del SIN</td></tr>
          <tr><td><b>Privación relativa</b></td>
            <td>Global Gridded Relative Deprivation Index de SEDAC, versión 1</td>
            <td>Media de la grilla, escala 0 a 100 donde 100 es la mayor privación</td>
            <td class="warn-cell">Periodo 2010-2020, índice global no comparable con el IPM
              del DANE</td></tr>
          <tr><td><b>Imagen satelital</b></td>
            <td>Esri World Imagery, Maxar y Earthstar Geographics</td>
            <td>Un recuadro por grilla con 15% de margen, a unos 7&nbsp;m por píxel, con el
              contorno real dibujado encima</td>
            <td>Cada foto muestra su fecha de captura</td></tr>
          <tr><td><b>Municipio y vereda</b></td>
            <td>Base veredal del IGAC</td>
            <td>Cruce espacial del centroide; el conflicto se une por código DANE y no por
              nombre, porque el mismo municipio aparece escrito de varias formas</td>
            <td>2024</td></tr>
          <tr><td><b>Potencial en MWp</b></td>
            <td>Cálculo propio</td>
            <td>Hectáreas de cobertura apta, ajustadas por pendiente, a razón de 1,5&nbsp;ha por MWp</td>
            <td>Derivado</td></tr>
        </tbody>
      </table>
    </div>
    <p class="aviso"><b>Dos advertencias.</b> La capa de subestaciones es un consolidado con
    vigencias entre 2017 y 2021 y un tercio de los registros sin fecha, así que el operador
    conviene confirmarlo antes de cualquier gestión comercial. Y el potencial en megavatios es
    el techo físico de la superficie apta, no una cartera de proyectos: sirve para dimensionar
    la oportunidad de una zona y compararla con otra, no para prometer capacidad.</p>
  </section>


  <footer>
    <b>Cómo leer esto.</b> El puntaje mide parecido con las zonas donde ya hay generación solar,
    no calidad del recurso. Las plantas existentes están en el percentil 68 de recurso solar del
    país pero en el 97 de densidad poblacional, así que el ranking premia sobre todo accesibilidad
    e infraestructura. La clasificación en tres niveles sí aplica criterios físicos y jurídicos.
    Una grilla mide 5×5&nbsp;km y no es un lote: es la unidad de búsqueda del paso siguiente.
  </footer>
</div>

<script>
const D = __DATOS__;
const DEPS = __DEPS__;
const ZONAS = __ZONAS__;
const BARRAS = __BARRAS__;
const CRIT = __CRIT__;
const SUP = __SUP__;
const SUBES = __SUBES__;
const LINEAS = __LINEAS__;
const DIVISIONES = __DIVISIONES__;
const VBW = __VBW__, VBH = __VBH__;
const CLASES = ["Prioritaria","Elegible","Condicionada","Excluida"];
const PILL = {"Prioritaria":"p-pre","Elegible":"p-via","Condicionada":"p-rep","Excluida":"p-des"};
const COLCLASE = {"Prioritaria":"var(--good)","Elegible":"var(--warn)",
                  "Condicionada":"var(--bad)","Excluida":"var(--ink-3)"};
const PVMIN = Math.min(...D.map(g=>g.pvout||9e9));
const PVMAX = Math.max(...D.map(g=>g.pvout||0));
const svgNS = "http://www.w3.org/2000/svg";

// paleta de zonas: tonos distintos pero de saturación pareja, para no competir con la rampa
// La primera zona, que es la mayor, se lleva el teal de la marca. El resto son tonos
// de saturación pareja para que ninguno domine sobre otro.
const PALZ = ["#18919C","#A8492F","#3D7A5A","#7A5C9E","#B0761E","#2F6BA8","#8C4F6B",
              "#4F7A2F","#9E6B3D","#5A6E8C","#7B3F52","#3F7B72","#8C7A2F","#6B4FA8"];
const zonaColor = {};
ZONAS.forEach((z,i)=>{ zonaColor[z.zona] = PALZ[i % PALZ.length]; });

function radColor(v){
  if(v==null) return "var(--ink-3)";
  const t=(v-PVMIN)/Math.max(1,(PVMAX-PVMIN));
  return "var(--rad"+(Math.min(4,Math.max(0,Math.floor(t*5)))+1)+")";
}
function colorDe(g){
  if(modoColor==="clase") return COLCLASE[g.clase];
  if(modoColor==="zona")  return zonaColor[g.zona] || "var(--ink-3)";
  return radColor(g.pvout);
}
function fmt(v,d){ return (v==null||isNaN(v))?"—":Number(v).toFixed(d===undefined?0:d); }

// --- mapa ---
const gdeps=document.getElementById("deps");
for(const k in DEPS){
  const p=document.createElementNS(svgNS,"path");
  p.setAttribute("class","dep"); p.setAttribute("d",DEPS[k]); gdeps.appendChild(p);
}
const gpts=document.getElementById("pts");
D.forEach(g=>{
  const c=document.createElementNS(svgNS,"circle");
  c.setAttribute("cx",g.x); c.setAttribute("cy",g.y);
  c.setAttribute("r", 5); c.setAttribute("class","pt"); c.dataset.id=g.id;
  const t=document.createElementNS(svgNS,"title");
  t.textContent=g.id+" · "+g.depto+" · "+(g.pvout||"?")+" kWh/kWp/año · "+g.clase+" · "+g.zona;
  c.appendChild(t);
  // Tras el clic se lleva la ficha a la vista. Sin esto, en pantallas donde el buscador
  // ocupa la columna entera la ficha se actualiza fuera del encuadre y parece que el
  // clic no hizo nada.
  c.addEventListener("click",()=>{
    sel(g.id);
    const f = document.getElementById("ficha");
    const r = f.getBoundingClientRect();
    if(r.top < 0 || r.bottom > window.innerHeight)
      f.scrollIntoView({behavior:"smooth", block:"nearest"});
  });
  gpts.appendChild(c);
  g._el=c;
});

// --- capas conmutables: subestaciones y líneas de transmisión ---
const gsubs = document.getElementById("subs");
SUBES.forEach(s=>{
  const c=document.createElementNS(svgNS,"circle");
  c.setAttribute("cx",s.x); c.setAttribute("cy",s.y); c.setAttribute("r",2.2);
  c.setAttribute("class","sub-pt");
  const t=document.createElementNS(svgNS,"title");
  t.textContent=s.n+(s.kv?" · "+s.kv+" kV":"");
  c.appendChild(t); gsubs.appendChild(c);
});

const glin = document.getElementById("lineas");
LINEAS.forEach(l=>{
  const p=document.createElementNS(svgNS,"path");
  p.setAttribute("d","M"+l.p.map(q=>q[0]+" "+q[1]).join("L"));
  p.setAttribute("class","lin"+(l.kv && l.kv>=220000 ? " alta" : ""));
  p.setAttribute("vector-effect","non-scaling-stroke");
  if(l.kv){ const t=document.createElementNS(svgNS,"title");
            t.textContent=(l.kv/1000)+" kV"; p.appendChild(t); }
  glin.appendChild(p);
});

// --- límites administrativos ---
// Se dibujan una sola vez y se muestran u ocultan por CSS: reconstruir miles de paths
// en cada clic haría que el botón tardara medio segundo en responder.
Object.entries(DIVISIONES).forEach(([nivel, mapa])=>{
  const g = document.getElementById("div-"+nivel);
  if(!g) return;
  Object.entries(mapa).forEach(([etiqueta, d])=>{
    const p=document.createElementNS(svgNS,"path");
    p.setAttribute("d", d);
    const nombre = etiqueta.split("|")[0];
    const t=document.createElementNS(svgNS,"title"); t.textContent=nombre;
    p.appendChild(t); g.appendChild(p);
  });
});

document.querySelectorAll(".chip[data-div]").forEach(b=>{
  const g = document.getElementById("div-"+b.dataset.div);
  if(!g || !g.childElementCount){ b.disabled = true; b.title = "Capa sin datos"; return; }
  b.title = g.childElementCount + " límites";
  b.addEventListener("click",()=>{
    const on = b.getAttribute("aria-pressed")!=="true";
    b.setAttribute("aria-pressed", on?"true":"false");
    g.classList.toggle("on", on);
  });
});

document.querySelectorAll(".chip[data-capa]").forEach(b=>{
  const capa = document.getElementById(b.dataset.capa);
  if(!capa || !capa.childElementCount){ b.disabled = true; b.title = "Capa sin datos"; return; }
  b.addEventListener("click",()=>{
    const on = b.getAttribute("aria-pressed")!=="true";
    b.setAttribute("aria-pressed", on?"true":"false");
    capa.classList.toggle("on", on);
    leyenda();
  });
});

// --- zoom y desplazamiento ---
// Se transforma el grupo entero en vez de tocar el viewBox: así los radios se pueden
// compensar con la escala y los símbolos no engordan al acercarse.
const svgEl = document.getElementById("svgmapa");
const vp = document.getElementById("vp");
const nivel = document.getElementById("zNivel");
let K = 1, TX = 0, TY = 0;
const K_MIN = 1, K_MAX = 14;

function aplicar(){
  vp.setAttribute("transform", `translate(${TX} ${TY}) scale(${K})`);
  nivel.textContent = K.toFixed(1).replace(".", ",") + "×";
  D.forEach(g=>g._el.setAttribute("r", (g.clase==="Prioritaria"?6:5)/K));
  gsubs.querySelectorAll("circle").forEach(c=>c.setAttribute("r", 2.2/K));
}

function limitar(){
  K = Math.min(K_MAX, Math.max(K_MIN, K));
  TX = Math.min(0, Math.max(VBW - VBW*K, TX));
  TY = Math.min(0, Math.max(VBH - VBH*K, TY));
}

function zoomEn(cx, cy, factor){
  const k2 = Math.min(K_MAX, Math.max(K_MIN, K*factor));
  TX = cx - (cx - TX) * (k2 / K);   // deja quieto el punto bajo el cursor
  TY = cy - (cy - TY) * (k2 / K);
  K = k2; limitar(); aplicar();
}

function puntoSvg(ev){
  const r = svgEl.getBoundingClientRect();
  return [ (ev.clientX - r.left) / r.width * VBW, (ev.clientY - r.top) / r.height * VBH ];
}

svgEl.addEventListener("wheel", ev=>{
  ev.preventDefault();
  const [cx, cy] = puntoSvg(ev);
  zoomEn(cx, cy, ev.deltaY < 0 ? 1.22 : 1/1.22);
}, {passive:false});

let arrastre = null;
svgEl.addEventListener("pointerdown", ev=>{
  if(ev.target.classList.contains("pt")) return;   // no robarle el clic a una grilla
  arrastre = {x:ev.clientX, y:ev.clientY, tx:TX, ty:TY};
  svgEl.classList.add("arrastrando");
  try { svgEl.setPointerCapture(ev.pointerId); } catch(e){}
});
svgEl.addEventListener("pointermove", ev=>{
  if(!arrastre) return;
  const r = svgEl.getBoundingClientRect();
  TX = arrastre.tx + (ev.clientX - arrastre.x) / r.width * VBW;
  TY = arrastre.ty + (ev.clientY - arrastre.y) / r.height * VBH;
  limitar(); aplicar();
});
["pointerup","pointercancel","pointerleave"].forEach(e=>
  svgEl.addEventListener(e, ()=>{ arrastre=null; svgEl.classList.remove("arrastrando"); }));

function restablecer(){ K=1; TX=0; TY=0; aplicar(); }
svgEl.addEventListener("dblclick", restablecer);
document.getElementById("zIn").addEventListener("click", ()=>zoomEn(VBW/2, VBH/2, 1.5));
document.getElementById("zOut").addEventListener("click", ()=>zoomEn(VBW/2, VBH/2, 1/1.5));
document.getElementById("zRes").addEventListener("click", restablecer);

function acercarA(g, k=6){
  K = k; TX = VBW/2 - g.x*K; TY = VBH/2 - g.y*K; limitar(); aplicar();
}

// --- criterios editables ---
// CRIT viene de reporte_grillas.py, así que la lógica de aquí y la de allí no pueden
// divergir en los umbrales de partida. El descarte jurídico no aparece: manda sobre
// todo y ningún umbral lo negocia.
const CLAVES = Object.keys(CRIT);
const U = {};
CLAVES.forEach(k => U[k] = {bueno: CRIT[k].bueno, limite: CRIT[k].limite});

const DEC = {"%":0, "kWh/kWp":0, "km":1, "°":1, "m":0};
function fmtCrit(k, v){
  const u = CRIT[k].unidad;
  return v.toFixed(DEC[u] === undefined ? 1 : DEC[u]) + (u === "°" ? "°" : " " + u);
}
// --- perfil de proyecto -----------------------------------------------------------
// Los dos perfiles viajan dentro del JSON, cada uno con sus umbrales y su rango de
// tension. Cambiar de perfil solo reescribe U y vuelve a clasificar; no hace falta
// regenerar el reporte ni abrir otro archivo.
const PERFILES = SUP.perfiles || {};
let PERFIL = SUP.perfil || Object.keys(PERFILES)[0];

// La distancia al punto de conexion cambia con el perfil, porque cambia el techo de
// tension: para 1-2 MW no sirven las subestaciones de 220 kV para arriba.
function distSub(g){
  const alt = g["dist_sub__" + PERFIL];
  return alt !== undefined ? alt : g.dist_sub;
}

// La capacidad tambien cambia con el perfil: el de 1-2 MW se conecta en media tension
// y el de utility en la barra de alta, y son cupos distintos.
function capacidad(g){
  // Sin fallback entre niveles a proposito. Si falta la capacidad de media tension no
  // se puede sustituir por la de alta: son puntos de conexion distintos, y hacerlo daba
  // por buena una barra a la que el proyecto no se conectaria. Cuando falta, el criterio
  // no puntua y la grilla se evalua con los seis restantes.
  return PERFIL === "distribuida" ? g.cap_mt : g.cap_at;
}

function valorDe(g, k){
  return {cobertura:g.cobertura, dist_sub:distSub(g), recurso:g.pvout,
          pendiente:g.pendiente, rugosidad:g.rugosidad, dist_via:g.via,
          capacidad:capacidad(g)}[k];
}
let UMBRAL = SUP.indice_prioritaria || 80;

function aplicarPerfil(nombre){
  const p = PERFILES[nombre];
  if(!p) return;
  PERFIL = nombre;
  CLAVES.forEach(k=>{
    const u = p.umbrales[k];
    if(u){ CRIT[k].tope=u.tope; CRIT[k].bueno=u.bueno; CRIT[k].limite=u.limite;
           U[k].bueno=u.bueno; U[k].limite=u.limite; }
    // Los pesos tambien cambian con el perfil: el efecto de cada criterio crece con el
    // tamano del proyecto, asi que usar los de las plantas grandes para el perfil chico
    // le atribuiria un criterio de seleccion que esas plantas no tuvieron.
    if(p.pesos && p.pesos[k] != null) CRIT[k].d_cohen = p.pesos[k];
  });
  const et = document.getElementById("eyebrow-perfil");
  if(et) et.textContent = p.etiqueta;
  const av = document.getElementById("aviso-perfil");
  if(av) av.innerHTML = p.aviso
    ? `<div class="aviso-p"><b>Sobre el punto de conexión.</b> ${p.aviso}</div>` : "";
  document.querySelectorAll("#selperfil button").forEach(b=>
    b.classList.toggle("on", b.dataset.p===nombre));
  reclasificar(); render();
}

// Utilidad en dos tramos: 0 en el limite, 70 en el objetivo, 100 en el tope. Los tres
// puntos vienen de las plantas que ya operan, no de la cartera que se este mirando.
//
// Esta funcion tiene que dar exactamente lo mismo que utilidad() en reporte_grillas.py.
// Son dos copias de la misma formula, una en Python para los exports y otra aqui para
// que la matriz recalcule sin recargar, y cuando se separan el navegador y el CSV
// muestran clasificaciones distintas para la misma grilla.
function utilidad(k, v){
  const c=CRIT[k], u=U[k], s=c.mayor_mejor?1:-1;
  const V=s*v, L=s*u.limite, B=s*u.bueno, T=s*(u.tope!=null?u.tope:c.tope);
  if(V<=L) return 0;
  if(V<=B) return 70*(V-L)/Math.max(1e-9,B-L);
  const holgura = T-B;
  return holgura<=1e-9 ? 70 : 70+30*Math.min(1,(V-B)/holgura);
}

// Botonera de perfil. Se pinta una vez y a partir de ahi todo lo demas es reactivo.
(function botoneraPerfil(){
  const cont = document.getElementById("selperfil");
  if(!cont) return;
  cont.innerHTML = Object.entries(PERFILES).map(([k,p])=>
    `<button data-p="${k}" title="Umbrales calibrados con ${p.n_referencia} grillas que ya
      tienen planta de ${p.mw_referencia} MW o más">${p.etiqueta}</button>`).join("");
  cont.querySelectorAll("button").forEach(b=>
    b.addEventListener("click", ()=>aplicarPerfil(b.dataset.p)));
  const nota = document.getElementById("perfil-nota");
  if(nota) nota.textContent = "Cambia los seis umbrales y el punto de conexión. "
    + "Las exclusiones son las mismas en ambos.";
})();

// Desglose del indice de la grilla que va primera. Se calcula con la misma funcion que
// clasifica, no con numeros escritos aparte, para que no pueda quedarse desfasado.
function pintarCalculo(){
  const el = document.getElementById("calc-ejemplo");
  if(!el) return;
  const g = [...D].filter(x=>x.clase!=="Excluida").sort((a,b)=>b.indice-a.indice)[0];
  if(!g) return;
  const peso_tot = CLAVES.reduce((s,k)=>s+CRIT[k].d_cohen, 0);
  let suma = 0;
  const filas = CLAVES.map(k=>{
    const c=CRIT[k], u=U[k], v=valorDe(g,k);
    if(v==null) return `<tr><td>${c.etiqueta}</td><td colspan="6" class="sinval">sin dato</td></tr>`;
    const nota=utilidad(k,v), w=c.d_cohen/peso_tot, ap=nota*w;
    suma += ap;
    return `<tr><td>${c.etiqueta}</td>
      <td class="num">${fmtCrit(k,v)}</td>
      <td class="num esc">${fmtCrit(k,u.limite)}</td>
      <td class="num esc">${fmtCrit(k,u.bueno)}</td>
      <td class="num esc">${fmtCrit(k,c.tope)}</td>
      <td class="num"><b>${nota.toFixed(1)}</b></td>
      <td class="num">${(w*100).toFixed(1)}%</td>
      <td class="num">${ap.toFixed(2)}</td></tr>`;
  }).join("");
  el.innerHTML = `
    <p class="calc-cab">Grilla <span class="mono">${g.id}</span>, ${g.municipio},
      ${g.depto.toLowerCase()}. La primera de la lista.</p>
    <div class="tablebox"><table class="calc-t">
      <thead><tr><th>Criterio</th><th class="tr">Valor</th>
        <th class="tr esc">Límite<br><small>vale 0</small></th>
        <th class="tr esc">Objetivo<br><small>vale 70</small></th>
        <th class="tr esc">Tope<br><small>vale 100</small></th>
        <th class="tr">Nota</th><th class="tr">Peso</th><th class="tr">Aporte</th></tr></thead>
      <tbody>${filas}</tbody>
      <tfoot><tr><td colspan="7">Índice</td>
        <td class="num"><b>${suma.toFixed(1)}</b></td></tr></tfoot>
    </table></div>
    <p class="calc-pie">La nota sale de interpolar entre los tres puntos de la escala. El
    aporte es la nota por el peso, y el índice es la suma de los seis aportes.</p>`;
}

// --- competencia por barra ---------------------------------------------------------
// Lo que decide aqui no es la tabla sino una pregunta: cabe mi proyecto en esa barra?
// Se responde con la capacidad libre frente al tamano del perfil activo, y se dice
// cuantos proyectos de ese tamano entran antes de que la barra se llene.
//
// La configuracion de barras se traduce a lenguaje llano. Es el esquema electrico del
// patio de la subestacion, y determina cuanta holgura hay para colgar una conexion nueva
// y si hacerlo obliga a dejar sin servicio a las que ya estan.
const CONFIG_BARRA = [
  [/interruptor y medio|breaker and a half/i, "alta",
   "Interruptor y medio. Cada salida comparte interruptores con la vecina: es la "
   + "configuracion mas flexible y admite conexiones nuevas sin sacar de servicio al resto."],
  [/anillo|ring/i, "alta",
   "En anillo. La energia puede llegar por dos caminos, asi que una falla no deja sin "
   + "servicio a las demas salidas."],
  [/doble barra|barra doble/i, "media",
   "Doble barra. Hay dos barras y las salidas pueden pasar de una a otra, lo que permite "
   + "mantenimiento sin cortar el servicio."],
  [/transferencia/i, "media",
   "Barra principal y de transferencia. Existe una barra de reserva para mover una salida "
   + "mientras se le hace mantenimiento, pero no para operar dos a la vez."],
  [/sencilla|simple/i, "baja",
   "Barra sencilla. Una sola barra y un interruptor por salida: es la configuracion con "
   + "menos holgura, y ampliarla suele exigir obra en el patio."],
];

function leerConfig(txt){
  for(const c of CONFIG_BARRA) if(c[0].test(txt||"")) return {nivel:c[1], desc:c[2]};
  return {nivel:"nd", desc:"Sin dato de configuracion en la capa de subestaciones."};
}

function pintarBarras(){
  const cuerpo = document.getElementById("tbb");
  if(!cuerpo) return;
  const mw = (PERFILES[PERFIL]||{}).mw_proyecto || 20;
  const et = document.getElementById("barrasProy");
  if(et) et.textContent = fmt(mw,0);

  // Se ordena por lo que importa: primero las barras donde no cabe el proyecto, que son
  // las que hay que descartar o negociar, y dentro de cada grupo por competencia.
  const filas = [...BARRAS].sort((a,b)=>{
    const ca=a.capacidad_disponible_mw, cb=b.capacidad_disponible_mw;
    if(ca==null && cb==null) return b.candidatas-a.candidatas;
    if(ca==null) return 1;
    if(cb==null) return -1;
    return (Math.floor(ca/mw)-Math.floor(cb/mw)) || (b.candidatas-a.candidatas);
  });

  cuerpo.innerHTML = filas.map(b=>{
    const cap = b.capacidad_disponible_mw;
    const cfg = leerConfig(b.barras);
    let estado, texto;
    if(cap==null){ estado="nd"; texto="sin dato"; }
    else {
      const caben = Math.floor(cap/mw);
      if(caben===0){ estado="no"; texto="no cabe ninguno"; }
      else if(caben < b.candidatas){
        estado="justo";
        texto = "caben "+caben+", compiten "+b.candidatas;
      } else { estado="si"; texto = "caben "+caben; }
    }
    return `
    <tr class="est-${estado}">
      <td><b>${b.sub_nombre_subestacion}</b><span class="sub-mun">${b.municipio||""}</span></td>
      <td class="tr num">${b.tension_kv==null?"—":b.tension_kv.toFixed(0)}</td>
      <td class="tr num${cap==null?" pend":""}">${cap==null?"—":cap.toFixed(0)}</td>
      <td><span class="veredicto v-${estado}">${texto}</span></td>
      <td class="tr num"><b>${b.candidatas}</b>${b.prioritarias?'<small> · '+b.prioritarias+' pri.</small>':''}</td>
      <td class="tr num">${b.km_medio==null?"—":b.km_medio.toFixed(1)}</td>
      <td><span class="hol h-${cfg.nivel}" title="${cfg.desc}">${
        cfg.nivel==="nd"?"sin dato":"holgura "+cfg.nivel}</span></td>
    </tr>`;
  }).join("");
}

function reclasificar(){
  D.forEach(g=>{
    if(g.n_restric>0){
      // solo baja la inicial: toLowerCase() entero convertiría RUNAP en runap
      const r=g.restricciones;
      g.clase="Excluida";
      g.motivo="Excluida: la grilla cae sobre "+r.charAt(0).toLowerCase()+r.slice(1)+".";
      g.cumple=0; g.indice=0;
      return;
    }
    const graves=[], cortos=[], ok=[];
    let suma=0, peso=0;
    CLAVES.forEach(k=>{
      const v = valorDe(g,k);
      if(v==null) return;
      const c = CRIT[k], u = U[k];
      suma += utilidad(k,v)*c.d_cohen; peso += c.d_cohen;
      const peor  = c.mayor_mejor ? v < u.limite : v > u.limite;
      const corto = c.mayor_mejor ? v < u.bueno  : v > u.bueno;
      const txt = c.etiqueta.toLowerCase()+" de "+fmtCrit(k,v);
      if(peor) graves.push(txt+", fuera del límite de "+fmtCrit(k,u.limite));
      else if(corto) cortos.push(txt);
      else ok.push(k);
    });
    g.cumple = ok.length;      // criterios que ALCANZAN EL OBJETIVO
    g.enRojo = graves.length;  // criterios FUERA DEL LIMITE. Son varas distintas.
    g.indice = peso ? Math.round(suma/peso*10)/10 : 0;

    // El índice resume, pero no puede tapar un criterio fuera de límite.
    const obj = " Alcanza el objetivo en "+ok.length+" de "+CLAVES.length+" criterios.";
    if(graves.length){ g.clase="Condicionada";
      g.motivo="Índice "+g.indice.toFixed(0)+" sobre 100, con "+graves.length+
        (graves.length===1?" criterio fuera de límite":" criterios fuera de límite")+
        ". Requiere gestión adicional por "+graves.join("; y ")+"."; }
    else if(g.indice>=UMBRAL){ g.clase="Prioritaria";
      g.motivo="Índice "+g.indice.toFixed(0)+" sobre 100 y ningún criterio fuera de límite."+
        obj+" Entra en la lista corta."; }
    else { g.clase="Elegible";
      g.motivo="Índice "+g.indice.toFixed(0)+" sobre 100, sin criterios fuera de límite, pero "+
        "por debajo del corte de "+UMBRAL+"."+obj+
        (cortos.length?" Se queda corta en "+cortos.join(" y ")+".":""); }
  });

  const c={Prioritaria:0,Elegible:0,Condicionada:0,Excluida:0};
  D.forEach(g=>c[g.clase]++);
  [["pre","Prioritaria"],["via","Elegible"],["rep","Condicionada"],["des","Excluida"]].forEach(([k,nombre])=>{
    const kpi=document.getElementById("k-"+k), crit=document.getElementById("c-"+k);
    if(kpi) kpi.textContent=c[nombre];
    if(crit) crit.textContent=c[nombre];
  });
  pintarReparto(c);
  pintarMatriz();
  pintarCalculo();
  pintarZonas();
  pintarBarras();
}

// --- matriz de criterios con histograma ---
function histograma(k, ancho, alto){
  const c = CRIT[k], u = U[k];
  const vals = D.map(g=>valorDe(g,k)).filter(v=>v!=null);
  if(!vals.length) return "";
  const min=Math.min(...vals), max=Math.max(...vals);
  const rango = (max-min)||1, nb=22;
  const bins = new Array(nb).fill(0);
  vals.forEach(v=>{ bins[Math.min(nb-1, Math.floor((v-min)/rango*nb))]++; });
  const pico = Math.max(...bins)||1;
  const bw = ancho/nb;
  const x = v => (v-min)/rango*ancho;
  let s = `<svg class="hist" width="${ancho}" height="${alto}" viewBox="0 0 ${ancho} ${alto}">`;
  bins.forEach((n,i)=>{
    const centro = min + (i+0.5)/nb*rango;
    const peor  = c.mayor_mejor ? centro < u.limite : centro > u.limite;
    const bueno = c.mayor_mejor ? centro >= u.bueno : centro <= u.bueno;
    const cls = peor ? "bar no" : (bueno ? "bar ok" : "bar");
    const h = n/pico*(alto-3);
    s += `<rect class="${cls}" x="${(i*bw).toFixed(1)}" y="${(alto-h).toFixed(1)}" width="${(bw-0.8).toFixed(1)}" height="${h.toFixed(1)}"></rect>`;
  });
  [["obj",u.bueno],["lim",u.limite]].forEach(([tipo,v])=>{
    if(v>=min && v<=max){
      s += `<line class="marca-${tipo}" x1="${x(v).toFixed(1)}" y1="0" x2="${x(v).toFixed(1)}" y2="${alto}"></line>`;
    }
  });
  return s+"</svg>";
}

function pintarMatriz(){
  const dmax = Math.max(...CLAVES.map(k=>CRIT[k].d_cohen));
  document.getElementById("tcrit").innerHTML = CLAVES.map(k=>{
    const c=CRIT[k], u=U[k];
    const cumplen = D.filter(g=>{
      const v=valorDe(g,k); if(v==null||g.n_restric>0) return false;
      return c.mayor_mejor ? v>=u.bueno : v<=u.bueno;
    }).length;
    const paso = c.unidad==="kWh/kWp" ? 10 : (c.unidad==="%" ? 1 : 0.5);
    return `<tr>
      <td><div class="cr-nom">${c.etiqueta}</div><div class="cr-uni">medido en ${c.unidad}</div></td>
      <td><div class="cr-efecto"><span class="track"><span class="fill" style="width:${(c.d_cohen/dmax*100).toFixed(0)}%"></span></span><span class="val">${c.d_cohen.toFixed(2)}</span></div></td>
      <td class="tr"><input class="umbral obj" type="number" step="${paso}" value="${u.bueno}" data-k="${k}" data-tipo="bueno" aria-label="Objetivo de ${c.etiqueta}"></td>
      <td class="tr"><input class="umbral lim" type="number" step="${paso}" value="${u.limite}" data-k="${k}" data-tipo="limite" aria-label="Límite de ${c.etiqueta}"></td>
      <td>${histograma(k, 210, 34)}</td>
      <td class="tr cr-cumplen">${cumplen}</td>
    </tr>`;
  }).join("");

  document.querySelectorAll("input.umbral").forEach(inp=>{
    inp.addEventListener("change",()=>{
      const v=parseFloat(inp.value);
      if(!isNaN(v)){ U[inp.dataset.k][inp.dataset.tipo]=v; reclasificar(); render(); }
    });
  });
}

function pintarReparto(c){
  // Los nombres tienen que ser los mismos que produce clasificar() en Python. Cuando se
  // renombraron las clases esta funcion se quedo con los viejos, y como un nombre que no
  // existe da undefined en vez de error, la barra salia vacia sin avisar de nada.
  const orden=[["Prioritaria","var(--good)"],["Elegible","var(--warn)"],
               ["Condicionada","var(--bad)"],["Excluida","var(--ink-3)"]];
  const tot=D.length;
  document.getElementById("apilada").innerHTML = orden.map(([n,col])=>{
    const v=c[n]||0;
    return v ? `<span style="width:${v/tot*100}%;background:${col}" title="${n}: ${v}">${v/tot>=0.08?v:""}</span>` : "";
  }).join("");
  document.getElementById("apilada-leg").innerHTML = orden.map(([n,col])=>
    `<span><i style="background:${col}"></i>${n} ${c[n]||0}</span>`).join("");

  // Las dos varas se pintan igual pero cuentan cosas distintas, y por eso van juntas:
  // "fuera de limite" es lo que decide la clase, "alcanza el objetivo" solo informa.
  // Las excluidas se dejan fuera de las dos, que no compiten.
  const vivas = D.filter(g=>g.clase!=="Excluida");
  const barras = (cont, dist, etq) => {
    const el = document.getElementById(cont);
    if(!el) return;
    const maxn = Math.max(...Object.values(dist), 1);
    el.innerHTML = Object.keys(dist).map(Number).sort((a,b)=>a-b)
      .filter(n=>dist[n]).map(n=>
        `<div class="cd-row"><span>${etq(n)}</span>
         <span class="t"><span style="width:${dist[n]/maxn*100}%"></span></span>
         <span class="n">${dist[n]}</span></div>`).join("");
  };

  const rojo={}; vivas.forEach(g=>{ rojo[g.enRojo||0]=(rojo[g.enRojo||0]||0)+1; });
  barras("rojo-dist", rojo, n => n===0 ? "ninguno" : (n===1 ? "uno" : n+" criterios"));

  const dist={}; vivas.forEach(g=>{ dist[g.cumple]=(dist[g.cumple]||0)+1; });
  barras("cumplen-dist", dist, n => n+" de "+CLAVES.length);
}

// ===================================================================================
// LOTE PARA BUSQUEDA DE PREDIOS
// ===================================================================================
// Consultar el FeatureServer del IGAC cuesta minutos por grilla, asi que no tiene
// sentido lanzarlo sobre las cien. Aqui se marcan las que interesan y se descargan en
// el formato que el notebook 2 espera como entrada: un GeoJSON con la geometria de cada
// grilla y su cell_id, o un CSV con el contorno en WKT para quien prefiera tabla.
const LOTE = new Set();

function pintarLote(){
  const el = document.getElementById("loteN");
  if(!el) return;
  const n = LOTE.size;
  el.textContent = n === 0 ? "ninguna marcada"
    : n + (n === 1 ? " grilla marcada" : " grillas marcadas");
  el.classList.toggle("hay", n > 0);
  ["loteGeojson","loteCsv"].forEach(id=>{
    const b = document.getElementById(id); if(b) b.disabled = n === 0;
  });
}

function contornoDe(g){
  // El contorno exacto viaja con la imagen satelital. Si esa grilla no tiene foto se
  // reconstruye un cuadrado de 5 km alrededor del centro, que para lanzar la consulta
  // al IGAC es suficiente: el servicio recorta por interseccion.
  const s = SAT[g.id];
  if(s && s.poly && s.poly.length) return s.poly;
  const dy = 2.5/111.32, dx = 2.5/(111.32*Math.cos(g.lat*Math.PI/180));
  return [[g.lon-dx,g.lat-dy],[g.lon+dx,g.lat-dy],[g.lon+dx,g.lat+dy],
          [g.lon-dx,g.lat+dy],[g.lon-dx,g.lat-dy]];
}

function descargar(nombre, texto, tipo){
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([texto], {type:tipo}));
  a.download = nombre;
  document.body.appendChild(a); a.click();
  setTimeout(()=>{ URL.revokeObjectURL(a.href); a.remove(); }, 400);
}

function lotePorId(){
  return D.filter(g=>LOTE.has(g.id)).sort((a,b)=>a.ranking-b.ranking);
}

function exportarLoteGeojson(){
  const sel = lotePorId();
  if(!sel.length) return;
  const fc = {
    type: "FeatureCollection",
    name: "grillas_para_predios",
    crs: {type:"name", properties:{name:"urn:ogc:def:crs:OGC:1.3:CRS84"}},
    features: sel.map(g=>({
      type: "Feature",
      geometry: {type:"Polygon", coordinates:[contornoDe(g)]},
      properties: {
        cell_id: g.id, ranking: g.ranking, clasificacion: g.clase,
        indice: g.indice, zona: g.zona, departamento: g.depto,
        municipio: g.municipio, vereda: g.vereda,
        ha_aptas: g.ha, mwp: g.mwp,
        subestacion: g.subestacion, operador: g.operador,
        lat: g.lat, lon: g.lon
      }
    }))
  };
  descargar("grillas_para_predios.geojson", JSON.stringify(fc), "application/geo+json");
}

function exportarLoteCsv(){
  const sel = lotePorId();
  if(!sel.length) return;
  const esc = v => { const s = v==null?"":String(v);
    return /[";\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s; };
  const cab = ["cell_id","ranking","clasificacion","indice","zona","departamento",
               "municipio","vereda","lat","lon","ha_aptas","mwp","subestacion",
               "operador","wkt"];
  const filas = sel.map(g=>{
    const wkt = "POLYGON((" + contornoDe(g).map(p=>p[0]+" "+p[1]).join(",") + "))";
    return [g.id,g.ranking,g.clase,g.indice,g.zona,g.depto,g.municipio,g.vereda,
            g.lat,g.lon,g.ha,g.mwp,g.subestacion,g.operador,wkt].map(esc).join(";");
  });
  // BOM por codigo, para que Excel en Windows abra las tildes bien
  descargar("grillas_para_predios.csv",
            String.fromCharCode(0xFEFF) + [cab.join(";"), ...filas].join("\n"),
            "text/csv;charset=utf-8");
}

// ===================================================================================
// IMAGEN SATELITAL
// ===================================================================================
// La foto viene embebida y cubre un recuadro algo mayor que la grilla, para que se vea
// el entorno. Encima se dibuja el contorno real de la grilla: es cuadrada en la
// proyeccion metrica pero no en coordenadas geograficas, asi que se traza el poligono
// y no un rectangulo.
const SAT = __SAT__;
const SAT_FUENTE = __SATFTE__;

function vistaSatelital(g, lado){
  const s = SAT[g.id];
  if(!s) return "";
  const [x0,y0,x1,y1] = s.bbox;
  const px = p => ((p[0]-x0)/(x1-x0))*lado;
  const py = p => ((y1-p[1])/(y1-y0))*lado;
  const pts = (s.poly||[]).map(p=>px(p).toFixed(1)+","+py(p).toFixed(1)).join(" ");
  return `<div class="sat-caja">
    <img class="sat-img" src="${s.src}" loading="lazy"
         alt="Imagen satelital de la grilla ${g.id}">
    <svg class="sat-svg" viewBox="0 0 ${lado} ${lado}" preserveAspectRatio="none">
      <polygon points="${pts}" fill="none" stroke="#fff" stroke-width="3.4" opacity=".65"/>
      <polygon points="${pts}" fill="none" stroke="var(--brand)" stroke-width="1.9"/>
    </svg>
    <span class="sat-cred">${SAT_FUENTE}${s.fecha?" · "+s.fecha:""}</span>
  </div>`;
}

// ===================================================================================
// FICHA TECNICA IMPRIMIBLE
// ===================================================================================
// Se abre en una ventana aparte con su propio CSS y se manda a imprimir. El navegador
// ofrece "Guardar como PDF", que evita depender de una libreria externa: el reporte
// tiene que seguir funcionando como un archivo suelto, sin conexion y sin CDN.

// Las claves de DIVISIONES traen el codigo DANE pegado ("Sabanalarga|08638") y el
// departamento va capitalizado, mientras que la grilla lo trae en mayusculas. Se compara
// sin acentos y por la parte anterior a la barra.
function _llave(s){
  return (s||"").toString().split("|")[0].normalize("NFD")
    .replace(/[̀-ͯ]/g,"").toLowerCase().trim();
}
function buscaDiv(tipo, nombre){
  const dic = DIVISIONES[tipo] || {};
  const q = _llave(nombre);
  if(!q) return null;
  for(const k in dic) if(_llave(k) === q) return dic[k];
  return null;
}

// Caja envolvente de un path. Se mide creando un SVG fuera de pantalla porque getBBox
// da la geometria real, incluidas las curvas, y parsear la cadena a mano no.
function bboxDe(d){
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("style", "position:absolute;width:0;height:0;overflow:hidden");
  const p = document.createElementNS(ns, "path");
  p.setAttribute("d", d);
  svg.appendChild(p); document.body.appendChild(svg);
  const b = p.getBBox();
  document.body.removeChild(svg);
  return b;
}

// Mapa de situacion con lupa: el departamento entero, el municipio resaltado, y un
// circulo que amplia el entorno de la grilla para que se vea la vereda, que a escala
// departamental seria un punto invisible.
function mapaSituacion(g){
  const dDep = buscaDiv("departamento", g.depto);
  const dMun = buscaDiv("municipio", g.municipio);
  const dVer = buscaDiv("vereda", g.vereda);
  const dGri = (DIVISIONES.grilla || {})[g.id];
  if(!dDep && !dMun) return "";

  const W = 520, H = 300;
  const ref = dDep || dMun;
  const b = bboxDe(ref);
  const m = Math.max(b.width, b.height) * 0.10 + 2;
  const vb = [b.x - m, b.y - m, b.width + 2*m, b.height + 2*m];
  const k = Math.min(W / vb[2], H / vb[3]);

  // centro de la grilla en el sistema del mapa nacional
  const bg = dGri ? bboxDe(dGri) : (dMun ? bboxDe(dMun) : b);
  const cx = bg.x + bg.width/2, cy = bg.y + bg.height/2;
  // posicion de ese centro dentro del lienzo ya escalado
  const px = (cx - vb[0]) * k, py = (cy - vb[1]) * k;

  // La lupa se coloca en la esquina mas libre respecto al punto
  const lr = 74;
  const lx = px < W/2 ? W - lr - 12 : lr + 12;
  const ly = py < H/2 ? H - lr - 12 : lr + 12;

  // El aumento se ajusta a lo que hay que encuadrar, no se fija a ojo: se toma la vereda
  // si existe y si no la grilla, y se escala para que ocupe unos dos tercios del circulo.
  // Con un valor fijo, una vereda grande se salia y una pequena quedaba perdida.
  const enc = dVer ? bboxDe(dVer) : bg;
  const zoom = Math.max(4, Math.min(60,
    (lr * 1.35) / Math.max(enc.width, enc.height, 0.6)));

  const trazo = 1.1 / k;
  return `
  <svg class="mapa-sit" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
    <g transform="scale(${k}) translate(${-vb[0]},${-vb[1]})">
      ${dDep ? `<path d="${dDep}" fill="var(--sit-bg)" stroke="var(--sit-line)"
                 stroke-width="${trazo}"/>` : ""}
      ${dMun ? `<path d="${dMun}" fill="var(--sit-mun)" stroke="var(--sit-line)"
                 stroke-width="${trazo}"/>` : ""}
    </g>
    <circle cx="${px}" cy="${py}" r="4.5" fill="none" stroke="var(--brand)" stroke-width="1.6"/>
    <circle cx="${px}" cy="${py}" r="1.6" fill="var(--brand)"/>
    <line x1="${px}" y1="${py}" x2="${lx}" y2="${ly}" stroke="var(--brand)"
          stroke-width="0.8" stroke-dasharray="3 2.5" opacity=".55"/>

    <defs><clipPath id="lupa"><circle cx="${lx}" cy="${ly}" r="${lr}"/></clipPath></defs>
    <g clip-path="url(#lupa)">
      <circle cx="${lx}" cy="${ly}" r="${lr}" fill="var(--sit-lupa)"/>
      <g transform="translate(${lx},${ly}) scale(${zoom}) translate(${-cx},${-cy})">
        ${dMun ? `<path d="${dMun}" fill="var(--sit-mun)" stroke="var(--sit-line)"
                   stroke-width="${0.9/zoom}"/>` : ""}
        ${dVer ? `<path d="${dVer}" fill="var(--sit-ver)" stroke="var(--accent)"
                   stroke-width="${1.1/zoom}"/>` : ""}
        ${dGri ? `<path d="${dGri}" fill="var(--brand)" fill-opacity=".85"
                   stroke="var(--brand)" stroke-width="${1.4/zoom}"/>` : ""}
      </g>
    </g>
    <circle cx="${lx}" cy="${ly}" r="${lr}" fill="none" stroke="var(--brand)" stroke-width="1.8"/>
    <text x="${lx}" y="${ly + lr + 13}" text-anchor="middle" class="sit-cap">
      ${dVer ? "vereda " + g.vereda : g.municipio} · ×${zoom.toFixed(0)}</text>
    <text x="10" y="${H - 8}" class="sit-cap">${g.depto.toLowerCase()}</text>
  </svg>`;
}

function fichaTecnica(g){
  const pesoTot = CLAVES.reduce((s,k)=>s+CRIT[k].d_cohen,0);
  const filas = CLAVES.map(k=>{
    const c=CRIT[k], v=valorDe(g,k);
    if(v==null) return `<tr><td>${c.etiqueta}</td><td colspan="4" class="nd">sin dato</td></tr>`;
    const n=utilidad(k,v), w=c.d_cohen/pesoTot;
    const est = n===0 ? "fuera" : (n>=70 ? "cumple" : "corto");
    return `<tr><td>${c.etiqueta}</td>
      <td class="num">${fmtCrit(k,v)}</td>
      <td class="num lim">${fmtCrit(k,c.limite)} / ${fmtCrit(k,c.bueno)}</td>
      <td class="num"><b>${n.toFixed(0)}</b></td>
      <td><span class="est ${est}">${est==="fuera"?"fuera de límite":(est==="cumple"?"cumple objetivo":"por debajo")}</span></td></tr>`;
  }).join("");

  const marca = document.querySelector(".brand-mark")?.outerHTML || "";
  const hoy = new Date().toLocaleDateString("es-CO",{year:"numeric",month:"long",day:"numeric"});
  const perfil = (PERFILES[PERFIL]||{}).etiqueta || "";
  const pill = {Prioritaria:"#3D7A5A", Elegible:"#B0761E",
                Condicionada:"#A8492F", Excluida:"#6b6f76"}[g.clase] || "#6b6f76";

  const w = window.open("", "_blank", "width=900,height=1100");
  if(!w){ alert("El navegador bloqueó la ventana. Permite las ventanas emergentes para descargar la ficha."); return; }
  w.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Ficha ${g.id} · ${g.municipio}</title>
<style>
:root{--brand:#18919C; --accent:#157F88; --ink:#1a1d21; --ink-2:#4a5058; --ink-3:#878d96;
  --line:#e3e6ea; --surface-2:#f6f7f9;
  --sit-bg:#eef1f4; --sit-line:#c8ced6; --sit-mun:#dfe6ea; --sit-ver:#cfe6e8; --sit-lupa:#f7fafb}
*{box-sizing:border-box}
body{margin:0; padding:26px 30px; font-family:"Segoe UI",system-ui,sans-serif;
  color:var(--ink); font-size:12px; line-height:1.5; -webkit-print-color-adjust:exact;
  print-color-adjust:exact}
.cab{display:flex; align-items:flex-start; justify-content:space-between; gap:20px;
  border-bottom:2px solid var(--brand); padding-bottom:12px; margin-bottom:16px}
.cab-izq{display:flex; align-items:center; gap:11px}
.brand-mark{width:26px; height:28px; flex:none}
.n1{font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--brand);
  font-weight:700; margin:0}
.n2{font-size:10.5px; color:var(--ink-3); margin:1px 0 0}
h1{font-size:20px; margin:9px 0 2px; letter-spacing:-.01em}
.sub{color:var(--ink-2); margin:0; font-size:12.5px}
.chip{display:inline-block; padding:3px 10px; border-radius:11px; color:#fff;
  font-size:10.5px; font-weight:700; letter-spacing:.05em; text-transform:uppercase;
  background:${pill}}
.idx{text-align:right}
.idx b{font-size:30px; line-height:1; display:block; color:var(--brand)}
.idx span{font-size:10px; color:var(--ink-3); letter-spacing:.06em; text-transform:uppercase}
h2{font-size:10px; letter-spacing:.11em; text-transform:uppercase; color:var(--accent);
  margin:18px 0 7px; padding-bottom:4px; border-bottom:1px solid var(--line)}
.cols{display:grid; grid-template-columns:1fr 1fr; gap:20px; align-items:start}
.mapa-sit{width:100%; height:auto; background:#fff; border:1px solid var(--line); border-radius:4px}
.sat-caja{position:relative; border:1px solid var(--line); border-radius:4px;
  overflow:hidden; line-height:0}
.sat-img{width:100%; height:auto; display:block}
.sat-svg{position:absolute; inset:0; width:100%; height:100%}
.sat-cred{position:absolute; right:4px; bottom:3px; font-size:7px; color:#fff;
  background:rgba(0,0,0,.45); padding:1px 4px; border-radius:2px}
.sit-cap{font-size:8px; fill:var(--ink-3); font-family:"Segoe UI",sans-serif;
  letter-spacing:.04em; text-transform:uppercase}
table{width:100%; border-collapse:collapse; font-size:11px}
th{text-align:left; font-size:8.5px; letter-spacing:.07em; text-transform:uppercase;
  color:var(--ink-3); border-bottom:1px solid var(--line); padding:5px 6px; font-weight:600}
td{padding:5px 6px; border-bottom:1px solid var(--line)}
.num{text-align:right; font-variant-numeric:tabular-nums}
.lim{color:var(--ink-3); font-size:10px}
.nd{color:var(--ink-3); font-style:italic}
.est{font-size:9px; padding:1.5px 6px; border-radius:8px; white-space:nowrap}
.est.cumple{background:#E7F1EB; color:#2f6247}
.est.corto{background:#F8EFDC; color:#8a5c17}
.est.fuera{background:#F7E6E1; color:#8a3b26}
.datos{display:grid; grid-template-columns:repeat(3,1fr); gap:9px 16px; margin-top:3px}
.dato{border-top:1px solid var(--line); padding-top:5px}
.dk{font-size:8.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3);
  font-weight:600}
.dv{font-size:14px; font-variant-numeric:tabular-nums; margin-top:1px}
.dv small{font-size:9.5px; color:var(--ink-3)}
.h2sub{font-weight:400; text-transform:none; letter-spacing:0; color:var(--ink-3);
  font-style:italic; font-size:9px; margin-left:6px}
table.def{width:100%; border-collapse:collapse; font-size:10.5px; margin-top:2px}
table.def td{padding:5px 7px; border-bottom:1px solid var(--line); vertical-align:top}
table.def .dn{width:23%; color:var(--ink-2)}
table.def .dn b{color:var(--accent); font-family:"Cascadia Mono",Consolas,monospace;
  font-size:9.5px; letter-spacing:.03em}
table.def .dvv{width:19%; text-align:right; font-variant-numeric:tabular-nums;
  font-weight:600; white-space:nowrap}
table.def .dd{color:var(--ink-3); line-height:1.45; font-size:9.5px}
.aviso{background:var(--surface-2); border-left:3px solid var(--brand); padding:9px 12px;
  border-radius:0 3px 3px 0; margin-top:6px; font-size:11px; color:var(--ink-2)}
.pie{margin-top:20px; padding-top:9px; border-top:1px solid var(--line); font-size:9px;
  color:var(--ink-3); display:flex; justify-content:space-between; gap:14px}
@media print{ body{padding:14mm} @page{size:A4; margin:0} }
</style></head><body>

<div class="cab">
  <div>
    <div class="cab-izq">${marca}
      <div><p class="n1">Métodos Mixtos Consultores</p>
      <p class="n2">Prospección solar · ${perfil}</p></div>
    </div>
    <h1>Grilla ${g.id}</h1>
    <p class="sub">${g.municipio}${g.vereda&&g.vereda!=="Sin dato"?", vereda "+g.vereda:""} · ${g.depto.toLowerCase()}</p>
    <p style="margin:8px 0 0"><span class="chip">${g.clase}</span>
      <span style="color:var(--ink-3); font-size:11px; margin-left:8px">Puesto ${g.ranking} de ${D.length} · ${g.zona}</span></p>
  </div>
  <div class="idx">${g.clase==="Excluida"?'<b>—</b><span>excluida</span>'
    :`<b>${g.indice.toFixed(0)}</b><span>índice / 100</span>`}</div>
</div>

<div class="cols">
  <div>
    <h2>Situación</h2>
    ${mapaSituacion(g)}
    ${SAT[g.id] ? '<h2 style="margin-top:14px">Cómo se ve</h2>' + vistaSatelital(g, 400) : ""}
    <div class="datos" style="grid-template-columns:1fr 1fr">
      <div class="dato"><div class="dk">Coordenadas</div><div class="dv" style="font-size:11px">${g.lat.toFixed(5)}, ${g.lon.toFixed(5)}</div></div>
      <div class="dato"><div class="dk">Superficie</div><div class="dv">25 <small>km²</small></div></div>
    </div>
  </div>
  <div>
    <h2>Criterios de aptitud</h2>
    <table><thead><tr><th>Criterio</th><th class="num">Valor</th>
      <th class="num">Límite / objetivo</th><th class="num">Nota</th><th></th></tr></thead>
      <tbody>${filas}</tbody></table>
  </div>
</div>

<h2>Potencial estimado</h2>
<div class="datos">
  <div class="dato"><div class="dk">Hectáreas aptas</div><div class="dv">${fmt(g.ha)} <small>ha</small></div></div>
  <div class="dato"><div class="dk">Potencial indicativo</div><div class="dv">${fmt(g.mwp)} <small>MWp</small></div></div>
  <div class="dato"><div class="dk">Energía anual</div><div class="dv">${fmt(g.gwh)} <small>GWh</small></div></div>
</div>

<h2>Qué hay en el suelo</h2>
<div class="datos">
  <div class="dato"><div class="dk">Bosque</div><div class="dv">${fmt(g.bosque,0)}<small>%</small></div></div>
  <div class="dato"><div class="dk">Cultivos</div><div class="dv">${fmt(g.cultivos,0)}<small>%</small></div></div>
  <div class="dato"><div class="dk">Área construida</div><div class="dv">${fmt(g.construido,1)}<small>%</small></div></div>
  <div class="dato"><div class="dk">Agua</div><div class="dv">${g.agua==null?"—":fmt(g.agua,2)+"<small>%</small>"}</div></div>
  <div class="dato"><div class="dk">Dosel arbóreo en 2000</div><div class="dv">${g.bosque_2000==null?"—":fmt(g.bosque_2000,0)+"<small>%</small>"}</div></div>
  <div class="dato"><div class="dk">Cobertura apta</div><div class="dv">${fmt(g.cobertura,0)}<small>%</small></div></div>
</div>

<h2>Recurso solar <span class="h2sub">Global Solar Atlas</span></h2>
<table class="def"><tbody>
  <tr><td class="dn">Producción <b>PVOUT</b></td>
      <td class="dvv">${fmt(g.pvout)} kWh/kWp/año</td>
      <td class="dd">Lo que entrega al año un sistema de 1 kWp. Traduce el recurso a energía vendible.</td></tr>
  <tr><td class="dn">Plano inclinado <b>GTI</b></td>
      <td class="dvv">${g.gti==null?"—":fmt(g.gti)+" kWh/m²"}</td>
      <td class="dd">Irradiación sobre el plano ya inclinado al ángulo óptimo, que es la que ven los paneles fijos.</td></tr>
  <tr><td class="dn">Horizontal <b>GHI</b></td>
      <td class="dvv">${g.ghi==null?"—":fmt(g.ghi)+" kWh/m²"}</td>
      <td class="dd">Irradiación total sobre superficie horizontal. Es la medida estándar del recurso de un sitio.</td></tr>
  <tr><td class="dn">Directa <b>DNI</b></td>
      <td class="dvv">${g.dni==null?"—":fmt(g.dni)+" kWh/m²"}</td>
      <td class="dd">La parte que llega en rayo directo. Alta significa cielo despejado y es la que aprovechan los seguidores.</td></tr>
  <tr><td class="dn">Difusa <b>DIF</b></td>
      <td class="dvv">${g.dif==null?"—":fmt(g.dif)+" kWh/m²"}</td>
      <td class="dd">La parte dispersada por nubes y atmósfera. Alta respecto al total indica cielo cubierto con frecuencia.</td></tr>
  <tr><td class="dn">Inclinación óptima</td>
      <td class="dvv">${g.opta==null?"—":fmt(g.opta,1)+"°"}</td>
      <td class="dd">Ángulo al que montar los paneles fijos para captar el máximo anual.</td></tr>
  <tr><td class="dn">Temperatura</td>
      <td class="dvv">${fmt(g.temp,1)} °C</td>
      <td class="dd">Media del aire. Los paneles pierden del orden de 0,4% de rendimiento por cada grado.</td></tr>
</tbody></table>

<h2>Entorno socioeconómico</h2>
<table class="def"><tbody>
  <tr><td class="dn">Privación relativa <b>GRDI</b></td>
      <td class="dvv">${g.depriv==null?"—":fmt(g.depriv,1)+" / 100"}</td>
      <td class="dd">Índice global de privación de SEDAC, donde 100 es la mayor privación. Combina dependencia
        infantil, mortalidad infantil, desarrollo humano subnacional, luces nocturnas y densidad de construcción.</td></tr>
  <tr><td class="dn">Densidad de población</td>
      <td class="dvv">${g.pobl==null?"—":fmt(g.pobl,0)+" hab/km²"}</td>
      <td class="dd">Habitantes por kilómetro cuadrado dentro de la grilla.</td></tr>
  <tr><td class="dn">Tiempo a ciudad</td>
      <td class="dvv">${g.viaje==null?"—":fmt(g.viaje,0)+" min"}</td>
      <td class="dd">Viaje por tierra hasta la ciudad más cercana. Pesa en la logística de obra y en conseguir mano de obra.</td></tr>
</tbody></table>

<h2>Conexión</h2>
<div class="datos">
  <div class="dato"><div class="dk">Subestación</div><div class="dv" style="font-size:11px">${g.subestacion}</div></div>
  <div class="dato"><div class="dk">Tensión</div><div class="dv">${g.tension?fmt(g.tension)+" <small>kV</small>":"—"}</div></div>
  <div class="dato"><div class="dk">Capacidad en barra</div><div class="dv">${capacidad(g)==null?"—":fmt(capacidad(g),0)+" <small>MW</small>"}</div></div>
  <div class="dato"><div class="dk">Operador de red</div><div class="dv" style="font-size:11px">${g.operador}</div></div>
</div>

<h2>Restricciones y advertencias</h2>
<div class="aviso">${g.motivo}</div>
${g.restricciones && g.restricciones!=="Sin restricción registrada"
  ? `<div class="aviso"><b>Figura jurídica.</b> ${g.restricciones}</div>` : ""}
${g.ley2>0 ? `<div class="aviso"><b>Reserva Forestal de Ley 2ª.</b> Cubre el ${g.ley2.toFixed(0)}%
  de la grilla. El lote debe ubicarse fuera del polígono o tramitar sustracción ante el MADS.</div>` : ""}
${g.conf_n>0 ? `<div class="aviso"><b>Conflicto armado.</b> ${g.conf_n} acciones bélicas en el
  municipio desde 2022, ${g.conf_d.toFixed(1)} por mil km².${g.conf_act?" Actores: "+g.conf_act+".":""}</div>` : ""}

<div class="pie">
  <span>Métodos Mixtos Consultores · ficha generada el ${hoy}</span>
  <span>Los umbrales se calibran contra las plantas solares en operación en Colombia. La capacidad en barra
  es el techo físico del nodo según la UPME, no un cupo comprometido.</span>
</div>
</body></html>`);
  w.document.close();
  w.focus();
  setTimeout(()=>w.print(), 350);
}

// --- leyenda segun modo ---
function leyenda(){
  const el=document.getElementById("leyenda");
  if(modoColor==="rad"){
    el.innerHTML='<h3>Producción fotovoltaica</h3>'+
      '<div class="ramp"><span style="background:var(--rad1)"></span><span style="background:var(--rad2)"></span>'+
      '<span style="background:var(--rad3)"></span><span style="background:var(--rad4)"></span>'+
      '<span style="background:var(--rad5)"></span></div>'+
      '<div class="ramp-lab"><span>'+PVMIN.toFixed(0)+'</span><span>kWh/kWp/año</span><span>'+PVMAX.toFixed(0)+'</span></div>';
  } else if(modoColor==="clase"){
    const c={Preferente:0,Viable:0,"Con reparos":0}; D.forEach(g=>c[g.clase]++);
    el.innerHTML='<h3>Clasificación</h3>'+Object.keys(c).map(k=>
      '<div class="legend-row"><span class="sw" style="background:'+COLCLASE[k]+'"></span>'+k+' · '+c[k]+'</div>').join("");
  } else {
    el.innerHTML='<h3>Zonas de prospección</h3>'+ZONAS.slice(0,10).map(z=>
      '<div class="legend-row"><span class="sw" style="background:'+zonaColor[z.zona]+'"></span>'+
      z.zona+' · '+z.depto.toLowerCase()+' · '+z.grillas+'</div>').join("")+
      '<div class="legend-row"><span class="sw" style="background:var(--ink-3)"></span>Aisladas</div>';
  }
  // Leyenda de las capas encendidas, para que los colores nuevos no queden sin explicar
  const capas=[];
  if(document.getElementById("subs").classList.contains("on"))
    capas.push('<div class="legend-row"><span class="sw" style="background:var(--accent);opacity:.75"></span>Subestación del SIN · '+SUBES.length+'</div>');
  if(document.getElementById("lineas").classList.contains("on")){
    capas.push('<div class="legend-row"><span class="ln" style="background:var(--bad)"></span>Línea de 220 kV o más</div>');
    capas.push('<div class="legend-row"><span class="ln" style="background:var(--accent-2)"></span>Línea de 50 a 220 kV</div>');
  }
  if(capas.length) el.innerHTML += '<h3 style="margin-top:15px">Capas activas</h3>'+capas.join("");
}

// --- filtros y tabla ---
let fClase="todas", fDep="", fOp="", fZona="", sortK="ranking", sortD="asc", selId=null, modoColor="rad";
const selDep=document.getElementById("fdep"), selOp=document.getElementById("fop"), selZ=document.getElementById("fzona");
[...new Set(D.map(g=>g.depto))].sort().forEach(v=>selDep.add(new Option(v,v)));
[...new Set(D.map(g=>g.operador))].sort().forEach(v=>selOp.add(new Option(v.length>36?v.slice(0,34)+"…":v,v)));
[...new Set(D.map(g=>g.zona))].sort().forEach(v=>selZ.add(new Option(v,v)));

function visibles(){
  return D.filter(g=>(fClase==="todas"||g.clase===fClase)&&(!fDep||g.depto===fDep)
                   &&(!fOp||g.operador===fOp)&&(!fZona||g.zona===fZona));
}

function render(){
  const v=visibles().slice().sort((a,b)=>{
    let x=a[sortK],y=b[sortK];
    if(x==null)x=-Infinity; if(y==null)y=-Infinity;
    if(typeof x==="string") return sortD==="asc"?x.localeCompare(y):y.localeCompare(x);
    return sortD==="asc"?x-y:y-x;
  });
  const ids=new Set(v.map(g=>g.id));
  D.forEach(g=>{
    g._el.classList.toggle("off",!ids.has(g.id));
    g._el.setAttribute("fill",colorDe(g));
    g._el.setAttribute("r", g.clase==="Preferente"?6:5);
  });
  document.getElementById("count").textContent=v.length+" de "+D.length+" grillas";
  document.getElementById("tb").innerHTML=v.map(g=>`
   <tr data-id="${g.id}" class="${g.id===selId?"sel":""}">
    <td class="td-chk"><input type="checkbox" class="chk-lote" data-id="${g.id}"
        ${LOTE.has(g.id)?"checked":""} aria-label="Marcar ${g.id} para el lote"></td>
    <td class="num">${g.ranking}</td>
    <td class="id">${g.id}</td>
    <td class="zt">${g.zona}</td>
    <td><span class="pill ${PILL[g.clase]}" title="${g.motivo}">${g.clase}</span></td>
    <td><span class="trunc motivo" title="${g.motivo}">${g.motivo}</span></td>
    <td>${g.depto}</td>
    <td class="num">${g.clase==="Excluida"?"—":`<span class="idx"><span class="idx-t"><span style="width:${g.indice}%"></span></span>${g.indice.toFixed(0)}</span>`}</td>
    <td class="num">${g.clase==="Excluida"?"—":g.cumple+"/"+CLAVES.length}</td>
    <td class="num"><span class="radcell"><span class="radbar" style="background:${radColor(g.pvout)}"></span>${fmt(g.pvout)}</span></td>
    <td class="num">${fmt(g.cobertura,0)}%</td>
    <td class="num">${fmt(g.mwp)}</td>
    <td class="num">${fmt(g.pendiente,1)}°</td>
    <td class="num">${fmt(g.dist_sub,1)}</td>
    <td class="num">${g.via==null?"—":fmt(g.via,2)}</td>
    <td><span class="trunc" title="${g.operador}">${g.operador}</span></td>
   </tr>`).join("");
  // La fila selecciona la grilla, pero la casilla no: si el clic en la casilla llegara
  // a la fila, marcar para el lote abriria la ficha y movería el scroll en cada clic.
  document.querySelectorAll("#tb tr").forEach(tr=>tr.addEventListener("click", ev=>{
    if(ev.target.closest(".td-chk")) return;
    sel(tr.dataset.id);
  }));
  document.querySelectorAll(".chk-lote").forEach(c=>c.addEventListener("change", ev=>{
    ev.stopPropagation();
    if(c.checked) LOTE.add(c.dataset.id); else LOTE.delete(c.dataset.id);
    pintarLote();
  }));
  leyenda();
}

// Reserva Forestal de Ley 2a de 1959. No es una prohibicion como la de un parque: el
// ministerio puede sustraer el area, y un proyecto solar ya cumple el requisito de
// utilidad publica que ese tramite exige. Por eso lo que importa no es que la reserva
// toque la grilla, sino cuanta superficie deja libre para sitiar el lote fuera de ella.
function fichaLey2(g){
  const pct = g.ley2 || 0;
  if(!pct) return "";
  const ha = Math.round(2500 * pct / 100);
  const libre = 2500 - ha;
  const tono = pct >= 90 ? "f-alerta" : "f-aviso";
  return `<div class="f-item f-full ${tono}">
    <div class="f-k">Reserva Forestal de Ley 2ª de 1959</div>
    <div class="f-v sm">Cubre el ${pct.toFixed(pct<10?1:0)}% de la grilla, unas
      ${ha.toLocaleString("es-CO")} ha. Quedan ${libre.toLocaleString("es-CO")} ha fuera
      del polígono${pct>=90?"" : ", suficientes para ubicar el lote sin tramitar sustracción"}.
      ${pct>=90?"No queda superficie utilizable fuera de la reserva." :
        "Si la línea de conexión cruza la reserva, sí requiere sustracción temporal."}</div>
  </div>`;
}

// Acciones belicas del municipio. Va por municipio y no por distancia porque el CNMH
// geocodifica los hechos a un punto de referencia municipal, asi que un radio en
// kilometros seria una precision que el dato no tiene.
function fichaConflicto(g){
  const n = g.conf_n || 0;
  if(!n) return "";
  const d = g.conf_d || 0;
  const fuera = n >= 3 && d >= 3;
  return `<div class="f-item f-full ${fuera?"f-alerta":"f-aviso"}">
    <div class="f-k">Conflicto armado en el municipio</div>
    <div class="f-v sm">${n} ${n===1?"acción bélica registrada":"acciones bélicas registradas"}
      desde 2022, ${d.toFixed(d<10?1:0)} por cada mil km².
      ${g.conf_act?" Actores: "+g.conf_act+".":""}
      ${fuera?" Supera los dos umbrales, la grilla queda descartada."
             :" Por debajo del umbral que descarta, se reporta como contexto."}</div>
  </div>`;
}

function sel(id){
  selId=id;
  const g=D.find(x=>x.id===id);
  D.forEach(o=>o._el.classList.toggle("sel",o.id===id));
  document.querySelectorAll("#tb tr").forEach(tr=>tr.classList.toggle("sel",tr.dataset.id===id));
  // Con /maps/@lat,lon el mapa se centra pero no marca nada, y quedaba la duda de cual
  // es el punto entre todo lo que se ve. La forma con marcador es search/?api=1&query,
  // que deja un pin en la coordenada exacta del centroide de la grilla.
  const cc = g.lat.toFixed(6)+","+g.lon.toFixed(6);
  const maps="https://www.google.com/maps/search/?api=1&query="+cc;
  const earth="https://earth.google.com/web/search/"+cc+"/@"+cc+",3000a,0d,0y,0h,0t,0r";
  document.getElementById("ficha").innerHTML=`
    <div class="f-head"><h3 style="margin:0">Ficha de la grilla</h3>
      <button class="f-cerrar" id="fCerrar" title="Cerrar la ficha" aria-label="Cerrar">×</button></div>
    <div class="f-top"><span class="f-id mono">${g.id}</span><span class="f-rank">Puesto ${g.ranking} · ${g.zona}</span></div>
    <div class="f-loc">${g.municipio}${g.vereda&&g.vereda!=="Sin dato"?", vereda "+g.vereda:""} · ${g.depto.toLowerCase()}</div>
    <div class="f-idx-row">
      <span class="pill ${PILL[g.clase]}">${g.clase}</span>
      ${g.clase==="Excluida"?"":`<span class="f-idx"><b>${g.indice.toFixed(0)}</b><small>/100 índice</small></span>`}
    </div>
    <p class="f-motivo">${g.motivo}</p>
    <div class="f-sec">Criterios que deciden <span>${g.cumple} de ${CLAVES.length}</span></div>
    <div class="f-grid">
      <div class="f-item f-full"><div class="f-k">Figura jurídica</div><div class="f-v sm">${g.restricciones}</div></div>
      ${fichaConflicto(g)}
      ${fichaLey2(g)}
      <div class="f-item"><div class="f-k">A la red</div><div class="f-v">${fmt(g.dist_sub,1)} <small>km</small></div></div>
      <div class="f-item"><div class="f-k">Cobertura apta</div><div class="f-v">${fmt(g.cobertura,0)}<small>%</small></div></div>
      <div class="f-item"><div class="f-k">Pendiente</div><div class="f-v">${fmt(g.pendiente,1)}<small>°</small></div></div>
      <div class="f-item"><div class="f-k">Producción FV</div><div class="f-v">${fmt(g.pvout)} <small>kWh/kWp</small></div></div>
      <div class="f-item"><div class="f-k">Rugosidad</div><div class="f-v">${fmt(g.rugosidad,0)} <small>m</small></div></div>
      <div class="f-item"><div class="f-k">A vía carrozable</div><div class="f-v">${g.via==null?"—":fmt(g.via,2)+" <small>km</small>"}</div></div>
      <div class="f-item f-full"><div class="f-k">Punto de conexión</div><div class="f-v sm">${g.subestacion}${g.tension?" · "+fmt(g.tension)+" kV":""}</div></div>
    </div>

    <div class="f-sec">Potencial estimado</div>
    <div class="f-grid">
      <div class="f-item"><div class="f-k">Hectáreas aptas</div><div class="f-v">${fmt(g.ha)} <small>ha</small></div></div>
      <div class="f-item"><div class="f-k">Potencial</div><div class="f-v">${fmt(g.mwp)} <small>MWp</small></div></div>
      <div class="f-item"><div class="f-k">Energía anual</div><div class="f-v">${fmt(g.gwh)} <small>GWh</small></div></div>
      <div class="f-item"><div class="f-k">Caben</div><div class="f-v">${g.proy20} <small>de 20 MW</small></div></div>
    </div>

    ${SAT[g.id] ? '<div class="f-sec">Cómo se ve <span>imagen satelital</span></div>'
                  + vistaSatelital(g, 400) : ""}

    <div class="f-sec">Qué hay en el suelo <span>explica la cobertura apta</span></div>
    <div class="f-grid">
      <div class="f-item"><div class="f-k">Pastizal</div><div class="f-v">${fmt(100-g.bosque-g.cultivos-g.construido-(g.agua||0),0)}<small>%</small></div></div>
      <div class="f-item"><div class="f-k">Bosque</div><div class="f-v">${fmt(g.bosque,0)}<small>%</small></div></div>
      <div class="f-item"><div class="f-k">Cultivos</div><div class="f-v">${fmt(g.cultivos,0)}<small>%</small></div></div>
      <div class="f-item"><div class="f-k">Área construida</div><div class="f-v">${fmt(g.construido,1)}<small>%</small></div></div>
      <div class="f-item"><div class="f-k">Agua</div><div class="f-v">${g.agua==null?"—":fmt(g.agua,2)+"<small>%</small>"}</div></div>
      <div class="f-item"><div class="f-k">Dosel arbóreo en 2000<small> Hansen</small></div>
        <div class="f-v">${g.bosque_2000==null?"—":fmt(g.bosque_2000,0)+"<small>%</small>"}</div></div>
    </div>
    <p class="f-nota">El bosque de hoy sale de Sentinel-2 y el dosel de 2000 de Hansen. Son
    metodologías distintas, así que la diferencia entre ambos no mide deforestación.</p>

    <div class="f-sec">Recurso solar <span>Global Solar Atlas</span></div>
    <div class="f-grid">
      <div class="f-item" title="Lo que un sistema de 1 kWp entrega al año. Es la traducción del recurso a energía vendible.">
        <div class="f-k">Producción<small> PVOUT</small></div><div class="f-v">${fmt(g.pvout)} <small>kWh/kWp</small></div></div>
      <div class="f-item" title="Irradiación que recibe el plano ya inclinado al ángulo óptimo. Es la que ven los paneles fijos.">
        <div class="f-k">Plano inclinado<small> GTI</small></div><div class="f-v">${g.gti==null?"—":fmt(g.gti)+" <small>kWh/m²</small>"}</div></div>
      <div class="f-item" title="Irradiación total sobre una superficie horizontal. Es la medida estándar del recurso de un sitio.">
        <div class="f-k">Horizontal<small> GHI</small></div><div class="f-v">${g.ghi==null?"—":fmt(g.ghi)+" <small>kWh/m²</small>"}</div></div>
      <div class="f-item" title="La parte del recurso que llega en rayo directo. Alta significa cielo despejado y es la que aprovechan los seguidores.">
        <div class="f-k">Directa<small> DNI</small></div><div class="f-v">${g.dni==null?"—":fmt(g.dni)+" <small>kWh/m²</small>"}</div></div>
      <div class="f-item" title="La parte dispersada por nubes y atmósfera. Alta respecto al total indica cielo cubierto con frecuencia.">
        <div class="f-k">Difusa<small> DIF</small></div><div class="f-v">${g.dif==null?"—":fmt(g.dif)+" <small>kWh/m²</small>"}</div></div>
      <div class="f-item" title="Inclinación a la que hay que montar los paneles fijos para captar el máximo anual.">
        <div class="f-k">Inclinación óptima</div><div class="f-v">${g.opta==null?"—":fmt(g.opta,1)+"<small>°</small>"}</div></div>
      <div class="f-item" title="Temperatura media del aire. Los paneles pierden rendimiento con el calor, del orden de 0,4% por grado.">
        <div class="f-k">Temperatura</div><div class="f-v">${fmt(g.temp,1)}<small>°C</small></div></div>
      <div class="f-item"><div class="f-k">Elevación</div><div class="f-v">${fmt(g.elevacion)} <small>m</small></div></div>
    </div>

    <div class="f-sec">Entorno socioeconómico <span>no clasifica</span></div>
    <div class="f-grid">
      <div class="f-item f-full" title="Índice global de privación relativa de SEDAC, escala 0 a 100, donde 100 es la mayor privación. Combina dependencia infantil, mortalidad infantil, desarrollo humano subnacional, luces nocturnas y densidad de construcción.">
        <div class="f-k">Privación relativa<small> GRDI, 0 a 100</small></div>
        <div class="f-v">${g.depriv==null?"—":fmt(g.depriv,1)+' <small>'+(g.depriv>=70?"alta":(g.depriv>=50?"media":"baja"))+'</small>'}</div></div>
      <div class="f-item" title="Habitantes por kilómetro cuadrado dentro de la grilla.">
        <div class="f-k">Densidad de población</div><div class="f-v">${g.pobl==null?"—":fmt(g.pobl,0)+" <small>hab/km²</small>"}</div></div>
      <div class="f-item" title="Minutos de viaje por tierra hasta la ciudad más cercana. Pesa en la logística de obra y en conseguir mano de obra.">
        <div class="f-k">A ciudad</div><div class="f-v">${g.viaje==null?"—":fmt(g.viaje,0)+" <small>min</small>"}</div></div>
    </div>

    <div class="f-sec">Conexión <span>no clasifica</span></div>
    <div class="f-grid">
      <div class="f-item"><div class="f-k">Capacidad en barra</div>
        <div class="f-v">${capacidad(g)==null?"—":fmt(capacidad(g),0)+" <small>MW</small>"}</div></div>
      <div class="f-item"><div class="f-k">Tensión</div><div class="f-v">${g.tension?fmt(g.tension)+" <small>kV</small>":"—"}</div></div>
      <div class="f-item f-full"><div class="f-k">Operador de red</div><div class="f-v sm">${g.operador}</div></div>
      <div class="f-item f-full"><div class="f-k">Configuración de barras</div><div class="f-v sm">${g.barras}</div></div>
    </div>
    <div class="f-links">
      <button class="btn ghost" id="fZoom">Acercar en el mapa</button>
      <button class="btn ghost" id="fPdf">Ficha técnica en PDF</button>
      <a href="${maps}" target="_blank" rel="noopener">Google Maps</a>
      <a href="${earth}" target="_blank" rel="noopener">Google Earth</a>
      <button class="btn ghost" id="fCoord" title="Copiar ${cc}">Copiar coordenadas</button>
    </div>`;
  document.getElementById("fCoord")?.addEventListener("click", ev=>{
    navigator.clipboard?.writeText(cc);
    ev.target.textContent = "Copiadas: " + cc;
    setTimeout(()=>{ ev.target.textContent = "Copiar coordenadas"; }, 2200);
  });
  document.getElementById("fPdf")?.addEventListener("click", ()=>fichaTecnica(g));
  document.getElementById("fZoom")?.addEventListener("click", ()=>{
    acercarA(g);
    document.getElementById("svgmapa").scrollIntoView({behavior:"smooth", block:"center"});
  });
  document.getElementById("fCerrar")?.addEventListener("click", cerrarFicha);
}

// --- cerrar la ficha ---
function cerrarFicha(){
  selId = null;
  D.forEach(o=>o._el.classList.remove("sel"));
  document.querySelectorAll("#tb tr").forEach(tr=>tr.classList.remove("sel"));
  document.getElementById("ficha").innerHTML =
    '<h3>Ficha de la grilla</h3><p class="empty">Búscala arriba, o toca un punto del ' +
    'mapa o una fila de la tabla.</p>';
}
document.addEventListener("keydown", ev=>{
  if(ev.key==="Escape"){
    if(document.activeElement===cajaBusca && cajaBusca.value){ cajaBusca.value=""; buscar(); }
    else cerrarFicha();
  }
});

// --- buscador ---
// Se busca sobre una cadena precalculada por grilla en vez de recorrer campo por campo:
// con 100 grillas da igual, pero deja el filtrado en una sola pasada y sin acentos, que
// es lo que hace que escribir "bolivar" encuentre "BOLÍVAR".
function sinAcentos(s){
  return (s||"").toString().normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase();
}
D.forEach(g=>{
  // El puesto entra en la cadena de busqueda con y sin almohadilla, para que escribir
  // "7" o "#7" lleve a la septima. Es la forma mas rapida de saltar a una grilla cuando
  // ya se sabe en que posicion quedo.
  g._busca = sinAcentos([g.id, "#"+g.ranking, g.ranking, g.depto, g.municipio, g.vereda,
                         g.sub_municipio, g.zona, g.subestacion, g.operador,
                         g.clase].join(" "));
});

const cajaBusca = document.getElementById("busca");
const cajaRes = document.getElementById("resultados");
const cuenta = document.getElementById("bCuenta");
let marcado = -1;

// Filtros encadenados: cada uno acota los siguientes. Elegir departamento deja en el
// desplegable de municipio solo los de ese departamento, y así hasta vereda. Las
// opciones llevan entre paréntesis cuántas grillas hay, para no elegir a ciegas.
const FILTROS = [
  {id:"fbDepto", campo:"depto",  etiqueta:"Todos los departamentos", depende:null},
  {id:"fbMpio",  campo:"municipio", etiqueta:"Todos los municipios", depende:"fbDepto"},
  {id:"fbVer",   campo:"vereda", etiqueta:"Todas las veredas",       depende:"fbMpio"},
  {id:"fbClase", campo:"clase",  etiqueta:"Todas las clasificaciones", depende:null},
  {id:"fbZona",  campo:"zona",   etiqueta:"Todas las zonas",         depende:null},
];
const elFiltro = {};
FILTROS.forEach(f=>elFiltro[f.id]=document.getElementById(f.id));

function pasaFiltros(g, salvo){
  return FILTROS.every(f=>{
    if(f.id===salvo) return true;
    const v = elFiltro[f.id].value;
    return !v || g[f.campo]===v;
  });
}

function poblar(){
  FILTROS.forEach(f=>{
    const el = elFiltro[f.id];
    const previo = el.value;
    // el universo de cada desplegable respeta los demás filtros, no el suyo propio
    const base = D.filter(g=>pasaFiltros(g, f.id));
    const cuentas = {};
    base.forEach(g=>{
      const v = g[f.campo];
      if(v && v!=="Sin dato") cuentas[v] = (cuentas[v]||0)+1;
    });
    const claves = Object.keys(cuentas).sort((a,b)=>a.localeCompare(b,"es"));
    el.innerHTML = `<option value="">${f.etiqueta}</option>` +
      claves.map(k=>`<option value="${k}">${k} (${cuentas[k]})</option>`).join("");
    // se conserva la selección si sigue teniendo sentido; si no, se suelta
    el.value = claves.includes(previo) ? previo : "";
    el.disabled = claves.length === 0;
  });
}

function resaltar(txt, q){
  if(!q) return txt;
  const i = sinAcentos(txt).indexOf(q);
  if(i < 0) return txt;
  return txt.slice(0,i)+"<mark>"+txt.slice(i,i+q.length)+"</mark>"+txt.slice(i+q.length);
}

function buscar(){
  const q = sinAcentos(cajaBusca.value.trim());
  marcado = -1;
  const activos = FILTROS.filter(f=>elFiltro[f.id].value);
  const hits = D.filter(g=>pasaFiltros(g,null) && (!q || g._busca.includes(q)))
                .sort((a,b)=>b.indice-a.indice);

  if(!q && !activos.length){
    cuenta.innerHTML = "Sin filtros: <b>"+D.length+"</b> grillas. Elige uno o escribe para acotar.";
    cajaRes.innerHTML = "";
    return;
  }

  cuenta.innerHTML = "<b>"+hits.length+"</b> de "+D.length+" grillas" +
    (activos.length ? " · "+activos.length+" filtro"+(activos.length>1?"s":"") : "");

  if(!hits.length){
    cajaRes.innerHTML = '<div class="res-vacio">Ninguna grilla cumple esa combinación.</div>';
    return;
  }
  cajaRes.innerHTML = hits.slice(0,40).map(g=>{
    const loc = [g.municipio, g.depto].filter(x=>x&&x!=="Sin dato").join(", ");
    return `<div class="res" data-id="${g.id}">
      <span class="res-pos">#${g.ranking}</span>
      <span class="res-id">${resaltar(g.id,q)}</span>
      <span class="res-loc">${resaltar(loc,q)}</span>
      <span class="pill ${PILL[g.clase]}">${g.clase}</span>
      <span class="res-idx">${g.clase==="Excluida"?"—":g.indice.toFixed(0)}</span>
    </div>`;
  }).join("") + (hits.length>40
    ? '<div class="res-vacio">y '+(hits.length-40)+' más. Acota con otro filtro.</div>' : "");

  cajaRes.querySelectorAll(".res").forEach(el=>el.addEventListener("click",()=>{
    sel(el.dataset.id);
    document.getElementById("ficha").scrollIntoView({behavior:"smooth", block:"nearest"});
  }));
}

FILTROS.forEach(f=>elFiltro[f.id].addEventListener("change", ()=>{ poblar(); buscar(); }));
document.getElementById("bLimpiar").addEventListener("click", ()=>{
  cajaBusca.value = "";
  FILTROS.forEach(f=>elFiltro[f.id].value = "");
  poblar(); buscar();
});
cajaBusca.addEventListener("input", buscar);
cajaBusca.addEventListener("keydown", ev=>{
  const items = [...cajaRes.querySelectorAll(".res")];
  if(!items.length) return;
  if(ev.key==="ArrowDown" || ev.key==="ArrowUp"){
    ev.preventDefault();
    marcado = (marcado + (ev.key==="ArrowDown"?1:-1) + items.length) % items.length;
    items.forEach((el,i)=>el.classList.toggle("marcado", i===marcado));
    items[marcado].scrollIntoView({block:"nearest"});
  } else if(ev.key==="Enter"){
    ev.preventDefault();
    (items[marcado>=0?marcado:0]).click();
  }
});

// --- controles ---
document.querySelectorAll(".chip[data-f]").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll(".chip[data-f]").forEach(o=>o.setAttribute("aria-pressed","false"));
  b.setAttribute("aria-pressed","true"); fClase=b.dataset.f; render();
}));
document.querySelectorAll(".chip[data-color]").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll(".chip[data-color]").forEach(o=>o.setAttribute("aria-pressed","false"));
  b.setAttribute("aria-pressed","true"); modoColor=b.dataset.color; render();
}));
selDep.addEventListener("change",e=>{fDep=e.target.value; render();});
selOp.addEventListener("change",e=>{fOp=e.target.value; render();});
selZ.addEventListener("change",e=>{fZona=e.target.value; render();});
document.querySelectorAll("th[data-k]").forEach(th=>th.addEventListener("click",()=>{
  const k=th.dataset.k;
  if(sortK===k){sortD=sortD==="asc"?"desc":"asc";}else{sortK=k;sortD="asc";}
  document.querySelectorAll("th").forEach(o=>o.removeAttribute("data-dir"));
  th.setAttribute("data-dir",sortD); render();
}));

document.getElementById("reset").addEventListener("click",()=>{
  CLAVES.forEach(k=>{ U[k].bueno=CRIT[k].bueno; U[k].limite=CRIT[k].limite; });
  reclasificar(); render();
});

document.getElementById("exportar").addEventListener("click",()=>{
  const cols=[["ranking","Ranking"],["id","Grilla"],["zona","Zona"],["clase","Clasificacion"],
    ["motivo","Motivo"],["depto","Departamento"],["municipio","Municipio subestacion"],
    ["pvout","Produccion FV kWh/kWp/ano"],["gti","GTI"],["mwp","MWp indicativo"],["ha","Hectareas aptas"],
    ["gwh","GWh ano"],["pendiente","Pendiente grados"],["elevacion","Elevacion m"],
    ["dist_sub","Km a subestacion"],["via","Km a via"],["via_pri","Km a via principal"],
    ["subestacion","Subestacion"],["tension","kV"],["barras","Configuracion barras"],
    ["operador","Operador"],["restricciones","Restricciones"],
    ["ley2","Reserva Ley 2a pct de la grilla"],["lat","Latitud"],["lon","Longitud"]];
  const esc=v=>{ if(v==null) return ""; const s=String(v); return /[";\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s; };
  const filas=[cols.map(c=>c[1]).join(";")];
  visibles().forEach(g=>filas.push(cols.map(c=>esc(g[c[0]])).join(";")));
  // El BOM se construye por código y no se escribe como carácter invisible, que se
  // pierde al pasar por el generador. Sin BOM, Excel en español abre el CSV en ANSI
  // y destroza las tildes.
  const BOM=String.fromCharCode(0xFEFF);
  const blob=new Blob([BOM+filas.join("\r\n")],{type:"text/csv;charset=utf-8;"});
  const a=document.createElement("a");
  a.href=URL.createObjectURL(blob);
  a.download="grillas_seleccion.csv";
  a.click(); URL.revokeObjectURL(a.href);
});

// --- comparador de dos grillas ---
// Las filas de criterio marcan quién gana; las de contexto solo informan, porque en
// elevación o temperatura no hay un "mejor" que se pueda declarar sin discutirlo.
const FILAS_COMP = [
  {sep:"Resultado"},
  {k:"indice",  lab:"Índice de aptitud",      dec:0, mayor:true,  suf:"/100"},
  {k:"cumple",  lab:"Criterios cumplidos",    dec:0, mayor:true,  suf:"/"+CLAVES.length},
  {sep:"Criterios que deciden"},
  {k:"dist_sub", lab:"Distancia al punto de conexión", nota:"peso 0,79", dec:1, mayor:false, suf:" km"},
  {k:"cobertura",lab:"Cobertura apta del suelo",       nota:"peso 0,73", dec:0, mayor:true,  suf:" %"},
  {k:"pendiente",lab:"Pendiente media",                nota:"peso 0,69", dec:1, mayor:false, suf:"°"},
  {k:"pvout",    lab:"Producción fotovoltaica",        nota:"peso 0,66", dec:0, mayor:true,  suf:" kWh/kWp"},
  {k:"rugosidad",lab:"Rugosidad del relieve",          nota:"peso 0,57", dec:0, mayor:false, suf:" m"},
  {k:"via",      lab:"Distancia a vía carrozable",     nota:"peso 0,45", dec:2, mayor:false, suf:" km"},
  {sep:"Potencial estimado"},
  {k:"ha",     lab:"Hectáreas aptas",   dec:0, mayor:true, suf:" ha"},
  {k:"mwp",    lab:"Potencial",         dec:0, mayor:true, suf:" MWp"},
  {k:"gwh",    lab:"Energía anual",     dec:0, mayor:true, suf:" GWh"},
  {k:"proy20", lab:"Proyectos de 20 MW que caben", dec:0, mayor:true, suf:""},
  {sep:"Contexto"},
  {k:"elevacion", lab:"Elevación",   dec:0, suf:" m"},
  {k:"temp",      lab:"Temperatura", dec:1, suf:" °C"},
  {k:"depto",      lab:"Departamento",   texto:true},
  {k:"zona",       lab:"Zona",           texto:true},
  {k:"subestacion",lab:"Subestación",    texto:true},
  {k:"operador",   lab:"Operador de red",texto:true},
  {k:"barras",     lab:"Configuración de barras", texto:true},
  {k:"restricciones", lab:"Figura jurídica", texto:true},
  {k:"ley2",       lab:"Reserva Ley 2ª",  dec:0, mayor:false, suf:" %"},
];

function celdaComp(g, f, otro){
  if(f.texto) return `<td class="dato texto">${g[f.k] ?? "—"}</td>`;
  const v = g[f.k], w = otro[f.k];
  if(v==null) return `<td class="dato comp-empate">—</td>`;
  let gana = false;
  if(f.mayor!==undefined && w!=null && v!==w) gana = f.mayor ? v>w : v<w;
  const txt = Number(v).toFixed(f.dec)+f.suf;
  // barra relativa al mayor de los dos, para ver la diferencia de un vistazo
  let barra = "";
  if(f.mayor!==undefined && w!=null){
    const tope = Math.max(Math.abs(v), Math.abs(w)) || 1;
    barra = `<div class="comp-bar"><span style="width:${Math.abs(v)/tope*100}%"></span></div>`;
  }
  return `<td class="dato${gana?" gana":""}">${txt}${barra}</td>`;
}

function pintarComparador(){
  const a = D.find(g=>g.id===document.getElementById("cmpA").value);
  const b = D.find(g=>g.id===document.getElementById("cmpB").value);
  if(!a||!b){ document.getElementById("comparador").innerHTML=""; return; }

  const filas = FILAS_COMP.map(f=>{
    if(f.sep) return `<tr class="sep"><td colspan="3">${f.sep}</td></tr>`;
    const clase = f.k==="indice" ? " total" : "";
    return `<tr class="${clase.trim()}">
      <td class="var">${f.lab}${f.nota?`<small>${f.nota}</small>`:""}</td>
      ${celdaComp(a,f,b)}${celdaComp(b,f,a)}</tr>`;
  }).join("");

  const cab = g => `<th class="lado"><span class="pill ${PILL[g.clase]}">${g.clase}</span><br>
    <span style="font-family:'Cascadia Mono',monospace">${g.id}</span>
    <small>puesto ${g.ranking} · ${g.depto.toLowerCase()}</small></th>`;

  document.getElementById("comparador").innerHTML = `<table class="comp">
    <thead><tr><th></th>${cab(a)}${cab(b)}</tr></thead><tbody>${filas}</tbody></table>`;
}

(function initComparador(){
  const sa=document.getElementById("cmpA"), sb=document.getElementById("cmpB");
  const orden = D.slice().sort((x,y)=>x.ranking-y.ranking);
  orden.forEach(g=>{
    const et = `#${g.ranking} · ${g.id} · ${g.depto.toLowerCase()} · ${g.clase}`;
    sa.add(new Option(et,g.id)); sb.add(new Option(et,g.id));
  });
  // arranca comparando la mejor con la siguiente de otra zona, que es más informativo
  sa.value = orden[0].id;
  const otra = orden.find(g=>g.zona!==orden[0].zona) || orden[1];
  sb.value = otra.id;
  sa.addEventListener("change",pintarComparador);
  sb.addEventListener("change",pintarComparador);
  document.getElementById("cmpSwap").addEventListener("click",()=>{
    const t=sa.value; sa.value=sb.value; sb.value=t; pintarComparador();
  });
  pintarComparador();   // sin esta llamada la tabla arranca vacía
})();

// --- botonera del lote de predios ---
(function lotePredios(){
  const btn = (id, fn) => document.getElementById(id)?.addEventListener("click", fn);
  btn("loteVisibles", ()=>{ visibles().forEach(g=>LOTE.add(g.id)); render(); pintarLote(); });
  btn("loteTop10", ()=>{
    [...D].filter(g=>g.clase!=="Excluida").sort((a,b)=>a.ranking-b.ranking)
      .slice(0,10).forEach(g=>LOTE.add(g.id));
    render(); pintarLote();
  });
  btn("loteLimpiar", ()=>{ LOTE.clear(); render(); pintarLote(); });
  btn("loteGeojson", exportarLoteGeojson);
  btn("loteCsv", exportarLoteCsv);
  pintarLote();
})();

// Estado inicial del perfil. Va al final, cuando ya existen la botonera, la matriz y
// el comparador, para que la primera clasificacion los alcance a todos.
aplicarPerfil(PERFIL);

// --- tarjetas de zona -------------------------------------------------------------
// Se pintan en JS y no en el HTML de partida porque tienen que rehacerse al cambiar de
// perfil o de umbral: cuales son las prioritarias de cada zona depende de eso.
function pintarZonas(){
  const cont = document.getElementById("zonasCards");
  if(!cont) return;
  const vivas = D.filter(g=>g.clase!=="Excluida");
  const porZona = {};
  vivas.forEach(g=>{ (porZona[g.zona] = porZona[g.zona] || []).push(g); });

  // Se ordenan por el potencial de sus prioritarias y no por numero de grillas: una zona
  // de tres grillas con las tres en lista corta vale mas que una de doce sin ninguna.
  const zonas = Object.entries(porZona)
    .filter(([z])=>z!=="Aislada")
    .map(([z,gs])=>{
      const pri = gs.filter(g=>g.clase==="Prioritaria").sort((a,b)=>b.indice-a.indice);
      return {zona:z, gs, pri,
              mwp: gs.reduce((s,g)=>s+(g.mwp||0),0),
              ha:  gs.reduce((s,g)=>s+(g.ha||0),0),
              mwpPri: pri.reduce((s,g)=>s+(g.mwp||0),0),
              depto: moda(gs.map(g=>g.depto)),
              operador: moda(gs.map(g=>g.operador)),
              pvout: gs.reduce((s,g)=>s+(g.pvout||0),0)/gs.length,
              km: gs.reduce((s,g)=>s+(g.dist_sub||0),0)/gs.length};
    })
    .sort((a,b)=> (b.pri.length - a.pri.length) || (b.mwp - a.mwp));

  const maxMwp = Math.max(...zonas.map(z=>z.mwp), 1);
  const sueltas = porZona["Aislada"] || [];

  cont.innerHTML = zonas.slice(0,9).map(z=>`
    <div class="zona">
      <div class="zona-top"><span class="zona-id">${z.zona}</span>
        <span class="zona-mwp">${fmt(z.mwp)}<small> MWp</small></span></div>
      <div class="zona-dep">${z.depto ? z.depto.toLowerCase() : ""}</div>
      <div class="zona-datos">
        <span><b>${z.gs.length}</b> grillas</span>
        <span><b>${fmt(z.ha)}</b> ha aptas</span>
        <span><b>${fmt(z.pvout)}</b> kWh/kWp</span>
        <span><b>${fmt(z.km,1)}</b> km a la red</span>
      </div>
      ${z.pri.length
        ? `<div class="zona-pri"><div class="zona-pri-t">${z.pri.length}
             ${z.pri.length===1?"prioritaria":"prioritarias"} · ${fmt(z.mwpPri)} MWp</div>
           <div class="zona-chips">${z.pri.slice(0,6).map(g=>
             `<button class="zchip" data-id="${g.id}" title="${g.municipio}, índice ${g.indice.toFixed(0)}">
                #${g.ranking}<small>${g.indice.toFixed(0)}</small></button>`).join("")}
             ${z.pri.length>6?`<span class="zchip-mas">+${z.pri.length-6}</span>`:""}</div></div>`
        : '<div class="zona-pri sin">Ninguna en lista corta</div>'}
      <div class="zona-op" title="${z.operador}">${z.operador}</div>
      <div class="zona-bar" title="Potencial de la zona frente a la mayor: ${fmt(z.mwp)} de ${fmt(maxMwp)} MWp">
        <span style="width:${z.mwp/maxMwp*100}%"></span></div>
      <div class="zona-bar-lab">potencial frente a la mayor zona</div>
    </div>`).join("")
    + (sueltas.length ? `
    <div class="zona zona-sueltas">
      <div class="zona-top"><span class="zona-id">Aisladas</span>
        <span class="zona-mwp">${fmt(sueltas.reduce((s,g)=>s+(g.mwp||0),0))}<small> MWp</small></span></div>
      <div class="zona-dep">sin zona</div>
      <div class="zona-datos"><span><b>${sueltas.length}</b> grillas</span>
        <span><b>${sueltas.filter(g=>g.clase==="Prioritaria").length}</b> prioritarias</span></div>
      <p class="zona-nota">Sin otra candidata a menos de 20 km. No dice nada de su calidad:
      significa que su prospección no comparte costos con ninguna vecina.</p>
    </div>` : "");

  cont.querySelectorAll(".zchip").forEach(b=>b.addEventListener("click", ()=>{
    sel(b.dataset.id);
    document.getElementById("ficha").scrollIntoView({behavior:"smooth", block:"center"});
  }));
}

function moda(xs){
  const c={}; xs.forEach(x=>{ if(x) c[x]=(c[x]||0)+1; });
  return Object.keys(c).sort((a,b)=>c[b]-c[a])[0] || "";
}


// Primera pasada: reclasificar deja además pintada la matriz y el reparto, que son
// los que dependen de los umbrales vigentes.
reclasificar();
render();
poblar(); buscar();   // deja los desplegables cargados y el contador con el total
</script>
"""
