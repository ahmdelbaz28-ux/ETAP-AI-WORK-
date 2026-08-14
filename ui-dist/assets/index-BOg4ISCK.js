const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/Dashboard-CvYfdE1t.js","assets/rolldown-runtime-B0Z9INg1.js","assets/animation-vendor-CEItwqGc.js","assets/react-vendor-DLxfWmdq.js","assets/charts-vendor-9spKy9jJ.js","assets/ui-BoP_rEFt.js","assets/ContextHelpButton-gr8A7QaN.js","assets/studyCategories-H5lFewEM.js","assets/Studies-CLBl7QZ1.js","assets/GridEditor-BsDDvvZ6.js","assets/api-config-DyvswGew.js","assets/StudyRun-BtZgWjyK.js","assets/AssetManagement-Ce8DTCVA.js","assets/ModalHeader-Sb9N9LBd.js","assets/AIAssistant-cYyrnaXf.js","assets/Settings-CWTlEd1V.js","assets/Projects-CB3dFVri.js","assets/VisionKeys-CCblJxQd.js","assets/GuardReview-2gxT_k0v.js","assets/AgentMetrics-CIgT7LLr.js","assets/AuditLogs-CTfoD7fN.js","assets/EtapIntegration-CoZbO5Nv.js","assets/GisIntegration-DCaQY6Pi.js","assets/ScadaIntegration-nIdDyoYv.js","assets/Reports-Db1YWUsO.js","assets/Administration-A-2Z-YPt.js","assets/Diagnostics-Dtj-y2Ud.js","assets/DigitalTwin-B0pAU2c9.js","assets/DataImport-JVu88pMJ.js","assets/DataExport-Bxm7t7bG.js","assets/Logs-DvJSwUuT.js","assets/CuaMonitor-DzJU_xGJ.js","assets/CodeGuard-CMCru6eG.js","assets/ContextEngine-D27Jra0r.js","assets/Templates-BmeDxf7u.js","assets/AssetLibrary-C3P96iZz.js","assets/RbacAdmin-DlhiZrde.js","assets/EquipmentManagement-hNIrWPAW.js","assets/EmailDashboard-neDe4qX7.js","assets/EmailWebhooks-3PWPxbiS.js","assets/EmailDigest-D1lwkBdO.js","assets/admin-fetch-CQ1cuBDB.js","assets/StudyVersions-CgHzCj1o.js","assets/EmailOtp-CHbe4FhA.js","assets/AIPlayground-BmuUCAVw.js","assets/MagicLinks-3zBGme3S.js","assets/Mfa-BX33TrtN.js","assets/AgentsControlPanel-OzfJIBKU.js","assets/Login-DFAAq8CE.js","assets/Register-DscMU31y.js"])))=>i.map(i=>d[i]);
import{a as e}from"./rolldown-runtime-B0Z9INg1.js";import{i as t,n,r,t as i}from"./animation-vendor-CEItwqGc.js";import{$n as a,$t as o,An as s,C as c,Ct as l,Dt as u,E as d,En as f,Et as p,Fn as m,H as h,Hn as g,Ht as _,In as v,It as y,Jt as b,Kn as x,Kt as S,Ln as ee,Lt as C,Mn as w,Mt as T,N as te,Nt as E,O as ne,P as D,Pt as re,Q as O,Qn as k,Rt as ie,Sn as A,St as ae,T as j,Tn as oe,Tt as se,U as ce,V as le,Vt as ue,Wt as de,X as fe,Y as M,Yn as pe,Yt as me,Zn as N,_n as he,_t as ge,ar as P,bn as _e,bt as ve,dt as ye,er as F,fn as be,ft as xe,gn as Se,gt as Ce,in as we,j as Te,jt as Ee,ln as De,nr as Oe,nt as I,on as ke,or as Ae,ot as je,q as Me,qn as Ne,rr as Pe,rt as Fe,sn as Ie,sr as Le,st as Re,tn as ze,tr as Be,un as Ve,vt as He,w as Ue,wn as L,wt as We,xn as Ge,xt as Ke,yn as qe}from"./react-vendor-DLxfWmdq.js";import{d as Je}from"./charts-vendor-9spKy9jJ.js";import{r as Ye,t as R}from"./api-config-DyvswGew.js";import{n as Xe,t as Ze}from"./i18n-vendor-DO4EARL9.js";(function(){let e=document.createElement(`link`).relList;if(e&&e.supports&&e.supports(`modulepreload`))return;for(let e of document.querySelectorAll(`link[rel="modulepreload"]`))n(e);new MutationObserver(e=>{for(let t of e)if(t.type===`childList`)for(let e of t.addedNodes)e.tagName===`LINK`&&e.rel===`modulepreload`&&n(e)}).observe(document,{childList:!0,subtree:!0});function t(e){let t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),t.credentials=e.crossOrigin===`use-credentials`?`include`:e.crossOrigin===`anonymous`?`omit`:`same-origin`,t}function n(e){if(e.ep)return;e.ep=!0;let n=t(e);fetch(e.href,n)}})();var z=e(t(),1),Qe=Le(),B=r(),$e={dashboard:`sidebar.dashboard`,studies:`sidebar.studies`,assistant:`sidebar.assistant`,projects:`sidebar.projects`,"vision-keys":`sidebar.visionKeys`,"guard-review":`sidebar.guardReview`,"agent-metrics":`sidebar.agentMetrics`,"audit-logs":`sidebar.auditLogs`,etap:`sidebar.etapIntegration`,gis:`sidebar.gisIntegration`,"digital-twin":`sidebar.digitalTwin`,"asset-management":`sidebar.assetManagement`,reports:`sidebar.reports`,"data-import":`sidebar.dataImport`,"data-export":`sidebar.dataExport`,settings:`sidebar.settings`,admin:`sidebar.administration`,diagnostics:`sidebar.diagnostics`,logs:`sidebar.logs`,"code-guard":`sidebar.codeGuard`,"dual-control":`sidebar.dualControl`};function et({path:e}){let{t}=P(),n=e.split(`/`).filter(Boolean);return n.length===0?null:(0,B.jsxs)(`nav`,{className:`flex items-center gap-1.5 text-xs text-[var(--text-muted)] mb-4`,"aria-label":`Breadcrumb`,children:[(0,B.jsx)(ie,{className:`w-3.5 h-3.5`}),(0,B.jsx)(L,{className:`w-3 h-3 opacity-50`}),n.map((e,r)=>{let i=r===n.length-1,a=$e[e],o=n.slice(0,r+1).join(`/`);return(0,B.jsxs)(`span`,{className:`flex items-center gap-1.5`,children:[(0,B.jsx)(`span`,{className:i?`text-[var(--text-secondary)] font-medium`:``,children:a?t(a):e.replaceAll(`-`,` `)}),!i&&(0,B.jsx)(L,{className:`w-3 h-3 opacity-50`})]},o)})]})}var V=`authToken`,tt=`refreshToken`;function nt(){let e=sessionStorage.getItem(V);if(e)return e;let t=localStorage.getItem(V);return t?(sessionStorage.setItem(V,t),localStorage.removeItem(V),t):null}function rt(){sessionStorage.removeItem(V),localStorage.removeItem(V)}function it(){sessionStorage.removeItem(tt),localStorage.removeItem(tt)}function at(){rt(),it()}var ot=c(e=>({sidebarCollapsed:!1,toggleSidebar:()=>e(e=>({sidebarCollapsed:!e.sidebarCollapsed})),setSidebarCollapsed:t=>e({sidebarCollapsed:t}),mobileSidebarOpen:!1,toggleMobileSidebar:()=>e(e=>({mobileSidebarOpen:!e.mobileSidebarOpen})),setMobileSidebarOpen:t=>e({mobileSidebarOpen:t}),language:localStorage.getItem(`i18nextLng`)||`en`,setLanguage:t=>e({language:t}),searchQuery:``,setSearchQuery:t=>e({searchQuery:t}),commandPaletteOpen:!1,setCommandPaletteOpen:t=>e({commandPaletteOpen:t}),toggleCommandPalette:()=>e(e=>({commandPaletteOpen:!e.commandPaletteOpen})),contextPanelOpen:!1,setContextPanelOpen:t=>e({contextPanelOpen:t}),selectedItem:null,setSelectedItem:t=>e({selectedItem:t,contextPanelOpen:t!==null}),helpPanelOpen:!1,setHelpPanelOpen:t=>e({helpPanelOpen:t}),toggleHelpPanel:()=>e(e=>({helpPanelOpen:!e.helpPanelOpen})),lastError:null,setLastError:t=>e({lastError:t})})),st=`-`,ct=e=>{let t=ft(e),{conflictingClassGroups:n,conflictingClassGroupModifiers:r}=e;return{getClassGroupId:e=>{let n=e.split(st);return n[0]===``&&n.length!==1&&n.shift(),lt(n,t)||dt(e)},getConflictingClassGroupIds:(e,t)=>{let i=n[e]||[];return t&&r[e]?[...i,...r[e]]:i}}},lt=(e,t)=>{if(e.length===0)return t.classGroupId;let n=e[0],r=t.nextPart.get(n),i=r?lt(e.slice(1),r):void 0;if(i)return i;if(t.validators.length===0)return;let a=e.join(st);return t.validators.find(({validator:e})=>e(a))?.classGroupId},ut=/^\[(.+)\]$/,dt=e=>{if(ut.test(e)){let t=ut.exec(e)[1],n=t?.substring(0,t.indexOf(`:`));if(n)return`arbitrary..`+n}},ft=e=>{let{theme:t,prefix:n}=e,r={nextPart:new Map,validators:[]};return gt(Object.entries(e.classGroups),n).forEach(([e,n])=>{pt(n,r,e,t)}),r},pt=(e,t,n,r)=>{e.forEach(e=>{if(typeof e==`string`){let r=e===``?t:mt(t,e);r.classGroupId=n;return}if(typeof e==`function`){if(ht(e)){pt(e(r),t,n,r);return}t.validators.push({validator:e,classGroupId:n});return}Object.entries(e).forEach(([e,i])=>{pt(i,mt(t,e),n,r)})})},mt=(e,t)=>{let n=e;return t.split(st).forEach(e=>{n.nextPart.has(e)||n.nextPart.set(e,{nextPart:new Map,validators:[]}),n=n.nextPart.get(e)}),n},ht=e=>e.isThemeGetter,gt=(e,t)=>t?e.map(([e,n])=>[e,n.map(e=>typeof e==`string`?t+e:typeof e==`object`?Object.fromEntries(Object.entries(e).map(([e,n])=>[t+e,n])):e)]):e,_t=e=>{if(e<1)return{get:()=>void 0,set:()=>{}};let t=0,n=new Map,r=new Map,i=(i,a)=>{n.set(i,a),t++,t>e&&(t=0,r=n,n=new Map)};return{get(e){let t=n.get(e);if(t!==void 0)return t;if((t=r.get(e))!==void 0)return i(e,t),t},set(e,t){n.has(e)?n.set(e,t):i(e,t)}}},vt=`!`,yt=e=>{let{separator:t,experimentalParseClassName:n}=e,r=t.length===1,i=t[0],a=t.length,o=e=>{let n=[],o=0,s=0,c;for(let l=0;l<e.length;l++){let u=e[l];if(o===0){if(u===i&&(r||e.slice(l,l+a)===t)){n.push(e.slice(s,l)),s=l+a;continue}if(u===`/`){c=l;continue}}u===`[`?o++:u===`]`&&o--}let l=n.length===0?e:e.substring(s),u=l.startsWith(vt);return{modifiers:n,hasImportantModifier:u,baseClassName:u?l.substring(1):l,maybePostfixModifierPosition:c&&c>s?c-s:void 0}};return n?e=>n({className:e,parseClassName:o}):o},bt=e=>{if(e.length<=1)return e;let t=[],n=[];return e.forEach(e=>{e[0]===`[`?(t.push(...n.sort(),e),n=[]):n.push(e)}),t.push(...n.sort()),t},xt=e=>({cache:_t(e.cacheSize),parseClassName:yt(e),...ct(e)}),St=/\s+/,Ct=(e,t)=>{let{parseClassName:n,getClassGroupId:r,getConflictingClassGroupIds:i}=t,a=[],o=e.trim().split(St),s=``;for(let e=o.length-1;e>=0;--e){let t=o[e],{modifiers:c,hasImportantModifier:l,baseClassName:u,maybePostfixModifierPosition:d}=n(t),f=!!d,p=r(f?u.substring(0,d):u);if(!p){if(!f){s=t+(s.length>0?` `+s:s);continue}if(p=r(u),!p){s=t+(s.length>0?` `+s:s);continue}f=!1}let m=bt(c).join(`:`),h=l?m+vt:m,g=h+p;if(a.includes(g))continue;a.push(g);let _=i(p,f);for(let e=0;e<_.length;++e){let t=_[e];a.push(h+t)}s=t+(s.length>0?` `+s:s)}return s};function wt(){let e=0,t,n,r=``;for(;e<arguments.length;)(t=arguments[e++])&&(n=Tt(t))&&(r&&(r+=` `),r+=n);return r}var Tt=e=>{if(typeof e==`string`)return e;let t,n=``;for(let r=0;r<e.length;r++)e[r]&&(t=Tt(e[r]))&&(n&&(n+=` `),n+=t);return n};function Et(e,...t){let n,r,i,a=o;function o(o){return n=xt(t.reduce((e,t)=>t(e),e())),r=n.cache.get,i=n.cache.set,a=s,s(o)}function s(e){let t=r(e);if(t)return t;let a=Ct(e,n);return i(e,a),a}return function(){return a(wt.apply(null,arguments))}}var H=e=>{let t=t=>t[e]||[];return t.isThemeGetter=!0,t},Dt=/^\[(?:([a-z-]+):)?(.+)\]$/i,Ot=/^\d+\/\d+$/,kt=new Set([`px`,`full`,`screen`]),At=/^(\d+(\.\d+)?)?(xs|sm|md|lg|xl)$/,jt=/\d+(%|px|r?em|[sdl]?v([hwib]|min|max)|pt|pc|in|cm|mm|cap|ch|ex|r?lh|cq(w|h|i|b|min|max))|\b(calc|min|max|clamp)\(.+\)|^0$/,Mt=/^(rgba?|hsla?|hwb|(ok)?(lab|lch))\(.+\)$/,Nt=/^(inset_)?-?((\d+)?\.?(\d+)[a-z]+|0)_-?((\d+)?\.?(\d+)[a-z]+|0)/,Pt=/^(url|image|image-set|cross-fade|element|(repeating-)?(linear|radial|conic)-gradient)\(.+\)$/,U=e=>Ft(e)||kt.has(e)||Ot.test(e),W=e=>Kt(e,`length`,qt),Ft=e=>!!e&&!Number.isNaN(Number(e)),It=e=>Kt(e,`number`,Ft),Lt=e=>!!e&&Number.isInteger(Number(e)),Rt=e=>e.endsWith(`%`)&&Ft(e.slice(0,-1)),G=e=>Dt.test(e),K=e=>At.test(e),zt=new Set([`length`,`size`,`percentage`]),Bt=e=>Kt(e,zt,Jt),Vt=e=>Kt(e,`position`,Jt),Ht=new Set([`image`,`url`]),Ut=e=>Kt(e,Ht,Xt),Wt=e=>Kt(e,``,Yt),Gt=()=>!0,Kt=(e,t,n)=>{let r=Dt.exec(e);return r?r[1]?typeof t==`string`?r[1]===t:t.has(r[1]):n(r[2]):!1},qt=e=>jt.test(e)&&!Mt.test(e),Jt=()=>!1,Yt=e=>Nt.test(e),Xt=e=>Pt.test(e),Zt=Et(()=>{let e=H(`colors`),t=H(`spacing`),n=H(`blur`),r=H(`brightness`),i=H(`borderColor`),a=H(`borderRadius`),o=H(`borderSpacing`),s=H(`borderWidth`),c=H(`contrast`),l=H(`grayscale`),u=H(`hueRotate`),d=H(`invert`),f=H(`gap`),p=H(`gradientColorStops`),m=H(`gradientColorStopPositions`),h=H(`inset`),g=H(`margin`),_=H(`opacity`),v=H(`padding`),y=H(`saturate`),b=H(`scale`),x=H(`sepia`),S=H(`skew`),ee=H(`space`),C=H(`translate`),w=()=>[`auto`,`contain`,`none`],T=()=>[`auto`,`hidden`,`clip`,`visible`,`scroll`],te=()=>[`auto`,G,t],E=()=>[G,t],ne=()=>[``,U,W],D=()=>[`auto`,Ft,G],re=()=>[`bottom`,`center`,`left`,`left-bottom`,`left-top`,`right`,`right-bottom`,`right-top`,`top`],O=()=>[`solid`,`dashed`,`dotted`,`double`,`none`],k=()=>[`normal`,`multiply`,`screen`,`overlay`,`darken`,`lighten`,`color-dodge`,`color-burn`,`hard-light`,`soft-light`,`difference`,`exclusion`,`hue`,`saturation`,`color`,`luminosity`],ie=()=>[`start`,`end`,`center`,`between`,`around`,`evenly`,`stretch`],A=()=>[``,`0`,G],ae=()=>[`auto`,`avoid`,`all`,`avoid-page`,`page`,`left`,`right`,`column`],j=()=>[Ft,G];return{cacheSize:500,separator:`:`,theme:{colors:[Gt],spacing:[U,W],blur:[`none`,``,K,G],brightness:j(),borderColor:[e],borderRadius:[`none`,``,`full`,K,G],borderSpacing:E(),borderWidth:ne(),contrast:j(),grayscale:A(),hueRotate:j(),invert:A(),gap:E(),gradientColorStops:[e],gradientColorStopPositions:[Rt,W],inset:te(),margin:te(),opacity:j(),padding:E(),saturate:j(),scale:j(),sepia:A(),skew:j(),space:E(),translate:E()},classGroups:{aspect:[{aspect:[`auto`,`square`,`video`,G]}],container:[`container`],columns:[{columns:[K]}],"break-after":[{"break-after":ae()}],"break-before":[{"break-before":ae()}],"break-inside":[{"break-inside":[`auto`,`avoid`,`avoid-page`,`avoid-column`]}],"box-decoration":[{"box-decoration":[`slice`,`clone`]}],box:[{box:[`border`,`content`]}],display:[`block`,`inline-block`,`inline`,`flex`,`inline-flex`,`table`,`inline-table`,`table-caption`,`table-cell`,`table-column`,`table-column-group`,`table-footer-group`,`table-header-group`,`table-row-group`,`table-row`,`flow-root`,`grid`,`inline-grid`,`contents`,`list-item`,`hidden`],float:[{float:[`right`,`left`,`none`,`start`,`end`]}],clear:[{clear:[`left`,`right`,`both`,`none`,`start`,`end`]}],isolation:[`isolate`,`isolation-auto`],"object-fit":[{object:[`contain`,`cover`,`fill`,`none`,`scale-down`]}],"object-position":[{object:[...re(),G]}],overflow:[{overflow:T()}],"overflow-x":[{"overflow-x":T()}],"overflow-y":[{"overflow-y":T()}],overscroll:[{overscroll:w()}],"overscroll-x":[{"overscroll-x":w()}],"overscroll-y":[{"overscroll-y":w()}],position:[`static`,`fixed`,`absolute`,`relative`,`sticky`],inset:[{inset:[h]}],"inset-x":[{"inset-x":[h]}],"inset-y":[{"inset-y":[h]}],start:[{start:[h]}],end:[{end:[h]}],top:[{top:[h]}],right:[{right:[h]}],bottom:[{bottom:[h]}],left:[{left:[h]}],visibility:[`visible`,`invisible`,`collapse`],z:[{z:[`auto`,Lt,G]}],basis:[{basis:te()}],"flex-direction":[{flex:[`row`,`row-reverse`,`col`,`col-reverse`]}],"flex-wrap":[{flex:[`wrap`,`wrap-reverse`,`nowrap`]}],flex:[{flex:[`1`,`auto`,`initial`,`none`,G]}],grow:[{grow:A()}],shrink:[{shrink:A()}],order:[{order:[`first`,`last`,`none`,Lt,G]}],"grid-cols":[{"grid-cols":[Gt]}],"col-start-end":[{col:[`auto`,{span:[`full`,Lt,G]},G]}],"col-start":[{"col-start":D()}],"col-end":[{"col-end":D()}],"grid-rows":[{"grid-rows":[Gt]}],"row-start-end":[{row:[`auto`,{span:[Lt,G]},G]}],"row-start":[{"row-start":D()}],"row-end":[{"row-end":D()}],"grid-flow":[{"grid-flow":[`row`,`col`,`dense`,`row-dense`,`col-dense`]}],"auto-cols":[{"auto-cols":[`auto`,`min`,`max`,`fr`,G]}],"auto-rows":[{"auto-rows":[`auto`,`min`,`max`,`fr`,G]}],gap:[{gap:[f]}],"gap-x":[{"gap-x":[f]}],"gap-y":[{"gap-y":[f]}],"justify-content":[{justify:[`normal`,...ie()]}],"justify-items":[{"justify-items":[`start`,`end`,`center`,`stretch`]}],"justify-self":[{"justify-self":[`auto`,`start`,`end`,`center`,`stretch`]}],"align-content":[{content:[`normal`,...ie(),`baseline`]}],"align-items":[{items:[`start`,`end`,`center`,`baseline`,`stretch`]}],"align-self":[{self:[`auto`,`start`,`end`,`center`,`stretch`,`baseline`]}],"place-content":[{"place-content":[...ie(),`baseline`]}],"place-items":[{"place-items":[`start`,`end`,`center`,`baseline`,`stretch`]}],"place-self":[{"place-self":[`auto`,`start`,`end`,`center`,`stretch`]}],p:[{p:[v]}],px:[{px:[v]}],py:[{py:[v]}],ps:[{ps:[v]}],pe:[{pe:[v]}],pt:[{pt:[v]}],pr:[{pr:[v]}],pb:[{pb:[v]}],pl:[{pl:[v]}],m:[{m:[g]}],mx:[{mx:[g]}],my:[{my:[g]}],ms:[{ms:[g]}],me:[{me:[g]}],mt:[{mt:[g]}],mr:[{mr:[g]}],mb:[{mb:[g]}],ml:[{ml:[g]}],"space-x":[{"space-x":[ee]}],"space-x-reverse":[`space-x-reverse`],"space-y":[{"space-y":[ee]}],"space-y-reverse":[`space-y-reverse`],w:[{w:[`auto`,`min`,`max`,`fit`,`svw`,`lvw`,`dvw`,G,t]}],"min-w":[{"min-w":[G,t,`min`,`max`,`fit`]}],"max-w":[{"max-w":[G,t,`none`,`full`,`min`,`max`,`fit`,`prose`,{screen:[K]},K]}],h:[{h:[G,t,`auto`,`min`,`max`,`fit`,`svh`,`lvh`,`dvh`]}],"min-h":[{"min-h":[G,t,`min`,`max`,`fit`,`svh`,`lvh`,`dvh`]}],"max-h":[{"max-h":[G,t,`min`,`max`,`fit`,`svh`,`lvh`,`dvh`]}],size:[{size:[G,t,`auto`,`min`,`max`,`fit`]}],"font-size":[{text:[`base`,K,W]}],"font-smoothing":[`antialiased`,`subpixel-antialiased`],"font-style":[`italic`,`not-italic`],"font-weight":[{font:[`thin`,`extralight`,`light`,`normal`,`medium`,`semibold`,`bold`,`extrabold`,`black`,It]}],"font-family":[{font:[Gt]}],"fvn-normal":[`normal-nums`],"fvn-ordinal":[`ordinal`],"fvn-slashed-zero":[`slashed-zero`],"fvn-figure":[`lining-nums`,`oldstyle-nums`],"fvn-spacing":[`proportional-nums`,`tabular-nums`],"fvn-fraction":[`diagonal-fractions`,`stacked-fractions`],tracking:[{tracking:[`tighter`,`tight`,`normal`,`wide`,`wider`,`widest`,G]}],"line-clamp":[{"line-clamp":[`none`,Ft,It]}],leading:[{leading:[`none`,`tight`,`snug`,`normal`,`relaxed`,`loose`,U,G]}],"list-image":[{"list-image":[`none`,G]}],"list-style-type":[{list:[`none`,`disc`,`decimal`,G]}],"list-style-position":[{list:[`inside`,`outside`]}],"placeholder-color":[{placeholder:[e]}],"placeholder-opacity":[{"placeholder-opacity":[_]}],"text-alignment":[{text:[`left`,`center`,`right`,`justify`,`start`,`end`]}],"text-color":[{text:[e]}],"text-opacity":[{"text-opacity":[_]}],"text-decoration":[`underline`,`overline`,`line-through`,`no-underline`],"text-decoration-style":[{decoration:[...O(),`wavy`]}],"text-decoration-thickness":[{decoration:[`auto`,`from-font`,U,W]}],"underline-offset":[{"underline-offset":[`auto`,U,G]}],"text-decoration-color":[{decoration:[e]}],"text-transform":[`uppercase`,`lowercase`,`capitalize`,`normal-case`],"text-overflow":[`truncate`,`text-ellipsis`,`text-clip`],"text-wrap":[{text:[`wrap`,`nowrap`,`balance`,`pretty`]}],indent:[{indent:E()}],"vertical-align":[{align:[`baseline`,`top`,`middle`,`bottom`,`text-top`,`text-bottom`,`sub`,`super`,G]}],whitespace:[{whitespace:[`normal`,`nowrap`,`pre`,`pre-line`,`pre-wrap`,`break-spaces`]}],break:[{break:[`normal`,`words`,`all`,`keep`]}],hyphens:[{hyphens:[`none`,`manual`,`auto`]}],content:[{content:[`none`,G]}],"bg-attachment":[{bg:[`fixed`,`local`,`scroll`]}],"bg-clip":[{"bg-clip":[`border`,`padding`,`content`,`text`]}],"bg-opacity":[{"bg-opacity":[_]}],"bg-origin":[{"bg-origin":[`border`,`padding`,`content`]}],"bg-position":[{bg:[...re(),Vt]}],"bg-repeat":[{bg:[`no-repeat`,{repeat:[``,`x`,`y`,`round`,`space`]}]}],"bg-size":[{bg:[`auto`,`cover`,`contain`,Bt]}],"bg-image":[{bg:[`none`,{"gradient-to":[`t`,`tr`,`r`,`br`,`b`,`bl`,`l`,`tl`]},Ut]}],"bg-color":[{bg:[e]}],"gradient-from-pos":[{from:[m]}],"gradient-via-pos":[{via:[m]}],"gradient-to-pos":[{to:[m]}],"gradient-from":[{from:[p]}],"gradient-via":[{via:[p]}],"gradient-to":[{to:[p]}],rounded:[{rounded:[a]}],"rounded-s":[{"rounded-s":[a]}],"rounded-e":[{"rounded-e":[a]}],"rounded-t":[{"rounded-t":[a]}],"rounded-r":[{"rounded-r":[a]}],"rounded-b":[{"rounded-b":[a]}],"rounded-l":[{"rounded-l":[a]}],"rounded-ss":[{"rounded-ss":[a]}],"rounded-se":[{"rounded-se":[a]}],"rounded-ee":[{"rounded-ee":[a]}],"rounded-es":[{"rounded-es":[a]}],"rounded-tl":[{"rounded-tl":[a]}],"rounded-tr":[{"rounded-tr":[a]}],"rounded-br":[{"rounded-br":[a]}],"rounded-bl":[{"rounded-bl":[a]}],"border-w":[{border:[s]}],"border-w-x":[{"border-x":[s]}],"border-w-y":[{"border-y":[s]}],"border-w-s":[{"border-s":[s]}],"border-w-e":[{"border-e":[s]}],"border-w-t":[{"border-t":[s]}],"border-w-r":[{"border-r":[s]}],"border-w-b":[{"border-b":[s]}],"border-w-l":[{"border-l":[s]}],"border-opacity":[{"border-opacity":[_]}],"border-style":[{border:[...O(),`hidden`]}],"divide-x":[{"divide-x":[s]}],"divide-x-reverse":[`divide-x-reverse`],"divide-y":[{"divide-y":[s]}],"divide-y-reverse":[`divide-y-reverse`],"divide-opacity":[{"divide-opacity":[_]}],"divide-style":[{divide:O()}],"border-color":[{border:[i]}],"border-color-x":[{"border-x":[i]}],"border-color-y":[{"border-y":[i]}],"border-color-s":[{"border-s":[i]}],"border-color-e":[{"border-e":[i]}],"border-color-t":[{"border-t":[i]}],"border-color-r":[{"border-r":[i]}],"border-color-b":[{"border-b":[i]}],"border-color-l":[{"border-l":[i]}],"divide-color":[{divide:[i]}],"outline-style":[{outline:[``,...O()]}],"outline-offset":[{"outline-offset":[U,G]}],"outline-w":[{outline:[U,W]}],"outline-color":[{outline:[e]}],"ring-w":[{ring:ne()}],"ring-w-inset":[`ring-inset`],"ring-color":[{ring:[e]}],"ring-opacity":[{"ring-opacity":[_]}],"ring-offset-w":[{"ring-offset":[U,W]}],"ring-offset-color":[{"ring-offset":[e]}],shadow:[{shadow:[``,`inner`,`none`,K,Wt]}],"shadow-color":[{shadow:[Gt]}],opacity:[{opacity:[_]}],"mix-blend":[{"mix-blend":[...k(),`plus-lighter`,`plus-darker`]}],"bg-blend":[{"bg-blend":k()}],filter:[{filter:[``,`none`]}],blur:[{blur:[n]}],brightness:[{brightness:[r]}],contrast:[{contrast:[c]}],"drop-shadow":[{"drop-shadow":[``,`none`,K,G]}],grayscale:[{grayscale:[l]}],"hue-rotate":[{"hue-rotate":[u]}],invert:[{invert:[d]}],saturate:[{saturate:[y]}],sepia:[{sepia:[x]}],"backdrop-filter":[{"backdrop-filter":[``,`none`]}],"backdrop-blur":[{"backdrop-blur":[n]}],"backdrop-brightness":[{"backdrop-brightness":[r]}],"backdrop-contrast":[{"backdrop-contrast":[c]}],"backdrop-grayscale":[{"backdrop-grayscale":[l]}],"backdrop-hue-rotate":[{"backdrop-hue-rotate":[u]}],"backdrop-invert":[{"backdrop-invert":[d]}],"backdrop-opacity":[{"backdrop-opacity":[_]}],"backdrop-saturate":[{"backdrop-saturate":[y]}],"backdrop-sepia":[{"backdrop-sepia":[x]}],"border-collapse":[{border:[`collapse`,`separate`]}],"border-spacing":[{"border-spacing":[o]}],"border-spacing-x":[{"border-spacing-x":[o]}],"border-spacing-y":[{"border-spacing-y":[o]}],"table-layout":[{table:[`auto`,`fixed`]}],caption:[{caption:[`top`,`bottom`]}],transition:[{transition:[`none`,`all`,``,`colors`,`opacity`,`shadow`,`transform`,G]}],duration:[{duration:j()}],ease:[{ease:[`linear`,`in`,`out`,`in-out`,G]}],delay:[{delay:j()}],animate:[{animate:[`none`,`spin`,`ping`,`pulse`,`bounce`,G]}],transform:[{transform:[``,`gpu`,`none`]}],scale:[{scale:[b]}],"scale-x":[{"scale-x":[b]}],"scale-y":[{"scale-y":[b]}],rotate:[{rotate:[Lt,G]}],"translate-x":[{"translate-x":[C]}],"translate-y":[{"translate-y":[C]}],"skew-x":[{"skew-x":[S]}],"skew-y":[{"skew-y":[S]}],"transform-origin":[{origin:[`center`,`top`,`top-right`,`right`,`bottom-right`,`bottom`,`bottom-left`,`left`,`top-left`,G]}],accent:[{accent:[`auto`,e]}],appearance:[{appearance:[`none`,`auto`]}],cursor:[{cursor:[`auto`,`default`,`pointer`,`wait`,`text`,`move`,`help`,`not-allowed`,`none`,`context-menu`,`progress`,`cell`,`crosshair`,`vertical-text`,`alias`,`copy`,`no-drop`,`grab`,`grabbing`,`all-scroll`,`col-resize`,`row-resize`,`n-resize`,`e-resize`,`s-resize`,`w-resize`,`ne-resize`,`nw-resize`,`se-resize`,`sw-resize`,`ew-resize`,`ns-resize`,`nesw-resize`,`nwse-resize`,`zoom-in`,`zoom-out`,G]}],"caret-color":[{caret:[e]}],"pointer-events":[{"pointer-events":[`none`,`auto`]}],resize:[{resize:[`none`,`y`,`x`,``]}],"scroll-behavior":[{scroll:[`auto`,`smooth`]}],"scroll-m":[{"scroll-m":E()}],"scroll-mx":[{"scroll-mx":E()}],"scroll-my":[{"scroll-my":E()}],"scroll-ms":[{"scroll-ms":E()}],"scroll-me":[{"scroll-me":E()}],"scroll-mt":[{"scroll-mt":E()}],"scroll-mr":[{"scroll-mr":E()}],"scroll-mb":[{"scroll-mb":E()}],"scroll-ml":[{"scroll-ml":E()}],"scroll-p":[{"scroll-p":E()}],"scroll-px":[{"scroll-px":E()}],"scroll-py":[{"scroll-py":E()}],"scroll-ps":[{"scroll-ps":E()}],"scroll-pe":[{"scroll-pe":E()}],"scroll-pt":[{"scroll-pt":E()}],"scroll-pr":[{"scroll-pr":E()}],"scroll-pb":[{"scroll-pb":E()}],"scroll-pl":[{"scroll-pl":E()}],"snap-align":[{snap:[`start`,`end`,`center`,`align-none`]}],"snap-stop":[{snap:[`normal`,`always`]}],"snap-type":[{snap:[`none`,`x`,`y`,`both`]}],"snap-strictness":[{snap:[`mandatory`,`proximity`]}],touch:[{touch:[`auto`,`none`,`manipulation`]}],"touch-x":[{"touch-pan":[`x`,`left`,`right`]}],"touch-y":[{"touch-pan":[`y`,`up`,`down`]}],"touch-pz":[`touch-pinch-zoom`],select:[{select:[`none`,`text`,`all`,`auto`]}],"will-change":[{"will-change":[`auto`,`scroll`,`contents`,`transform`,G]}],fill:[{fill:[e,`none`]}],"stroke-w":[{stroke:[U,W,It]}],stroke:[{stroke:[e,`none`]}],sr:[`sr-only`,`not-sr-only`],"forced-color-adjust":[{"forced-color-adjust":[`auto`,`none`]}]},conflictingClassGroups:{overflow:[`overflow-x`,`overflow-y`],overscroll:[`overscroll-x`,`overscroll-y`],inset:[`inset-x`,`inset-y`,`start`,`end`,`top`,`right`,`bottom`,`left`],"inset-x":[`right`,`left`],"inset-y":[`top`,`bottom`],flex:[`basis`,`grow`,`shrink`],gap:[`gap-x`,`gap-y`],p:[`px`,`py`,`ps`,`pe`,`pt`,`pr`,`pb`,`pl`],px:[`pr`,`pl`],py:[`pt`,`pb`],m:[`mx`,`my`,`ms`,`me`,`mt`,`mr`,`mb`,`ml`],mx:[`mr`,`ml`],my:[`mt`,`mb`],size:[`w`,`h`],"font-size":[`leading`],"fvn-normal":[`fvn-ordinal`,`fvn-slashed-zero`,`fvn-figure`,`fvn-spacing`,`fvn-fraction`],"fvn-ordinal":[`fvn-normal`],"fvn-slashed-zero":[`fvn-normal`],"fvn-figure":[`fvn-normal`],"fvn-spacing":[`fvn-normal`],"fvn-fraction":[`fvn-normal`],"line-clamp":[`display`,`overflow`],rounded:[`rounded-s`,`rounded-e`,`rounded-t`,`rounded-r`,`rounded-b`,`rounded-l`,`rounded-ss`,`rounded-se`,`rounded-ee`,`rounded-es`,`rounded-tl`,`rounded-tr`,`rounded-br`,`rounded-bl`],"rounded-s":[`rounded-ss`,`rounded-es`],"rounded-e":[`rounded-se`,`rounded-ee`],"rounded-t":[`rounded-tl`,`rounded-tr`],"rounded-r":[`rounded-tr`,`rounded-br`],"rounded-b":[`rounded-br`,`rounded-bl`],"rounded-l":[`rounded-tl`,`rounded-bl`],"border-spacing":[`border-spacing-x`,`border-spacing-y`],"border-w":[`border-w-s`,`border-w-e`,`border-w-t`,`border-w-r`,`border-w-b`,`border-w-l`],"border-w-x":[`border-w-r`,`border-w-l`],"border-w-y":[`border-w-t`,`border-w-b`],"border-color":[`border-color-s`,`border-color-e`,`border-color-t`,`border-color-r`,`border-color-b`,`border-color-l`],"border-color-x":[`border-color-r`,`border-color-l`],"border-color-y":[`border-color-t`,`border-color-b`],"scroll-m":[`scroll-mx`,`scroll-my`,`scroll-ms`,`scroll-me`,`scroll-mt`,`scroll-mr`,`scroll-mb`,`scroll-ml`],"scroll-mx":[`scroll-mr`,`scroll-ml`],"scroll-my":[`scroll-mt`,`scroll-mb`],"scroll-p":[`scroll-px`,`scroll-py`,`scroll-ps`,`scroll-pe`,`scroll-pt`,`scroll-pr`,`scroll-pb`,`scroll-pl`],"scroll-px":[`scroll-pr`,`scroll-pl`],"scroll-py":[`scroll-pt`,`scroll-pb`],touch:[`touch-x`,`touch-y`,`touch-pz`],"touch-x":[`touch`],"touch-y":[`touch`],"touch-pz":[`touch`]},conflictingClassGroupModifiers:{"font-size":[`leading`]}}});function q(...e){return Zt(Je(e))}function Qt(e){return e<60?`${Math.round(e)}s`:e<3600?`${Math.round(e/60)}m`:`${Math.round(e/3600)}h ${Math.round(e%3600/60)}m`}function $t({size:e=44,withWordmark:t=!1,className:n=``}){return(0,B.jsxs)(`div`,{className:`flex items-center gap-2.5 ${n}`,children:[(0,B.jsxs)(`svg`,{width:e,height:e,viewBox:`0 0 512 512`,fill:`none`,xmlns:`http://www.w3.org/2000/svg`,role:`img`,"aria-label":`AhmedETAP`,children:[(0,B.jsxs)(`defs`,{children:[(0,B.jsxs)(`linearGradient`,{id:`brandLeftGrad`,x1:`0%`,y1:`0%`,x2:`100%`,y2:`100%`,children:[(0,B.jsx)(`stop`,{offset:`0%`,stopColor:`#1e3a8a`}),(0,B.jsx)(`stop`,{offset:`100%`,stopColor:`#3b82f6`})]}),(0,B.jsxs)(`linearGradient`,{id:`brandRightGrad`,x1:`0%`,y1:`0%`,x2:`100%`,y2:`100%`,children:[(0,B.jsx)(`stop`,{offset:`0%`,stopColor:`#0f766e`}),(0,B.jsx)(`stop`,{offset:`100%`,stopColor:`#0d9488`})]}),(0,B.jsxs)(`linearGradient`,{id:`brandTopGrad`,x1:`0%`,y1:`100%`,x2:`100%`,y2:`0%`,children:[(0,B.jsx)(`stop`,{offset:`0%`,stopColor:`#1d4ed8`}),(0,B.jsx)(`stop`,{offset:`100%`,stopColor:`#00d4ff`})]}),(0,B.jsxs)(`linearGradient`,{id:`brandGlowGrad`,x1:`0%`,y1:`0%`,x2:`100%`,y2:`100%`,children:[(0,B.jsx)(`stop`,{offset:`0%`,stopColor:`#00d4ff`,stopOpacity:`0.15`}),(0,B.jsx)(`stop`,{offset:`100%`,stopColor:`#3b82f6`,stopOpacity:`0`})]})]}),(0,B.jsx)(`circle`,{cx:`256`,cy:`256`,r:`220`,fill:`url(#brandGlowGrad)`}),(0,B.jsx)(`path`,{d:`M256,70 L256,256 L90,352 L90,166 Z`,fill:`url(#brandLeftGrad)`,stroke:`#070b14`,strokeWidth:`6`,strokeLinejoin:`round`}),(0,B.jsx)(`path`,{d:`M256,256 L422,352 L422,166 L256,70 Z`,fill:`url(#brandRightGrad)`,stroke:`#070b14`,strokeWidth:`6`,strokeLinejoin:`round`}),(0,B.jsx)(`path`,{d:`M90,352 L256,256 L422,352 L256,448 Z`,fill:`url(#brandTopGrad)`,stroke:`#070b14`,strokeWidth:`6`,strokeLinejoin:`round`}),(0,B.jsx)(`line`,{x1:`90`,y1:`352`,x2:`256`,y2:`256`,stroke:`#ffffff`,strokeWidth:`3`,opacity:`0.3`}),(0,B.jsx)(`line`,{x1:`422`,y1:`352`,x2:`256`,y2:`256`,stroke:`#ffffff`,strokeWidth:`3`,opacity:`0.3`}),(0,B.jsx)(`line`,{x1:`256`,y1:`70`,x2:`256`,y2:`256`,stroke:`#ffffff`,strokeWidth:`3`,opacity:`0.3`}),(0,B.jsx)(`path`,{d:`M150,210 L256,256`,stroke:`#ffffff`,strokeWidth:`4`,strokeLinecap:`round`,opacity:`0.85`}),(0,B.jsx)(`circle`,{cx:`150`,cy:`210`,r:`12`,fill:`#00d4ff`,stroke:`#ffffff`,strokeWidth:`3`}),(0,B.jsx)(`path`,{d:`M362,210 L256,256`,stroke:`#ffffff`,strokeWidth:`4`,strokeLinecap:`round`,opacity:`0.85`}),(0,B.jsx)(`circle`,{cx:`362`,cy:`210`,r:`12`,fill:`#0d9488`,stroke:`#ffffff`,strokeWidth:`3`}),(0,B.jsx)(`path`,{d:`M256,370 L256,256`,stroke:`#ffffff`,strokeWidth:`4`,strokeLinecap:`round`,opacity:`0.85`}),(0,B.jsx)(`circle`,{cx:`256`,cy:`370`,r:`12`,fill:`#00d4ff`,stroke:`#ffffff`,strokeWidth:`3`}),(0,B.jsx)(`circle`,{cx:`256`,cy:`256`,r:`16`,fill:`#ffffff`,stroke:`#00d4ff`,strokeWidth:`6`}),(0,B.jsx)(`circle`,{cx:`256`,cy:`256`,r:`6`,fill:`#070b14`})]}),t&&(0,B.jsxs)(`div`,{className:`flex flex-col leading-none`,children:[(0,B.jsx)(`span`,{className:`font-bold tracking-tight text-white`,style:{fontSize:e*.42},children:`AhmedETAP`}),(0,B.jsx)(`span`,{className:`text-slate-500 mt-0.5 tracking-wide uppercase`,style:{fontSize:e*.13,fontWeight:500},children:`Power Systems Engineering`})]})]})}var en={success:_e,error:A,warning:D,info:C},tn={success:`text-green-400`,error:`text-red-400`,warning:`text-amber-400`,info:`text-brand-400`};function nn({onClick:e,icon:t,title:n,badge:r,active:i,accent:a,unreadCount:o=0}){let s=i?`bg-brand-500/15 text-brand-400`:a===`brand`?`text-brand-400 hover:bg-brand-500/10 hover:text-brand-300`:`text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]`;return(0,B.jsxs)(`button`,{onClick:e,title:n,"aria-label":n,className:q(`relative p-2 rounded-lg transition-all duration-150 group focus:outline-none focus:ring-2 focus:ring-[var(--ring)]`,s),type:`button`,children:[(0,B.jsx)(t,{className:`w-5 h-5`}),r&&o>0&&(0,B.jsx)(`span`,{className:`absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center ring-2 ring-[var(--bg-secondary)]`,children:o>9?`9+`:o}),(0,B.jsx)(`span`,{className:`absolute top-full mt-2 left-1/2 -translate-x-1/2 px-2 py-1 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] text-[var(--text-secondary)] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg`,children:n})]})}function rn(){let{t:e,i18n:t}=P(),n=Pe(),{searchQuery:r,setSearchQuery:i,toggleMobileSidebar:a}=ot(),[o,s]=(0,z.useState)(!1),[c,d]=(0,z.useState)(new Date),[p,m]=(0,z.useState)(!1),[h,g]=(0,z.useState)(!1),[v,y]=(0,z.useState)(!1),[b,x]=(0,z.useState)([]),S=(0,z.useRef)(null),C=(0,z.useRef)(null),w=t.language===`ar`,T=()=>{globalThis.dispatchEvent(new CustomEvent(`toggle-smart-help`))},te=()=>{globalThis.dispatchEvent(new CustomEvent(`toggle-shortcuts-panel`))};(0,z.useEffect)(()=>{let e=setInterval(()=>d(new Date),1e3);return()=>clearInterval(e)},[]),(0,z.useEffect)(()=>{let e=()=>m(!!document.fullscreenElement);return document.addEventListener(`fullscreenchange`,e),()=>document.removeEventListener(`fullscreenchange`,e)},[]),(0,z.useEffect)(()=>{if(!h&&!v)return;let e=e=>{S.current&&!S.current.contains(e.target)&&g(!1),C.current&&!C.current.contains(e.target)&&y(!1)};return setTimeout(()=>document.addEventListener(`click`,e),0),()=>document.removeEventListener(`click`,e)},[h,v]);let E=()=>{let e=t.language===`ar`?`en`:`ar`;t.changeLanguage(e),document.documentElement.dir=e===`ar`?`rtl`:`ltr`,document.documentElement.lang=e},ne=()=>{document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen()},D=()=>{g(!1),at(),localStorage.removeItem(`etap-user`),n(`/login`)},k=()=>{x(e=>e.map(e=>({...e,read:!0})))},ie=e=>{x(t=>t.filter(t=>t.id!==e))},A=b.filter(e=>!e.read).length;return(0,B.jsxs)(`header`,{className:`navbar-glow flex items-center justify-between px-3 sm:px-4 py-2 bg-[var(--bg-secondary)]/80 backdrop-blur-xl border-b border-[var(--border-primary)]/50 shrink-0 z-[var(--z-navbar)] relative`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-2 flex-1 min-w-0`,children:[(0,B.jsx)(`button`,{onClick:a,"aria-label":`Open menu`,className:`lg:hidden p-2 -ml-1 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors shrink-0`,type:`button`,children:(0,B.jsx)(l,{className:`w-5 h-5`})}),(0,B.jsx)(`div`,{className:`lg:hidden flex items-center gap-1.5 shrink-0`,children:(0,B.jsx)($t,{size:28})}),(0,B.jsxs)(`div`,{className:q(`relative transition-all duration-300 ease-out`,o?`w-full opacity-100`:`w-9 opacity-0 pointer-events-none`),children:[(0,B.jsx)(I,{className:`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)] pointer-events-none`}),(0,B.jsx)(`input`,{type:`text`,value:r,onChange:e=>i(e.target.value),placeholder:e(`navbar.searchPlaceholder`)||`Search...`,className:`w-full pl-9 pr-10 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all`}),o&&(0,B.jsx)(`button`,{onClick:()=>{s(!1),i(``)},className:`absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors`,type:`button`,children:(0,B.jsx)(j,{className:`w-3.5 h-3.5`})})]}),!o&&(0,B.jsxs)(`button`,{onClick:()=>s(!0),className:`hidden sm:flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-input)]/50 border border-[var(--border-primary)]/50 hover:bg-[var(--bg-input)] hover:border-[var(--border-primary)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-all text-sm group`,"aria-label":`Search`,type:`button`,children:[(0,B.jsx)(I,{className:`w-4 h-4`}),(0,B.jsx)(`span`,{className:`hidden lg:inline text-xs`,children:e(`navbar.searchPlaceholder`)||`Search...`}),(0,B.jsxs)(`kbd`,{className:`hidden lg:flex items-center gap-0.5 text-[9px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]`,children:[(0,B.jsx)(be,{className:`w-2.5 h-2.5`}),`K`]})]}),!o&&(0,B.jsx)(`button`,{onClick:()=>s(!0),"aria-label":`Search`,className:`sm:hidden p-2 rounded-lg text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors shrink-0`,type:`button`,children:(0,B.jsx)(I,{className:`w-5 h-5`})})]}),(0,B.jsx)(`div`,{className:`hidden lg:flex items-center gap-2 absolute left-1/2 -translate-x-1/2`,children:(0,B.jsxs)(`div`,{className:`flex items-center gap-2 px-3 py-1 rounded-lg bg-[var(--bg-primary)]/40 border border-[var(--border-primary)]/30`,children:[(0,B.jsx)(`div`,{className:`w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse`}),(0,B.jsx)(`span`,{className:`text-[10px] font-mono text-[var(--text-muted)] uppercase tracking-wider`,children:`AhmedETAP v2.1`})]})}),(0,B.jsxs)(`div`,{className:`flex items-center gap-0.5 shrink-0`,children:[(0,B.jsx)(`div`,{className:`hidden sm:block`,children:(0,B.jsx)(nn,{onClick:E,icon:_,title:w?`Switch to English`:`التبديل للعربية`})}),(0,B.jsx)(`div`,{className:`hidden sm:block`,children:(0,B.jsx)(nn,{onClick:ne,icon:p?ae:We,title:p?`Exit Fullscreen (F11)`:`Fullscreen (F11)`})}),(0,B.jsx)(`div`,{className:`hidden sm:block w-px h-5 bg-[var(--border-primary)] mx-1`}),(0,B.jsx)(`div`,{className:`hidden md:block`,children:(0,B.jsx)(nn,{onClick:()=>globalThis.dispatchEvent(new CustomEvent(`start-magic-help-inspect`)),icon:ce,title:`Magic Help Inspector (Ctrl+Shift+H)`,accent:`brand`,badge:!0,unreadCount:A})}),(0,B.jsx)(`div`,{className:`hidden md:block`,children:(0,B.jsx)(nn,{onClick:T,icon:qe,title:`Smart Help (F1)`})}),(0,B.jsx)(`div`,{className:`hidden md:block`,children:(0,B.jsx)(nn,{onClick:te,icon:re,title:`Keyboard Shortcuts (Ctrl+/)`,active:!0})}),(0,B.jsxs)(`div`,{className:`relative`,ref:C,children:[(0,B.jsxs)(`button`,{onClick:e=>{e.stopPropagation(),y(e=>!e)},title:`Notifications`,"aria-label":`Notifications`,className:q(`relative p-2 rounded-lg transition-all duration-150 group focus:outline-none focus:ring-2 focus:ring-[var(--ring)]`,v?`bg-brand-500/15 text-brand-400`:`text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]`),type:`button`,children:[(0,B.jsx)(ee,{className:`w-5 h-5`}),A>0&&(0,B.jsx)(`span`,{className:`absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center ring-2 ring-[var(--bg-secondary)] animate-pulse`,children:A>9?`9+`:A}),(0,B.jsx)(`span`,{className:`absolute top-full mt-2 left-1/2 -translate-x-1/2 px-2 py-1 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] text-[var(--text-secondary)] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg`,children:`Notifications`})]}),v&&(0,B.jsxs)(`div`,{className:`dropdown-enhanced absolute right-0 top-full mt-2 w-96 bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50`,onClick:e=>e.stopPropagation(),onKeyDown:e=>{(e.key===`Enter`||e.key===` `)&&e.stopPropagation()},children:[(0,B.jsxs)(`div`,{className:`flex items-center justify-between px-4 py-3 border-b border-[var(--border-primary)] bg-[var(--bg-primary)]/50`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-2`,children:[(0,B.jsx)(ee,{className:`w-4 h-4 text-brand-400`}),(0,B.jsx)(`span`,{className:`text-sm font-semibold text-[var(--text-primary)]`,children:`Notifications`}),A>0&&(0,B.jsxs)(`span`,{className:`px-1.5 py-0.5 text-[9px] rounded-full bg-red-500/20 text-red-400 font-bold`,children:[A,` new`]})]}),A>0&&(0,B.jsx)(`button`,{onClick:k,className:`text-[10px] text-brand-400 hover:text-brand-300 font-medium transition-colors`,type:`button`,children:`Mark all read`})]}),(0,B.jsx)(`div`,{className:`max-h-96 overflow-y-auto`,children:b.length>0?b.map(e=>{let t=en[e.type];return(0,B.jsxs)(`div`,{className:q(`flex items-start gap-3 px-4 py-3 border-b border-[var(--border-primary)]/50 hover:bg-[var(--bg-elevated)]/50 transition-colors group`,!e.read&&`bg-brand-500/5`),children:[(0,B.jsx)(t,{className:q(`w-4 h-4 mt-0.5 shrink-0`,tn[e.type])}),(0,B.jsxs)(`div`,{className:`flex-1 min-w-0`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-2`,children:[(0,B.jsx)(`p`,{className:`text-xs font-semibold text-[var(--text-primary)] truncate`,children:e.title}),!e.read&&(0,B.jsx)(`span`,{className:`w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0`})]}),(0,B.jsx)(`p`,{className:`text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-2`,children:e.message}),(0,B.jsx)(`p`,{className:`text-[9px] text-[var(--text-muted)] mt-1 font-mono`,children:e.time})]}),(0,B.jsx)(`button`,{onClick:()=>ie(e.id),className:`p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors opacity-0 group-hover:opacity-100`,"aria-label":`Dismiss`,type:`button`,children:(0,B.jsx)(j,{className:`w-3 h-3`})})]},e.id)}):(0,B.jsxs)(`div`,{className:`py-12 text-center`,children:[(0,B.jsx)(ee,{className:`w-8 h-8 text-[var(--text-muted)] mx-auto mb-2 opacity-50`}),(0,B.jsx)(`p`,{className:`text-sm text-[var(--text-tertiary)]`,children:`No notifications`}),(0,B.jsx)(`p`,{className:`text-xs text-[var(--text-muted)] mt-1`,children:`You're all caught up!`})]})}),(0,B.jsx)(`div`,{className:`px-4 py-2 bg-[var(--bg-primary)]/50 border-t border-[var(--border-primary)] text-center`,children:(0,B.jsxs)(`span`,{className:`text-[10px] text-[var(--text-muted)]`,children:[`Notification center · `,b.length,` total`]})})]})]}),(0,B.jsx)(`div`,{className:`w-px h-5 bg-[var(--border-primary)] mx-1`}),(0,B.jsxs)(`div`,{className:`relative`,ref:S,children:[(0,B.jsxs)(`button`,{onClick:e=>{e.stopPropagation(),g(e=>!e)},className:`flex items-center gap-2 pl-1 pr-2 py-1 rounded-lg hover:bg-[var(--bg-elevated)] transition-colors group focus:outline-none focus:ring-2 focus:ring-[var(--ring)]`,"aria-label":`User menu`,type:`button`,children:[(0,B.jsxs)(`div`,{className:`relative`,children:[(0,B.jsx)(`div`,{className:`w-8 h-8 rounded-full bg-gradient-to-br from-brand-400 via-brand-500 to-brand-700 p-[2px]`,children:(0,B.jsx)(`div`,{className:`w-full h-full rounded-full bg-[var(--bg-secondary)] flex items-center justify-center`,children:(0,B.jsx)(Te,{className:`w-4 h-4 text-brand-400`})})}),(0,B.jsx)(`span`,{className:`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-green-400 ring-2 ring-[var(--bg-secondary)]`})]}),(0,B.jsxs)(`div`,{className:`hidden md:flex flex-col items-start leading-tight`,children:[(0,B.jsx)(`span`,{className:`text-xs font-medium text-[var(--text-primary)]`,children:e(`navbar.welcome`)||`Engineer`}),(0,B.jsxs)(`div`,{className:`flex items-center gap-1 text-[9px] text-[var(--text-muted)] font-mono`,children:[(0,B.jsx)(Se,{className:`w-2.5 h-2.5`}),(0,B.jsxs)(`span`,{children:[c.toLocaleDateString(w?`ar-EG`:`en-US`,{weekday:`short`,month:`short`,day:`numeric`}),` · `,c.toLocaleTimeString(w?`ar-EG`:`en-US`,{hour:`2-digit`,minute:`2-digit`,hour12:!w})]})]})]}),(0,B.jsx)(f,{className:q(`w-3.5 h-3.5 text-[var(--text-muted)] transition-transform hidden md:block`,h&&`rotate-180`)})]}),h&&(0,B.jsxs)(`div`,{className:`dropdown-enhanced absolute right-0 top-full mt-2 w-64 bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50`,onClick:e=>e.stopPropagation(),onKeyDown:e=>{(e.key===`Enter`||e.key===` `)&&e.stopPropagation()},children:[(0,B.jsx)(`div`,{className:`px-4 py-3 bg-gradient-to-br from-brand-500/8 to-transparent border-b border-[var(--border-primary)]`,children:(0,B.jsxs)(`div`,{className:`flex items-center gap-3`,children:[(0,B.jsx)(`div`,{className:`w-10 h-10 rounded-full bg-gradient-to-br from-brand-400 to-brand-700 p-[2px]`,children:(0,B.jsx)(`div`,{className:`w-full h-full rounded-full bg-[var(--bg-secondary)] flex items-center justify-center`,children:(0,B.jsx)(Te,{className:`w-5 h-5 text-brand-400`})})}),(0,B.jsxs)(`div`,{className:`flex-1 min-w-0`,children:[(0,B.jsx)(`div`,{className:`text-sm font-medium text-[var(--text-primary)] truncate`,children:`Eng. Ahmed Elbaz`}),(0,B.jsxs)(`div`,{className:`flex items-center gap-1 text-[10px] text-green-400`,children:[(0,B.jsx)(M,{className:`w-3 h-3`}),(0,B.jsx)(`span`,{children:`Administrator · Online`})]})]})]})}),(0,B.jsxs)(`div`,{className:`py-1.5`,children:[(0,B.jsxs)(`button`,{onClick:()=>{g(!1),n(`/settings`)},className:`w-full flex items-center gap-3 px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors`,type:`button`,children:[(0,B.jsx)(O,{className:`w-4 h-4 text-[var(--text-muted)]`}),(0,B.jsx)(`span`,{children:`Settings`}),(0,B.jsx)(`kbd`,{className:`ml-auto text-[9px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono text-[var(--text-muted)]`,children:`G E`})]}),(0,B.jsxs)(`button`,{onClick:()=>{g(!1),n(`/diagnostics`)},className:`w-full flex items-center gap-3 px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors`,type:`button`,children:[(0,B.jsx)(M,{className:`w-4 h-4 text-[var(--text-muted)]`}),(0,B.jsx)(`span`,{children:`Diagnostics`}),(0,B.jsx)(`kbd`,{className:`ml-auto text-[9px] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded border border-[var(--border-primary)] font-mono text-[var(--text-muted)]`,children:`G I`})]}),(0,B.jsx)(`div`,{className:`h-px bg-[var(--border-primary)] my-1.5`}),(0,B.jsxs)(`button`,{onClick:D,className:`w-full flex items-center gap-3 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors`,type:`button`,children:[(0,B.jsx)(u,{className:`w-4 h-4`}),(0,B.jsx)(`span`,{children:`Sign Out`})]})]}),(0,B.jsx)(`div`,{className:`px-4 py-2 bg-[var(--bg-primary)]/50 border-t border-[var(--border-primary)]`,children:(0,B.jsx)(`div`,{className:`text-[9px] text-[var(--text-muted)] font-mono text-center`,children:`AhmedETAP v2.1.0 · Build 2026.07.03`})})]})]})]})]})}var an=(0,z.createContext)({theme:`dark`,toggleTheme:()=>{}});function on({children:e}){let[t,n]=(0,z.useState)(()=>localStorage.getItem(`etap-theme`)===`light`?`light`:`dark`);(0,z.useEffect)(()=>{document.documentElement.classList.toggle(`dark`,t===`dark`),document.documentElement.classList.toggle(`light`,t===`light`),localStorage.setItem(`etap-theme`,t)},[t]);let r=(0,z.useCallback)(()=>n(e=>e===`dark`?`light`:`dark`),[]),i=(0,z.useMemo)(()=>({theme:t,toggleTheme:r}),[t,r]);return(0,B.jsx)(an.Provider,{value:i,children:e})}function sn(){return(0,z.useContext)(an)}function cn(e){let t={},n=e.PROVIDER_ACTIVE_PROVIDER_ID||`openai`;if(t[`x-active-provider`]=n,n===`custom_openai`)return e.CUSTOM_OPENAI_API_KEY&&(t[`x-active-key`]=e.CUSTOM_OPENAI_API_KEY),e.CUSTOM_OPENAI_BASE_URL&&(t[`x-active-url`]=e.CUSTOM_OPENAI_BASE_URL),e.CUSTOM_OPENAI_MODEL_ID&&(t[`x-active-model`]=e.CUSTOM_OPENAI_MODEL_ID),t;let r=n.toUpperCase(),i=`PROVIDER_${r}_KEY`,a=`PROVIDER_${r}_MODEL`;return e[i]&&(t[`x-active-key`]=e[i]),e[a]&&(t[`x-active-model`]=e[a]),t}async function ln(e){try{let t=await e.json();return t.detail||t.message||JSON.stringify(t)}catch{try{return await e.text()}catch{return`HTTP ${e.status} ${e.statusText}`}}}async function J(e,t){let n=`${R}${e}`,r=nt(),i={"Content-Type":`application/json`,...t?.headers};r&&(i.Authorization=`Bearer ${r}`),Object.assign(i,cn(Ye()));let a=await fetch(n,{...t,headers:i,signal:t?.signal??AbortSignal.timeout(15e3)});if(!a.ok){let e=await ln(a);throw Error(`API ${a.status}: ${e}`)}if(a.status!==204)return a.json()}async function un(){return J(`/health`)}async function dn(){let e=await J(`/api/v1/agents`);return Array.isArray(e)?e:e.agents??[]}async function fn(e,t,n=!1){if(!t.system)throw Error(`System configuration is required. Please provide a valid power system model.`);return J(`/api/v1/studies/run`,{method:`POST`,body:JSON.stringify({study_type:e,params:t,dry_run:n,system:t.system})})}async function pn(){return J(`/api/v1/studies/types`)}async function mn(){return J(`/metrics`)}async function hn(){return J(`/api/v1/audit`)}async function gn(e,t=`all`,n=`python`){return J(`/api/v1/guards/review`,{method:`POST`,body:JSON.stringify({source:e,guard_type:t,language:n})})}async function _n(){return(await J(`/api/v1/guards/info`)).data}async function vn(){return J(`/api/v1/settings/keys`)}async function yn(e,t,n,r,i=!0){let a=new URLSearchParams({api_key:t,is_active:String(i)});return n&&a.set(`base_url`,n),r&&a.set(`model_name`,r),J(`/api/v1/settings/keys/${e}?${a.toString()}`,{method:`POST`})}async function bn(e){return J(`/api/v1/settings/keys/${e}`,{method:`DELETE`})}async function xn(e){return J(`/api/v1/settings/keys/${e}/test`,{method:`POST`})}async function Sn(){return J(`/api/v1/agents/mcp-servers`)}async function Cn(){return J(`/api/v1/feature-flags`)}async function wn(e,t){return J(`/api/v1/feature-flags/${e}`,{method:`PATCH`,body:JSON.stringify({enabled:t}),headers:{"Content-Type":`application/json`}})}var Tn=[{id:`predict/load`,label:`Load Forecast`,method:`POST`,path:`/api/v1/predict/load`,description:`Predict future load using Prophet / LSTM / Linear LoadForecaster. Pass historical_data array + horizon_hours (1–168).`,inputSchema:{type:`object`,required:[`historical_data`],properties:{historical_data:{type:`array`,items:{type:`number`},maxItems:1e4},horizon_hours:{type:`integer`,minimum:1,maximum:168,default:24},method:{type:`string`,enum:[`auto`,`prophet`,`lstm`,`linear`],default:`auto`}}},sampleInput:{historical_data:[120,132,145,158,162,170,168,175,182,190,188,195],horizon_hours:6,method:`auto`}},{id:`predict/fault`,label:`Fault Prediction`,method:`POST`,path:`/api/v1/predict/fault`,description:`Predict fault probability using XGBoost with SHAP explanations. Pass features object + optional model_version.`,inputSchema:{type:`object`,required:[`features`],properties:{features:{type:`object`},model_version:{type:`string`}}},sampleInput:{features:{voltage_pu:.94,current_a:410,power_factor:.85,temperature_c:78,harmonic_thd:.08,load_pct:.92}}},{id:`predict/anomaly`,label:`Anomaly Detection`,method:`POST`,path:`/api/v1/predict/anomaly`,description:`Detect anomalies using Isolation Forest / PyOD. Pass data array + method + contamination.`,inputSchema:{type:`object`,required:[`data`],properties:{data:{type:`array`,items:{type:`number`},maxItems:1e4},method:{type:`string`,enum:[`iforest`,`pyod_iforest`,`pyod_knn`,`pyod_autoencoder`],default:`iforest`},contamination:{type:`number`,minimum:.01,maximum:.5,default:.05}}},sampleInput:{data:[10,12,11,13,12,14,11,50,12,13,11,12,75,12,13,11],method:`iforest`,contamination:.1}},{id:`gnn/predict`,label:`GNN Power Grid`,method:`POST`,path:`/api/v1/gnn/predict`,description:`Run Graph Neural Network analysis on the power grid topology. Pass nodes + edges.`,inputSchema:{type:`object`,required:[`nodes`],properties:{nodes:{type:`array`},edges:{type:`array`},target:{type:`string`}}},sampleInput:{nodes:[{id:`bus1`,type:`bus`,voltage_pu:1},{id:`bus2`,type:`bus`,voltage_pu:.98},{id:`line1`,type:`line`}],edges:[{source:`bus1`,target:`line1`},{source:`line1`,target:`bus2`}],target:`voltage_stability`}},{id:`rag/query`,label:`RAG Query`,method:`POST`,path:`/api/v1/rag/query`,description:`Run Retrieval-Augmented Generation query against the ETAP knowledge base.`,inputSchema:{type:`object`,required:[`query`],properties:{query:{type:`string`,maxLength:1e3},top_k:{type:`integer`,minimum:1,maximum:20,default:5},filter_tags:{type:`array`,items:{type:`string`}}}},sampleInput:{query:`What is the IEEE 519 harmonic limit for voltage distortion?`,top_k:3}}];async function En(e,t){return J(e,{method:`POST`,body:JSON.stringify(t),headers:{"Content-Type":`application/json`}})}async function Dn(e,t=1,n=50){let r=new URLSearchParams({page:String(t),page_size:String(n)});return e&&r.set(`status`,e),J(`/api/v1/projects/?${r.toString()}`)}async function On(e){return J(`/api/v1/projects/`,{method:`POST`,body:JSON.stringify(e)})}async function kn(e,t){return J(`/api/v1/projects/${encodeURIComponent(e)}`,{method:`PUT`,body:JSON.stringify(t)})}async function An(e){await J(`/api/v1/projects/${encodeURIComponent(e)}`,{method:`DELETE`})}var jn=[{to:`/dashboard`,icon:T,labelKey:`sidebar.dashboard`},{to:`/studies`,icon:me,labelKey:`sidebar.studies`},{to:`/assistant`,icon:m,labelKey:`sidebar.assistant`},{to:`/projects`,icon:b,labelKey:`sidebar.projects`,section:`engineering`},{to:`/grid-editor`,icon:ue,labelKey:`sidebar.gridEditor`,section:`engineering`},{to:`/asset-management`,icon:ge,labelKey:`sidebar.assetManagement`,section:`engineering`},{to:`/equipment`,icon:Ce,labelKey:`sidebar.equipment`,section:`engineering`},{to:`/vision-keys`,icon:y,labelKey:`sidebar.visionKeys`,section:`engineering`},{to:`/etap`,icon:xe,labelKey:`sidebar.etapIntegration`,section:`integration`},{to:`/gis`,icon:se,labelKey:`sidebar.gisIntegration`,section:`integration`},{to:`/scada`,icon:x,labelKey:`sidebar.scadaIntegration`,section:`integration`},{to:`/digital-twin`,icon:E,labelKey:`sidebar.digitalTwin`,section:`integration`},{to:`/reports`,icon:o,labelKey:`sidebar.reports`},{to:`/data-import`,icon:te,labelKey:`sidebar.dataImport`,section:`system`},{to:`/data-export`,icon:Ie,labelKey:`sidebar.dataExport`,section:`system`},{to:`/settings`,icon:O,labelKey:`sidebar.settings`,section:`system`},{to:`/admin`,icon:M,labelKey:`sidebar.administration`,section:`system`},{to:`/admin/rbac`,icon:Me,labelKey:`sidebar.rbacAdmin`,section:`system`},{to:`/admin/email-dashboard`,icon:p,labelKey:`sidebar.emailDashboard`,section:`system`},{to:`/admin/email-digest`,icon:s,labelKey:`sidebar.emailDigest`,section:`system`},{to:`/admin/study-versions`,icon:de,labelKey:`sidebar.studyVersions`,section:`system`},{to:`/admin/email-otp`,icon:y,labelKey:`sidebar.emailOtp`,section:`system`},{to:`/admin/magic-links`,icon:Ee,labelKey:`sidebar.magicLinks`,section:`system`},{to:`/admin/mfa`,icon:M,labelKey:`sidebar.mfa`,section:`system`},{to:`/admin/agents`,icon:m,labelKey:`sidebar.agentsControlPanel`,section:`system`},{to:`/admin/ai-playground`,icon:ce,labelKey:`sidebar.aiPlayground`,to:`/admin/cua-monitor`,icon:fe,labelKey:`sidebar.cuaMonitor`,section:`system`},{to:`/diagnostics`,icon:w,labelKey:`sidebar.diagnostics`,section:`system`},{to:`/code-guard`,icon:Me,labelKey:`sidebar.codeGuard`,section:`system`},{to:`/context-engine`,icon:I,labelKey:`sidebar.contextEngine`,section:`system`},{to:`/templates`,icon:o,labelKey:`sidebar.templates`,section:`system`},{to:`/asset-library`,icon:Ce,labelKey:`sidebar.assetLibrary`,section:`system`},{to:`/logs`,icon:Fe,labelKey:`sidebar.logs`,section:`system`},{to:`/audit-logs`,icon:Fe,labelKey:`sidebar.auditLogs`,section:`system`}],Mn=[`engineering`,`integration`,`system`],Nn={engineering:`sidebar.engineering`,integration:`sidebar.integration`,system:`sidebar.system`},Pn={engineering:De,integration:xe,system:d};function Fn(e){return e===`online`?`bg-green-400 animate-pulse`:e===`checking`?`bg-amber-400`:`bg-red-400`}function In(e){let t={},n=[];for(let r of e)r.section?(t[r.section]||(t[r.section]=[]),t[r.section].push(r)):n.push(r);return{topLevel:n,grouped:t}}function Ln({mobileSidebarOpen:e,setMobileSidebarOpen:t,healthStatus:n,topLevel:r,groupedItems:i,theme:a,toggleTheme:o,t:s,location:c}){return(0,B.jsxs)(B.Fragment,{children:[e&&(0,B.jsx)(`div`,{className:`lg:hidden fixed inset-0 bg-black/70 backdrop-blur-sm z-[90]`,onClick:()=>t(!1),onKeyDown:e=>{(e.key===`Enter`||e.key===` `)&&(e.preventDefault(),t(!1))},role:`button`,tabIndex:0,"aria-hidden":`true`}),(0,B.jsxs)(`aside`,{"aria-label":`Mobile Sidebar Navigation`,"aria-hidden":!e,className:q(`lg:hidden fixed top-0 left-0 h-full w-72 max-w-[85vw]`,`bg-[var(--bg-secondary)] border-r border-[var(--border-primary)]`,`flex flex-col overflow-hidden shadow-2xl`,`transition-transform duration-300 ease-out z-[100]`,e?`translate-x-0`:`-translate-x-full`),children:[(0,B.jsxs)(`div`,{className:`p-4 border-b border-[var(--border-primary)] flex items-center justify-between`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-2.5 min-w-0`,children:[(0,B.jsxs)(`div`,{className:`shrink-0 relative`,children:[(0,B.jsx)($t,{size:36}),n===`online`&&(0,B.jsx)(`span`,{className:`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-green-400 rounded-full border-2 border-[var(--bg-secondary)]`})]}),(0,B.jsxs)(`div`,{className:`min-w-0`,children:[(0,B.jsx)(`h1`,{className:`text-sm font-bold text-[var(--text-primary)] truncate tracking-tight`,children:s(`app.name`)}),(0,B.jsxs)(`div`,{className:`flex items-center gap-1.5 mt-0.5`,children:[(0,B.jsx)(`span`,{className:q(`w-1.5 h-1.5 rounded-full`,Fn(n))}),(0,B.jsx)(`span`,{className:`text-[10px] text-[var(--text-muted)] capitalize`,children:s(`dashboard.${n}`)})]})]})]}),(0,B.jsx)(`button`,{onClick:()=>t(!1),"aria-label":`Close menu`,className:`p-2 -mr-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors shrink-0`,type:`button`,children:(0,B.jsx)(j,{className:`w-5 h-5`})})]}),(0,B.jsxs)(`nav`,{className:`flex-1 overflow-y-auto py-2 px-2 space-y-0.5`,children:[r.map(e=>(0,B.jsxs)(pe,{to:e.to,className:({isActive:e})=>q(`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150`,e?`bg-brand-600/80 text-white font-medium shadow-sm shadow-brand-600/30 ring-1 ring-brand-500/30`:`text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]`),children:[(0,B.jsx)(e.icon,{className:`w-[18px] h-[18px] shrink-0`}),(0,B.jsx)(`span`,{className:`truncate`,children:s(e.labelKey)})]},e.to)),Mn.map(e=>{let t=i[e];if(!t?.length)return null;let n=Pn[e];return(0,B.jsxs)(`div`,{className:`pt-4`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-1.5 px-3 mb-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider`,children:[n&&(0,B.jsx)(n,{className:`w-3 h-3`}),s(Nn[e])]}),t.map(e=>{let t=c.pathname===e.to;return(0,B.jsxs)(pe,{to:e.to,className:()=>q(`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 mt-0.5`,t?`bg-brand-600 text-white font-medium shadow-sm shadow-brand-600/30`:`text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]`),children:[(0,B.jsx)(e.icon,{className:`w-[18px] h-[18px] shrink-0`}),(0,B.jsx)(`span`,{className:`truncate`,children:s(e.labelKey)})]},e.to)})]},e)})]}),(0,B.jsxs)(`div`,{className:`p-2 border-t border-[var(--border-primary)] space-y-1`,children:[(0,B.jsxs)(`button`,{onClick:o,className:`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors`,"aria-label":s(a===`dark`?`sidebar.lightMode`:`sidebar.darkMode`),type:`button`,children:[a===`dark`?(0,B.jsx)(le,{className:`w-[18px] h-[18px] shrink-0`}):(0,B.jsx)(ve,{className:`w-[18px] h-[18px] shrink-0`}),(0,B.jsx)(`span`,{children:s(a===`dark`?`sidebar.lightMode`:`sidebar.darkMode`)})]}),(0,B.jsxs)(`div`,{className:`text-[10px] text-[var(--text-muted)] text-center pt-1`,children:[`v`,s(`app.version`),` · `,new Date().getFullYear()]})]})]})]})}function Rn(){let{t:e,i18n:t}=P(),{theme:n,toggleTheme:r}=sn(),i=Oe(),{sidebarCollapsed:a,toggleSidebar:o,mobileSidebarOpen:s,setMobileSidebarOpen:c}=ot(),[l,u]=(0,z.useState)(`checking`),d=t.language===`ar`;(0,z.useEffect)(()=>{c(!1)},[i,c]),(0,z.useEffect)(()=>{if(!s)return;let e=e=>{e.key===`Escape`&&c(!1)};return globalThis.addEventListener(`keydown`,e),()=>globalThis.removeEventListener(`keydown`,e)},[s,c]),(0,z.useEffect)(()=>{un().then(e=>u(e.ok?`online`:`offline`)).catch(()=>u(`offline`));let e=setInterval(()=>{un().then(e=>u(e.ok?`online`:`offline`)).catch(()=>u(`offline`))},3e4);return()=>clearInterval(e)},[]);let{topLevel:f,grouped:p}=In(jn);return(0,B.jsxs)(B.Fragment,{children:[(0,B.jsxs)(`aside`,{"aria-label":`Sidebar Navigation`,className:q(`hidden lg:flex h-full flex-col bg-[var(--bg-secondary)] border-r border-[var(--border-primary)] shrink-0 transition-all duration-300 overflow-hidden z-[var(--z-sidebar)]`,a?`w-[68px]`:`w-64`),children:[(0,B.jsx)(`div`,{className:`p-4 border-b border-[var(--border-primary)]`,children:(0,B.jsxs)(`div`,{className:q(`flex items-center gap-2.5`,a&&`justify-center`),children:[(0,B.jsxs)(`div`,{className:`shrink-0 relative`,children:[(0,B.jsx)($t,{size:36}),l===`online`&&(0,B.jsx)(`span`,{className:`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-green-400 rounded-full border-2 border-[var(--bg-secondary)]`})]}),!a&&(0,B.jsxs)(`div`,{className:`min-w-0`,children:[(0,B.jsx)(`h1`,{className:`text-sm font-bold text-[var(--text-primary)] truncate tracking-tight`,children:e(`app.name`)}),(0,B.jsxs)(`div`,{className:`flex items-center gap-1.5 mt-0.5`,children:[(0,B.jsx)(`span`,{className:q(`w-1.5 h-1.5 rounded-full`,Fn(l))}),(0,B.jsx)(`span`,{className:`text-[10px] text-[var(--text-muted)] capitalize`,children:e(`dashboard.${l}`)})]})]})]})}),(0,B.jsxs)(`nav`,{className:`flex-1 overflow-y-auto py-2 px-2 space-y-0.5`,children:[f.map(t=>(0,B.jsxs)(pe,{to:t.to,className:({isActive:e})=>q(`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 group relative`,a&&`justify-center px-0`,!a&&`nav-indicator`,e&&!a&&`active`,e?`bg-brand-600/80 text-white font-medium shadow-sm shadow-brand-600/30 ring-1 ring-brand-500/30`:`text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]`),children:[(0,B.jsx)(t.icon,{className:`w-[18px] h-[18px] shrink-0`}),!a&&(0,B.jsx)(`span`,{className:`truncate`,children:e(t.labelKey)}),a&&(0,B.jsx)(`div`,{className:`absolute left-full ml-2 px-2 py-1 bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-md text-xs text-[var(--text-primary)] shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50`,children:e(t.labelKey)})]},t.to)),Mn.map(t=>{let n=p[t];if(!n?.length)return null;let r=Pn[t];return(0,B.jsxs)(`div`,{className:`sidebar-section-divider`,children:[!a&&(0,B.jsxs)(`div`,{className:`sidebar-section-label`,children:[r&&(0,B.jsx)(r,{className:`w-3 h-3`}),e(Nn[t])]}),a&&(0,B.jsx)(`hr`,{className:`border-[var(--border-primary)] mx-2`}),n.map(t=>{let n=i.pathname===t.to;return(0,B.jsxs)(pe,{to:t.to,className:()=>q(`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150 mt-0.5 group relative`,a&&`justify-center px-0`,n?`bg-brand-600 text-white font-medium shadow-sm shadow-brand-600/30`:`text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]`),children:[(0,B.jsx)(t.icon,{className:`w-[18px] h-[18px] shrink-0`}),!a&&(0,B.jsx)(`span`,{className:`truncate`,children:e(t.labelKey)}),a&&(0,B.jsx)(`div`,{className:`absolute left-full ml-2 px-2 py-1 bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-md text-xs text-[var(--text-primary)] shadow-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50`,children:e(t.labelKey)})]},t.to)})]},t)})]}),(0,B.jsxs)(`div`,{className:`p-2 border-t border-[var(--border-primary)] space-y-1`,children:[(0,B.jsxs)(`button`,{onClick:r,className:q(`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors`,a&&`justify-center px-0`),"aria-label":e(n===`dark`?`sidebar.lightMode`:`sidebar.darkMode`),type:`button`,children:[n===`dark`?(0,B.jsx)(le,{className:`w-[18px] h-[18px] shrink-0`}):(0,B.jsx)(ve,{className:`w-[18px] h-[18px] shrink-0`}),!a&&(0,B.jsx)(`span`,{children:e(n===`dark`?`sidebar.lightMode`:`sidebar.darkMode`)})]}),(0,B.jsx)(`button`,{onClick:o,className:q(`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-secondary)] transition-colors`,a&&`justify-center px-0`),title:e(a?`sidebar.expand`:`sidebar.collapse`),"aria-label":e(a?`sidebar.expand`:`sidebar.collapse`),type:`button`,children:a?(0,B.jsx)(L,{className:`w-[18px] h-[18px] shrink-0 ${d?`rotate-180`:``}`}):(0,B.jsxs)(B.Fragment,{children:[d?(0,B.jsx)(L,{className:`w-[18px] h-[18px] shrink-0`}):(0,B.jsx)(oe,{className:`w-[18px] h-[18px] shrink-0`}),(0,B.jsx)(`span`,{children:e(`sidebar.collapse`)})]})}),!a&&(0,B.jsxs)(`div`,{className:`text-[10px] text-[var(--text-muted)] text-center pt-1`,children:[`v`,e(`app.version`),` · `,new Date().getFullYear()]})]})]}),(0,B.jsx)(Ln,{mobileSidebarOpen:s,setMobileSidebarOpen:c,healthStatus:l,topLevel:f,groupedItems:p,theme:n,toggleTheme:r,t:e,location:i})]})}function zn(){let{t:e}=P(),[t,n]=(0,z.useState)(!1),r=!!window.electronAPI;return(0,z.useEffect)(()=>{if(!r)return;window.electronAPI?.isMaximized().then(n);let e=setInterval(async()=>{window.electronAPI&&n(await window.electronAPI.isMaximized())},1e3);return()=>clearInterval(e)},[r]),r?(0,B.jsxs)(`div`,{className:`h-9 flex items-center justify-between bg-[var(--bg-secondary)] border-b border-[var(--border-primary)] select-none`,style:{WebkitAppRegion:`drag`},children:[(0,B.jsx)(`div`,{className:`flex items-center gap-2 px-4`,children:(0,B.jsxs)(`span`,{className:`text-xs font-semibold text-[var(--text-secondary)] tracking-wide`,children:[`⚡ `,e(`app.name`)]})}),(0,B.jsxs)(`div`,{className:`flex items-center h-full`,style:{WebkitAppRegion:`no-drag`},children:[(0,B.jsx)(`button`,{type:`button`,onClick:()=>window.electronAPI?.minimize(),className:`h-full px-3 flex items-center justify-center hover:bg-white/5 transition-colors`,title:`Minimize`,"aria-label":`Minimize Window`,children:(0,B.jsx)(Ke,{className:`w-3.5 h-3.5 text-[var(--text-muted)]`})}),(0,B.jsx)(`button`,{type:`button`,onClick:async()=>{await window.electronAPI?.maximize(),n(await window.electronAPI?.isMaximized()??!1)},className:`h-full px-3 flex items-center justify-center hover:bg-white/5 transition-colors`,title:t?`Restore`:`Maximize`,"aria-label":t?`Restore Window`:`Maximize Window`,children:t?(0,B.jsx)(h,{className:`w-3 h-3 text-[var(--text-muted)]`}):(0,B.jsx)(We,{className:`w-3.5 h-3.5 text-[var(--text-muted)]`})}),(0,B.jsx)(`button`,{type:`button`,onClick:()=>window.electronAPI?.close(),className:`h-full px-3 flex items-center justify-center hover:bg-red-500/80 group transition-colors`,title:`Close`,"aria-label":`Close Window`,children:(0,B.jsx)(j,{className:`w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-white`})})]})]}):null}function Bn(){let e=Oe();return(0,B.jsxs)(`div`,{className:`flex flex-col h-screen overflow-hidden bg-[var(--bg-primary)] relative`,children:[(0,B.jsxs)(`div`,{className:`fixed inset-0 pointer-events-none overflow-hidden`,"aria-hidden":`true`,children:[(0,B.jsx)(`div`,{className:`absolute -top-40 -left-40 w-[500px] h-[500px] bg-gradient-to-br from-[var(--accent-primary)]/4 via-transparent to-transparent rounded-full blur-3xl animate-aurora`}),(0,B.jsx)(`div`,{className:`absolute -bottom-60 -right-40 w-[600px] h-[600px] bg-gradient-to-tl from-purple-500/4 via-transparent to-transparent rounded-full blur-3xl animate-aurora`,style:{animationDelay:`-7s`,animationDirection:`reverse`}}),(0,B.jsx)(`div`,{className:`absolute top-1/2 left-1/3 w-[400px] h-[400px] bg-gradient-to-r from-cyan-500/3 via-transparent to-transparent rounded-full blur-3xl animate-aurora`,style:{animationDelay:`-14s`}})]}),(0,B.jsx)(zn,{}),(0,B.jsxs)(`div`,{className:`flex flex-1 overflow-hidden relative z-10`,children:[(0,B.jsx)(Rn,{}),(0,B.jsxs)(`div`,{className:`flex-1 flex flex-col overflow-hidden min-w-0`,children:[(0,B.jsx)(rn,{}),(0,B.jsxs)(`main`,{className:`flex-1 overflow-y-auto relative`,children:[(0,B.jsx)(`div`,{className:`absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[var(--accent-primary)]/1 pointer-events-none`}),(0,B.jsxs)(`div`,{className:`relative p-6 max-w-[1400px] mx-auto w-full page-transition-enter mobile-p-compact`,children:[(0,B.jsx)(et,{path:e.pathname}),(0,B.jsx)(a,{})]})]})]})]})]})}var Y=sessionStorage,X=`authToken`,Vn=`refreshToken`;function Hn(e){if(e.length===0)return null;let t=e[0];if(!t||typeof t!=`object`||typeof t.msg!=`string`)return null;let n=t.msg,r=Array.isArray(t.loc)?t.loc.join(`.`):``;return r?`${n} (field: ${r})`:n}function Un(e){let t;try{t=JSON.parse(e)}catch{return null}if(typeof t!=`object`||!t)return null;let n=t;if(Array.isArray(n.detail)){let e=Hn(n.detail);if(e)return e}return typeof n.detail==`string`&&n.detail.length>0?n.detail:typeof n.message==`string`&&n.message.length>0?n.message:null}async function Wn(e,t){let n=e.status,r=await e.text().catch(()=>``);if(!r)return`${t} (HTTP ${n})`;let i=Un(r);if(i)return i;let a=r.trim();return a.length>0&&a.length<200?`${a} (HTTP ${n})`:`${t} (HTTP ${n})`}async function Gn(e,t,n){try{let r=await fetch(`${R}/api/v1/auth/me`,{headers:{Authorization:`Bearer ${e}`}});r.ok?n(await r.json()):n({id:``,email:t,name:t,role:`engineer`})}catch{n({id:``,email:t,name:t,role:`engineer`})}}var Kn=(0,z.createContext)(null),qn=()=>{let e=(0,z.useContext)(Kn);if(!e)throw Error(`useAuth must be used within an AuthProvider`);return e},Jn=({children:e})=>{let[t,n]=(0,z.useState)(null),[r,i]=(0,z.useState)(!0),a=(0,z.useRef)(null);(0,z.useEffect)(()=>()=>{a.current?.abort()},[]),(0,z.useEffect)(()=>{let e=Y.getItem(X);e?o(e):i(!1)},[]);let o=async e=>{let t=new AbortController,r=setTimeout(()=>t.abort(),5e3);try{let r=await fetch(`${R}/api/v1/auth/me`,{headers:{Authorization:`Bearer ${e}`,"Content-Type":`application/json`},signal:t.signal});if(r.ok){let e=await r.json();n(e)}else Y.removeItem(X),Y.removeItem(Vn)}catch(e){console.error(`Error validating token:`,e),Y.removeItem(X),Y.removeItem(Vn)}finally{clearTimeout(r),i(!1)}},s=async(e,t)=>{a.current?.abort();let r=new AbortController;a.current=r;let i=await fetch(`${R}/api/v1/auth/login`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({username:e,password:t}),signal:r.signal});if(!i.ok)throw Error(await Wn(i,`Invalid credentials`));let o=await i.json();Y.setItem(X,o.access_token),Y.setItem(Vn,o.refresh_token),await Gn(o.access_token,e,n)},c=()=>{Y.removeItem(X),Y.removeItem(Vn),n(null)},l={user:t,isAuthenticated:!!t,isLoading:r,login:s,logout:c,register:async(e,t,n)=>{a.current?.abort();let r=new AbortController;a.current=r;let i=await fetch(`${R}/api/v1/auth/register`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({username:n.toLowerCase().replace(/[^a-z0-9_-]/g,`-`).substring(0,64)||e.split(`@`)[0],email:e,password:t}),signal:r.signal});if(!i.ok)throw Error(await Wn(i,`Registration failed`));await s(e,t)},refreshToken:async()=>{try{let e=Y.getItem(Vn);if(!e)throw Error(`No refresh token available`);let t=await fetch(`${R}/api/v1/auth/refresh`,{method:`POST`,headers:{"Content-Type":`application/json`,Authorization:`Bearer ${e}`}});if(!t.ok)throw Error(`Refresh token failed`);let n=await t.json();Y.setItem(X,n.access_token)}catch(e){throw c(),e}}};return(0,z.createElement)(Kn.Provider,{value:l},e)};function Yn({children:e,requireRole:t}){let{isAuthenticated:n,isLoading:r,user:i}=qn(),a=Oe();if(r)return(0,B.jsx)(`div`,{className:`min-h-screen flex items-center justify-center bg-[var(--bg-primary)]`,children:(0,B.jsxs)(`div`,{className:`flex flex-col items-center gap-4`,children:[(0,B.jsx)(`div`,{className:`w-10 h-10 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin`}),(0,B.jsx)(`p`,{className:`text-sm text-[var(--text-muted)]`,children:`Loading session…`})]})});if(!n){let e=encodeURIComponent(a.pathname+a.search);return(0,B.jsx)(k,{to:`/login?from=${e}`,replace:!0})}return t&&i?.role!==t&&i?.role!==`admin`?(0,B.jsx)(k,{to:`/dashboard`,replace:!0}):(0,B.jsx)(B.Fragment,{children:e})}var Z={en:`Navigation`,ar:`التنقل`},Xn={en:`Engineering`,ar:`الهندسة`},Zn={en:`Actions`,ar:`إجراءات`},Qn=[{id:`nav-dashboard`,label:{en:`Dashboard`,ar:`لوحة التحكم`},description:{en:`Go to main dashboard`,ar:`الذهاب للوحة الرئيسية`},icon:T,shortcut:`G D`,section:Z,buildAction:e=>()=>e(`/dashboard`)},{id:`nav-studies`,label:{en:`Studies`,ar:`الدراسات`},description:{en:`Engineering studies`,ar:`نظرة عامة على الدراسات`},icon:me,shortcut:`G S`,section:Z,buildAction:e=>()=>e(`/studies`)},{id:`nav-assistant`,label:{en:`AI Assistant`,ar:`المساعد الذكي`},description:{en:`Chat with AI agents`,ar:`الدردشة مع الوكلاء`},icon:m,shortcut:`G A`,section:Z,buildAction:e=>()=>e(`/assistant`)},{id:`nav-projects`,label:{en:`Projects`,ar:`المشاريع`},description:{en:`Manage projects`,ar:`إدارة المشاريع`},icon:S,shortcut:`G P`,section:Z,buildAction:e=>()=>e(`/projects`)},{id:`nav-asset-management`,label:{en:`Asset Management`,ar:`إدارة الأصول`},description:{en:`Power system assets`,ar:`أصول النظام`},icon:x,section:Z,buildAction:e=>()=>e(`/asset-management`)},{id:`nav-reports`,label:{en:`Reports`,ar:`التقارير`},description:{en:`View reports`,ar:`عرض التقارير`},icon:o,section:Z,buildAction:e=>()=>e(`/reports`)},{id:`nav-settings`,label:{en:`Settings`,ar:`الإعدادات`},description:{en:`App settings`,ar:`إعدادات التطبيق`},icon:O,shortcut:`G ,`,section:Z,buildAction:e=>()=>e(`/settings`)},{id:`nav-diagnostics`,label:{en:`Diagnostics`,ar:`التشخيص`},description:{en:`System checks`,ar:`فحوصات النظام`},icon:w,section:Z,buildAction:e=>()=>e(`/diagnostics`)},{id:`nav-logs`,label:{en:`Logs`,ar:`السجلات`},description:{en:`Audit log`,ar:`سجل التدقيق`},icon:Fe,section:Z,buildAction:e=>()=>e(`/logs`)},{id:`nav-admin`,label:{en:`Administration`,ar:`الإدارة`},description:{en:`System admin`,ar:`إدارة النظام`},icon:M,section:Z,buildAction:e=>()=>e(`/admin`)},{id:`nav-etap`,label:{en:`ETAP Integration`,ar:`تكامل ETAP`},icon:Ue,section:Xn,buildAction:e=>()=>e(`/etap`)},{id:`nav-gis`,label:{en:`GIS Integration`,ar:`تكامل GIS`},icon:se,section:Xn,buildAction:e=>()=>e(`/gis`)},{id:`nav-digital-twin`,label:{en:`Digital Twin`,ar:`التوأم الرقمي`},icon:E,section:Xn,buildAction:e=>()=>e(`/digital-twin`)},{id:`nav-code-guard`,label:{en:`Code Guard`,ar:`حارس الكود`},icon:M,section:Xn,buildAction:e=>()=>e(`/code-guard`)},{id:`act-import`,label:{en:`Import Data`,ar:`استيراد البيانات`},icon:te,section:Zn,buildAction:e=>()=>e(`/data-import`)},{id:`act-export`,label:{en:`Export Data`,ar:`تصدير البيانات`},icon:Ie,section:Zn,buildAction:e=>()=>e(`/data-export`)},{id:`act-help`,label:{en:`Smart Help`,ar:`المساعدة الذكية`},icon:qe,shortcut:`F1`,section:Zn,buildAction:()=>()=>globalThis.dispatchEvent(new CustomEvent(`toggle-smart-help`))},{id:`act-magic-help`,label:{en:`✨ Magic Help Inspector`,ar:`✨ فاحص المساعدة`},icon:Ue,section:Zn,buildAction:()=>()=>globalThis.dispatchEvent(new CustomEvent(`start-magic-help-inspect`))}];function $n(e,t){return Qn.map(n=>({id:n.id,label:n.label[e],description:n.description?.[e],icon:n.icon,shortcut:n.shortcut,section:n.section[e],action:n.buildAction(t)}))}function er(){let[e,t]=(0,z.useState)(!1),[n,r]=(0,z.useState)(``),[i,a]=(0,z.useState)(0),o=(0,z.useRef)(null),s=(0,z.useRef)(null),c=Pe(),{i18n:l}=P(),u=l.language===`ar`?`ar`:`en`,d=(0,z.useMemo)(()=>$n(u,c),[u,c]),f=(0,z.useMemo)(()=>{if(!n.trim())return d;let e=n.toLowerCase();return d.filter(t=>`${t.label} ${t.description||``} ${t.section} ${t.id}`.toLowerCase().includes(e))},[n,d]),p=(0,z.useMemo)(()=>{let e=new Set;for(let t of f)e.add(t.section);return Array.from(e)},[f]),m=(0,z.useCallback)(e=>{e.action(),t(!1),r(``),a(0)},[]);return(0,z.useEffect)(()=>{let e=e=>{(e.ctrlKey||e.metaKey)&&e.key===`k`&&(e.preventDefault(),t(e=>!e))};return globalThis.addEventListener(`keydown`,e),()=>globalThis.removeEventListener(`keydown`,e)},[]),(0,z.useEffect)(()=>{e&&(setTimeout(()=>o.current?.focus(),50),a(0))},[e]),(0,z.useEffect)(()=>{a(0)},[n]),(0,z.useEffect)(()=>{if(!e)return;let n=e=>{e.key===`ArrowDown`?(e.preventDefault(),a(e=>Math.min(e+1,Math.max(f.length-1,0)))):e.key===`ArrowUp`?(e.preventDefault(),a(e=>Math.max(e-1,0))):e.key===`Enter`&&f[i]?(e.preventDefault(),m(f[i])):e.key===`Escape`&&(e.preventDefault(),t(!1),r(``))};return globalThis.addEventListener(`keydown`,n),()=>globalThis.removeEventListener(`keydown`,n)},[e,f,i,m]),(0,z.useEffect)(()=>{s.current&&s.current.querySelector(`[data-index="${i}"]`)?.scrollIntoView({block:`nearest`})},[i]),e?(0,B.jsxs)(`div`,{className:`fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]`,children:[(0,B.jsx)(`button`,{type:`button`,className:`absolute inset-0 bg-black/60 backdrop-blur-sm cursor-default border-0 p-0`,"aria-label":`Close command palette`,onClick:()=>{t(!1),r(``)},onKeyDown:e=>{(e.key===`Enter`||e.key===` `)&&(t(!1),r(``))}}),(0,B.jsxs)(`div`,{className:`relative z-[101] w-full max-w-xl mx-4 bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-xl shadow-2xl overflow-hidden`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-3 px-4 py-3 border-b border-[var(--border-primary)]`,children:[(0,B.jsx)(I,{className:`w-5 h-5 text-[var(--text-muted)] shrink-0`}),(0,B.jsx)(`input`,{ref:o,type:`text`,value:n,onChange:e=>r(e.target.value),placeholder:u===`ar`?`ابحث في ${f.length} عنصر...`:`Search ${f.length} items...`,className:`flex-1 bg-transparent text-[var(--text-primary)] text-sm placeholder:text-[var(--text-muted)] outline-none`}),(0,B.jsx)(`kbd`,{className:`px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded`,children:`ESC`})]}),(0,B.jsx)(`div`,{ref:s,className:`max-h-[50vh] overflow-y-auto py-2`,children:f.length>0?p.map(e=>{let t=f.map((e,t)=>({cmd:e,idx:t})).filter(({cmd:t})=>t.section===e);return(0,B.jsxs)(`div`,{children:[(0,B.jsx)(`div`,{className:`px-4 py-1.5 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider`,children:e}),t.map(({cmd:e,idx:t})=>{let n=t===i;return(0,B.jsxs)(`button`,{"data-index":t,onClick:()=>m(e),onMouseEnter:()=>a(t),className:q(`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors`,n?`bg-[var(--accent-glow)] text-[var(--accent-primary)]`:`text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]`),type:`button`,children:[(0,B.jsx)(e.icon,{className:q(`w-4 h-4 shrink-0`,n?`text-[var(--accent-primary)]`:`text-[var(--text-muted)]`)}),(0,B.jsxs)(`div`,{className:`flex-1 min-w-0`,children:[(0,B.jsx)(`div`,{className:`text-sm font-medium truncate`,children:e.label}),e.description&&(0,B.jsx)(`div`,{className:`text-xs text-[var(--text-muted)] truncate`,children:e.description})]}),e.shortcut&&(0,B.jsx)(`div`,{className:`flex gap-1`,children:e.shortcut.split(` `).map(e=>(0,B.jsx)(`kbd`,{className:`px-1.5 py-0.5 text-[10px] font-mono text-[var(--text-muted)] bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded`,children:e},e))}),n&&(0,B.jsx)(g,{className:`w-3.5 h-3.5 text-[var(--accent-primary)] shrink-0`})]},e.id)})]},e)}):(0,B.jsx)(`div`,{className:`px-4 py-8 text-center text-sm text-[var(--text-muted)]`,children:u===`ar`?`لا توجد نتائج لـ "${n}"`:`No results for "${n}"`})}),(0,B.jsxs)(`div`,{className:`flex items-center gap-4 px-4 py-2.5 border-t border-[var(--border-primary)] text-[10px] text-[var(--text-muted)]`,children:[(0,B.jsxs)(`span`,{className:`flex items-center gap-1`,children:[(0,B.jsx)(be,{className:`w-3 h-3`}),` K to toggle`]}),(0,B.jsx)(`span`,{children:`↑↓ navigate`}),(0,B.jsx)(`span`,{children:`↵ select`}),(0,B.jsx)(`span`,{children:`esc close`}),(0,B.jsxs)(`span`,{className:`ml-auto`,children:[f.length,` commands`]})]})]})]}):null}var tr={d:`/dashboard`,p:`/projects`,s:`/studies`,a:`/assistant`,r:`/reports`,e:`/settings`,t:`/digital-twin`,i:`/diagnostics`,l:`/logs`};function nr(e){let t=[];(e.ctrlKey||e.metaKey)&&t.push(`ctrl`),e.shiftKey&&t.push(`shift`),e.altKey&&t.push(`alt`);let n=e.key.toLowerCase();return n===` `&&(n=`space`),t.push(n),t.join(`+`)}function rr(e){let t=e;return t?t.tagName===`INPUT`||t.tagName===`TEXTAREA`||t.isContentEditable:!1}function ir(e){globalThis.dispatchEvent(new CustomEvent(`shortcut-g-sequence`));let t=n=>{let r=tr[n.key.toLowerCase()];r&&(n.preventDefault(),e(r)),globalThis.removeEventListener(`keydown`,t)};setTimeout(()=>globalThis.removeEventListener(`keydown`,t),1500),globalThis.addEventListener(`keydown`,t,{once:!0})}function ar(){let e=Pe(),[t,n]=(0,z.useState)(!1),r=(0,z.useCallback)(()=>n(!0),[]),i=(0,z.useCallback)(()=>n(!1),[]);return(0,z.useEffect)(()=>{let t=t=>{let r=rr(t.target),i=t.ctrlKey||t.metaKey,a=t.key.startsWith(`F`);if(r&&!i&&!a)return;let o=nr(t);if(o===`g`&&!r){t.preventDefault(),ir(e);return}switch(o){case`ctrl+k`:break;case`f1`:case`ctrl+h`:t.preventDefault(),globalThis.dispatchEvent(new CustomEvent(`toggle-smart-help`));break;case`ctrl+shift+h`:t.preventDefault(),globalThis.dispatchEvent(new CustomEvent(`start-magic-help-inspect`));break;case`ctrl+/`:t.preventDefault(),n(e=>!e);break;case`shift+/`:r||(t.preventDefault(),n(e=>!e));break;case`ctrl+n`:t.preventDefault(),e(`/studies`);break;case`ctrl+s`:t.preventDefault(),globalThis.dispatchEvent(new CustomEvent(`shortcut-save`));break;case`ctrl+e`:t.preventDefault(),globalThis.dispatchEvent(new CustomEvent(`shortcut-export`));break;case`escape`:r||globalThis.dispatchEvent(new CustomEvent(`shortcut-escape`));break;case`f11`:t.preventDefault(),document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();break;case`ctrl+shift+l`:t.preventDefault(),globalThis.dispatchEvent(new CustomEvent(`toggle-theme`));break;case`ctrl+shift+g`:t.preventDefault(),globalThis.dispatchEvent(new CustomEvent(`toggle-language`))}};return globalThis.addEventListener(`keydown`,t),()=>globalThis.removeEventListener(`keydown`,t)},[e]),{shortcutsPanelOpen:t,openShortcutsPanel:r,closeShortcutsPanel:i}}var or=[{keys:[`G`,`D`],description:`Go to Dashboard`,category:`navigation`},{keys:[`G`,`P`],description:`Go to Projects`,category:`navigation`},{keys:[`G`,`S`],description:`Go to Studies`,category:`navigation`},{keys:[`G`,`A`],description:`Go to AI Assistant`,category:`navigation`},{keys:[`G`,`R`],description:`Go to Reports`,category:`navigation`},{keys:[`G`,`E`],description:`Go to Settings`,category:`navigation`},{keys:[`G`,`T`],description:`Go to Digital Twin`,category:`navigation`},{keys:[`G`,`I`],description:`Go to Diagnostics`,category:`navigation`},{keys:[`G`,`L`],description:`Go to Logs`,category:`navigation`},{keys:[`Ctrl`,`K`],description:`Open Command Palette`,category:`actions`},{keys:[`Ctrl`,`N`],description:`New Study`,category:`actions`},{keys:[`Ctrl`,`S`],description:`Save Current Work`,category:`actions`},{keys:[`Ctrl`,`E`],description:`Export Data`,category:`actions`},{keys:[`Esc`],description:`Close Modal / Drawer`,category:`actions`},{keys:[`F1`],description:`Open Smart Help`,category:`help`},{keys:[`Ctrl`,`H`],description:`Toggle Help Panel`,category:`help`},{keys:[`Ctrl`,`Shift`,`H`],description:`Magic Help Inspector`,category:`help`},{keys:[`Ctrl`,`/`],description:`Show Keyboard Shortcuts`,category:`help`},{keys:[`?`],description:`Show Keyboard Shortcuts`,category:`help`},{keys:[`F11`],description:`Toggle Fullscreen`,category:`view`},{keys:[`Ctrl`,`Shift`,`L`],description:`Toggle Theme`,category:`view`},{keys:[`Ctrl`,`Shift`,`G`],description:`Toggle Language (EN/AR)`,category:`view`}],sr={navigation:{icon:He,label:`Navigation`,color:`text-blue-400`},actions:{icon:Ue,label:`Actions`,color:`text-amber-400`},help:{icon:qe,label:`Help`,color:`text-brand-400`},view:{icon:we,label:`View`,color:`text-green-400`}};function cr({children:e}){return(0,B.jsx)(`kbd`,{className:q(`inline-flex items-center justify-center min-w-[28px] h-7 px-2`,`bg-[var(--bg-elevated)] border border-[var(--border-secondary)]`,`rounded-md text-xs font-mono font-medium text-[var(--text-secondary)]`,`shadow-[0_2px_0_0_var(--border-primary)]`,`transition-all`),children:e})}function lr({keys:e}){return(0,B.jsx)(`div`,{className:`flex items-center gap-1`,children:e.map((t,n)=>(0,B.jsxs)(`span`,{className:`flex items-center gap-1`,children:[(0,B.jsx)(cr,{children:t}),t!==e[e.length-1]&&(0,B.jsx)(`span`,{className:`text-[var(--text-muted)] text-xs`,children:t===`G`?`→`:`+`})]},n))})}function ur({open:e,onClose:t}){let r=Array.from(new Set(or.map(e=>e.category)));return(0,B.jsx)(n,{children:e&&(0,B.jsxs)(B.Fragment,{children:[(0,B.jsx)(i.div,{initial:{opacity:0},animate:{opacity:1},exit:{opacity:0},className:`fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm`,onClick:t}),(0,B.jsx)(i.div,{initial:{opacity:0,scale:.95,y:-20},animate:{opacity:1,scale:1,y:0},exit:{opacity:0,scale:.95,y:-20},transition:{duration:.2,ease:`easeOut`},className:`fixed top-[10vh] left-1/2 -translate-x-1/2 z-[201] w-full max-w-2xl mx-4`,children:(0,B.jsxs)(`div`,{className:`bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-2xl shadow-2xl shadow-black/40 overflow-hidden`,children:[(0,B.jsxs)(`div`,{className:`flex items-center justify-between px-6 py-4 border-b border-[var(--border-primary)] bg-gradient-to-r from-brand-500/5 to-transparent`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-3`,children:[(0,B.jsx)(`div`,{className:`w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center`,children:(0,B.jsx)(be,{className:`w-5 h-5 text-brand-400`})}),(0,B.jsxs)(`div`,{children:[(0,B.jsx)(`h2`,{className:`text-base font-semibold text-[var(--text-primary)]`,children:`Keyboard Shortcuts`}),(0,B.jsxs)(`p`,{className:`text-xs text-[var(--text-muted)]`,children:[`Press`,` `,(0,B.jsx)(`kbd`,{className:`px-1 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] font-mono`,children:`Ctrl`}),` + `,(0,B.jsx)(`kbd`,{className:`px-1 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] font-mono`,children:`/`}),` `,`anytime to toggle this panel`]})]})]}),(0,B.jsx)(`button`,{type:`button`,onClick:t,className:`p-2 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors`,children:(0,B.jsx)(j,{className:`w-4 h-4`})})]}),(0,B.jsx)(`div`,{className:`max-h-[60vh] overflow-y-auto p-6`,children:(0,B.jsx)(`div`,{className:`grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-6`,children:r.map(e=>{let t=sr[e],n=or.filter(t=>t.category===e);return(0,B.jsxs)(`div`,{children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-2 mb-3`,children:[(0,B.jsx)(t.icon,{className:q(`w-4 h-4`,t.color)}),(0,B.jsx)(`span`,{className:`text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]`,children:t.label}),(0,B.jsx)(`div`,{className:`flex-1 h-px bg-[var(--border-primary)]`})]}),(0,B.jsx)(`div`,{className:`space-y-2`,children:n.map(e=>(0,B.jsxs)(`div`,{className:`flex items-center justify-between gap-3 py-1.5 px-2 rounded-lg hover:bg-[var(--bg-elevated)] transition-colors group`,children:[(0,B.jsx)(`span`,{className:`text-xs text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors`,children:e.description}),(0,B.jsx)(lr,{keys:e.keys})]},e.description))})]},e)})})}),(0,B.jsxs)(`div`,{className:`flex items-center justify-between px-6 py-3 border-t border-[var(--border-primary)] bg-[var(--bg-primary)]/50`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-2 text-[10px] text-[var(--text-muted)]`,children:[(0,B.jsx)(ye,{className:`w-3 h-3`}),(0,B.jsx)(`span`,{children:`Navigation shortcuts use a two-key sequence: press`}),(0,B.jsx)(cr,{children:`G`}),(0,B.jsx)(`span`,{children:`then the destination key`})]}),(0,B.jsxs)(`div`,{className:`flex items-center gap-1 text-[10px] text-[var(--text-muted)]`,children:[(0,B.jsx)(Ve,{className:`w-3 h-3`}),(0,B.jsx)(`span`,{children:`Press Esc to close`})]})]})]})})]})})}var Q={backend_unavailable:{topic:`troubleshooting.backend`,title:`Backend Service Unavailable`,description:`The engineering service is not responding. This usually means the Python backend is not running or the connection was refused.`,url:`https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-#quick-start`,actions:[{label:`Check Backend Status`,action:`check_status`},{label:`Restart Service`,action:`restart_service`}]},auth_failed:{topic:`troubleshooting.auth`,title:`Authentication Failed`,description:`Your credentials were rejected. Your session may have expired or the API key is invalid.`,actions:[{label:`Refresh Token`,action:`refresh_token`},{label:`Check API Key`,action:`check_api_key`}]},project_not_found:{topic:`projects.troubleshooting`,title:`Project Not Found`,description:`The requested project does not exist or has been deleted. It may have been removed by another user.`,actions:[{label:`Browse Projects`,action:`browse_projects`},{label:`Create New Project`,action:`create_project`}]},report_generation_failed:{topic:`reports.troubleshooting`,title:`Report Generation Failed`,description:`The report could not be generated. This may be due to missing study results or a template error.`,actions:[{label:`Run Study First`,action:`run_study`},{label:`Check Templates`,action:`check_templates`}]},study_failed:{topic:`studies.troubleshooting`,title:`Study Execution Failed`,description:`The engineering study did not complete successfully. Check your input parameters and try again.`,actions:[{label:`Validate Input`,action:`validate_input`},{label:`Try Different Parameters`,action:`retry_study`}]},network_error:{topic:`troubleshooting.network`,title:`Network Error`,description:`A network error occurred while communicating with the server. Check your internet connection.`,actions:[{label:`Retry Request`,action:`retry`},{label:`Check Connectivity`,action:`check_connectivity`}]},rate_limited:{topic:`troubleshooting.rate_limit`,title:`Rate Limit Exceeded`,description:`Too many requests were sent in a short period. Wait a moment before trying again.`,actions:[{label:`Wait and Retry`,action:`wait_retry`}]},validation_error:{topic:`input.validation`,title:`Input Validation Error`,description:`The data you provided does not meet the required format. Check the fields and try again.`,actions:[{label:`Review Input`,action:`review_input`}]}};function dr(e){let t=(typeof e==`string`?e:e.message).toLowerCase();return t.includes(`fetch`)||t.includes(`network`)||t.includes(`econnrefused`)||t.includes(`failed to fetch`)?Q.backend_unavailable:t.includes(`401`)||t.includes(`unauthorized`)||t.includes(`token`)?Q.auth_failed:t.includes(`404`)||t.includes(`not found`)?Q.project_not_found:t.includes(`report`)?Q.report_generation_failed:t.includes(`study`)||t.includes(`engine`)?Q.study_failed:t.includes(`429`)||t.includes(`rate limit`)?Q.rate_limited:t.includes(`valid`)?Q.validation_error:Q.network_error}function fr({error:e,onDismiss:t,onRetry:n}){let[r,i]=(0,z.useState)(null),[a,o]=(0,z.useState)(!1);(0,z.useEffect)(()=>{e?(i(dr(e)),o(!0)):(i(null),o(!1))},[e]);let s=(0,z.useCallback)(e=>{switch(e){case`check_status`:case`check_api_key`:case`check_connectivity`:globalThis.location.hash=`/diagnostics`;break;case`browse_projects`:globalThis.location.hash=`/projects`;break;case`create_project`:globalThis.location.hash=`/projects`;break;case`run_study`:globalThis.location.hash=`/studies`;break;case`retry`:case`retry_study`:case`wait_retry`:n?.()}t()},[n,t]);return!e||!r?null:(0,B.jsxs)(`div`,{className:q(`fixed bottom-4 left-4 z-[90] w-96 max-w-[calc(100vw-2rem)]`,`bg-[var(--bg-secondary)] border border-red-500/30 rounded-xl shadow-xl shadow-red-500/10`,`transition-all duration-300`,a?`translate-y-0 opacity-100`:`translate-y-4 opacity-0 pointer-events-none`),role:`alertdialog`,"aria-modal":`false`,"aria-label":r.title,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-3 px-4 py-3 border-b border-[var(--border-primary)]`,children:[(0,B.jsx)(`div`,{className:`w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center shrink-0`,children:(0,B.jsx)(D,{className:`w-4 h-4 text-red-400`})}),(0,B.jsxs)(`div`,{className:`flex-1 min-w-0`,children:[(0,B.jsx)(`div`,{className:`text-sm font-medium text-[var(--text-primary)]`,children:r.title}),(0,B.jsx)(`div`,{className:`text-xs text-[var(--text-muted)]`,children:r.topic})]}),(0,B.jsx)(`button`,{type:`button`,onClick:t,className:`p-1 rounded hover:bg-[var(--bg-elevated)] text-[var(--text-muted)]`,"aria-label":`Dismiss error`,children:(0,B.jsx)(j,{className:`w-4 h-4`})})]}),(0,B.jsx)(`div`,{className:`px-4 py-3`,role:`alert`,"aria-live":`assertive`,"aria-atomic":`true`,children:(0,B.jsx)(`p`,{className:`text-xs text-[var(--text-secondary)] leading-relaxed`,children:r.description})}),(0,B.jsxs)(`div`,{className:`px-4 pb-3 flex gap-2`,children:[n&&(0,B.jsxs)(`button`,{type:`button`,onClick:()=>{n(),t()},className:`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] rounded-lg hover:bg-[var(--accent-primary)]/20 transition-colors`,children:[(0,B.jsx)(je,{className:`w-3 h-3`}),`Retry`]}),r.actions?.map(e=>(0,B.jsx)(`button`,{type:`button`,onClick:()=>s(e.action),className:`flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-[var(--bg-elevated)] text-[var(--text-secondary)] rounded-lg hover:bg-[var(--border-primary)] transition-colors`,children:e.label},e.label)),r.url&&(0,B.jsxs)(`a`,{href:r.url,target:`_blank`,rel:`noopener noreferrer`,className:`flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors`,children:[(0,B.jsx)(ke,{className:`w-3 h-3`}),`Help`]})]})]})}var pr=[{contextId:`dashboard`,topicId:`dashboard.overview`,priority:1},{contextId:`dashboard.overview`,topicId:`dashboard.overview`,priority:1},{contextId:`dashboard.status-cards`,topicId:`dashboard.overview`,priority:2},{contextId:`dashboard.quick-actions`,topicId:`studies.overview`,priority:2},{contextId:`dashboard.recent-studies`,topicId:`studies.overview`,priority:2},{contextId:`projects`,topicId:`projects.create`,priority:1},{contextId:`projects.create`,topicId:`projects.create`,priority:1},{contextId:`projects.manage`,topicId:`projects.manage`,priority:1},{contextId:`projects.new-button`,topicId:`projects.create`,priority:2},{contextId:`projects.search`,topicId:`projects.manage`,priority:2},{contextId:`projects.filter`,topicId:`projects.manage`,priority:2},{contextId:`projects.card`,topicId:`projects.manage`,priority:2},{contextId:`studies`,topicId:`studies.overview`,priority:1},{contextId:`studies.overview`,topicId:`studies.overview`,priority:1},{contextId:`studies.load-flow`,topicId:`studies.load-flow`,priority:1},{contextId:`studies.short-circuit`,topicId:`studies.short-circuit`,priority:1},{contextId:`studies.arc-flash`,topicId:`studies.arc-flash`,priority:1},{contextId:`studies.harmonic`,topicId:`studies.harmonic`,priority:1},{contextId:`studies.motor-starting`,topicId:`studies.motor-starting`,priority:1},{contextId:`studies.protection`,topicId:`studies.protection`,priority:1},{contextId:`studies.cable-sizing`,topicId:`studies.cable-sizing`,priority:1},{contextId:`studies.earth-grid`,topicId:`studies.earth-grid`,priority:1},{contextId:`studies.stability`,topicId:`studies.stability`,priority:1},{contextId:`studies.opf`,topicId:`studies.opf`,priority:1},{contextId:`studies.run-button`,topicId:`studies.overview`,priority:2},{contextId:`studies.parameters`,topicId:`studies.overview`,priority:2},{contextId:`ai-assistant`,topicId:`ai-assistant.overview`,priority:1},{contextId:`ai-assistant.overview`,topicId:`ai-assistant.overview`,priority:1},{contextId:`ai-assistant.chat-input`,topicId:`ai-assistant.overview`,priority:2},{contextId:`ai-assistant.agent-selector`,topicId:`ai-assistant.overview`,priority:2},{contextId:`ai-assistant.send-button`,topicId:`ai-assistant.overview`,priority:2},{contextId:`asset-management`,topicId:`asset-management.overview`,priority:1},{contextId:`asset-management.overview`,topicId:`asset-management.overview`,priority:1},{contextId:`asset-management.add-asset`,topicId:`asset-management.overview`,priority:2},{contextId:`etap`,topicId:`etap-integration.overview`,priority:1},{contextId:`etap-integration`,topicId:`etap-integration.overview`,priority:1},{contextId:`etap-integration.overview`,topicId:`etap-integration.overview`,priority:1},{contextId:`etap.worker-url`,topicId:`etap-integration.overview`,priority:2},{contextId:`etap.license-path`,topicId:`etap-integration.overview`,priority:2},{contextId:`etap.use-toggle`,topicId:`etap-integration.overview`,priority:2},{contextId:`gis`,topicId:`gis-integration.overview`,priority:1},{contextId:`gis-integration`,topicId:`gis-integration.overview`,priority:1},{contextId:`gis-integration.overview`,topicId:`gis-integration.overview`,priority:1},{contextId:`gis.provider-select`,topicId:`gis-integration.overview`,priority:2},{contextId:`gis.import-button`,topicId:`gis-integration.overview`,priority:2},{contextId:`reports`,topicId:`reports.generate`,priority:1},{contextId:`reports.generate`,topicId:`reports.generate`,priority:1},{contextId:`reports.new-button`,topicId:`reports.generate`,priority:2},{contextId:`reports.format-select`,topicId:`reports.generate`,priority:2},{contextId:`digital-twin`,topicId:`digital-twin.overview`,priority:1},{contextId:`digital-twin.overview`,topicId:`digital-twin.overview`,priority:1},{contextId:`digital-twin.sync-toggle`,topicId:`digital-twin.overview`,priority:2},{contextId:`settings`,topicId:`settings.backend`,priority:1},{contextId:`settings.backend`,topicId:`settings.backend`,priority:1},{contextId:`settings.external-services`,topicId:`settings.external-services`,priority:1},{contextId:`settings.ai-providers`,topicId:`settings.ai-providers`,priority:1},{contextId:`settings.scada`,topicId:`integration.scada`,priority:1},{contextId:`settings.test-connection`,topicId:`settings.external-services`,priority:2},{contextId:`settings.save`,topicId:`settings.backend`,priority:2},{contextId:`settings.export`,topicId:`settings.backend`,priority:2},{contextId:`settings.reset`,topicId:`settings.backend`,priority:2},{contextId:`code-guard`,topicId:`code-guard.overview`,priority:1},{contextId:`code-guard.overview`,topicId:`code-guard.overview`,priority:1},{contextId:`code-guard.editor`,topicId:`code-guard.overview`,priority:2},{contextId:`code-guard.review-button`,topicId:`code-guard.overview`,priority:2},{contextId:`data-import`,topicId:`data-import.overview`,priority:1},{contextId:`data-import.overview`,topicId:`data-import.overview`,priority:1},{contextId:`data-export`,topicId:`data-export.overview`,priority:1},{contextId:`data-export.overview`,topicId:`data-export.overview`,priority:1},{contextId:`admin`,topicId:`administration.overview`,priority:1},{contextId:`administration`,topicId:`administration.overview`,priority:1},{contextId:`administration.overview`,topicId:`administration.overview`,priority:1},{contextId:`administration.user-list`,topicId:`administration.overview`,priority:2},{contextId:`diagnostics`,topicId:`diagnostics.overview`,priority:1},{contextId:`diagnostics.overview`,topicId:`diagnostics.overview`,priority:1},{contextId:`diagnostics.health-checks`,topicId:`diagnostics.overview`,priority:2},{contextId:`logs`,topicId:`logs.overview`,priority:1},{contextId:`logs.overview`,topicId:`logs.overview`,priority:1},{contextId:`logs.filter`,topicId:`logs.overview`,priority:2},{contextId:`magic-help`,topicId:`magic-help.inspector`,priority:1},{contextId:`magic-help.inspector`,topicId:`magic-help.inspector`,priority:1},{contextId:`troubleshooting.backend`,topicId:`troubleshooting.backend`,priority:1},{contextId:`troubleshooting.api`,topicId:`troubleshooting.api`,priority:1},{contextId:`troubleshooting.auth`,topicId:`troubleshooting.auth`,priority:1},{contextId:`action.create-project`,topicId:`projects.create`,priority:1},{contextId:`action.add-device`,topicId:`asset-management.overview`,priority:1},{contextId:`action.generate-report`,topicId:`reports.generate`,priority:1},{contextId:`action.run-study`,topicId:`studies.overview`,priority:1},{contextId:`action.sync-project`,topicId:`digital-twin.overview`,priority:1},{contextId:`action.configure-backend`,topicId:`settings.backend`,priority:1},{contextId:`action.configure-scada`,topicId:`integration.scada`,priority:1},{contextId:`action.test-connection`,topicId:`settings.external-services`,priority:1},{contextId:`action.open-help`,topicId:`magic-help.inspector`,priority:1}];function mr(e){return pr.filter(t=>t.contextId===e).sort((e,t)=>(t.priority??0)-(e.priority??0))[0]?.topicId??null}var hr=`[data-help-context], button, a, select, input, textarea, .card, [role="button"], h1, h2, h3, h4, li, label`,gr=String.raw`.fixed.z-\[100\], .magic-inspector-overlay, .magic-inspector-banner`,_r=[{contextId:`dashboard.overview`,keywords:[`dashboard`,`لوحة التحكم`,`التحكم`]},{contextId:`studies.load-flow`,keywords:[`load flow`,`تدفق الحمل`]},{contextId:`studies.short-circuit`,keywords:[`short circuit`,`دائرة قصيرة`,`قصر`]},{contextId:`studies.arc-flash`,keywords:[`arc flash`,`شرارة`,`قوس`]},{contextId:`studies.overview`,keywords:[`studies`,`دراسات`]},{contextId:`projects.create`,keywords:[`project`,`مشروع`]},{contextId:`reports.generate`,keywords:[`report`,`تقرير`]},{contextId:`digital-twin.overview`,keywords:[`twin`,`توأم`]},{contextId:`settings.backend`,keywords:[`settings`,`إعدادات`]},{contextId:`ai-assistant.overview`,keywords:[`assistant`,`مساعد`,`ذكاء`]},{contextId:`asset-management.overview`,keywords:[`asset`,`أصول`,`أصل`]},{contextId:`etap-integration.overview`,keywords:[`etap`,`إيتاب`]},{contextId:`gis-integration.overview`,keywords:[`gis`,`جغرافي`]},{contextId:`code-guard.overview`,keywords:[`code`,`كود`,`حارس`]},{contextId:`administration.overview`,keywords:[`admin`,`إدارة`,`مسؤول`]},{contextId:`diagnostics.overview`,keywords:[`diagnostic`,`تشخيص`]},{contextId:`logs.overview`,keywords:[`logs`,`سجلات`]},{contextId:`data-import.overview`,keywords:[`import`,`استيراد`]},{contextId:`data-export.overview`,keywords:[`export`,`تصدير`]},{contextId:`settings.external-services`,keywords:[`test`,`اختبار`,`اتصال`]}],vr=[{contextId:`dashboard.overview`,path:`dashboard`},{contextId:`projects.create`,path:`projects`},{contextId:`studies.overview`,path:`studies`},{contextId:`ai-assistant.overview`,path:`assistant`},{contextId:`asset-management.overview`,path:`asset`},{contextId:`etap-integration.overview`,path:`etap`},{contextId:`gis-integration.overview`,path:`gis`},{contextId:`reports.generate`,path:`reports`},{contextId:`digital-twin.overview`,path:`digital-twin`},{contextId:`settings.backend`,path:`settings`},{contextId:`code-guard.overview`,path:`code-guard`},{contextId:`data-import.overview`,path:`data-import`},{contextId:`data-export.overview`,path:`data-export`},{contextId:`administration.overview`,path:`admin`},{contextId:`diagnostics.overview`,path:`diagnostics`},{contextId:`logs.overview`,path:`logs`}];function yr(e){let t=e.toLowerCase();for(let e of _r)if(e.keywords.some(e=>t.includes(e)))return e.contextId;return null}function br(e){for(let t of vr)if(e.includes(t.path))return t.contextId;return`dashboard.overview`}function xr(e){let t=e.parentElement,n=0;for(;t&&n<5;){let e=t.dataset.helpContext;if(e)return e;t=t.parentElement,n++}return null}function Sr(e){return!!e.closest(gr)}function Cr(){let{i18n:e}=P(),t=e.language===`ar`?`ar`:`en`,[n,r]=(0,z.useState)(!1),[i,a]=(0,z.useState)(null),[o,s]=(0,z.useState)(``);return(0,z.useEffect)(()=>{let e=()=>{r(!0),document.body.style.cursor=`help`};return globalThis.addEventListener(`start-magic-help-inspect`,e),()=>{globalThis.removeEventListener(`start-magic-help-inspect`,e)}},[]),(0,z.useEffect)(()=>{if(!n)return;let e=e=>{let t=e.target;if(!t)return;let n=t.closest(hr);if(n&&!Sr(n)){a(n.getBoundingClientRect());let e=n.dataset.helpContext??null,t=(n.textContent||``).trim().slice(0,40),r=n.tagName.toLowerCase();s(e?`📋 ${e}`:`🔍 <${r}> "${t}"`)}else a(null),s(``)},t=e=>{e.key===`Escape`&&o()},i=e=>{e.preventDefault(),e.stopPropagation();let t=e.target;if(!t){o();return}let n=t.closest(hr),r=null;n&&(r=n.dataset.helpContext??null,r||=xr(n),r||=yr(n.textContent||``)),r||=br(globalThis.location.hash||globalThis.location.pathname),mr(r)||console.warn(`[MagicHelpInspector] contextId "${r}" is not in the contextRegistry. Falling back to dashboard.overview. Add an entry to contextRegistry.ts to fix.`),globalThis.dispatchEvent(new CustomEvent(`open-smart-help`,{detail:{contextId:r}})),o()},o=()=>{r(!1),a(null),s(``),document.body.style.cursor=`default`};return globalThis.addEventListener(`mousemove`,e),globalThis.addEventListener(`click`,i,!0),globalThis.addEventListener(`keydown`,t),()=>{globalThis.removeEventListener(`mousemove`,e),globalThis.removeEventListener(`click`,i,!0),globalThis.removeEventListener(`keydown`,t),document.body.style.cursor=`default`}},[n]),n?(0,B.jsxs)(B.Fragment,{children:[i&&(0,B.jsx)(`div`,{className:`magic-inspector-overlay fixed border-2 border-dashed border-[var(--accent-primary)] bg-[var(--accent-glow)] rounded-lg pointer-events-none transition-all duration-75 ease-out shadow-[0_0_15px_rgba(0,212,255,0.4)]`,style:{top:i.top-2,left:i.left-2,width:i.width+4,height:i.height+4,zIndex:99999}}),i&&o&&(0,B.jsx)(`div`,{className:`magic-inspector-banner fixed px-2.5 py-1 rounded-md bg-[rgba(15,21,37,0.95)] border border-[var(--accent-primary)] text-[10px] text-[var(--text-primary)] font-mono pointer-events-none`,style:{top:i.bottom+6,left:i.left,zIndex:99999,maxWidth:`300px`},children:o}),(0,B.jsxs)(`div`,{className:`magic-inspector-banner fixed top-6 left-1/2 -translate-x-1/2 px-5 py-3 rounded-full bg-[rgba(15,21,37,0.95)] border border-[var(--accent-primary)] shadow-2xl backdrop-blur-md flex items-center gap-3`,style:{zIndex:1e5},children:[(0,B.jsx)(`div`,{className:`w-6 h-6 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center animate-pulse`,children:(0,B.jsx)(ce,{className:`w-3.5 h-3.5 text-brand-400`})}),(0,B.jsx)(`div`,{className:`text-xs font-medium text-[var(--text-primary)]`,children:t===`ar`?(0,B.jsxs)(`span`,{children:[`✨ `,(0,B.jsx)(`strong`,{children:`وضع فحص المساعدة نشط`}),` — اضغط على أي عنصر أو بطاقة في الصفحة لشرح كيفية عملها. اضغط `,(0,B.jsx)(`strong`,{children:`ESC`}),` للخروج.`]}):(0,B.jsxs)(`span`,{children:[`✨ `,(0,B.jsx)(`strong`,{children:`Help Inspector Active`}),` — Click any element or card on the screen to see how it works. Press `,(0,B.jsx)(`strong`,{children:`ESC`}),` to exit.`]})}),(0,B.jsx)(`button`,{onClick:()=>r(!1),className:`ml-2 p-1 rounded hover:bg-white/10 transition-colors`,title:t===`ar`?`إغلاق`:`Close`,type:`button`,children:(0,B.jsx)(j,{className:`w-3.5 h-3.5 text-[var(--text-muted)]`})})]})]}):null}var wr=[{id:`getting-started`,label:{en:`Getting Started`,ar:`البداية`}},{id:`projects`,label:{en:`Projects`,ar:`المشاريع`}},{id:`fire-alarm`,label:{en:`Fire Alarm`,ar:`إنذار الحريق`}},{id:`engineering`,label:{en:`Engineering`,ar:`الهندسة`}},{id:`reports`,label:{en:`Reports`,ar:`التقارير`}},{id:`digital-twin`,label:{en:`Digital Twin`,ar:`التوأم الرقمي`}},{id:`settings`,label:{en:`Settings`,ar:`الإعدادات`}},{id:`troubleshooting`,label:{en:`Troubleshooting`,ar:`استكشاف الأخطاء`}},{id:`keyboard-shortcuts`,label:{en:`Keyboard Shortcuts`,ar:`اختصارات لوحة المفاتيح`}}],Tr=[{id:`dashboard.overview`,category:`getting-started`,title:{en:`Dashboard Overview`,ar:`نظرة عامة على لوحة التحكم`},description:{en:`Navigate the main dashboard and understand system status`,ar:`التنقل في لوحة التحكم الرئيسية وفهم حالة النظام`},content:{en:`The Dashboard is your central hub for monitoring the AhmedETAP Platform.

**Key Areas:**
- **Status Cards** — Real-time system health, active agents, and study metrics
- **Charts** — API activity, study distribution, and resource utilization
- **Quick Actions** — Shortcut buttons for common engineering tasks
- **Recent Studies** — Your latest study results and their status

**How to Use:**
1. On page load, the dashboard fetches health data from the backend
2. The green/red indicator in the top-right shows backend connection status
3. Click any chart to drill down into detailed metrics
4. Use the quick-action buttons to jump to a specific study type

**Tips:**
- The sidebar provides access to all modules
- Press Ctrl+K to open the command palette
- Press F1 anywhere for contextual help
- Click the Sparkles (✨) icon in the top bar to activate Magic Help`,ar:`لوحة التحكم هي مركزك المركزي لمراقبة منصة AhmedETAP.

**المناطق الرئيسية:**
- **بطاقات الحالة** — صحة النظام في الوقت الفعلي والوكلاء النشطين ومقاييس الدراسة
- **الرسوم البيانية** — نشاط API وتوزيع الدراسات واستخدام الموارد
- **الإجراءات السريعة** — أزرار اختصار للمهام الهندسية الشائعة
- **الدراسات الأخيرة** — أحدث نتائج دراساتك وحالتها

**كيفية الاستخدام:**
1. عند تحميل الصفحة، تجلب لوحة التحكم بيانات الحالة من الخادم
2. المؤشر الأخضر/الأحمر في الأعلى يُظهر حالة اتصال الخادم
3. انقر على أي رسم بياني للتفاصيل
4. استخدم أزرار الإجراءات السريعة للانتقال لنوع دراسة محدد

**نصائح:**
- يوفر الشريط الجانبي الوصول إلى جميع الوحدات
- اضغط Ctrl+K لفتح لوحة الأوامر
- اضغط F1 في أي مكان للمساعدة السياقية
- اضغط على أيقونة البريق (✨) في الشريط العلوي لتفعيل المساعدة السحرية`},tags:[`dashboard`,`overview`,`home`,`لوحة تحكم`,`نظرة عامة`],navigateTo:`/dashboard`,relatedTopics:[`projects.manage`,`studies.load-flow`]},{id:`keyboard-shortcuts`,category:`getting-started`,title:{en:`Keyboard Shortcuts`,ar:`اختصارات لوحة المفاتيح`},description:{en:`Essential keyboard shortcuts for faster workflow`,ar:`اختصارات لوحة المفاتيح الأساسية لسرعة العمل`},content:{en:`**Global Shortcuts:**
- \`F1\` — Open Smart Help (context-aware)
- \`Ctrl+K\` — Command Palette (search & navigate)
- \`Ctrl+H\` — Toggle Help Panel
- \`Esc\` — Close any open modal/drawer

**Magic Help Inspector:**
- Click the ✨ Sparkles icon in the top bar to start
- The cursor changes to a help cursor
- Click any element on screen to get its documentation
- Press \`Esc\` to exit inspector mode

**Navigation:**
- Use the sidebar (left side) to switch between modules
- Click the AhmedETAP logo to return to the dashboard
- Use breadcrumbs (top of content area) to navigate back

**Settings:**
- \`Ctrl+S\` — Save current settings (when on Settings page)`,ar:`**الاختصارات العامة:**
- \`F1\` — فتح المساعدة الذكية (حسب السياق)
- \`Ctrl+K\` — لوحة الأوامر (بحث وتنقل)
- \`Ctrl+H\` — إظهار/إخفاء لوحة المساعدة
- \`Esc\` — إغلاق أي نافذة مفتوحة

**فاحص المساعدة السحرية:**
- اضغط على أيقونة ✨ البريق في الشريط العلوي للبدء
- يتغير المؤشر إلى مؤشر مساعدة
- انقر على أي عنصر في الشاشة للحصول على شرحه
- اضغط \`Esc\` للخروج من وضع الفحص

**التنقل:**
- استخدم الشريط الجانبي (يسار) للتبديل بين الوحدات
- انقر على شعار AhmedETAP للعودة للوحة التحكم
- استخدم فتات الخبز (أعلى المحتوى) للرجوع للخلف

**الإعدادات:**
- \`Ctrl+S\` — حفظ الإعدادات الحالية (عند وجودك في صفحة الإعدادات)`},tags:[`keyboard`,`shortcuts`,`hotkeys`,`keys`,`لوحة مفاتيح`,`اختصارات`],relatedTopics:[`dashboard.overview`,`magic-help.inspector`]},{id:`magic-help.inspector`,category:`getting-started`,title:{en:`Magic Help Inspector`,ar:`فاحص المساعدة السحرية`},description:{en:`Click any element to instantly see its documentation`,ar:`انقر على أي عنصر لرؤية شرحه فوراً`},content:{en:`**What is Magic Help?**
Magic Help is an interactive inspector that lets you click on ANY element in the application and instantly see its documentation.

**How to Activate:**
1. Click the ✨ Sparkles icon in the top-right of the navbar
2. OR open the Help drawer (F1) and click "Magic Inspect"
3. The cursor changes to a help cursor
4. A floating banner appears: "Help Inspector Active"

**How to Use:**
1. Move your mouse over the page — elements highlight with a dashed cyan border
2. Click any element (button, card, icon, input) to open its help topic
3. The Smart Help drawer opens with detailed documentation
4. Press \`Esc\` or click anywhere to exit inspector mode

**What Gets Highlighted:**
- Buttons and links
- Cards and panels
- Form inputs and selects
- Headings (h1-h4)
- List items
- Any element with \`data-help-context\` attribute

**Tips:**
- If an element doesn't have specific docs, the inspector falls back to the page-level help
- The inspector works on every page in the application
- Use it to learn what each button does before clicking it`,ar:`**ما هي المساعدة السحرية؟**
المساعدة السحرية هي فاحص تفاعلي يتيح لك النقر على أي عنصر في التطبيق ورؤية شرحه فوراً.

**كيفية التفعيل:**
1. انقر على أيقونة ✨ البريق في أعلى يمين الشريط العلوي
2. أو افتح درج المساعدة (F1) وانقر "الفحص الذكي"
3. يتغير المؤشر إلى مؤشر مساعدة
4. يظهر شريط عائم: "وضع فحص المساعدة نشط"

**كيفية الاستخدام:**
1. حرّك الماوس فوق الصفحة — تتميز العناصر بحدود متقطعة سماوية
2. انقر على أي عنصر (زر، بطاقة، أيقونة، حقل) لفتح موضوع مساعدته
3. يفتح درج المساعدة الذكية مع الشرح التفصيلي
4. اضغط \`Esc\` أو انقر في أي مكان للخروج

**ما الذي يتم تمييزه:**
- الأزرار والروابط
- البطاقات واللوحات
- حقول الإدخال والقوائم
- العناوين (h1-h4)
- عناصر القائمة
- أي عنصر يحمل السمة \`data-help-context\`

**نصائح:**
- إذا لم يكن للعنصر شرح محدد، يلجأ الفاحص لمساعدة الصفحة العامة
- الفاحص يعمل في كل صفحات التطبيق
- استخدمه لتعلم وظيفة كل زر قبل النقر عليه`},tags:[`magic`,`help`,`inspector`,`inspect`,`سحري`,`مساعدة`,`فحص`],relatedTopics:[`keyboard-shortcuts`,`dashboard.overview`]},{id:`projects.create`,category:`projects`,title:{en:`Creating a Project`,ar:`إنشاء مشروع`},description:{en:`How to create and configure a new engineering project`,ar:`كيفية إنشاء وتكوين مشروع هندسي جديد`},content:{en:`**Steps to Create a Project:**
1. Navigate to **Projects** from the sidebar
2. Click the **"New Project"** button (top-right)
3. Fill in the form:
   - **Name** (required) — descriptive name, e.g. "IEEE 14-Bus Load Flow Study"
   - **Description** (optional) — what the project is for
   - **System Config** (optional) — JSON definition of buses, lines, generators
4. Click **Create**

**Project Status:**
- \`active\` — currently being worked on
- \`archived\` — completed and stored
- \`deleted\` — soft-deleted (recoverable)

**Tips:**
- Use descriptive names including the standard (IEEE/IEC) and bus count
- Add tags for better organization
- Projects are auto-saved as you work
- Each project can have multiple studies`,ar:`**خطوات إنشاء مشروع:**
1. انتقل إلى **المشاريع** من الشريط الجانبي
2. انقر على زر **"مشروع جديد"** (أعلى اليمين)
3. املأ النموذج:
   - **الاسم** (مطلوب) — اسم وصفي، مثل "دراسة تدفق حمل IEEE 14 باص"
   - **الوصف** (اختياري) — الغرض من المشروع
   - **تكوين النظام** (اختياري) — تعريف JSON للباصات والخطوط والمولدات
4. انقر على **إنشاء**

**حالة المشروع:**
- \`نشط\` — قيد العمل حالياً
- \`مؤرشف\` — مكتمل ومخزن
- \`محذوف\` — حذف ناعم (قابل للاسترجاع)

**نصائح:**
- استخدم أسماء وصفية تشمل المعيار (IEEE/IEC) وعدد الباصات
- أضف وسوماً لتنظيم أفضل
- تُحفظ المشاريع تلقائياً أثناء العمل
- كل مشروع يمكن أن يحتوي على دراسات متعددة`},tags:[`project`,`create`,`new`,`مشروع`,`إنشاء`,`جديد`],navigateTo:`/projects`,relatedTopics:[`projects.manage`,`studies.load-flow`]},{id:`projects.manage`,category:`projects`,title:{en:`Managing Projects`,ar:`إدارة المشاريع`},description:{en:`Open, edit, archive, and delete projects`,ar:`فتح وتعديل وأرشفة وحذف المشاريع`},content:{en:`**Project Management Actions:**

**Open a Project:**
- Click anywhere on a project card to open it
- The project dashboard shows its studies, settings, and history

**Edit a Project:**
- Click the pencil (✏️) icon on a project card
- Modify name, description, or system configuration
- Click **Save** to persist changes

**Archive a Project:**
- Click the archive (📦) icon
- Archived projects are hidden from the default list
- Use the status filter to view archived projects
- Archived projects can be restored

**Delete a Project:**
- Click the trash (🗑️) icon
- Confirm the deletion in the modal
- This is a soft-delete — the project is marked as \`deleted\` but not removed from the database
- Only admins can permanently delete projects

**Filter & Search:**
- Use the search box to find projects by name
- Use the status filter (active/archived/deleted) to narrow the list
- Sort by created date, name, or last activity`,ar:`**إجراءات إدارة المشاريع:**

**فتح مشروع:**
- انقر في أي مكان على بطاقة المشروع لفتحه
- تعرض لوحة تحكم المشروع دراساته وإعداداته وسجله

**تعديل مشروع:**
- انقر على أيقونة القلم (✏️) على بطاقة المشروع
- عدّل الاسم أو الوصف أو تكوين النظام
- انقر على **حفظ** للاحتفاظ بالتغييرات

**أرشفة مشروع:**
- انقر على أيقونة الأرشفة (📦)
- المشاريع المؤرشفة مخفية من القائمة الافتراضية
- استخدم فلتر الحالة لعرض المشاريع المؤرشفة
- يمكن استعادة المشاريع المؤرشفة

**حذف مشروع:**
- انقر على أيقونة سلة المهملات (🗑️)
- أكد الحذف في النافذة المنبثقة
- هذا حذف ناعم — يُعلَّم المشروع كـ \`محذوف\` لكن لا يُزال من قاعدة البيانات
- فقط المسؤولون يمكنهم حذف المشاريع نهائياً

**الفلترة والبحث:**
- استخدم صندوق البحث للعثور على مشاريع بالاسم
- استخدم فلتر الحالة (نشط/مؤرشف/محذوف) لتضييق القائمة
- رتّب حسب تاريخ الإنشاء أو الاسم أو آخر نشاط`},tags:[`project`,`manage`,`open`,`edit`,`archive`,`delete`,`مشروع`,`إدارة`,`فتح`,`تعديل`],navigateTo:`/projects`,relatedTopics:[`projects.create`,`studies.load-flow`]},{id:`studies.overview`,category:`engineering`,title:{en:`Studies Overview`,ar:`نظرة عامة على الدراسات`},description:{en:`All available engineering study types and how to run them`,ar:`جميع أنواع الدراسات الهندسية المتاحة وكيفية تشغيلها`},content:{en:`**Available Study Types:**

1. **Load Flow** — Newton-Raphson power flow analysis (IEEE 3002.7)
2. **Short Circuit** — IEC 60909 fault current calculation
3. **Arc Flash** — IEEE 1584-2018 incident energy analysis
4. **Harmonic Analysis** — IEEE 519-2022 distortion study
5. **Motor Starting** — IEEE 399 transient analysis
6. **Protection Coordination** — IEC 60255 relay curves
7. **Cable Sizing** — IEC 60364 current-carrying capacity
8. **Earth Grid** — IEEE 80 ground grid design
9. **Stability** — Transient stability analysis
10. **Optimal Power Flow (OPF)** — Cost-optimized dispatch

**How to Run a Study:**
1. Navigate to **Studies** from the sidebar
2. Click the study-type card you want to run
3. Configure the system (buses, lines, generators, loads)
4. Set study parameters (tolerance, max iterations, etc.)
5. Click **Run Study**
6. View results in the results panel
7. Optionally export to PDF/CSV

**Tips:**
- Each study type has its own input schema
- Studies can be run with the native engine or via ETAP (if connected)
- Results are cached for repeated runs with the same inputs
- Use the projects page to organize studies by project`,ar:`**أنواع الدراسات المتاحة:**

1. **تدفق الحمل** — تحليل تدفق القدرة بطريقة نيوتن-رافسون (IEEE 3002.7)
2. **الدائرة القصيرة** — حساب تيار العطل IEC 60909
3. **شرارة القوس** — تحليل طاقة الحادث IEEE 1584-2018
4. **تحليل التوافقيات** — دراسة التشوه IEEE 519-2022
5. **بدء المحرك** — تحليل عابر IEEE 399
6. **تنسيق الحماية** — منحنيات المُرحّل IEC 60255
7. **تحديد مقاس الكابلات** — القدرة على حمل التيار IEC 60364
8. **شبكة التأريض** — تصميم شبكة التأريض IEEE 80
9. **الاستقرار** — تحليل الاستقرار العابر
10. **تدفق القدرة الأمثل (OPF)** — إرسال أمثل للتكلفة

**كيفية تشغيل دراسة:**
1. انتقل إلى **الدراسات** من الشريط الجانبي
2. انقر على بطاقة نوع الدراسة التي تريد تشغيلها
3. قم بتكوين النظام (باصات، خطوط، مولدات، أحمال)
4. اضبط معلمات الدراسة (التسامح، أقصى تكرارات، إلخ)
5. انقر على **تشغيل الدراسة**
6. اعرض النتائج في لوحة النتائج
7. اخترياً صدّرها إلى PDF/CSV

**نصائح:**
- كل نوع دراسة له مخطط إدخال خاص به
- يمكن تشغيل الدراسات بالمحرك الأصلي أو عبر ETAP (إذا كان متصلاً)
- تُحفظ النتائج مؤقتاً للتشغيل المتكرر بنفس المدخلات
- استخدم صفحة المشاريع لتنظيم الدراسات حسب المشروع`},tags:[`studies`,`overview`,`all`,`دراسات`,`نظرة عامة`],navigateTo:`/studies`,relatedTopics:[`studies.load-flow`,`studies.short-circuit`,`studies.arc-flash`]},{id:`studies.load-flow`,category:`engineering`,title:{en:`Load Flow Study`,ar:`دراسة تدفق الحمل`},description:{en:`Newton-Raphson power flow analysis per IEEE 3002.7`,ar:`تحليل تدفق القدرة بطريقة نيوتن-رافسون حسب IEEE 3002.7`},content:{en:`**What it does:**
Calculates bus voltages, branch power flows, and system losses under steady-state conditions.

**Required Inputs:**
- **Buses** — at least one slack (swing) bus, plus PV and PQ buses
- **Lines** — with R1, X1, B1 parameters in per-unit or ohms
- **Transformers** — with R1, X1, tap ratio, phase shift
- **Generators** — at PV buses, with P and V setpoints
- **Loads** — at PQ buses, with P and Q values

**Parameters:**
- \`tolerance\` — convergence tolerance (default 1e-6)
- \`max_iterations\` — max Newton-Raphson iterations (default 50)
- \`method\` — \`newton_raphson\`, \`fast_decoupled\`, or \`dc\`

**Results:**
- Bus voltage magnitudes and angles
- Real and reactive power flows on each branch
- Total system losses
- Convergence report

**Common Issues:**
- "Singular Jacobian" — usually means a bus is disconnected; check line connectivity
- "Did not converge" — try a different initial guess or relax tolerance
- Negative losses — check per-unit base consistency`,ar:`**ما يفعله:**
يحسب جهود الباصات وتدفقات القدرة في الفروع وخسائر النظام في ظل الحالة المستقرة.

**المدخلات المطلوبة:**
- **الباصات** — باص slack واحد على الأقل، بالإضافة إلى باصات PV و PQ
- **الخطوط** — بمعلمات R1, X1, B1 بنظام per-unit أو أوم
- **المحولات** — بـ R1, X1، نسبة التحويل، إزاحة الطور
- **المولدات** — في باصات PV، مع قيم P و V المحددة
- **الأحمال** — في باصات PQ، مع قيم P و Q

**المعلمات:**
- \`tolerance\` — تسامح التقارب (افتراضي 1e-6)
- \`max_iterations\` — أقصى تكرارات نيوتن-رافسون (افتراضي 50)
- \`method\` — \`newton_raphson\` أو \`fast_decoupled\` أو \`dc\`

**النتائج:**
- جهود الباصات (القيمة والزاوية)
- تدفقات القدرة الفعلية والتفاعلية في كل فرع
- إجمالي خسائر النظام
- تقرير التقارب

**مشاكل شائعة:**
- "Jacobian مفرد" — عادةً يعني أن باص غير متصل؛ تحقق من اتصال الخطوط
- "لم يتقارب" — جرّب تخمين مبدئي مختلف أو تساهل في التسامح
- خسائر سلبية — تحقق من اتساق قاعدة per-unit`},tags:[`load`,`flow`,`newton`,`raphson`,`power`,`تدفق`,`حمل`,`قدرة`],navigateTo:`/studies/load_flow`,relatedTopics:[`studies.overview`,`studies.short-circuit`]},{id:`studies.short-circuit`,category:`engineering`,title:{en:`Short Circuit Study`,ar:`دراسة الدائرة القصيرة`},description:{en:`IEC 60909 fault current calculation`,ar:`حساب تيار العطل حسب IEC 60909`},content:{en:`**What it does:**
Calculates three-phase, line-to-ground, line-to-line, and double-line-to-ground fault currents at every bus.

**Required Inputs:**
- Same as Load Flow, PLUS:
- Generator subtransient reactance (\`X''d\`)
- Negative-sequence and zero-sequence reactances (X2, X0)
- Transformer connections (Yg, Y, D) for ground fault analysis
- Neutral grounding impedance

**IEC 60909 Parameters:**
- \`c_factor\` — voltage factor (1.1 for max, 1.0 for min)
- \`decayed_dc\` — true/false (compute asymmetrical peak)
- \`fault_type\` — \`3p\`, \`LG\`, \`LL\`, \`LLG\`

**Results:**
- Initial symmetrical short-circuit current (I''k)
- Peak short-circuit current (ip)
- DC component (idc)
- Breaking current (Ib) at contact opening time

**Standards:**
- IEC 60909-0:2016 — Calculation of currents
- IEC 60909-1:2002 — Factors for calculations`,ar:`**ما يفعله:**
يحسب تيارات العطل ثلاثية الطور، خط-أرض، خط-خط، وخط-خط-أرض في كل باص.

**المدخلات المطلوبة:**
- نفس تدفق الحمل، بالإضافة إلى:
- مفاعلة العبور الجزئية للمولد (\`X''d\`)
- مفاعلات التسلسل السالبة والصفرية (X2، X0)
- توصيلات المحولات (Yg، Y، D) لتحليل عطل الأرض
- مقاومة تأريض النقطة المحايدة

**معلمات IEC 60909:**
- \`c_factor\` — معامل الجهد (1.1 للأقصى، 1.0 للأدنى)
- \`decayed_dc\` — true/false (احسب القمة غير المتماثلة)
- \`fault_type\` — \`3p\`، \`LG\`، \`LL\`، \`LLG\`

**النتائج:**
- تيار القصر التماثلي الابتدائي (I''k)
- تيار ذروة القصر (ip)
- مركبة التيار المستمر (idc)
- تيار القطع (Ib) عند وقت فتح التلامس

**المعايير:**
- IEC 60909-0:2016 — حساب التيارات
- IEC 60909-1:2002 — معاملات الحسابات`},tags:[`short`,`circuit`,`fault`,`iec`,`60909`,`قصر`,`دائرة`,`عطل`],navigateTo:`/studies/short_circuit`,relatedTopics:[`studies.overview`,`studies.arc-flash`,`studies.protection`]},{id:`studies.arc-flash`,category:`engineering`,title:{en:`Arc Flash Study`,ar:`دراسة شرارة القوس`},description:{en:`IEEE 1584-2018 incident energy analysis`,ar:`تحليل طاقة الحادث حسب IEEE 1584-2018`},content:{en:`**What it does:**
Calculates incident energy (cal/cm²) and arc-flash boundary at each bus, used to specify PPE (Personal Protective Equipment) levels.

**Required Inputs:**
- Bolted fault current (from Short Circuit study)
- Arc duration (clearing time of protective device)
- Working distance (typical: 18" for LV, 24" for MV)
- System voltage
- Equipment type (panel, switchgear, open air)
- Electrode configuration (VCB, VCBB, HCB, etc.)

**IEEE 1584-2018 Parameters:**
- \`electrode_gap\` — typical gaps by voltage class
- \`arc_current_variation_factor\` — 1.0 default, 0.85 for reduced current
- \`enclosure_size\` — for medium-voltage equipment

**Results:**
- Incident energy (cal/cm²) at working distance
- Arc-flash boundary (inches)
- PPE category (0, 1, 2, 3, 4, or "Dangerous")
- Reduced incident energy at lower current (if applicable)

**Safety Notes:**
- Always round UP the PPE category
- Use the higher of: (a) bolted fault current, (b) reduced current calculation
- Document all assumptions for audit compliance`,ar:`**ما يفعله:**
يحسب طاقة الحادث (cal/cm²) وحدود شرارة القوس في كل باص، تُستخدم لتحديد مستويات معدات الحماية الشخصية (PPE).

**المدخلات المطلوبة:**
- تيار العطل الملحوم (من دراسة الدائرة القصيرة)
- مدة القوس (وقت تطهير جهاز الحماية)
- مسافة العمل (نموذجية: 18" للجهد المنخفض، 24" للمتوسط)
- جهد النظام
- نوع المعدة (لوحة، switchgear، هواء مفتوح)
- تكوين القطب (VCB، VCBB، HCB، إلخ)

**معلمات IEEE 1584-2018:**
- \`electrode_gap\` — فجوات نموذجية حسب فئة الجهد
- \`arc_current_variation_factor\` — 1.0 افتراضي، 0.85 للتيار المخفض
- \`enclosure_size\` — لمعدات الجهد المتوسط

**النتائج:**
- طاقة الحادث (cal/cm²) عند مسافة العمل
- حدود شرارة القوس (بوصة)
- فئة PPE (0، 1، 2، 3، 4، أو "خطير")
- طاقة الحادث المخفضة عند تيار أقل (إن وجدت)

**ملاحظات السلامة:**
- دائماً قرّب للأعلى فئة PPE
- استخدم الأعلى من: (أ) تيار العطل الملحوم، (ب) حساب التيار المخفض
- وثّق جميع الافتراضات للامتثال للتدقيق`},tags:[`arc`,`flash`,`ieee`,`1584`,`incident`,`energy`,`قوس`,`شرارة`,`حادث`],navigateTo:`/studies/arc_flash`,relatedTopics:[`studies.short-circuit`,`studies.protection`,`studies.overview`]},{id:`studies.protection`,category:`engineering`,title:{en:`Protection Coordination`,ar:`تنسيق الحماية`},description:{en:`IEC 60255 relay curve coordination`,ar:`تنسيق منحنيات المُرحّل IEC 60255`},content:{en:`**What it does:**
Analyzes time-current curves of protective relays (overcurrent, earth fault) to ensure proper coordination — upstream devices should clear faults slower than downstream devices.

**Required Inputs:**
- Relay types (IEC 60255 standard curves: Standard Inverse, Very Inverse, Extremely Inverse)
- Pick-up current (Ip) for each relay
- Time Multiplier Setting (TMS)
- Fault currents at each relay location (from Short Circuit study)

**IEC 60255 Curve Equations:**
- Standard Inverse: t = TMS × (0.14 / ((I/Ip)^0.02 - 1))
- Very Inverse: t = TMS × (13.5 / ((I/Ip) - 1))
- Extremely Inverse: t = TMS × (80 / ((I/Ip)^2 - 1))

**Results:**
- Operating time for each relay at each fault current
- Coordination intervals (CTI — should be ≥ 0.3 seconds)
- Curve plot showing all relays on a log-log graph
- Miscoordination warnings

**Tips:**
- Standard CTI (Coordination Time Interval) is 0.3-0.4 seconds
- Check fuse-relay coordination as well as relay-relay
- Consider cold-load pickup when setting pick-up current`,ar:`**ما يفعله:**
يحلل منحنيات الوقت-التيار للمُرحّلات الحماية (زيادة التيار، عطل الأرض) لضمان التنسيق الصحيح — يجب أن تطهّر الأجهزة المنبع الأعطال أبطأ من الأجهزة المصب.

**المدخلات المطلوبة:**
- أنواع المُرحّلات (منحنيات IEC 60255 القياسية: عكسية قياسية، عكسية جداً، عكسية للغاية)
- تيار الالتقاط (Ip) لكل مُرحّل
- إعداد مضاعف الوقت (TMS)
- تيارات العطل عند كل موقع مُرحّل (من دراسة الدائرة القصيرة)

**معادلات منحنيات IEC 60255:**
- عكسية قياسية: t = TMS × (0.14 / ((I/Ip)^0.02 - 1))
- عكسية جداً: t = TMS × (13.5 / ((I/Ip) - 1))
- عكسية للغاية: t = TMS × (80 / ((I/Ip)^2 - 1))

**النتائج:**
- وقت التشغيل لكل مُرحّل عند كل تيار عطل
- فواصل التنسيق (CTI — يجب أن يكون ≥ 0.3 ثانية)
- رسم بياني للمنحنيات يُظهر جميع المُرحّلات على رسم log-log
- تحذيرات عدم التنسيق

**نصائح:**
- CTI القياسي (فاصل وقت التنسيق) هو 0.3-0.4 ثانية
- تحقق من تنسيق الفيوز-المُرحّل وكذلك المُرحّل-المُرحّل
- اعتبر التقاط الحمل البارد عند ضبط تيار الالتقاط`},tags:[`protection`,`relay`,`coordination`,`iec`,`60255`,`حماية`,`مُرحّل`,`تنسيق`],navigateTo:`/studies/protection_coordination`,relatedTopics:[`studies.short-circuit`,`studies.overview`]},{id:`studies.harmonic`,category:`engineering`,title:{en:`Harmonic Analysis`,ar:`تحليل التوافقيات`},description:{en:`IEEE 519-2022 distortion study`,ar:`دراسة التشوه IEEE 519-2022`},content:{en:`**What it does:**
Calculates harmonic voltage and current distortion at each bus, with frequency sweep and resonance detection.

**Required Inputs:**
- Harmonic current spectrum of nonlinear loads (VFDs, rectifiers, etc.)
- System impedance at fundamental frequency
- Capacitor bank locations and sizes (for resonance check)

**IEEE 519-2022 Limits:**
- Voltage THD: ≤ 5% for general systems (≤ 8% for dedicated)
- Current TDD at PCC: depends on Isc/IL ratio (5% to 20%)

**Results:**
- Voltage THD at each bus
- Current TDD at each branch
- Frequency scan plot showing parallel/series resonances
- Recommended mitigation (filters, reactor sizing)`,ar:`**ما يفعله:**
يحسب تشوه الجهد والتيار التوافقي في كل باص، مع مسح التردد وكشف الرنين.

**المدخلات المطلوبة:**
- طيف التيار التوافقي للأحمال غير الخطية (VFDs، المقومات، إلخ)
- مقاومة النظام عند التردد الأساسي
- مواقع وأحجام مكثفات البنك (للتحقق من الرنين)

**حدود IEEE 519-2022:**
- THD الجهد: ≤ 5% للأنظمة العامة (≤ 8% للمخصصة)
- TDD التيار عند PCC: يعتمد على نسبة Isc/IL (5% إلى 20%)

**النتائج:**
- THD الجهد في كل باص
- TDD التيار في كل فرع
- رسم المسح الترددي يُظهر الرنين المتوازي/المتسلسل
- التخفيف الموصى به (فلاتر، تحديد مقاومة المفاعل)`},tags:[`harmonic`,`thd`,`ieee`,`519`,`distortion`,`توافقيات`,`تشوه`],navigateTo:`/studies/harmonic`,relatedTopics:[`studies.overview`]},{id:`studies.motor-starting`,category:`engineering`,title:{en:`Motor Starting Study`,ar:`دراسة بدء المحرك`},description:{en:`IEEE 399 transient analysis`,ar:`تحليل عابر IEEE 399`},content:{en:`**What it does:**
Simulates the voltage dip and recovery during motor starting, ensuring the dip stays within acceptable limits (typically ≤ 15% at the motor terminals).

**Required Inputs:**
- Motor parameters (rated kW, voltage, LRT, LRM, inertia)
- Motor starting method (DOL, star-delta, soft starter, VFD)
- Source impedance (transformer + grid)
- Other running loads

**Results:**
- Voltage dip at motor terminals and at all buses
- Motor acceleration time
- Effect on other running motors
- Recommendation for starting method if dip is excessive`,ar:`**ما يفعله:**
يحاكي انخفاض الجهد واستعادته أثناء بدء المحرك، مع التأكد من بقاء الانخفاض ضمن الحدود المقبولة (عادة ≤ 15% عند أطراف المحرك).

**المدخلات المطلوبة:**
- معلمات المحرك (kW المقدّر، الجهد، LRT، LRM، القصور الذاتي)
- طريقة بدء المحرك (مباشرة DOL، نجمة-دلتا، مشغل ناعم، VFD)
- مقاومة المصدر (محول + شبكة)
- الأحمال الأخرى المشغّلة

**النتائج:**
- انخفاض الجهد عند أطراف المحرك وفي جميع الباصات
- وقت تسارع المحرك
- التأثير على المحركات الأخرى المشغّلة
- التوصية لطريقة البدء إذا كان الانخفاض مفرطاً`},tags:[`motor`,`starting`,`ieee`,`399`,`voltage`,`dip`,`محرك`,`بدء`],navigateTo:`/studies/motor_starting`,relatedTopics:[`studies.overview`,`studies.load-flow`]},{id:`studies.cable-sizing`,category:`engineering`,title:{en:`Cable Sizing`,ar:`تحديد مقاس الكابلات`},description:{en:`IEC 60364 current-carrying capacity`,ar:`القدرة على حمل التيار IEC 60364`},content:{en:`**What it does:**
Determines the minimum cable cross-section based on load current, installation method, ambient temperature, and voltage drop constraints.

**Required Inputs:**
- Load current (A)
- Cable length (m)
- Installation method (in air, in conduit, direct buried, on tray)
- Ambient temperature (°C)
- Number of loaded conductors
- Insulation type (PVC, XLPE)
- Voltage drop limit (%)

**IEC 60364 Tables:**
- Table B.52.4 — PVC insulation, single-core
- Table B.52.5 — PVC insulation, multi-core
- Table B.52.8 — XLPE insulation, single-core
- Table B.52.9 — XLPE insulation, multi-core

**Results:**
- Minimum cable cross-section (mm²)
- Actual current-carrying capacity (after derating)
- Voltage drop (% and V)
- Recommended cable size (next standard size up)`,ar:`**ما يفعله:**
يحدد الحد الأدنى لمقطع الكابل بناءً على تيار الحمل وطريقة التركيب ودرجة حرارة المحيط وقيود انخفاض الجهد.

**المدخلات المطلوبة:**
- تيار الحمل (A)
- طول الكابل (m)
- طريقة التركيب (في الهواء، في الأنبوب، مدفون مباشرة، على صينية)
- درجة حرارة المحيط (°C)
- عدد الموصلات المحمّلة
- نوع العزل (PVC، XLPE)
- حد انخفاض الجهد (%)

**جداول IEC 60364:**
- الجدول B.52.4 — عزل PVC، أحادي القلب
- الجدول B.52.5 — عزل PVC، متعدد القلوب
- الجدول B.52.8 — عزل XLPE، أحادي القلب
- الجدول B.52.9 — عزل XLPE، متعدد القلوب

**النتائج:**
- الحد الأدنى لمقطع الكابل (mm²)
- القدرة الفعلية على حمل التيار (بعد التخفيض)
- انخفاض الجهد (% و V)
- مقاس الكابل الموصى به (المقاس القياسي الأعلى التالي)`},tags:[`cable`,`sizing`,`iec`,`60364`,`كابل`,`مقاس`],navigateTo:`/studies/cable_sizing`,relatedTopics:[`studies.overview`]},{id:`studies.earth-grid`,category:`engineering`,title:{en:`Earth Grid Design`,ar:`تصميم شبكة التأريض`},description:{en:`IEEE 80 ground grid design`,ar:`تصميم شبكة التأريض IEEE 80`},content:{en:`**What it does:**
Designs a substation grounding grid that limits touch and step voltages to safe levels during ground faults.

**Required Inputs:**
- Fault current (A) — from Short Circuit study
- Fault duration (s) — typically 1 second
- Soil resistivity (Ω·m) — measured via Wenner 4-pin method
- Grid area (m²)
- Grid depth (m) — typically 0.5m
- Conductor spacing (m)

**IEEE 80-2013 Calculations:**
- Touch voltage limit: E_t = (116 + 0.7ρ) / √t
- Step voltage limit: E_s = (116 + 0.7ρ) / √t (different coefficient)
- Ground Potential Rise (GPR): I × Rg

**Results:**
- Grid resistance (Ω)
- Touch and step voltages (actual vs limits)
- GPR (Ground Potential Rise)
- Recommended conductor size (per IEEE 80 thermal capacity)`,ar:`**ما يفعله:**
يصمم شبكة تأريض محطة فرعية تحدّ من جهود اللمس والخطوة لمستويات آمنة أثناء أعطال الأرض.

**المدخلات المطلوبة:**
- تيار العطل (A) — من دراسة الدائرة القصيرة
- مدة العطل (s) — عادة 1 ثانية
- مقاومة التربة (Ω·m) — تُقاس بطريقة Wenner 4-pin
- مساحة الشبكة (m²)
- عمق الشبكة (m) — عادة 0.5m
- تباعد الموصل (m)

**حسابات IEEE 80-2013:**
- حد جهد اللمس: E_t = (116 + 0.7ρ) / √t
- حد جهد الخطوة: E_s = (116 + 0.7ρ) / √t (معامل مختلف)
- ارتفاع جهد التأريض (GPR): I × Rg

**النتائج:**
- مقاومة الشبكة (Ω)
- جهود اللمس والخطوة (الفعلية مقابل الحدود)
- ارتفاع جهد التأريض (GPR)
- مقاس الموصل الموصى به (حسب السعة الحرارية IEEE 80)`},tags:[`earth`,`grid`,`ground`,`ieee`,`80`,`تأريض`,`شبكة`],navigateTo:`/studies/earth_grid`,relatedTopics:[`studies.short-circuit`,`studies.overview`]},{id:`studies.opf`,category:`engineering`,title:{en:`Optimal Power Flow (OPF)`,ar:`تدفق القدرة الأمثل`},description:{en:`Cost-optimized generation dispatch`,ar:`إرسال توليد أمثل للتكلفة`},content:{en:`**What it does:**
Finds the optimal generation dispatch that minimizes total generation cost while satisfying all power flow constraints and limits.

**Required Inputs:**
- Same as Load Flow
- Generator cost curves (quadratic: aP² + bP + c)
- Generator limits (Pmin, Pmax)
- Line flow limits (MVA)
- Bus voltage limits

**Objective Functions:**
- \`min_cost\` — minimize total generation cost (default)
- \`min_losses\` — minimize transmission losses
- \`min_emissions\` — minimize CO2 emissions

**Results:**
- Optimal P for each generator
- Total generation cost ($/h)
- Marginal prices at each bus ($/MWh)
- Binding constraints (lines/generators at limits)
- Comparison with base case`,ar:`**ما يفعله:**
يجد الإرسال الأمثل للتوليد الذي يقلل من إجمالي تكلفة التوليد مع تلبية جميع قيود تدفق القدرة والحدود.

**المدخلات المطلوبة:**
- نفس تدفق الحمل
- منحنيات تكلفة المولد (تربيعية: aP² + bP + c)
- حدود المولد (Pmin، Pmax)
- حدود تدفق الخط (MVA)
- حدود جهد الباص

**دوال الهدف:**
- \`min_cost\` — تقليل إجمالي تكلفة التوليد (افتراضي)
- \`min_losses\` — تقليل خسائر النقل
- \`min_emissions\` — تقليل انبعاثات CO2

**النتائج:**
- P المثلى لكل مولد
- إجمالي تكلفة التوليد ($/h)
- الأسعار الحدية في كل باص ($/MWh)
- القيود المُلزِمة (خطوط/مولدات عند الحدود)
- المقارنة مع الحالة الأساسية`},tags:[`opf`,`optimal`,`power`,`flow`,`cost`,`أمثل`,`تكلفة`],navigateTo:`/studies/opf`,relatedTopics:[`studies.overview`,`studies.load-flow`]},{id:`studies.stability`,category:`engineering`,title:{en:`Transient Stability`,ar:`الاستقرار العابر`},description:{en:`Power system transient stability analysis`,ar:`تحليل الاستقرار العابر لنظام القدرة`},content:{en:`**What it does:**
Simulates the dynamic response of generators and loads to large disturbances (3-phase faults, line trips, generator outages) to verify the system remains stable.

**Required Inputs:**
- Generator dynamic models (H constant, Xd, Xd', Td0', etc.)
- AVR and governor models
- Load model (constant power, constant current, constant impedance)
- Disturbance specification (fault location, duration, clearing)

**Results:**
- Rotor angle vs time plot
- Frequency vs time plot
- Critical Clearing Time (CCT)
- Stability margin
- Recommendation for corrective actions if unstable`,ar:`**ما يفعله:**
يحاكي الاستجابة الديناميكية للمولدات والأحمال للاضطرابات الكبيرة (أعطال ثلاثية الطور، قطع الخطوط، خروج المولدات) للتحقق من بقاء النظام مستقراً.

**المدخلات المطلوبة:**
- نماذج ديناميكية للمولدات (ثابت H، Xd، Xd'، Td0'، إلخ)
- نماذج AVR والحاكم
- نموذج الحمل (قدرة ثابتة، تيار ثابت، مقاومة ثابتة)
- مواصفات الاضطراب (موقع العطل، المدة، التطهير)

**النتائج:**
- رسم زاوية الدوار مقابل الزمن
- رسم التردد مقابل الزمن
- وقت التطهير الحرج (CCT)
- هامش الاستقرار
- التوصية للإجراءات التصحيحية إذا كان غير مستقر`},tags:[`stability`,`transient`,`rotor`,`angle`,`استقرار`,`عابر`],navigateTo:`/studies/stability`,relatedTopics:[`studies.overview`,`studies.load-flow`]},{id:`ai-assistant.overview`,category:`getting-started`,title:{en:`AI Assistant`,ar:`المساعد الذكي`},description:{en:`Chat with the ETAP Expert AI agent for engineering guidance`,ar:`تحدث مع وكيل ETAP Expert الذكي للحصول على إرشادات هندسية`},content:{en:`**What it does:**
The AI Assistant page lets you chat with specialized AI agents (ETAP Expert, ETAP GUI, Load Flow Agent, etc.) to get engineering guidance, code suggestions, and step-by-step instructions.

**How to Use:**
1. Navigate to **AI Assistant** from the sidebar
2. Select an agent from the dropdown at the top (default: ETAP Expert)
3. Type your question in the textarea at the bottom
4. Press Enter (or click Send) to submit
5. The agent's response appears in the chat history

**Available Agents:**
- **ETAP Expert** — General ETAP knowledge and best practices
- **ETAP GUI** — ETAP user interface guidance
- **Load Flow Agent** — Specialized in load flow analysis
- **Short Circuit Agent** — IEC 60909 fault calculations
- **Arc Flash Agent** — IEEE 1584 incident energy
- **Protection Agent** — Relay coordination
- **Code Guard** — Code review for engineering calculations

**Tips:**
- Be specific in your questions (include bus count, voltage, standard)
- Reference standards explicitly (IEEE 1584-2018, not just "arc flash")
- The agent has access to a knowledge base of ETAP manuals and IEEE/IEC standards
- For complex problems, break them into multiple smaller questions`,ar:`**ما يفعله:**
تتيح لك صفحة المساعد الذكي الدردشة مع وكلاء ذكاء اصطناعي متخصصين (ETAP Expert، ETAP GUI، وكيل تدفق الحمل، إلخ) للحصول على إرشادات هندسية واقتراحات أكواد وتعليمات خطوة بخطوة.

**كيفية الاستخدام:**
1. انتقل إلى **المساعد الذكي** من الشريط الجانبي
2. اختر وكيلاً من القائمة المنسدلة في الأعلى (افتراضي: ETAP Expert)
3. اكتب سؤالك في منطقة النص السفلية
4. اضغط Enter (أو انقر إرسال) للتقديم
5. تظهر استجابة الوكيل في سجل الدردشة

**الوكلاء المتاحون:**
- **ETAP Expert** — معرفة ETAP العامة وأفضل الممارسات
- **ETAP GUI** — إرشادات واجهة مستخدم ETAP
- **وكيل تدفق الحمل** — متخصص في تحليل تدفق الحمل
- **وكيل الدائرة القصيرة** — حسابات عطل IEC 60909
- **وكيل شرارة القوس** — طاقة الحادث IEEE 1584
- **وكيل الحماية** — تنسيق المُرحّل
- **حارس الكود** — مراجعة الكود للحسابات الهندسية

**نصائح:**
- كن محدداً في أسئلتك (اذكر عدد الباصات، الجهد، المعيار)
- اذكر المعايير صراحةً (IEEE 1584-2018، ليس فقط "شرارة القوس")
- للوكيل وصول إلى قاعدة معرفية لأدلة ETAP ومعايير IEEE/IEC
- للمشاكل المعقدة، قسّمها لأسئلة أصغر متعددة`},tags:[`ai`,`assistant`,`chat`,`agent`,`ذكاء`,`اصطناعي`,`مساعد`],navigateTo:`/assistant`,relatedTopics:[`dashboard.overview`,`code-guard.overview`]},{id:`asset-management.overview`,category:`engineering`,title:{en:`Asset Management`,ar:`إدارة الأصول`},description:{en:`Track physical equipment across your power system`,ar:`تتبع المعدات الفيزيائية في نظام القدرة`},content:{en:`**What it does:**
The Asset Management page tracks physical equipment (transformers, breakers, cables, generators) across your power system. Each asset has metadata (manufacturer, model, install date), maintenance history, and links to the engineering model.

**Key Features:**
- Asset list with filter by type, location, status
- Asset detail view with maintenance history
- Add/edit/delete assets
- Import assets from CSV
- Export asset register to Excel/PDF

**Asset Types:**
- Transformers (with test results)
- Circuit breakers (with timing tests)
- Cables (with insulation tests)
- Generators (with capability curves)
- Motors (with starting characteristics)
- Protective relays (with settings)`,ar:`**ما يفعله:**
تتبع صفحة إدارة الأصول المعدات الفيزيائية (محولات، قواطع، كابلات، مولدات) في نظام القدرة. لكل أصل بيانات وصفية (الشركة المصنعة، الموديل، تاريخ التركيب)، سجل الصيانة، وروابط للنموذج الهندسي.

**الميزات الرئيسية:**
- قائمة الأصول مع الفلترة حسب النوع، الموقع، الحالة
- عرض تفاصيل الأصل مع سجل الصيانة
- إضافة/تعديل/حذف الأصول
- استيراد الأصول من CSV
- تصدير سجل الأصول إلى Excel/PDF

**أنواع الأصول:**
- المحولات (مع نتائج الاختبار)
- القواطع الكهربية (مع اختبارات التوقيت)
- الكابلات (مع اختبارات العزل)
- المولدات (مع منحنيات القدرة)
- المحركات (مع خصائص البدء)
- المُرحّلات الحماية (مع الإعدادات)`},tags:[`asset`,`management`,`equipment`,`أصول`,`معدات`],navigateTo:`/asset-management`,relatedTopics:[`dashboard.overview`]},{id:`etap-integration.overview`,category:`engineering`,title:{en:`ETAP Integration`,ar:`تكامل ETAP`},description:{en:`Connect to ETAP desktop software for native study execution`,ar:`اتصل ببرنامج ETAP المكتبي لتنفيذ الدراسات الأصلية`},content:{en:`**What it does:**
The ETAP Integration page configures the connection between AhmedETAP and the ETAP desktop software running on Windows. This allows running studies using the real ETAP engine instead of the native Python engine.

**Prerequisites:**
- ETAP licensed and installed on a Windows machine
- ETAP Worker Service running on the Windows machine (port 8080 by default)
- Network connectivity between AhmedETAP server and the Windows worker

**Configuration:**
1. **ETAP Worker URL** — IP:port of the Windows worker (e.g. http://192.168.1.100:8080)
2. **ETAP License Path** — path to the ETAP license file on the Windows machine
3. **Use ETAP** — toggle to enable ETAP execution (vs native Python)

**Worker Status:**
- 🟢 Online — worker is registered and responding
- 🟡 Degraded — worker responding but slow
- 🔴 Offline — worker not registered or unreachable

**Tips:**
- Use ETAP for studies that require ETAP-specific features (e.g., IEEE 1584 with specific equipment)
- Use native Python for faster iteration during development
- The worker can be load-balanced across multiple Windows machines`,ar:`**ما يفعله:**
تقوم صفحة تكامل ETAP بتكوين الاتصال بين AhmedETAP وبرنامج ETAP المكتبي الذي يعمل على Windows. هذا يسمح بتشغيل الدراسات باستخدام محرك ETAP الحقيقي بدلاً من محرك Python الأصلي.

**المتطلبات المسبقة:**
- ETAP مرخص ومثبت على جهاز Windows
- ETAP Worker Service يعمل على جهاز Windows (المنفذ 8080 افتراضياً)
- اتصال شبكة بين خادم AhmedETAP وعامل Windows

**التكوين:**
1. **رابط عامل ETAP** — IP:منفذ عامل Windows (مثل http://192.168.1.100:8080)
2. **مسار ترخيص ETAP** — المسار لملف ترخيص ETAP على جهاز Windows
3. **استخدام ETAP** — تبديل لتمكين تنفيذ ETAP (مقابل Python الأصلي)

**حالة العامل:**
- 🟢 متصل — العامل مسجل ويستجيب
- 🟡 متدهور — العامل يستجيب لكن ببطء
- 🔴 غير متصل — العامل غير مسجل أو لا يمكن الوصول إليه

**نصائح:**
- استخدم ETAP للدراسات التي تتطلب ميزات ETAP محددة (مثل IEEE 1584 مع معدات محددة)
- استخدم Python الأصلي للتكرار الأسرع أثناء التطوير
- يمكن موازنة حمل العامل عبر أجهزة Windows متعددة`},tags:[`etap`,`integration`,`worker`,`windows`,`تكامل`,`عامل`],navigateTo:`/etap`,relatedTopics:[`studies.overview`,`settings.backend`]},{id:`gis-integration.overview`,category:`engineering`,title:{en:`GIS Integration`,ar:`تكامل GIS`},description:{en:`Connect to ArcGIS / QGIS / PostGIS for geospatial power system data`,ar:`اتصل بـ ArcGIS / QGIS / PostGIS لبيانات نظام القدرة الجغرافية`},content:{en:`**What it does:**
The GIS Integration page connects AhmedETAP to Geographic Information Systems (ArcGIS, QGIS, PostGIS) to import geospatial data for power system assets (lines, substations, transformers with coordinates).

**Supported Providers:**
- **ArcGIS Pro** — ESRI's desktop GIS (via ArcPy)
- **QGIS** — open-source desktop GIS (via PyQGIS)
- **PostGIS** — PostgreSQL spatial database extension

**Configuration:**
1. Select the GIS provider from the dropdown
2. Provide connection parameters (file path, server URL, or DB connection string)
3. Click **Test Connection** to verify
4. Click **Import** to load GIS data into the engineering model

**What Gets Imported:**
- Substation locations (latitude, longitude)
- Line routes (polylines)
- Transformer positions
- Service area boundaries

**Validation:**
- CRS (Coordinate Reference System) check
- Topology validation (no dangling lines, no overlapping)
- Electrical connectivity validation

**Tips:**
- Use WGS84 (EPSG:4326) for cross-platform compatibility
- Run validation after every import to catch GIS-to-electrical mismatches`,ar:`**ما يفعله:**
تقوم صفحة تكامل GIS بربط AhmedETAP بأنظمة المعلومات الجغرافية (ArcGIS، QGIS، PostGIS) لاستيراد البيانات الجغرافية لأصول نظام القدرة (الخطوط، المحطات الفرعية، المحولات بالإحداثيات).

**المزودون المدعومون:**
- **ArcGIS Pro** — GIS المكتبي من ESRI (عبر ArcPy)
- **QGIS** — GIS المكتبي مفتوح المصدر (عبر PyQGIS)
- **PostGIS** — امتداد قاعدة بيانات PostgreSQL المكاني

**التكوين:**
1. اختر مزود GIS من القائمة المنسدلة
2. قدّم معلمات الاتصال (مسار الملف، رابط الخادم، أو سلسلة اتصال DB)
3. انقر على **اختبار الاتصال** للتحقق
4. انقر على **استيراد** لتحميل بيانات GIS في النموذج الهندسي

**ما يتم استيراده:**
- مواقع المحطات الفرعية (خط العرض، خط الطول)
- مسارات الخطوط (خطوط متعددة)
- مواقع المحولات
- حدود منطقة الخدمة

**التحقق:**
- التحقق من CRS (نظام الإحداثيات المرجعي)
- التحقق من الطوبولوجيا (لا خطوط معلقة، لا تداخل)
- التحقق من الاتصال الكهربائي

**نصائح:**
- استخدم WGS84 (EPSG:4326) للتوافق عبر المنصات
- شغّل التحقق بعد كل استيراد لالتقاط عدم التطابق بين GIS والكهرباء`},tags:[`gis`,`arcgis`,`qgis`,`postgis`,`geo`,`جغرافي`],navigateTo:`/gis`,relatedTopics:[`asset-management.overview`,`digital-twin.overview`]},{id:`reports.generate`,category:`reports`,title:{en:`Generating Reports`,ar:`إنشاء التقارير`},description:{en:`How to generate and customize engineering reports`,ar:`كيفية إنشاء وتخصيص التقارير الهندسية`},content:{en:`**Report Types:**
- **Compliance Report** — Standards verification (IEEE 1584, IEC 60909, etc.)
- **Calculation Report** — Detailed analysis results with formulas
- **Summary Report** — Executive overview (1-2 pages)
- **Audit Report** — System configuration audit trail

**Steps:**
1. Navigate to **Reports** from the sidebar
2. Click **New Report**
3. Select report type
4. Choose source project and study
5. Configure report options:
   - Format (PDF, DOCX, CSV, JSON)
   - Include sections (executive summary, methodology, results, recommendations)
   - Language (English or Arabic)
   - Logo and branding
6. Click **Generate Report**
7. Download the file when ready

**Export Formats:**
- PDF — primary, with formatted tables and figures
- DOCX — editable in Microsoft Word
- CSV — data only (for spreadsheet analysis)
- JSON — for API integration with other tools

**Tips:**
- Compliance reports include a cover page with standard references
- Use the audit report for ISO 9001 / IEC quality management
- Reports are generated server-side; allow 10-30 seconds for large reports`,ar:`**أنواع التقارير:**
- **تقرير الامتثال** — التحقق من المعايير (IEEE 1584، IEC 60909، إلخ)
- **تقرير الحسابات** — نتائج التحليل التفصيلية مع الصيغ
- **تقرير الملخص** — نظرة عامة تنفيذية (1-2 صفحة)
- **تقرير التدقيق** — سجل تدقيق تكوين النظام

**الخطوات:**
1. انتقل إلى **التقارير** من الشريط الجانبي
2. انقر على **تقرير جديد**
3. حدد نوع التقرير
4. اختر المشروع والدراسة المصدر
5. قوم خيارات التقرير:
   - التنسيق (PDF، DOCX، CSV، JSON)
   - الأقسام المضمنة (الملخص التنفيذي، المنهجية، النتائج، التوصيات)
   - اللغة (الإنجليزية أو العربية)
   - الشعار والعلامة التجارية
6. انقر على **إنشاء التقرير**
7. نزّل الملف عندما يكون جاهزاً

**تنسيقات التصدير:**
- PDF — أساسي، مع جداول وأشكال منسقة
- DOCX — قابل للتعديل في Microsoft Word
- CSV — بيانات فقط (لتحليل جداول البيانات)
- JSON — لتكامل API مع أدوات أخرى

**نصائح:**
- تقارير الامتثال تشمل صفحة غلاف مع مراجع المعايير
- استخدم تقرير التدقيق لإدارة الجودة ISO 9001 / IEC
- تُنشأ التقارير من جانب الخادم؛ اسمح بـ 10-30 ثانية للتقارير الكبيرة`},tags:[`report`,`generate`,`pdf`,`compliance`,`تقرير`,`إنشاء`,`امتثال`],navigateTo:`/reports`,relatedTopics:[`projects.manage`,`studies.overview`]},{id:`digital-twin.overview`,category:`digital-twin`,title:{en:`Digital Twin Overview`,ar:`نظرة عامة على التوأم الرقمي`},description:{en:`Real-time virtual replica of your physical power system`,ar:`نسخة افتراضية في الوقت الفعلي من نظام القدرة الفيزيائي`},content:{en:`**What is a Digital Twin?**
A digital twin is a real-time virtual replica of your physical power system. It syncs with SCADA, BMS, and IoT sensors to provide a live view of system state.

**Features:**
- Real-time state synchronization (every 1-10 seconds)
- Predictive maintenance alerts
- What-if scenario simulation
- Historical data comparison
- Automated compliance monitoring

**Getting Started:**
1. Connect to your SCADA system (Copa-Data zenon, others via OPC UA)
2. Map SCADA tags to ETAP entities (buses, breakers, generators)
3. Enable real-time sync
4. Monitor the dashboard for anomalies
5. Set up alerts for threshold violations

**Supported Sync Protocols:**
- IEC 61850 (via zenon)
- IEC 60870-5-104
- Modbus TCP
- OPC UA
- DNP3 (future)

**Tips:**
- Start with a small subset of tags and expand gradually
- Use the validation gateway to verify commands before sending to SCADA
- Historical comparison lets you detect performance drift over time`,ar:`**ما هو التوأم الرقمي؟**
التوأم الرقمي هو نسخة افتراضية في الوقت الفعلي من نظام القدرة الفيزيائي. يتزامن مع SCADA و BMS و IoT sensors لتوفير عرض مباشر لحالة النظام.

**الميزات:**
- مزامنة الحالة في الوقت الفعلي (كل 1-10 ثوانٍ)
- تنبيهات الصيانة التنبؤية
- محاكاة سيناريو ماذا لو
- مقارنة البيانات التاريخية
- مراقبة الامتثال التلقائية

**البدء:**
1. اتصل بنظام SCADA (Copa-Data zenon، أخرى عبر OPC UA)
2. عيّن وسوم SCADA لكيانات ETAP (باصات، قواطع، مولدات)
3. فعّل المزامنة المباشرة
4. راقب لوحة التحكم للشذوذ
5. اعداد تنبيهات لانتهاكات العتبة

**بروتوكولات المزامنة المدعومة:**
- IEC 61850 (عبر zenon)
- IEC 60870-5-104
- Modbus TCP
- OPC UA
- DNP3 (مستقبلاً)

**نصائح:**
- ابدأ بمجموعة صغيرة من الوسوم ووسّع تدريجياً
- استخدم بوابة التحقق للتحقق من الأوامر قبل الإرسال إلى SCADA
- تتيح المقارنة التاريخية كشف انحراف الأداء بمرور الوقت`},tags:[`digital`,`twin`,`sync`,`real-time`,`توأم`,`رقمي`,`مزامنة`],navigateTo:`/digital-twin`,relatedTopics:[`dashboard.overview`,`integration.scada`]},{id:`settings.backend`,category:`settings`,title:{en:`Backend Configuration`,ar:`تكوين الخادم`},description:{en:`Configure the engineering service backend connection`,ar:`تكوين اتصال خادم الخدمة الهندسية`},content:{en:`**Backend Settings (Engineering Service tab):**
- **Service URL** — URL of the FastAPI engineering service (default: http://localhost:8000)
- **API Key** — Authentication key sent in the X-API-Key header
- **Timeout** — Request timeout in milliseconds (default: 30000)

**Connection Status:**
- 🟢 Connected — Backend is healthy
- 🟡 Degraded — Backend responding slowly (>2s)
- 🔴 Disconnected — Backend unavailable

**How to Test:**
1. Save the URL and API key
2. The status indicator updates automatically
3. If red, check:
   - Is the backend running? (\`curl http://localhost:8000/healthz\`)
   - Is the URL correct?
   - Is the API key correct?
   - Is there a firewall blocking the port?

**Tips:**
- For local development: http://localhost:8000
- For HF Space deployment: use the full hf.space URL
- The API key is stored in localStorage (obfuscated, NOT encrypted)`,ar:`**إعدادات الخادم (تبويب الخدمة الهندسية):**
- **رابط الخدمة** — رابط خدمة FastAPI الهندسية (افتراضي: http://localhost:8000)
- **مفتاح API** — مفتاح المصادقة المُرسل في ترويسة X-API-Key
- **المهلة** — مهلة الطلب بالمللي ثانية (افتراضي: 30000)

**حالة الاتصال:**
- 🟢 متصل — الخادم يعمل بشكل صحيح
- 🟡 متدهور — الخادم يستجيب ببطء (>2s)
- 🔴 غير متصل — الخادم غير متاح

**كيفية الاختبار:**
1. احفظ الرابط ومفتاح API
2. يتم تحديث مؤشر الحالة تلقائياً
3. إذا كان أحمر، تحقق من:
   - هل الخادم يعمل؟ (\`curl http://localhost:8000/healthz\`)
   - هل الرابط صحيح؟
   - هل مفتاح API صحيح؟
   - هل يوجد جدار حماية يحظر المنفذ؟

**نصائح:**
- للتطوير المحلي: http://localhost:8000
- لنشر HF Space: استخدم رابط hf.space الكامل
- مفتاح API محفوظ في localStorage (مشوّه، وليس مشفّراً)`},tags:[`settings`,`backend`,`config`,`api`,`إعدادات`,`خادم`,`تكوين`],navigateTo:`/settings`,relatedTopics:[`troubleshooting.backend`,`settings.external-services`]},{id:`settings.external-services`,category:`settings`,title:{en:`External Services (LangWatch, Smithery, HF, GitHub, Vercel)`,ar:`الخدمات الخارجية (LangWatch, Smithery, HF, GitHub, Vercel)`},description:{en:`Configure and test third-party integrations`,ar:`تكوين واختبار التكاملات الخارجية`},content:{en:`**The External Services tab lets you configure 5 third-party integrations:**

**1. LangWatch** — LLM observability dashboard
- API Key, Project Name, Endpoint URL
- Test button calls /api/v1/projects (with CORS fallback)
- Status: ✓ green = connected, ✗ red = invalid key or network error

**2. Smithery MCP** — Model Context Protocol server registry
- API Key, Base URL
- Test button calls /v1/servers (Bearer auth)

**3. Hugging Face** — Model hub & Spaces deployment
- Access Token, Space Name, Space URL
- Test button calls /api/whoami-v2 (returns your username)

**4. GitHub** — Repository access & CI/CD
- Personal Access Token, Repository (owner/repo)
- Test button calls /api/user (returns your login)

**5. Vercel** — Frontend deployment
- Project ID, Access Token
- Test button calls /v9/projects/{id} (returns project name)

**How to Use:**
1. Enter your credentials for each service
2. Click "Test Connection" — a real API call is made
3. The status badge updates: ✓/✗/spinner
4. The detail message tells you exactly what happened
5. Click the external-link icon to open the service's dashboard

**Privacy:**
- Tokens are stored in browser localStorage (obfuscated)
- They are NEVER sent to our backend
- For backend runtime use, copy them to your .env or HF Space secrets`,ar:`**تبويب الخدمات الخارجية يتيح لك تكوين 5 تكاملات خارجية:**

**1. LangWatch** — لوحة مراقبة LLM
- مفتاح API، اسم المشروع، رابط النقطة
- زر الاختبار يستدعي /api/v1/projects (مع بديل CORS)
- الحالة: ✓ أخضر = متصل، ✗ أحمر = مفتاح غير صحيح أو خطأ شبكة

**2. Smithery MCP** — سجل خوادم بروتوكول السياق النموذجي
- مفتاح API، الرابط الأساسي
- زر الاختبار يستدعي /v1/servers (مصادقة Bearer)

**3. Hugging Face** — مركز النماذج ونشر المساحات
- رمز الوصول، اسم المساحة، رابط المساحة
- زر الاختبار يستدعي /api/whoami-v2 (يُرجع اسم المستخدم)

**4. GitHub** — الوصول للمستودعات و CI/CD
- رمز الوصول الشخصي، المستودع (المالك/المستودع)
- زر الاختبار يستدعي /api/user (يُرجع تسجيل الدخول)

**5. Vercel** — نشر الواجهة
- معرف المشروع، رمز الوصول
- زر الاختبار يستدعي /v9/projects/{id} (يُرجع اسم المشروع)

**كيفية الاستخدام:**
1. أدخل بيانات الاعتماد لكل خدمة
2. انقر على "اختبار الاتصال" — يتم إجراء استدعاء API حقيقي
3. يتم تحديث شارة الحالة: ✓/✗/spinner
4. تخبرك الرسالة التفصيلية بما حدث بالضبط
5. انقر على أيقونة الرابط الخارجي لفتح لوحة الخدمة

**الخصوصية:**
- الرموز محفوظة في localStorage بالمتصفح (مشوّهة)
- لا يتم إرسالها أبداً إلى الخادم
- للاستخدام في الخادم، انسخها إلى .env أو أسرار HF Space`},tags:[`settings`,`external`,`services`,`langwatch`,`smithery`,`huggingface`,`github`,`vercel`,`إعدادات`,`خدمات`,`خارجية`],navigateTo:`/settings`,relatedTopics:[`settings.backend`,`integration.scada`]},{id:`settings.ai-providers`,category:`settings`,title:{en:`AI Providers Configuration`,ar:`تكوين مزودي الذكاء الاصطناعي`},description:{en:`Connect to OpenAI, Anthropic, Gemini, DeepSeek, Groq, Cohere, Hugging Face, OpenRouter, etc.`,ar:`اتصل بـ OpenAI و Anthropic و Gemini و DeepSeek و Groq و Cohere و Hugging Face و OpenRouter`},content:{en:`**The AI Providers tab lets you connect to 17+ popular LLM providers:**

**Built-in Providers (one-click):**
- **OpenAI** — GPT-4o, GPT-4o-mini, o1-mini, o1-preview
- **Anthropic** — Claude 3.5 Sonnet, Claude 3 Opus, Claude 3.5 Haiku
- **Google Gemini** — Gemini 1.5 Pro/Flash, Gemini 2.0 Flash
- **DeepSeek** — DeepSeek Chat, DeepSeek Coder, DeepSeek Reasoner
- **Groq** — Llama 3.3 70B, Mixtral 8x7B, Gemma 2 9B (free tier)
- **Cohere** — Command R+, Command R
- **Hugging Face** — Llama 3.3 70B, Mixtral 8x7B (free tier)
- **NVIDIA NIM** — Llama 3.1 8B/70B/405B (free tier)
- **OpenRouter** — 340+ models including GPT-OSS, Llama, Claude (26 free)
- **Fireworks AI** — Llama, Mixtral, Qwen Coder
- **Cloudflare Workers AI** — Llama, Mistral, Gemma (free tier)
- **Zhipu AI (GLM)** — GLM-4 Flash/Plus (free tier)
- **GitHub Models** — GPT-4o, Phi-3.5, Llama 3.1 (free tier)
- **OpenModel** — GPT-4o, GPT-5.4, Claude 3.5 Sonnet
- **Modal** — GLM-5.1, GLM-4.5 (free research)
- **Bynara Router** — Kimi K2.6, GPT-5.4, Claude Sonnet 5
- **KiloCode** — KiloCode Coder (free), Standard
- **OpenCode Zen** — DeepSeek V4 Flash (free), GPT-5.4, Claude Sonnet 5
- **OpenClaude** — Claude 3.5 Sonnet (free, proxy)
- **Claude Code** — Anthropic direct API

**How to Connect:**
1. Click the provider card you want to configure
2. Enter your API key in the field that appears
3. Select the model from the dropdown
4. Click "Connect"
5. A success toast confirms the connection

**Custom Provider (Advanced):**
- Use the "Custom Provider" section to connect to any OpenAI-compatible API
- Paste a curl command and click "Parse" to auto-fill fields
- Examples: Ollama (http://localhost:11434/v1), LM Studio (http://localhost:1234/v1)

**Tips:**
- API keys are stored in localStorage (obfuscated with XOR + base64)
- You can configure multiple providers simultaneously
- The AI Assistant page lets you select which provider to use per chat
- Free tier providers are marked with "(free)" in the model list`,ar:`**تبويب مزودي الذكاء الاصطناعي يتيح لك الاتصال بـ 17+ مزودين LLM شائعين:**

**المزودون المدمجون (بنقرة واحدة):**
- **OpenAI** — GPT-4o، GPT-4o-mini، o1-mini، o1-preview
- **Anthropic** — Claude 3.5 Sonnet، Claude 3 Opus، Claude 3.5 Haiku
- **Google Gemini** — Gemini 1.5 Pro/Flash، Gemini 2.0 Flash
- **DeepSeek** — DeepSeek Chat، DeepSeek Coder، DeepSeek Reasoner
- **Groq** — Llama 3.3 70B، Mixtral 8x7B، Gemma 2 9B (مجاني)
- **Cohere** — Command R+، Command R
- **Hugging Face** — Llama 3.3 70B، Mixtral 8x7B (مجاني)
- **NVIDIA NIM** — Llama 3.1 8B/70B/405B (مجاني)
- **OpenRouter** — 340+ نموذج包括 GPT-OSS و Llama و Claude (26 مجاني)
- **Fireworks AI** — Llama، Mixtral، Qwen Coder
- **Cloudflare Workers AI** — Llama، Mistral، Gemma (مجاني)
- **Zhipu AI (GLM)** — GLM-4 Flash/Plus (مجاني)
- **GitHub Models** — GPT-4o، Phi-3.5، Llama 3.1 (مجاني)
- **OpenModel** — GPT-4o، GPT-5.4، Claude 3.5 Sonnet
- **Modal** — GLM-5.1، GLM-4.5 (بحث مجاني)
- **Bynara Router** — Kimi K2.6، GPT-5.4، Claude Sonnet 5
- **KiloCode** — KiloCode Coder (مجاني)، Standard
- **OpenCode Zen** — DeepSeek V4 Flash (مجاني)، GPT-5.4، Claude Sonnet 5
- **OpenClaude** — Claude 3.5 Sonnet (مجاني، بروكسي)
- **Claude Code** — Anthropic API مباشر

**كيفية الاتصال:**
1. انقر على بطاقة المزود الذي تريد تكوينه
2. أدخل مفتاح API في الحقل الذي يظهر
3. اختر النموذج من القائمة المنسدلة
4. انقر على "اتصال"
5. تؤكد رسالة نجاح الاتصال

**المزود المخصص (متقدم):**
- استخدم قسم "المزود المخصص" للاتصال بأي API متوافق مع OpenAI
- الصق أمر curl وانقر على "تحليل" لتعبئة الحقول تلقائياً
- أمثلة: Ollama (http://localhost:11434/v1)، LM Studio (http://localhost:1234/v1)

**نصائح:**
- مفاتيح API محفوظة في localStorage (مشوّهة بـ XOR + base64)
- يمكنك تكوين مزودين متعددين في نفس الوقت
- تتيح لك صفحة المساعد الذكي اختيار المزود المستخدم لكل دردشة
- المزودون المجانين مميزون بـ "(مجاني)" في قائمة النماذج`},tags:[`ai`,`provider`,`openai`,`anthropic`,`gemini`,`deepseek`,`groq`,`cohere`,`huggingface`,`openrouter`,`مزود`,`ذكاء`],navigateTo:`/settings`,relatedTopics:[`ai-assistant.overview`,`settings.backend`]},{id:`settings.mcp`,category:`settings`,title:{en:`MCP Servers`,ar:`خوادم MCP`},description:{en:`Model Context Protocol server configuration and exposed tools`,ar:`تكوين خوادم بروتوكول السياق النموذجي والأدوات المعروضة`},content:{en:`**What it does:**
The MCP Servers tab shows which Model Context Protocol (MCP) servers are running and what tools they expose to AI agents.

**Built-in MCP Servers:**
1. **Weather MCP Server** — Real-time weather and temperature for renewable energy planning
   - Tool: \`weatherTool\`
   - Status: Active

2. **QGIS Map Service MCP Server** — Bridges GIS data (coordinates, lines, substations)
   - Tools: \`load_gis_features\`, \`sync_gis_telemetry\`
   - Status: Active

3. **SCADA zenon Telemetry MCP Server** — Subscribes to SCADA alerts and live telemetry (I, V, P, Q)
   - Tools: \`fetch_live_telemetry\`, \`trigger_zenon_alarm\`
   - Status: Active

4. **ETAP COM Automation MCP Server** — Executes COM automation scripts for Newton-Raphson studies
   - Tools: \`run_etap_study\`, \`export_etap_one_line\`
   - Status: Standby (requires Windows + ETAP installed)

5. **AI Code Guard MCP Server** — Validates generated code for safety and compliance
   - Tool: \`validate_code\`
   - Status: Active

**How It Works:**
- MCP servers expose local files, databases, and APIs as secure tools
- AI agents (in AI Assistant) can call these tools with user consent
- Each server has a status: Active, Standby, or Offline

**Tips:**
- MCP is automatically configured — no user action needed
- To add a custom MCP server, restart the backend with the server config in .env
- Tool calls are logged for audit purposes`,ar:`**ما يفعله:**
تبويب خوادم MCP يُظهر خوادم بروتوكول السياق النموذجي (MCP) النشطة والأدوات التي تعرضها لوكلاء الذكاء الاصطناعي.

**خوادم MCP المدمجة:**
1. **خادم MCP للطقس** — طقس ودرجة حرارة في الوقت الفعلي لتخطيط الطاقة المتجددة
   - الأداة: \`weatherTool\`
   - الحالة: نشط

2. **خادم MCP لخدمة الخرائط QGIS** — يربط بيانات GIS (إحداثيات، خطوط، محطات)
   - الأدوات: \`load_gis_features\`، \`sync_gis_telemetry\`
   - الحالة: نشط

3. **خادم MCP لبث الإسكادا زينون** — يشترك في إنذارات الإسكادا والبيانات القياسية الحية (I, V, P, Q)
   - الأدوات: \`fetch_live_telemetry\`، \`trigger_zenon_alarm\`
   - الحالة: نشط

4. **خادم MCP لأتمتة ETAP COM** — ينفذ سكريبتات أتمتة COM لدراسات نيوتن-رافسون
   - الأدوات: \`run_etap_study\`، \`export_etap_one_line\`
   - الحالة: standby (يتطلب Windows + ETAP مثبت)

5. **خادم MCP لحارس الكود AI** — يتحقق من الكود المولد للسلامة والامتثال
   - الأداة: \`validate_code\`
   - الحالة: نشط

**كيف يعمل:**
- خوادم MCP تعرض الملفات المحلية وقواعد البيانات وAPIs كأدوات آمنة
- وكلاء الذكاء الاصطناعي (في المساعد الذكي) يمكنهم استدعاء هذه الأدوات بموافقة المستخدم
- كل خادم له حالة: نشط، standby، أو غير متصل

**نصائح:**
- MCP مُكوّن تلقائياً — لا يحتاج إجراء من المستخدم
- لإضافة خادم MCP مخصص، أعد تشغيل الخادم مع تكوين الخادم في .env
- استدعاءات الأدوات مسجلة لأغراض التدقيق`},tags:[`mcp`,`server`,`protocol`,`context`,`tool`,`خادم`,`بروتوكول`],navigateTo:`/settings`,relatedTopics:[`settings.ai-providers`,`ai-assistant.overview`]},{id:`settings.coding-agents`,category:`settings`,title:{en:`Coding Agents (OpenHands, OpenCode, KiloCode)`,ar:`وكلاء البرمجة (OpenHands, OpenCode, KiloCode)`},description:{en:`Configure autonomous coding agent integrations`,ar:`تكوين تكاملات وكلاء البرمجة المستقلين`},content:{en:`**What it does:**
The Coding Agents tab configures integrations with autonomous coding agents that can write, review, and execute engineering code.

**Supported Agents:**
1. **OpenHands** (formerly OpenDevin) — Full autonomous software engineering agent
   - URL: http://localhost:3000 (default)
   - Enable: Set \`OPENHANDS_ENABLED=true\`
   - Workspace: Directory for agent files

2. **OpenCode** — CLI coding agent with zen-powered models
   - URL: http://localhost:8080 (default)
   - Enable: Set \`OPENCODE_ENABLED=true\`
   - Supports DeepSeek V4 Flash (free) via OpenCode Zen

3. **KiloCode** — Code generation agent
   - URL: http://localhost:8090 (default)
   - Enable: Set \`KILOCODE_ENABLED=true\`
   - Model: KiloCode Coder (free) or Standard

**How to Use:**
1. Enable the agent by setting the \`*_ENABLED\` flag to \`true\`
2. Set the URL where the agent runtime is running
3. Optionally configure a workspace directory
4. Save settings
5. Use the agent from the AI Assistant page by selecting it from the agent dropdown

**Security Notes:**
- Agents run in isolated sandboxes
- All code execution is logged
- Users must approve code before it runs on their system`,ar:`**ما يفعله:**
تبويب وكلاء البرمجة يكوّن تكاملات مع وكلاء برمجة مستقلين يمكنهم كتابة ومراجعة وتنفيذ كود هندسي.

**الوكلاء المدعومون:**
1. **OpenHands** (سابقاً OpenDevin) — وكيل برمجة مستقل كامل
   - الرابط: http://localhost:3000 (افتراضي)
   - التفعيل: تعيين \`OPENHANDS_ENABLED=true\`
   - مساحة العمل: مجلد ملفات الوكيل

2. **OpenCode** — وكيل برمجة CLI مع نماذج مدعومة بـ zen
   - الرابط: http://localhost:8080 (افتراضي)
   - التفعيل: تعيين \`OPENCODE_ENABLED=true\`
   - يدعم DeepSeek V4 Flash (مجاني) عبر OpenCode Zen

3. **KiloCode** — وكيل توليد كود
   - الرابط: http://localhost:8090 (افتراضي)
   - التفعيل: تعيين \`KILOCODE_ENABLED=true\`
   - النموذج: KiloCode Coder (مجاني) أو Standard

**كيفية الاستخدام:**
1. فعّل الوكيل بتعيين العلم \`*_ENABLED\` إلى \`true\`
2. عيّن الرابط حيث يعمل الوكيل
3. اخترياً عيّن مجلد مساحة العمل
4. احفظ الإعدادات
5. استخدم الوكيل من صفحة المساعد الذكي باختياره من القائمة المنسدلة

**ملاحظات الأمان:**
- الوكلاء يعملون في حاويات معزولة
- كل تنفيذ كود مسجل
- المستخدمون يجب他们 بالموافقة على الكود قبل تشغيله`},tags:[`coding`,`agent`,`openhands`,`opencode`,`kilocode`,`وكيل`,`برمجة`],navigateTo:`/settings`,relatedTopics:[`settings.ai-providers`,`code-guard.overview`]},{id:`settings.database`,category:`settings`,title:{en:`Database & Cache Configuration`,ar:`تكوين قاعدة البيانات والذاكرة المؤقتة`},description:{en:`Configure database connection and cache settings`,ar:`تكوين اتصال قاعدة البيانات وإعدادات الذاكرة المؤقتة`},content:{en:`**What it does:**
The Database & Cache tab configures the PostgreSQL database connection and Redis cache for the engineering service.

**Database Settings:**
- **MASTRA_DB_URL** — SQLite database for workflow state (default: file:./mastra.db)
- **DATABASE_URL** — PostgreSQL connection string (e.g. postgresql://user:pass@host:5432/etap)
- **REDIS_URL** — Redis connection string (e.g. redis://localhost:6379/0)

**Cache Settings:**
- **CACHE_SIZE_MB** — Maximum cache size in MB (default: 512)
- **CACHE_DEFAULT_TTL** — Time-to-live for cached items in seconds (default: 3600 = 1 hour)
- **MAX_WORKERS** — Number of parallel worker processes (default: 4)

**How to Configure:**
1. Enter your PostgreSQL connection string (if using Postgres instead of SQLite)
2. Enter your Redis URL (if using Redis for caching)
3. Adjust cache size and TTL based on your workload
4. Set MAX_WORKERS based on your CPU cores (2-8 recommended)
5. Click **Save**

**Recommendations:**
- Use PostgreSQL for production (better concurrency)
- Use Redis for caching study results (faster repeat runs)
- Set CACHE_TTL to 3600 for normal use, 86400 for rarely-changing data
- MAX_WORKERS = CPU cores - 1 (leave one core for OS)`,ar:`**ما يفعله:**
تبويب قاعدة البيانات والذاكرة المؤقتة يكوّن اتصال قاعدة بيانات PostgreSQL والذاكرة المؤقتة Redis للخدمة الهندسية.

**إعدادات قاعدة البيانات:**
- **MASTRA_DB_URL** — رابط قاعدة بيانات SQLite لحالة سير العمل (افتراضي: file:./mastra.db)
- **DATABASE_URL** — سلسلة اتصال PostgreSQL (مثل postgresql://user:pass@host:5432/etap)
- **REDIS_URL** — سلسلة اتصال Redis (مثل redis://localhost:6379/0)

**إعدادات الذاكرة المؤقتة:**
- **CACHE_SIZE_MB** — الحد الأقصى لحجم الذاكرة المؤقتة بالميجابايت (افتراضي: 512)
- **CACHE_DEFAULT_TTL** — مدة البقاء للعناصر المخزنة مؤقتاً بالثواني (افتراضي: 3600 = ساعة واحدة)
- **MAX_WORKERS** — عدد عمليات العامل المتوازية (افتراضي: 4)

**كيفية التكوين:**
1. أدخل سلسلة اتصال PostgreSQL (إذا كنت تستخدم Postgres بدلاً من SQLite)
2. أدخل رابط Redis (إذا كنت تستخدم Redis للذاكرة المؤقتة)
3. اضبط حجم الذاكرة المؤقتة و TTL بناءً على عبء العمل
4. عيّن MAX_WORKERS بناءً على أنوية CPU (2-8 موصى به)
5. انقر **حفظ**

**التوصيات:**
- استخدم PostgreSQL للإنتاج (تزامن أفضل)
- استخدم Redis للذاكرة المؤقتة لنتائج الدراسات (تشغيل متكرر أسرع)
- عيّن CACHE_TTL إلى 3600 للاستخدام العادي، 86400 للبيانات نادرة التغيير
- MAX_WORKERS = أنوية CPU - 1 (اترك نواة للنظام)`},tags:[`database`,`postgres`,`redis`,`cache`,`قاعدة بيانات`,`ذاكرة مؤقتة`],navigateTo:`/settings`,relatedTopics:[`settings.backend`,`diagnostics.overview`]},{id:`settings.security`,category:`settings`,title:{en:`Security & Secrets Management`,ar:`الأمان وإدارة الأسرار`},description:{en:`Configure authentication keys, JWT secrets, and Vault integration`,ar:`تكوين مفاتيح المصادقة وأسرار JWT وتكامل Vault`},content:{en:`**What it does:**
The Security tab configures authentication keys, JWT secrets, and optional HashiCorp Vault integration for secrets management.

**Authentication Settings:**
- **API_KEY_SECRET** — Secret key for validating API requests (X-API-Key header)
- **JWT_SECRET_KEY** — Secret key for signing/verifying JWT tokens

**Vault Integration (Optional):**
- **VAULT_ADDR** — HashiCorp Vault server URL (e.g. https://vault.example.com)
- **VAULT_TOKEN** — Vault authentication token

**How to Configure:**
1. Generate strong random secrets (use a password manager or \`openssl rand -hex 32\`)
2. Enter the API_KEY_SECRET (used by the frontend to authenticate to the backend)
3. Enter the JWT_SECRET_KEY (used for login sessions)
4. Optionally configure Vault for centralized secrets management
5. Click **Save**

**Security Best Practices:**
- Use secrets that are at least 32 characters long
- Rotate secrets every 90 days
- Never commit secrets to git
- Use Vault in production for automatic secret rotation
- Enable MFA for all admin accounts

**Vault Benefits:**
- Centralized secrets management
- Automatic secret rotation
- Audit logging of secret access
- Dynamic secrets (database credentials that expire)`,ar:`**ما يفعله:**
تبويب الأمان يكوّن مفاتيح المصادقة وأسرار JWT وتكامل HashiCorp Vault الاختياري لإدارة الأسرار.

**إعدادات المصادقة:**
- **API_KEY_SECRET** — المفتاح السري للتحقق من طلبات API (ترويسة X-API-Key)
- **JWT_SECRET_KEY** — المفتاح السري لتوقيع/التحقق من رموز JWT

**تكامل Vault (اختياري):**
- **VAULT_ADDR** — رابط خادم HashiCorp Vault (مثل https://vault.example.com)
- **VAULT_TOKEN** — رمز مصادقة Vault

**كيفية التكوين:**
1. توليد أسرار عشوائية قوية (استخدم مدير كلمات مرور أو \`openssl rand -hex 32\`)
2. أدخل API_KEY_SECRET (تستخدمه الواجهة للمصادقة على الخادم)
3. أدخل JWT_SECRET_KEY (تستخدم لجلسات تسجيل الدخول)
4. اخترياً عيّن Vault لإدارة الأسرار المركزية
5. انقر **حفظ**

**أفضل ممارسات الأمان:**
- استخدم أسرار بطول 32 حرف على الأقل
- دور الأسرار كل 90 يوماً
- لا ترفع الأسرار إلى git أبداً
- استخدم Vault في الإنتاج للتدوير التلقائي للأسرار
- فعّل MFA لجميع حسابات المسؤولين

**فوائد Vault:**
- إدارة أسرار مركزية
- تدوير أسرار تلقائي
- سجل تدقيق للوصول للأسرار
- أسرار ديناميكية (بيانات اعتماد قاعدة البيانات تنتهي)`},tags:[`security`,`vault`,`jwt`,`api-key`,`secret`,`أمان`,`أسرار`],navigateTo:`/settings`,relatedTopics:[`settings.backend`,`troubleshooting.auth`]},{id:`settings.integration`,category:`settings`,title:{en:`System Integration (ETAP, SCADA, Email)`,ar:`تكامل النظام (ETAP, SCADA, البريد)`},description:{en:`Configure ETAP desktop, SCADA zenon, and email alert integrations`,ar:`تكوين تكاملات ETAP المكتبي و SCADA zenon وتنبيهات البريد`},content:{en:`**What it does:**
The Integration tab configures connections to external engineering systems: ETAP desktop, SCADA zenon, and email alerts.

**ETAP Integration:**
- **ETAP_LICENSE_PATH** — Path to the ETAP license file on the Windows worker
- **ETAP_WORKER_URL** — URL of the ETAP Worker Service (e.g. http://192.168.1.100:8080)
- Requires: ETAP licensed and installed on Windows, ETAP Worker Service running

**SCADA Integration (Copa-Data zenon):**
- **SCADA_SYSTEM_TYPE** — Type of SCADA system (default: Copa-Data zenon SCADA)
- **SCADA_SERVER_URL** — HTTP endpoint of the zenon REST API (e.g. http://localhost:8080/zenon)
- **SCADA_PROJECT_NAME** — Active zenon project name (default: ETAP_Zenon_Sync)
- **SCADA_SYNC_INTERVAL_SEC** — Polling interval in seconds (default: 10)
- **SCADA_API_KEY** — Authorization token for secure SCADA data transfer

**Email Alerts:**
- **SMTP_SERVER** — SMTP server hostname (e.g. smtp.gmail.com)
- **SMTP_PORT** — SMTP port (587 for TLS, 465 for SSL)
- **SMTP_USERNAME** — Email account username
- **ALERT_EMAIL_TO** — Recipient email for system alerts

**Tips:**
- Test each integration with its respective "Test Connection" button before saving
- For SCADA, use a low sync interval (5-10s) for near-real-time monitoring
- For email, use an app-specific password if your provider supports it`,ar:`**ما يفعله:**
تبويب التكامل يكوّن الاتصالات بأنظمة هندسية خارجية: ETAP المكتبي و SCADA zenon وتنبيهات البريد.

**تكامل ETAP:**
- **ETAP_LICENSE_PATH** — مسار ملف ترخيص ETAP على عامل Windows
- **ETAP_WORKER_URL** — رابط خدمة ETAP العاملة (مثل http://192.168.1.100:8080)
- متطلبات: ETAP مرخص ومثبت على Windows، خدمة ETAP العاملة تعمل

**تكامل SCADA (Copa-Data zenon):**
- **SCADA_SYSTEM_TYPE** — نوع نظام الإسكادا (افتراضي: Copa-Data zenon SCADA)
- **SCADA_SERVER_URL** — رابط نقطة نهاية zenon REST API (مثل http://localhost:8080/zenon)
- **SCADA_PROJECT_NAME** — اسم مشروع zenon النشط (افتراضي: ETAP_Zenon_Sync)
- **SCADA_SYNC_INTERVAL_SEC** — فترة الاقتراع بالثواني (افتراضي: 10)
- **SCADA_API_KEY** — رمز تفويض لنقل بيانات SCADA الآمن

**تنبيهات البريد:**
- **SMTP_SERVER** — خادم SMTP (مثل smtp.gmail.com)
- **SMTP_PORT** — منفذ SMTP (587 لـ TLS، 465 لـ SSL)
- **SMTP_USERNAME** — اسم مستخدم البريد
- **ALERT_EMAIL_TO** — بريد المستلم لتنبيهات النظام

**نصائح:**
- اختبر كل تكامل بزر "اختبار الاتصال" قبل الحفظ
- لـ SCADA، استخدم فترة مزامنة منخفضة (5-10 ثواني) لمراقبة شبه مباشرة
- للبريد، استخدم كلمة مرور خاصة بالتطبيق إذا كان مزودك يدعمها`},tags:[`integration`,`etap`,`scada`,`zenon`,`email`,`smtp`,`تكامل`,`إسكادا`],navigateTo:`/settings`,relatedTopics:[`etap-integration.overview`,`scada-integration.overview`]},{id:`settings.performance`,category:`settings`,title:{en:`Performance & Observability`,ar:`الأداء والمراقبة`},description:{en:`Configure rate limiting, circuit breaker, caching, and Prometheus metrics`,ar:`تكوين تقييد المعدل وقاطع الدائرة والذاكرة المؤقتة ومقاييس Prometheus`},content:{en:`**What it does:**
The Performance tab configures observability, rate limiting, circuit breaker, and feature flags for the engineering service.

**Observability:**
- **HEALTH_CHECK_API_URL** — External health check endpoint (leave empty to skip)
- **PROMETHEUS_ENABLED** — Enable Prometheus metrics export (true/false)
- **PROMETHEUS_PORT** — Port for Prometheus metrics server (default: 9090)

**Rate Limiting & Circuit Breaker:**
- **RATE_LIMIT_REQUESTS_PER_MINUTE** — Max API requests per minute per user (default: 60)
- **CIRCUIT_BREAKER_FAILURE_THRESHOLD** — Failures before circuit opens (default: 3)
- **MAX_BODY_SIZE** — Max request body size in bytes (default: 100000)

**Feature Flags:**
- **ENABLE_ASYNC_EXECUTION** — Run studies asynchronously (true/false, default: true)
- **ENABLE_CACHING** — Cache study results (true/false, default: true)
- **ENABLE_OBSERVABILITY** — Log metrics and traces (true/false, default: true)

**How to Configure:**
1. Set RATE_LIMIT to prevent abuse (60 req/min is typical)
2. Set CIRCUIT_BREAKER to 3-5 for resilience
3. Enable Prometheus for production monitoring
4. Toggle feature flags based on your needs
5. Click **Save**

**Tips:**
- Disable caching during development for fresh results
- Enable async execution for long-running studies
- Prometheus metrics are available at /metrics endpoint`,ar:`**ما يفعله:**
تبويب الأداء يكوّن المراقبة وتقييد المعدل وقاطع الدائرة وأعلام الميزات للخدمة الهندسية.

**المراقبة:**
- **HEALTH_CHECK_API_URL** — رابط نقطة نهاية فحص الصحة الخارجية (اترك فارغاً للتخطي)
- **PROMETHEUS_ENABLED** — تفعيل تصدير مقاييس Prometheus (true/false)
- **PROMETHEUS_PORT** — منفذ خادم مقاييس Prometheus (افتراضي: 9090)

**تقييد المعدل وقاطع الدائرة:**
- **RATE_LIMIT_REQUESTS_PER_MINUTE** — أقصى طلبات API في الدقيقة لكل مستخدم (افتراضي: 60)
- **CIRCUIT_BREAKER_FAILURE_THRESHOLD** — حالات فشل قبل فتح الدائرة (افتراضي: 3)
- **MAX_BODY_SIZE** — الحد الأقصى لحجم جسم الطلب بالبايت (افتراضي: 100000)

**أعلام الميزات:**
- **ENABLE_ASYNC_EXECUTION** — تشغيل الدراسات بشكل غير متزامن (true/false، افتراضي: true)
- **ENABLE_CACHING** — تخزين نتائج الدراسات مؤقتاً (true/false، افتراضي: true)
- **ENABLE_OBSERVABILITY** — تسجيل المقاييس والتتبع (true/false، افتراضي: true)

**كيفية التكوين:**
1. عيّن RATE_LIMIT لمنع الاستغلال (60 req/min نموذجي)
2. عيّن CIRCUIT_BREAKER إلى 3-5 للصلابة
3. فعّل Prometheus لمراقبة الإنتاج
4. بدّل أعلام الميزات بناءً على احتياجاتك
5. انقر **حفظ**

**نصائح:**
- عطّل التخزين المؤقت أثناء التطوير لنتائج جديدة
- فعّل التنفيذ غير المتزامن للدراسات طويلة التشغيل
- مقاييس Prometheus متاحة عند نقطة نهاية /metrics`},tags:[`performance`,`prometheus`,`rate-limit`,`circuit-breaker`,`cache`,`أداء`,`مراقبة`],navigateTo:`/settings`,relatedTopics:[`diagnostics.overview`,`settings.backend`]},{id:`settings.vision`,category:`settings`,title:{en:`Vision API Keys`,ar:`مفاتيح API الرؤية`},description:{en:`Configure vision-capable LLM provider API keys`,ar:`تكوين مفاتيح مزودي LLM القادرون على الرؤية`},content:{en:`**What it does:**
The Vision API Keys tab configures API keys for LLM providers that support image/multimodal inputs. These are used by features like "snap-to-analyze" in the Grid Editor and asset photo recognition.

**Supported Vision Providers:**
- **OpenAI** — GPT-4o, GPT-4o-mini (vision enabled by default)
- **Anthropic** — Claude 3.5 Sonnet, Claude 3 Opus (vision enabled)
- **Google Gemini** — Gemini 1.5 Pro/Flash (vision enabled)
- **Groq** — Llama 3.3 70B (vision via Groq)
- **OpenRouter** — Models with vision capabilities

**Configuration:**
1. Navigate to the Vision API Keys tab in Settings
2. Select a vision provider from the list
3. Enter your API key
4. Click **Save Vision Key**
5. The key is validated and stored (obfuscated)

**How to Use:**
- In Grid Editor: Click the camera icon on any component to analyze its image
- In Asset Management: Upload a photo of equipment for AI-powered identification
- The vision model returns: equipment type, likely model, and maintenance notes

**Privacy:**
- Images are sent to the vision provider's API for analysis
- Images are not stored on our servers
- Review your provider's privacy policy`,ar:`**ما يفعله:**
تبويب مفاتيح API الرؤية يكوّن مفاتيح API لمزودي LLM الذين يدعمون المدخلات متعددة الوسائط (صور). تُستخدم هذه الميزات مثل "التقاط للتحليل" في محرر الشبكة والتعرف على صور الأصول.

**مزودو الرؤية المدعومون:**
- **OpenAI** — GPT-4o، GPT-4o-mini (الرؤية مفعلة افتراضياً)
- **Anthropic** — Claude 3.5 Sonnet، Claude 3 Opus (الرؤية مفعلة)
- **Google Gemini** — Gemini 1.5 Pro/Flash (الرؤية مفعلة)
- **Groq** — Llama 3.3 70B (رؤية عبر Groq)
- **OpenRouter** — النماذج ذات قدرات الرؤية

**التكوين:**
1. انتقل إلى تبويب مفاتيح API الرؤية في الإعدادات
2. اختر مزود رؤية من القائمة
3. أدخل مفتاح API
4. انقر **حفظ مفتاح الرؤية**
5. يتم التحقق من المفتاح وحفظه (مشوّه)

**كيفية الاستخدام:**
- في محرر الشبكة: انقر على أيقونة الكاميرا على أي مكون لتحليل صورته
- في إدارة الأصول: ارفع صورة المعدة untuk التعرف عليها بالذكاء الاصطناعي
- نموذج الرؤية يُرجع: نوع المعدة، الموديل المحتمل، وملاحظات الصيانة

**الخصوصية:**
- الصور مرسلة إلى API مزود الرؤية للتحليل
- الصور لا تُخزن على خوادمنا
- راجع سياسة الخصوصية لمزودك`},tags:[`vision`,`image`,`multimodal`,`gpt-4o`,`claude`,`gemini`,`رؤية`,`صورة`],navigateTo:`/settings`,relatedTopics:[`settings.ai-providers`,`grid-editor.overview`]},{id:`code-guard.overview`,category:`engineering`,title:{en:`Code Guard`,ar:`حارس الكود`},description:{en:`AI-powered code review for engineering calculations`,ar:`مراجعة أكواد بالذكاء الاصطناعي للحسابات الهندسية`},content:{en:`**What it does:**
Code Guard reviews your engineering Python/code for correctness, safety, and compliance with IEEE/IEC standards. It catches common bugs (unit conversion errors, missing factors, wrong formulas) before they cause real-world failures.

**How to Use:**
1. Navigate to **Code Guard** from the sidebar
2. Paste your code in the editor (Python, MATLAB, or pseudo-code)
3. Optionally select a specific standard (IEEE 1584, IEC 60909, etc.)
4. Click **Review Code**
5. The agent returns:
   - Issues found (with severity: error/warning/info)
   - Suggested fixes (with code snippets)
   - Standard references (clause numbers)

**Common Issues Detected:**
- Unit conversion errors (per-unit vs. actual ohms)
- Missing c-factors in IEC 60909
- Wrong electrode configuration in IEEE 1584
- Off-by-one in bus indexing
- Floating-point precision issues
- Missing validation for negative values

**Tips:**
- Be explicit about units in comments (e.g. "# voltage in kV")
- Reference the standard you're targeting
- The reviewer has access to the same IEEE/IEC knowledge base as the AI Assistant`,ar:`**ما يفعله:**
يراجع حارس الكود أكوادك الهندسية (Python/أكواد) للتأكد من الصحة والسلامة والامتثال لمعايير IEEE/IEC. يلتقط الأخطاء الشائعة (أخطاء تحويل الوحدات، العوامل المفقودة، الصيغ الخاطئة) قبل أن تسبب فشلاً في العالم الحقيقي.

**كيفية الاستخدام:**
1. انتقل إلى **حارس الكود** من الشريط الجانبي
2. الصق الكود في المحرر (Python، MATLAB، أو شبه كود)
3. اخترياً حدد معياراً محدداً (IEEE 1584، IEC 60909، إلخ)
4. انقر على **مراجعة الكود**
5. يُرجع الوكيل:
   - المشاكل المكتشفة (مع الشدة: خطأ/تحذير/معلومة)
   - الإصلاحات المقترحة (مع مقتطفات الكود)
   - مراجع المعايير (أرقام البنود)

**المشاكل الشائعة المكتشفة:**
- أخطاء تحويل الوحدات (per-unit مقابل أوم فعلية)
- عوامل c مفقودة في IEC 60909
- تكوين القطب الخاطئ في IEEE 1584
- خطأ بمقدار واحد في فهرسة الباص
- مشاكل دقة الفاصلة العائمة
- التحقق المفقود للقيم السالبة

**نصائح:**
- كن صريحاً بشأن الوحدات في التعليقات (مثل "# الجهد بـ kV")
- اذكر المعيار الذي تستهدفه
- للمراجع وصول إلى نفس قاعدة المعرفة IEEE/IEC مثل المساعد الذكي`},tags:[`code`,`guard`,`review`,`ai`,`كود`,`حارس`,`مراجعة`],navigateTo:`/code-guard`,relatedTopics:[`ai-assistant.overview`]},{id:`data-import.overview`,category:`engineering`,title:{en:`Data Import`,ar:`استيراد البيانات`},description:{en:`Import engineering data from CSV, JSON, Excel, ETAP files`,ar:`استيراد بيانات هندسية من CSV، JSON، Excel، ملفات ETAP`},content:{en:`**What it does:**
The Data Import page lets you bulk-import engineering data (buses, lines, generators, loads, assets) from external files.

**Supported Formats:**
- CSV — comma-separated values
- JSON — structured nested data
- Excel (.xlsx, .xls) — with sheet selection
- ETAP (.etap, .etapz) — ETAP project files
- CIM (.xml) — Common Information Model (IEC 61970)

**How to Use:**
1. Navigate to **Data Import** from the sidebar
2. Select the data type to import (buses, lines, generators, etc.)
3. Choose the file format
4. Click **Choose File** and select your file
5. Preview the parsed data in the table
6. Map columns to ETAP fields if needed
7. Click **Import** to load into the current project

**Validation:**
- Required fields check
- Data type validation (numbers, ranges)
- Reference integrity (e.g. line.from_bus_id must exist)
- Duplicate detection

**Tips:**
- Download the CSV template for each data type to ensure correct column names
- For large imports (>1000 rows), use CSV (faster than Excel)
- Imports are transactional — if any row fails, the entire import is rolled back`,ar:`**ما يفعله:**
تتيح لك صفحة استيراد البيانات استيراد بيانات هندسية مجمّعة (باصات، خطوط، مولدات، أحمال، أصول) من ملفات خارجية.

**التنسيقات المدعومة:**
- CSV — قيم مفصولة بفواصل
- JSON — بيانات متداخلة منظمة
- Excel (.xlsx، .xls) — مع اختيار الورقة
- ETAP (.etap، .etapz) — ملفات مشروع ETAP
- CIM (.xml) — نموذج المعلومات الشائع (IEC 61970)

**كيفية الاستخدام:**
1. انتقل إلى **استيراد البيانات** من الشريط الجانبي
2. اختر نوع البيانات للاستيراد (باصات، خطوط، مولدات، إلخ)
3. اختر تنسيق الملف
4. انقر على **اختر ملف** واختر ملفك
5. عاين البيانات المحللة في الجدول
6. عيّن الأعمدة لحقول ETAP إن لزم
7. انقر على **استيراد** للتحميل في المشروع الحالي

**التحقق:**
- التحقق من الحقول المطلوبة
- التحقق من نوع البيانات (أرقام، نطاقات)
- سلامة المرجع (مثل line.from_bus_id يجب أن يكون موجوداً)
- كشف التكرار

**نصائح:**
- نزّل قالب CSV لكل نوع بيانات لضمان أسماء الأعمدة الصحيحة
- للاستيرادات الكبيرة (>1000 صف)، استخدم CSV (أسرع من Excel)
- الاستيرادات معاملاتية — إذا فشل أي صف، يتم التراجع عن الاستيراد بالكامل`},tags:[`import`,`csv`,`json`,`excel`,`data`,`استيراد`,`بيانات`],navigateTo:`/data-import`,relatedTopics:[`data-export.overview`,`projects.create`]},{id:`data-export.overview`,category:`engineering`,title:{en:`Data Export`,ar:`تصدير البيانات`},description:{en:`Export engineering data to CSV, JSON, Excel, PDF`,ar:`تصدير بيانات هندسية إلى CSV، JSON، Excel، PDF`},content:{en:`**What it does:**
The Data Export page lets you export your engineering data and study results to various formats for sharing, archiving, or importing into other tools.

**Supported Formats:**
- CSV — for spreadsheet analysis
- JSON — for API integration
- Excel (.xlsx) — formatted with headers and styling
- PDF — formatted reports with tables and figures
- CIM XML — for interchange with other utility systems

**How to Use:**
1. Navigate to **Data Export** from the sidebar
2. Select the data to export:
   - Project configuration
   - Study results (current or all)
   - Asset register
   - Audit log
3. Choose the export format
4. Configure options (date range, include secrets, etc.)
5. Click **Export**
6. The file downloads to your browser

**Tips:**
- For compliance audits, export to PDF with the audit log included
- For sharing with team members who don't have AhmedETAP, use Excel
- For backup, use JSON (preserves all data structures)
- Exported files never include secrets (API keys, tokens) — those stay in your browser`,ar:`**ما يفعله:**
تتيح لك صفحة تصدير البيانات تصدير بياناتك الهندسية ونتائج الدراسات إلى تنسيقات مختلفة للمشاركة أو الأرشفة أو الاستيراد في أدوات أخرى.

**التنسيقات المدعومة:**
- CSV — لتحليل جداول البيانات
- JSON — لتكامل API
- Excel (.xlsx) — منسق مع الترويسات والتنسيق
- PDF — تقارير منسقة مع جداول وأشكال
- CIM XML — للتبادل مع أنظمة المرافق الأخرى

**كيفية الاستخدام:**
1. انتقل إلى **تصدير البيانات** من الشريط الجانبي
2. اختر البيانات للتصدير:
   - تكوين المشروع
   - نتائج الدراسة (الحالية أو الكل)
   - سجل الأصول
   - سجل التدقيق
3. اختر تنسيق التصدير
4. قوم الخيارات (النطاق الزمني، تضمين الأسرار، إلخ)
5. انقر على **تصدير**
6. يتم نزول الملف إلى متصفحك

**نصائح:**
- لتدقيق الامتثال، صدّر إلى PDF مع سجل التدقيق المضمن
- للمشاركة مع أعضاء الفريق الذين ليس لديهم AhmedETAP، استخدم Excel
- للنسخ الاحتياطي، استخدم JSON (يحفظ جميع هياكل البيانات)
- الملفات المصدّرة لا تتضمن أبداً الأسرار (مفاتيح API، الرموز) — تبقى في متصفحك`},tags:[`export`,`csv`,`json`,`excel`,`pdf`,`data`,`تصدير`,`بيانات`],navigateTo:`/data-export`,relatedTopics:[`data-import.overview`,`reports.generate`]},{id:`administration.overview`,category:`settings`,title:{en:`Administration`,ar:`الإدارة`},description:{en:`User management, roles, and system administration`,ar:`إدارة المستخدمين والأدوار وإدارة النظام`},content:{en:`**What it does:**
The Administration page (admin-only) lets you manage users, roles, and system-wide settings.

**Features (admin role required):**
- **User List** — view all registered users
- **Deactivate User** — soft-delete a user (set is_active = false)
- **View Audit Log** — see all user actions (login, study runs, settings changes)
- **System Metrics** — request counts, error rates, response times

**Roles:**
- \`admin\` — full access including user management
- \`engineer\` — default role, can run studies and manage own projects
- \`viewer\` — read-only access (cannot run studies or modify settings)

**Permissions Matrix:**
| Action | admin | engineer | viewer |
|--------|-------|----------|--------|
| View dashboard | ✓ | ✓ | ✓ |
| Run studies | ✓ | ✓ | ✗ |
| Create projects | ✓ | ✓ | ✗ |
| Delete projects | ✓ | ✗ | ✗ |
| Manage users | ✓ | ✗ | ✗ |
| View audit log | ✓ | ✗ | ✗ |

**Tips:**
- Only admins can access /admin route
- Deactivated users cannot log in but their data is preserved
- Audit log is retained for 90 days`,ar:`**ما يفعله:**
تتيح لك صفحة الإدارة (للمسؤولين فقط) إدارة المستخدمين والأدوار والإعدادات على مستوى النظام.

**الميزات (تتطلب دور المسؤول):**
- **قائمة المستخدمين** — عرض جميع المستخدمين المسجلين
- **تعطيل مستخدم** — حذف ناعم (تعيين is_active = false)
- **عرض سجل التدقيق** — رؤية جميع إجراءات المستخدم (تسجيل الدخول، تشغيل الدراسات، تغييرات الإعدادات)
- **مقاييس النظام** — عدد الطلبات، معدلات الأخطاء، أوقات الاستجابة

**الأدوار:**
- \`admin\` — وصول كامل بما في ذلك إدارة المستخدمين
- \`engineer\` — الدور الافتراضي، يمكن تشغيل الدراسات وإدارة مشاريعه الخاصة
- \`viewer\` — وصول للقراءة فقط (لا يمكن تشغيل الدراسات أو تعديل الإعدادات)

**مصفوفة الصلاحيات:**
| الإجراء | admin | engineer | viewer |
|--------|-------|----------|--------|
| عرض لوحة التحكم | ✓ | ✓ | ✓ |
| تشغيل الدراسات | ✓ | ✓ | ✗ |
| إنشاء المشاريع | ✓ | ✓ | ✗ |
| حذف المشاريع | ✓ | ✗ | ✗ |
| إدارة المستخدمين | ✓ | ✗ | ✗ |
| عرض سجل التدقيق | ✓ | ✗ | ✗ |

**نصائح:**
- فقط المسؤولون يمكنهم الوصول إلى مسار /admin
- المستخدمون المعطلون لا يمكنهم تسجيل الدخول لكن بياناتهم محفوظة
- سجل التدقيق محفوظ لمدة 90 يوماً`},tags:[`admin`,`user`,`management`,`role`,`إدارة`,`مستخدم`,`دور`],navigateTo:`/admin`,relatedTopics:[`settings.backend`,`troubleshooting.auth`]},{id:`diagnostics.overview`,category:`troubleshooting`,title:{en:`Diagnostics`,ar:`التشخيص`},description:{en:`System health checks, logs, and performance metrics`,ar:`فحوصات صحة النظام والسجلات ومقاييس الأداء`},content:{en:`**What it does:**
The Diagnostics page provides real-time system health monitoring, log viewing, and performance metrics for troubleshooting.

**Sections:**
1. **Health Checks** — live status of all subsystems
   - Backend connectivity
   - Database connection
   - Redis cache
   - ETAP worker (if configured)
   - External services (LangWatch, Smithery, etc.)

2. **Logs** — real-time log stream
   - Filter by level (INFO, WARN, ERROR, DEBUG)
   - Filter by source (api, engine, agent, integration)
   - Search by text
   - Export to file

3. **Performance Metrics**
   - API response times (p50, p95, p99)
   - Request rates (req/sec)
   - Error rates (% by status code)
   - Memory and CPU usage

4. **Trace IDs** — search for a specific request trace

**How to Use:**
- When something fails, check Health Checks first
- Then check Logs for the error message
- Use the trace_id from the error response to find related log entries
- Performance metrics help identify slow endpoints`,ar:`**ما يفعله:**
توفر صفحة التشخيص مراقبة صحة النظام في الوقت الفعلي وعرض السجلات ومقاييس الأداء لاستكشاف الأخطاء وإصلاحها.

**الأقسام:**
1. **فحوصات الصحة** — الحالة المباشرة لجميع الأنظمة الفرعية
   - اتصال الخادم
   - اتصال قاعدة البيانات
   - ذاكرة التخزين المؤقت Redis
   - عامل ETAP (إذا تم تكوينه)
   - الخدمات الخارجية (LangWatch، Smithery، إلخ)

2. **السجلات** — تدفق السجلات المباشر
   - الفلترة حسب المستوى (INFO، WARN، ERROR، DEBUG)
   - الفلترة حسب المصدر (api، engine، agent، integration)
   - البحث بالنص
   - التصدير إلى ملف

3. **مقاييس الأداء**
   - أوقات استجابة API (p50، p95، p99)
   - معدلات الطلبات (req/sec)
   - معدلات الأخطاء (% حسب كود الحالة)
   - استخدام الذاكرة و CPU

4. **معرفات التتبع** — البحث عن تتبع طلب محدد

**كيفية الاستخدام:**
- عند فشل شيء، تحقق من فحوصات الصحة أولاً
- ثم تحقق من السجلات لرسالة الخطأ
- استخدم trace_id من استجابة الخطأ للعثور على إدخالات السجل ذات الصلة
- تساعد مقاييس الأداء في تحديد النقاط البطيئة`},tags:[`diagnostics`,`health`,`logs`,`metrics`,`تشخيص`,`صحة`,`سجلات`],navigateTo:`/diagnostics`,relatedTopics:[`troubleshooting.backend`,`troubleshooting.api`]},{id:`logs.overview`,category:`troubleshooting`,title:{en:`Logs`,ar:`السجلات`},description:{en:`Real-time application logs with filtering`,ar:`سجلات التطبيق المباشرة مع الفلترة`},content:{en:`**What it does:**
The Logs page shows a real-time stream of application logs with powerful filtering.

**Features:**
- Live log stream (auto-refresh)
- Filter by level: INFO, WARN, ERROR, DEBUG
- Filter by source: api, engine, agent, security, integration
- Full-text search
- Timestamp range filter
- Click a log entry for full details
- Export filtered logs to JSON or text file

**Log Levels:**
- \`DEBUG\` — verbose diagnostic info (typically off in production)
- \`INFO\` — normal operation events
- \`WARN\` — unexpected but non-fatal conditions
- \`ERROR\` — failures that need attention

**Tips:**
- When debugging, start with ERROR level, then expand to WARN
- The trace_id field lets you follow a single request across services
- Logs are kept for 7 days by default (configurable in admin settings)
- Use the search box to find specific error messages or user IDs`,ar:`**ما يفعله:**
تعرض صفحة السجلات تدفقاً مباشراً لسجلات التطبيق مع فلترة قوية.

**الميزات:**
- تدفق السجلات المباشر (تحديث تلقائي)
- الفلترة حسب المستوى: INFO، WARN، ERROR، DEBUG
- الفلترة حسب المصدر: api، engine، agent، security، integration
- بحث نصي كامل
- فلتر النطاق الزمني
- انقر على إدخال السجل للتفاصيل الكاملة
- تصدير السجلات المفلترة إلى JSON أو ملف نصي

**مستويات السجل:**
- \`DEBUG\` — معلومات تشخيصية مطوّلة (عادةً مغلقة في الإنتاج)
- \`INFO\` — أحداث التشغيل العادية
- \`WARN\` — ظروف غير متوقعة لكن غير قاتلة
- \`ERROR\` — فشل يحتاج اهتماماً

**نصائح:**
- عند التصحيح، ابدأ بمستوى ERROR، ثم وسّع إلى WARN
- يتيح لك حقل trace_id متابعة طلب واحد عبر الخدمات
- تُحفظ السجلات لمدة 7 أيام افتراضياً (قابلة للتكوين في إعدادات المسؤول)
- استخدم صندوق البحث للعثور على رسائل خطأ محددة أو معرفات المستخدم`},tags:[`logs`,`stream`,`filter`,`debug`,`سجلات`,`تصحيح`],navigateTo:`/logs`,relatedTopics:[`diagnostics.overview`,`troubleshooting.backend`]},{id:`scada-integration.overview`,category:`digital-twin`,title:{en:`SCADA Integration (zenon)`,ar:`تكامل الإسكادا (زينون)`},description:{en:`Connect and sync with Copa-Data zenon SCADA system`,ar:`الاتصال والمزامنة مع نظام إسكادا زينون من كوبا-داتا`},content:{en:`**What it does:**
The SCADA Integration page connects AhmedETAP with a Copa-Data zenon SCADA server to stream real-time telemetry (voltages, currents, frequencies) and receive alarms/events.

**Required Configuration:**
- **Zenon Server URL** — e.g. \`http://localhost:8080/zenon\`
- **API Key / Token** — authentication token for the SCADA API
- **Project Name** — zenon project identifier (default: \`ETAP_Zenon_Sync\`)
- **Sync Rate (sec)** — polling interval in seconds (default: 2)

**Features:**
1. **Live Telemetry Sync** — WebSocket or HTTP fallback polling
2. **Alarm Stream** — real-time alarm ingestion with severity levels
3. **Connection Trace Logs** — debug logs for connection lifecycle
4. **Offline Simulation** — local simulated feed when zenon is unreachable

**How to Use:**
1. Enter your zenon server URL and API token
2. Click **Save SCADA Configuration** to persist to localStorage
3. Click **Ping Server** to verify connectivity and measure latency
4. Click **Start Live** to begin streaming data
5. Monitor telemetry table, alarm stream, and connection logs

**Simulation Mode:**
Enable the **Offline Simulation Mode** checkbox to test without a real zenon runtime. The system generates fluctuating values and random alarms for demonstration.

**Troubleshooting:**
- "Connection failed" — ensure zenon runtime is running and CORS is configured
- WebSocket fails — falls back automatically to HTTP polling
- No telemetry data — check API key permissions and project name`,ar:`**ما يفعله:**
تتصل صفحة تكامل الإسكادا بخادم إسكادا زينون من كوبا-داتا لبث البيانات القياسية الحية (جهود، تيارات، ترددات) واستقبال الإنذارات/الأحداث.

**التكوين المطلوب:**
- **رابط خادم زينون** — مثل \`http://localhost:8080/zenon\`
- **مفتاح API / رمز** — رمز مصادقة لـ API الإسكادا
- **اسم المشروع** — معرف مشروع زينون (افتراضي: \`ETAP_Zenon_Sync\`)
- **معدل التحديث (ثانية)** — فترة الاقتراع بالثواني (افتراضي: 2)

**الميزات:**
1. **مزامنة البيانات الحية** — WebSocket أو اقتراع HTTP احتياطي
2. **بث الإنذارات** — استهلاك إنذارات فورية بمستويات خطورة
3. **سجلات تتبع الاتصال** — سجلات تشخيص لدورة حياة الاتصال
4. **محاكاة غير متصلة** — تغذية محلية محاكاة عند عدم توفر زينون

**كيفية الاستخدام:**
1. أدخل رابط خادم زينون ورمز API
2. انقر **حفظ إعدادات الربط** للتخزين المحلي
3. انقر **فحص الاتصال** للتحقق من الاتصال وقياس زمن الاستجابة
4. انقر **تشغيل البث** لبدء تدفق البيانات
5. راقب جدول البيانات القياسية وبث الإنذارات وسجلات الاتصال

**وضع المحاكاة:**
فعّل خانة **تفعيل بيئة المحاكاة المحلية** للاختبار بدون تشغيل زينون فعلي. يولد النظام قيمًا متقلبة وإنذارات عشوائية للعرض.

**استكشاف الأخطاء:**
- "فشل الاتصال" — تأكد من تشغيل zenon وتكوين CORS
- WebSocket يفشل — يحول تلقائيًا لاقتراع HTTP
- لا توجد بيانات — تحقق من صلاحيات مفتاح API واسم المشروع`},tags:[`scada`,`zenon`,`copa-data`,`telemetry`,`websocket`,`alarm`,`إسكادا`,`زينون`,`هاتف`],navigateTo:`/scada`,relatedTopics:[`digital-twin.overview`,`integration.scada`]},{id:`grid-editor.overview`,category:`engineering`,title:{en:`Grid Editor`,ar:`محرر الشبكة`},description:{en:`Interactive power system diagram editor for buses, lines, and transformers`,ar:`محرر رسومي تفاعلي لنظام القدرة: باصات، خطوط، محولات`},content:{en:`**What it does:**
The Grid Editor provides a visual canvas for building and editing single-line diagrams (SLDs) of power systems. Drag components from the palette, connect them with lines, and configure electrical parameters.

**Component Palette:**
- **Buses** — Slack, PV, PQ bus types with voltage/power setpoints
- **Lines** — Transmission/distribution lines with R, X, B parameters
- **Transformers** — Two-winding and three-winding with tap ratios
- **Generators** — Synchronous machines with P/Q/V setpoints
- **Loads** — Constant power/current/impedance models
- **Capacitors/Reactors** — Shunt compensation devices

**How to Use:**
1. Select a component from the left palette
2. Click on the canvas to place it
3. Drag from a component's port to another to connect
4. Click a placed component to edit its properties in the right panel
5. Use the toolbar actions: Save, Undo/Redo, Zoom, Export

**Keyboard Shortcuts:**
- \`Delete\` — remove selected component
- \`Ctrl+Z\` — undo
- \`Ctrl+Shift+Z\` — redo
- \`Ctrl+S\` — save diagram
- \`Ctrl+A\` — select all

**Tips:**
- Snap-to-grid keeps diagram tidy
- Ports highlight when dragging a connection near them
- The properties panel shows context-sensitive fields based on component type`,ar:`**ما يفعله:**
يوفر محرر الشبكة لوحة رسم مرئية لبناء وتعديل المخططات أحادية الخط (SLD) لأنظمة القدرة. اسحب المكونات من اللوحة، اربطها بالخطوط، وقم بتكوين المعلمات الكهربية.

**لوحة المكونات:**
- **الباصات** — أنواع slack و PV و PQ مع تحديد الجهد/القدرة
- **الخطوط** — خطوط نقل/توزيع بمعاملات R و X و B
- **المحولات** — ثنائي وثلاثي اللفات مع نسب التحويل
- **المولدات** — آلات تزامنية مع تحديد P/Q/V
- **الأحمال** — نماذج قدرة/تيار/مقاومة ثابتة
- **مكثفات/مفاعلات** — أجهزة تعويض موازٍ

**كيفية الاستخدام:**
1. اختر مكونًا من اللوحة اليسرى
2. انقر على اللوحة لوضعه
3. اسحب من منفذ المكون إلى آخر للاتصال
4. انقر على المكون الموجود لتعديل خصائصه في اللوحة اليمنى
5. استخدم أزرار شريط الأدوات: حفظ، تراجع/إعادة، تكبير، تصدير

**نصائح:**
- المحاذاة للشبكة تحافظ على ترتيب الرسم
- تظهر المنافذ عند السحب قربها
- تعرض لوحة الخصائص حقول حساسة لنوع المكون`},tags:[`grid`,`editor`,`sld`,`diagram`,`canvas`,`محرر`,`شبكة`,`رسم`],navigateTo:`/grid-editor`,relatedTopics:[`studies.load-flow`,`asset-management.overview`]}];function Er(e,t){let n=e.toLowerCase(),r=t.toLowerCase();if(r.includes(n))return!0;let i=0;for(let e=0;e<r.length&&i<n.length;e++)r[e]===n[i]&&i++;return i===n.length}function Dr(){let{i18n:e}=P(),t=e.language===`ar`?`ar`:`en`,[n,r]=(0,z.useState)(``),[i,a]=(0,z.useState)(`all`),[o,s]=(0,z.useState)(null),c=(0,z.useMemo)(()=>Tr.find(e=>e.id===o)??null,[o]),l=(0,z.useMemo)(()=>{let e=Tr;if(i!==`all`&&(e=e.filter(e=>e.category===i)),n.trim()){let r=n.trim();e=e.filter(e=>{let n=[e.title[t],e.description[t],e.content[t],...e.tags].join(` `);return Er(r,n)})}return e},[n,i,t]);return{topics:Tr,categories:wr,activeTopic:c,searchQuery:n,selectedCategory:i,setSearchQuery:r,setSelectedCategory:a,openTopic:(0,z.useCallback)(e=>{s(e)},[]),openContext:(0,z.useCallback)(e=>{let t=mr(e);t&&s(t)},[]),closeTopic:(0,z.useCallback)(()=>{s(null)},[]),filteredTopics:l}}var Or={"getting-started":Ue,projects:S,"fire-alarm":Re,engineering:x,reports:o,"digital-twin":E,settings:O,troubleshooting:w,"keyboard-shortcuts":v},kr=[{label:{en:`📚 Getting Started`,ar:`📚 مقدمة البداية`},children:[{label:{en:`Overview Dashboard`,ar:`نظرة عامة على لوحة التحكم`},topicId:`dashboard.overview`},{label:{en:`Keyboard Shortcuts`,ar:`اختصارات لوحة المفاتيح`},topicId:`keyboard-shortcuts`}]},{label:{en:`📁 Project Management`,ar:`📁 إدارة المشاريع`},children:[{label:{en:`Creating a New Project`,ar:`إنشاء مشروع جديد`},topicId:`projects.create`},{label:{en:`Managing Projects`,ar:`إدارة وتعديل المشاريع`},topicId:`projects.manage`}]},{label:{en:`🚨 Fire Alarm System`,ar:`🚨 أنظمة إنذار الحريق`},children:[{label:{en:`Detector Placement`,ar:`وضع أجهزة الاستشعار`},topicId:`fire-alarm.detector-placement`},{label:{en:`Zone Design & Navigation`,ar:`تصميم وتنقل المناطق`},topicId:`fire-alarm.zone-navigation`},{label:{en:`Device Symbol Library`,ar:`مكتبة رموز الأجهزة`},topicId:`fire-alarm.symbol-library`}]},{label:{en:`📊 Reports & Documentation`,ar:`📊 التقارير والتوثيق`},children:[{label:{en:`Generating Reports`,ar:`إنشاء وتصدير التقارير`},topicId:`reports.generate`}]},{label:{en:`🔗 System Integration & SCADA`,ar:`🔗 تكامل الأنظمة والإسكادا`},children:[{label:{en:`ETAP Worker Integration`,ar:`تكامل بيئة عمل إيتاب`},topicId:`projects.create`},{label:{en:`SCADA System zenon Integration`,ar:`ربط نظام إسكادا (زينون)`},topicId:`integration.scada`},{label:{en:`Digital Twin Overview`,ar:`التوأم الرقمي للمشروع`},topicId:`digital-twin.overview`}]},{label:{en:`⚙️ Configuration & Settings`,ar:`⚙️ التكوين والإعدادات`},children:[{label:{en:`FastAPI Backend Config`,ar:`إعدادات خادم الخدمات الهندسية`},topicId:`settings.backend`}]},{label:{en:`🛠️ Troubleshooting`,ar:`🛠️ استكشاف الأخطاء وحلها`},children:[{label:{en:`Backend Service Offline`,ar:`مشاكل توقف الخادم`},topicId:`troubleshooting.backend`},{label:{en:`REST API Error Codes`,ar:`أكواد أخطاء استجابة الـ API`},topicId:`troubleshooting.api`},{label:{en:`User Auth & JWT Issues`,ar:`مشاكل مصادقة رموز الدخول`},topicId:`troubleshooting.auth`}]}];function Ar({node:e,lang:t,onSelectTopic:n,expandedNodes:r,onToggleNode:i,level:a=0}){let o=!!e.children,s=e.label.en,c=r.has(s);return(0,B.jsxs)(`div`,{className:`select-none text-left`,style:{marginLeft:`${a*10}px`},children:[(0,B.jsxs)(`button`,{type:`button`,onClick:()=>{o?i(s):e.topicId&&n(e.topicId)},onKeyDown:t=>{(t.key===`Enter`||t.key===` `)&&(t.preventDefault(),o?i(s):e.topicId&&n(e.topicId))},className:q(`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium cursor-pointer transition-all mt-0.5`,`bg-transparent border-0 text-left w-full appearance-none`,`hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]`,!o&&`pl-6 border-l border-transparent hover:border-[var(--accent-primary)]/40`),children:[o?(0,B.jsx)(`span`,{className:`text-[9px] text-[var(--text-muted)] font-mono shrink-0 w-3 text-center`,children:c?`▼`:`▶`}):(0,B.jsx)(ze,{className:`w-3 h-3 text-[var(--text-muted)] shrink-0`}),(0,B.jsx)(`span`,{className:`truncate`,children:e.label[t]})]}),o&&c&&e.children&&(0,B.jsx)(`div`,{className:`mt-0.5 border-l border-[var(--border-primary)] ml-3.5 pl-1.5 space-y-0.5`,children:e.children.map(e=>(0,B.jsx)(Ar,{node:e,lang:t,onSelectTopic:n,expandedNodes:r,onToggleNode:i,level:a+1},e.label.en))})]})}function jr({activeTopic:e,lang:t,navigate:n,onClose:r,closeTopic:i,openTopic:a,filteredTopics:o}){let s=Or[e.category]||v,c=!!e.relatedTopics&&e.relatedTopics.length>0;return(0,B.jsxs)(`div`,{className:`flex-1 overflow-y-auto`,children:[(0,B.jsxs)(`button`,{onClick:i,className:`flex items-center gap-1.5 px-5 py-3 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors`,type:`button`,children:[`← `,t===`ar`?`العودة للفهرس`:`Back to book index`]}),(0,B.jsxs)(`div`,{className:`px-5 pb-4`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-2 mb-2`,children:[(0,B.jsx)(s,{className:`w-5 h-5 text-[var(--accent-primary)]`}),(0,B.jsx)(`h3`,{className:`text-lg font-semibold text-[var(--text-primary)]`,children:e.title[t]})]}),(0,B.jsx)(`p`,{className:`text-sm text-[var(--text-secondary)]`,children:e.description[t]})]}),(0,B.jsx)(`div`,{className:`px-5 pb-4`,children:(0,B.jsx)(`div`,{className:`prose prose-sm max-w-none text-[var(--text-secondary)]`,children:e.content[t].split(`
`).map(e=>(0,B.jsx)(Mr,{line:e},`line-${e.length}-${e.substring(0,16)}`))})}),(0,B.jsx)(`div`,{className:`px-5 pb-4 space-y-2`,children:e.navigateTo&&(0,B.jsxs)(`button`,{onClick:()=>{n(e.navigateTo),r(),e.navigateTo&&n(e.navigateTo)},className:`w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] rounded-lg hover:bg-[var(--accent-primary)]/20 transition-colors`,type:`button`,children:[(0,B.jsx)(g,{className:`w-4 h-4`}),t===`ar`?`فتح الصفحة ذات الصلة`:`Open related page`]})}),c&&(0,B.jsxs)(`div`,{className:`px-5 pb-5 border-t border-[var(--border-primary)] pt-4`,children:[(0,B.jsx)(`h4`,{className:`text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2`,children:t===`ar`?`مواضيع ذات صلة`:`Related Topics`}),(0,B.jsx)(`div`,{className:`space-y-1`,children:(e.relatedTopics??[]).map(e=>{let n=o.find(t=>t.id===e)??null;return n?(0,B.jsxs)(`button`,{onClick:()=>a(e),className:`w-full flex items-center gap-2 px-3 py-2 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] rounded-lg transition-colors text-left`,type:`button`,children:[(0,B.jsx)(L,{className:`w-3 h-3 text-[var(--text-muted)]`}),n.title[t]]},e):null})})]})]})}function Mr({line:e}){let t=`line-${e.length}-${e.substring(0,16)}`;return e.startsWith(`**`)&&e.endsWith(`**`)?(0,B.jsx)(`h4`,{className:`text-sm font-semibold text-[var(--text-primary)] mt-4 mb-2`,children:e.replaceAll(`**`,``)},t):e.startsWith(`- `)?(0,B.jsx)(`li`,{className:`text-xs ml-4 mb-1`,children:e.substring(2)},t):e.startsWith("```")?null:e.trim()===``?(0,B.jsx)(`div`,{className:`h-2`},t):(0,B.jsx)(`p`,{className:`text-xs leading-relaxed mb-2`,children:e},t)}function Nr({helpViewMode:e,setHelpViewMode:t,lang:n,expandedNodes:r,toggleNode:i,openTopic:a,categories:o,selectedCategory:s,setSelectedCategory:c,searchRef:l,searchQuery:u,setSearchQuery:d,filteredTopics:f}){return(0,B.jsxs)(B.Fragment,{children:[(0,B.jsxs)(`div`,{className:`px-5 py-2 border-b border-[var(--border-primary)] flex gap-2`,children:[(0,B.jsxs)(`button`,{onClick:()=>t(`tree`),className:q(`flex-1 py-1.5 text-xs font-semibold rounded-lg border text-center transition-all`,e===`tree`?`bg-brand-500/10 text-brand-400 border-brand-500/25`:`bg-transparent text-[var(--text-muted)] border-transparent hover:text-[var(--text-primary)]`),type:`button`,children:[`🗂️ `,n===`ar`?`كتاب الفهرس (Tree)`:`Book Manual (Tree)`]}),(0,B.jsxs)(`button`,{onClick:()=>t(`list`),className:q(`flex-1 py-1.5 text-xs font-semibold rounded-lg border text-center transition-all`,e===`list`?`bg-brand-500/10 text-brand-400 border-brand-500/25`:`bg-transparent text-[var(--text-muted)] border-transparent hover:text-[var(--text-primary)]`),type:`button`,children:[`🔎 `,n===`ar`?`بحث سريع`:`Quick Search`]})]}),e===`tree`?(0,B.jsx)(`div`,{className:`flex-1 overflow-y-auto p-4 space-y-1.5`,children:kr.map(e=>(0,B.jsx)(Ar,{node:e,lang:n,onSelectTopic:e=>a(e),expandedNodes:r,onToggleNode:i},e.label.en))}):(0,B.jsx)(Pr,{lang:n,searchRef:l,searchQuery:u,setSearchQuery:d,categories:o,selectedCategory:s,setSelectedCategory:c,filteredTopics:f,openTopic:a}),(0,B.jsx)(`div`,{className:`px-5 py-3 border-t border-[var(--border-primary)] text-[10px] text-[var(--text-muted)]`,children:n===`ar`?`${f.length} مواضيع · F1 للمساعدة`:`${f.length} topics · F1 for help`})]})}function Pr({lang:e,searchRef:t,searchQuery:n,setSearchQuery:r,categories:i,selectedCategory:a,setSelectedCategory:o,filteredTopics:s,openTopic:c}){return(0,B.jsxs)(B.Fragment,{children:[(0,B.jsx)(`div`,{className:`px-5 py-3 border-b border-[var(--border-primary)]`,children:(0,B.jsxs)(`div`,{className:`flex items-center gap-2 px-3 py-2 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]`,children:[(0,B.jsx)(I,{className:`w-4 h-4 text-[var(--text-muted)]`}),(0,B.jsx)(`input`,{ref:t,type:`text`,value:n,onChange:e=>r(e.target.value),placeholder:e===`ar`?`البحث في المواضيع...`:`Search topics...`,className:`flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none`})]})}),(0,B.jsx)(`div`,{className:`px-5 py-2 border-b border-[var(--border-primary)] flex gap-1 overflow-x-auto`,children:i.map(t=>(0,B.jsx)(`button`,{onClick:()=>o(t.id),className:q(`px-2.5 py-1 text-[11px] font-medium rounded-md whitespace-nowrap transition-colors`,a===t.id?`bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]`:`text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-secondary)]`),type:`button`,children:t.label[e]},t.id))}),(0,B.jsx)(`div`,{className:`flex-1 overflow-y-auto py-2`,children:s.length===0?(0,B.jsxs)(`div`,{className:`px-5 py-12 text-center`,children:[(0,B.jsx)(qe,{className:`w-10 h-10 text-[var(--text-muted)] mx-auto mb-3`}),(0,B.jsx)(`p`,{className:`text-sm text-[var(--text-muted)]`,children:e===`ar`?`لم يتم العثور على مواضيع`:`No topics found`})]}):(0,B.jsx)(`div`,{className:`space-y-0.5`,children:s.map(t=>{let n=Or[t.category]||v;return(0,B.jsxs)(`button`,{onClick:()=>c(t.id),className:`w-full flex items-center gap-3 px-5 py-2.5 text-left hover:bg-[var(--bg-elevated)] transition-colors group`,type:`button`,children:[(0,B.jsx)(`div`,{className:`w-7 h-7 rounded-md bg-[var(--bg-elevated)] flex items-center justify-center shrink-0 group-hover:bg-[var(--accent-glow)]`,children:(0,B.jsx)(n,{className:`w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-[var(--accent-primary)]`})}),(0,B.jsxs)(`div`,{className:`flex-1 min-w-0`,children:[(0,B.jsx)(`div`,{className:`text-xs font-medium text-[var(--text-primary)] truncate`,children:t.title[e]}),(0,B.jsx)(`div`,{className:`text-[10px] text-[var(--text-muted)] truncate`,children:t.description[e]})]}),(0,B.jsx)(L,{className:`w-3.5 h-3.5 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity`})]},t.id)})})})]})}function Fr(e,t){let n=mr(e);if(!n)return;let r=kr.find(e=>e.children?.some(e=>e.topicId===n));r&&t(e=>{let t=new Set(e);return t.add(r.label.en),t})}function Ir({open:e,onClose:t,initialContextId:n}){let{i18n:r}=P(),i=Pe(),a=r.language===`ar`?`ar`:`en`,o=(0,z.useRef)(null),{categories:s,activeTopic:c,searchQuery:l,selectedCategory:u,setSearchQuery:d,setSelectedCategory:f,openTopic:p,openContext:m,closeTopic:h,filteredTopics:g}=Dr(),[_,v]=(0,z.useState)(`tree`),[y,b]=(0,z.useState)(new Set([`📚 Getting Started`]));return(0,z.useEffect)(()=>{!e||!n||(m(n),Fr(n,b))},[e,n,m]),(0,z.useEffect)(()=>{e&&_===`list`&&setTimeout(()=>o.current?.focus(),100)},[e,_]),(0,z.useEffect)(()=>{if(!e)return;let n=e=>{e.key===`Escape`&&(c?h():t())};return globalThis.addEventListener(`keydown`,n),()=>globalThis.removeEventListener(`keydown`,n)},[e,c,t,h]),e?(0,B.jsxs)(`div`,{className:`fixed inset-0 z-[100] flex justify-end`,children:[(0,B.jsx)(`button`,{type:`button`,className:`absolute inset-0 bg-black/50 backdrop-blur-sm cursor-default border-0 p-0`,"aria-label":`Close help drawer`,onClick:t,onKeyDown:e=>{(e.key===`Enter`||e.key===` `)&&t()}}),(0,B.jsxs)(`div`,{className:q(`relative z-[101] w-full max-w-lg h-full`,`bg-[var(--bg-secondary)] border-l border-[var(--border-primary)]`,`shadow-2xl shadow-black/30`,`flex flex-col`,`animate-slide-in`),children:[(0,B.jsxs)(`div`,{className:`flex items-center justify-between px-5 py-4 border-b border-[var(--border-primary)]`,children:[(0,B.jsxs)(`div`,{className:`flex items-center gap-3`,children:[(0,B.jsx)(`div`,{className:`w-8 h-8 rounded-lg bg-[var(--accent-glow)] flex items-center justify-center`,children:(0,B.jsx)(qe,{className:`w-4 h-4 text-[var(--accent-primary)]`})}),(0,B.jsxs)(`div`,{children:[(0,B.jsx)(`h2`,{className:`text-sm font-semibold text-[var(--text-primary)]`,children:a===`ar`?`المساعدة الذكية (TOC)`:`Smart Help (TOC)`}),(0,B.jsx)(`p`,{className:`text-[10px] text-[var(--text-muted)]`,children:a===`ar`?`دليل شجرة الفهرس والمستندات`:`TOC book index & context guide`})]})]}),(0,B.jsxs)(`div`,{className:`flex items-center gap-2`,children:[(0,B.jsxs)(`button`,{onClick:()=>{t(),globalThis.dispatchEvent(new CustomEvent(`start-magic-help-inspect`))},className:`flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-brand-500/10 border border-brand-500/20 text-brand-400 hover:bg-brand-500 hover:text-white transition-all text-[11px] font-medium`,title:a===`ar`?`فحص عناصر الصفحة`:`Inspect page elements`,type:`button`,children:[(0,B.jsx)(ce,{className:`w-3 h-3 text-brand-400`}),(0,B.jsx)(`span`,{children:a===`ar`?`الفحص الذكي`:`Magic Inspect`})]}),(0,B.jsx)(`button`,{onClick:t,className:`p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors`,type:`button`,children:(0,B.jsx)(j,{className:`w-4 h-4`})})]})]}),c?(0,B.jsx)(jr,{activeTopic:c,lang:a,navigate:i,onClose:t,closeTopic:h,openTopic:p,filteredTopics:g}):(0,B.jsx)(Nr,{helpViewMode:_,setHelpViewMode:v,lang:a,expandedNodes:y,toggleNode:e=>{b(t=>{let n=new Set(t);return n.has(e)?n.delete(e):n.add(e),n})},openTopic:p,categories:s,selectedCategory:u,setSelectedCategory:f,searchRef:o,searchQuery:l,setSearchQuery:d,filteredTopics:g})]})]}):null}var Lr=`etap-ai-onboarding-completed`;function Rr(){let[e,t]=(0,z.useState)(!1),[n,r]=(0,z.useState)(0),[i,a]=(0,z.useState)(!1),o=Pe(),s=Oe(),c=(0,z.useMemo)(()=>[{id:`welcome`,title:`Welcome to Ahmed etap Platform`,description:`Enterprise-grade autonomous engineering intelligence for power systems. This tour will guide you through the key features.`,icon:Ue,position:`bottom`},{id:`sidebar`,title:`Navigation Sidebar`,description:`Access all modules from the sidebar. It's organized into sections: main navigation, engineering, integration, and system tools. You can collapse it for more workspace.`,icon:T,target:`sidebar`,position:`right`},{id:`projects`,title:`Project Management`,description:`Create and manage power system projects. Each project stores your system configuration, study results, and reports in one place.`,icon:S,action:()=>o(`/projects`),position:`bottom`},{id:`studies`,title:`Engineering Studies`,description:`Run real engineering computations: Load Flow, Short Circuit, Arc Flash, Harmonic Analysis, and more. Select a study type and configure parameters.`,icon:Ue,action:()=>o(`/studies`),position:`bottom`},{id:`help`,title:`Smart Help`,description:`Press F1 anytime to open contextual help. When errors occur, the help system maps them to relevant troubleshooting guides.`,icon:qe,position:`bottom`},{id:`status`,title:`Backend Status`,description:`Monitor the connection to the engineering service. The status indicator in the sidebar shows real-time connectivity.`,icon:x,action:()=>o(`/diagnostics`),position:`bottom`},{id:`complete`,title:`You're All Set!`,description:`You're ready to start using Ahmed etap. Press Ctrl+K anytime to open the command palette for quick navigation.`,icon:Ge,position:`bottom`}],[o]);(0,z.useEffect)(()=>{if(s.pathname===`/login`||s.pathname===`/register`){t(!1);return}if(!localStorage.getItem(Lr)){let e=setTimeout(()=>t(!0),1e3);return()=>clearTimeout(e)}},[s.pathname]);let l=(0,z.useCallback)(()=>{localStorage.setItem(Lr,`true`),a(!0),setTimeout(()=>t(!1),300)},[]),u=l,d=(0,z.useCallback)(()=>{if(n<c.length-1){let e=c[n+1];e.action&&e.action(),r(n+1)}else l()},[n,c,l]),f=(0,z.useCallback)(()=>{n>0&&r(n-1)},[n]),p=(0,z.useCallback)(()=>{localStorage.removeItem(Lr),r(0),a(!1),t(!0)},[]);if((0,z.useEffect)(()=>{let e=globalThis;return e.__restartOnboarding=p,()=>{e.__restartOnboarding=void 0}},[p]),(0,z.useEffect)(()=>{if(!e)return;let t=e=>{e.key===`Escape`?(e.preventDefault(),u()):e.key===`Enter`?(e.preventDefault(),d()):e.key===`Backspace`&&n>0&&(e.preventDefault(),f())};return globalThis.addEventListener(`keydown`,t),()=>globalThis.removeEventListener(`keydown`,t)},[e,n,u,d,f]),!e)return null;let m=c[n],h=m.icon,g=n===c.length-1;return(0,B.jsxs)(`dialog`,{open:!0,className:`fixed inset-0 z-[200] flex items-center justify-center p-4 m-0 max-w-none max-h-none w-screen h-screen bg-transparent border-0 p-0`,"aria-labelledby":`onboarding-title`,children:[(0,B.jsx)(`button`,{type:`button`,className:`absolute inset-0 bg-black/80 backdrop-blur-md cursor-default border-0 p-0`,onClick:u,onKeyDown:e=>{(e.key===`Escape`||e.key===`Enter`)&&u()},"aria-label":`Skip onboarding`}),(0,B.jsxs)(`div`,{className:q(`relative z-[201] w-full max-w-[520px]`,`bg-[var(--bg-secondary)] border border-[var(--border-secondary)]`,`rounded-2xl overflow-hidden`,`shadow-[0_24px_80px_-12px_rgba(0,0,0,0.7)]`,`ring-1 ring-white/5`,`transition-all duration-300 ease-out`,i?`opacity-0 scale-95 translate-y-2`:`opacity-100 scale-100 translate-y-0`),children:[(0,B.jsx)(`div`,{className:q(`absolute top-0 left-0 right-0 h-[3px]`,g?`bg-gradient-to-r from-emerald-500 via-green-400 to-emerald-500`:`bg-gradient-to-r from-[var(--accent-primary)] via-cyan-400 to-[var(--accent-primary)]`),"aria-hidden":`true`}),(0,B.jsx)(`div`,{className:`absolute -top-20 -left-20 w-64 h-64 rounded-full opacity-20 blur-3xl pointer-events-none`,style:{background:g?`#22c55e`:`var(--accent-primary)`},"aria-hidden":`true`}),(0,B.jsxs)(`div`,{className:`relative flex items-center justify-between px-7 pt-6 pb-2`,children:[(0,B.jsx)(`div`,{className:`flex items-center gap-2.5`,children:(0,B.jsxs)(`span`,{className:q(`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wide uppercase`,g?`bg-green-500/15 text-green-400`:`bg-[var(--accent-glow)] text-[var(--accent-primary)]`),children:[(0,B.jsx)(`span`,{className:`w-1.5 h-1.5 rounded-full bg-current animate-pulse`}),`Step `,n+1,` / `,c.length]})}),(0,B.jsx)(`button`,{onClick:u,"aria-label":`Close tour`,className:`p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors`,type:`button`,children:(0,B.jsx)(j,{className:`w-4 h-4`})})]}),(0,B.jsx)(`div`,{className:`relative px-7 pb-1`,children:(0,B.jsx)(`div`,{className:`flex gap-1.5`,children:c.map((e,t)=>(0,B.jsx)(`div`,{className:q(`h-1 flex-1 rounded-full transition-all duration-500`,t<n&&`bg-[var(--accent-primary)]`,t===n&&(g?`bg-green-400`:`bg-[var(--accent-primary)]`),t>n&&`bg-[var(--border-primary)]`)},e.id))})}),(0,B.jsx)(`div`,{className:`relative px-7 pt-6 pb-5`,children:(0,B.jsxs)(`div`,{className:`flex items-start gap-5`,children:[(0,B.jsx)(`div`,{className:q(`shrink-0 w-16 h-16 rounded-2xl flex items-center justify-center`,`ring-1 ring-inset transition-colors`,g?`bg-green-500/10 text-green-400 ring-green-500/20`:`bg-[var(--accent-glow)] text-[var(--accent-primary)] ring-[var(--accent-primary)]/20`),children:(0,B.jsx)(h,{className:`w-8 h-8`,strokeWidth:1.75})}),(0,B.jsxs)(`div`,{className:`flex-1 min-w-0 pt-1`,children:[(0,B.jsx)(`h3`,{id:`onboarding-title`,className:`text-xl font-semibold text-[var(--text-primary)] leading-tight mb-2 tracking-tight`,children:m.title}),(0,B.jsx)(`p`,{className:`text-[13.5px] text-[var(--text-secondary)] leading-relaxed`,children:m.description})]})]})}),(0,B.jsxs)(`div`,{className:`relative flex items-center justify-between px-7 py-4 border-t border-[var(--border-primary)] bg-[var(--bg-tertiary)]/40`,children:[(0,B.jsx)(`button`,{onClick:u,className:`text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors px-2 py-1.5 -ml-2`,type:`button`,children:`Skip tour`}),(0,B.jsxs)(`div`,{className:`flex items-center gap-2`,children:[n>0&&(0,B.jsxs)(`button`,{onClick:f,className:`flex items-center gap-1 px-3.5 py-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] rounded-lg transition-colors`,type:`button`,children:[(0,B.jsx)(oe,{className:`w-3.5 h-3.5`,strokeWidth:2.5}),`Back`]}),(0,B.jsxs)(`button`,{onClick:d,className:q(`flex items-center gap-1.5 px-5 py-2 text-[13px] font-semibold rounded-lg transition-all`,`shadow-lg active:scale-95`,g?`bg-green-600 hover:bg-green-500 text-white shadow-green-900/30`:`bg-[var(--accent-primary)] hover:brightness-110 text-black shadow-cyan-900/30`),type:`button`,children:[g?`Get Started`:`Next`,g?(0,B.jsx)(Ge,{className:`w-4 h-4`,strokeWidth:2.5}):(0,B.jsx)(L,{className:`w-4 h-4`,strokeWidth:2.5})]})]})]}),(0,B.jsxs)(`div`,{className:`relative px-7 pb-3 -mt-1 text-[10px] text-[var(--text-muted)] text-center`,children:[`Press`,` `,(0,B.jsx)(`kbd`,{className:`px-1.5 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] font-mono text-[10px]`,children:`Esc`}),` `,`to skip ·`,` `,(0,B.jsx)(`kbd`,{className:`px-1.5 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] font-mono text-[10px]`,children:`↵`}),` `,`to continue`]})]})]})}var zr=(0,z.createContext)({notifications:[],backendReachable:!0,notify:()=>{},dismiss:()=>{},backendReachable:!0}),Br={success:Ge,error:he,warning:D,info:C},Vr={success:`bg-green-600/90 border-green-400/30`,error:`bg-red-600/90 border-red-400/30`,warning:`bg-amber-600/90 border-amber-400/30`,info:`bg-brand-600/90 border-brand-400/30`};function Hr(e={}){let t=nt();return{...t?{Authorization:`Bearer ${t}`}:{},...e}}function Ur(e){let t=e.notification_type?.toLowerCase()??``;return t.includes(`error`)||t.includes(`critical`)||e.priority===`critical`||e.priority===`high`?`error`:t.includes(`warning`)||t.includes(`alert`)||e.priority===`medium`?`warning`:t.includes(`success`)||t.includes(`info`)?`success`:`info`}function Wr(e){let t=R||``,n;n=t.startsWith(`http://`)||t.startsWith(`https://`)?t.replace(/^http/,`ws`):t.startsWith(`ws://`)||t.startsWith(`wss://`)?t:`${globalThis.location?.protocol===`https:`?`wss:`:`ws:`}//${globalThis.location?.host??``}${t}`;let r=n.includes(`?`)?`&`:`?`;return`${n}/ws/notifications${r}token=${encodeURIComponent(e)}`}function Gr({children:e}){let[t,r]=(0,z.useState)([]),[a,o]=(0,z.useState)(!0),s=(0,z.useRef)(new Set),c=(0,z.useRef)(null),l=(0,z.useRef)(1e3),u=(0,z.useRef)(!0),d=(0,z.useCallback)((e,t,n)=>{if(!u.current)return;let i=n??crypto.randomUUID();r(n=>n.some(n=>n.type===e&&n.message===t)?n:[...n,{id:i,type:e,message:t}]),setTimeout(()=>{u.current&&r(e=>e.filter(e=>e.id!==i))},5e3)},[]),f=(0,z.useCallback)((e,t)=>{let n=t.replace(/^(Error|Warning|Info|Success|خطأ|تحذير)\s*:\s*/i,``);d(e,n)},[d]),p=(0,z.useCallback)(e=>{r(t=>t.filter(t=>t.id!==e)),s.current.has(e)&&fetch(`${R}/api/v1/notifications/${encodeURIComponent(e)}/read`,{method:`PUT`,headers:Hr({"Content-Type":`application/json`})}).catch(e=>{console.warn(`Failed to mark notification as read:`,e)})},[]),m=(0,z.useCallback)(()=>{if(!u.current)return;let e=nt();if(!e)return;let t;try{t=new WebSocket(Wr(e))}catch(e){console.warn(`Failed to construct WebSocket:`,e),o(!1);return}c.current=t,t.onopen=()=>{u.current&&(o(!0),l.current=1e3)},t.onmessage=e=>{if(u.current)try{let t=JSON.parse(e.data);if(!t.id||!t.message||s.current.has(t.id))return;s.current.add(t.id);let n=Ur(t),r=t.title?`${t.title}: ${t.message}`:t.message;d(n,r,t.id)}catch{}},t.onerror=()=>{u.current&&o(!1)},t.onclose=()=>{if(!u.current)return;c.current=null;let e=Math.min(l.current,3e4);l.current=Math.min(l.current*2,3e4),setTimeout(()=>{u.current&&m()},e)}},[d]);(0,z.useEffect)(()=>(u.current=!0,nt()&&(fetch(`${R}/api/v1/notifications/?page=1&page_size=20&unread_only=true`,{headers:Hr()}).then(async e=>{if(!e.ok)throw Error(`HTTP ${e.status}`);let t=await e.json();if(u.current){for(let e of t.notifications??[]){if(s.current.has(e.id))continue;s.current.add(e.id);let t=Ur(e),n=e.title?`${e.title}: ${e.message}`:e.message;d(t,n,e.id)}o(!0)}}).catch(()=>{u.current&&o(!1)}),m()),()=>{u.current=!1,c.current&&=(c.current.close(),null)}),[m,d]);let h=(0,z.useMemo)(()=>({notifications:t,notify:f,dismiss:p,backendReachable:a}),[t,f,p,a]);return(0,B.jsxs)(zr.Provider,{value:h,children:[e,(0,B.jsxs)(`div`,{style:{position:`fixed`,bottom:`16px`,right:`16px`,zIndex:80,display:`flex`,flexDirection:`column`,gap:`8px`,width:`min(384px, calc(100vw - 32px))`,maxWidth:`384px`,pointerEvents:`none`},children:[!a&&(0,B.jsxs)(`button`,{type:`button`,className:`pointer-events-auto px-4 py-2.5 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 cursor-pointer border backdrop-blur-md bg-amber-600/90 border-amber-400/30 text-white`,onClick:()=>o(!0),title:`Click to dismiss — real-time push will retry automatically`,children:[(0,B.jsx)(ne,{className:`w-4 h-4 shrink-0`}),(0,B.jsx)(`span`,{className:`flex-1 text-left`,children:`Real-time notifications offline — retrying`}),(0,B.jsx)(j,{className:`w-3.5 h-3.5 text-white/60 hover:text-white transition-colors shrink-0`})]}),(0,B.jsx)(n,{mode:`popLayout`,children:t.map(e=>{let t=Br[e.type];return(0,B.jsxs)(i.div,{layout:!0,initial:{opacity:0,x:120,scale:.9},animate:{opacity:1,x:0,scale:1},exit:{opacity:0,x:120,scale:.9},transition:{type:`spring`,damping:20,stiffness:300},onClick:()=>p(e.id),role:`alert`,"aria-live":`assertive`,"aria-atomic":`true`,className:`pointer-events-auto px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-3 cursor-pointer border backdrop-blur-md ${Vr[e.type]}`,style:{minWidth:`280px`},children:[(0,B.jsx)(t,{className:`w-5 h-5 shrink-0 text-white`}),(0,B.jsx)(`span`,{className:`flex-1 text-white`,children:e.message}),(0,B.jsx)(j,{className:`w-4 h-4 text-white/60 hover:text-white transition-colors shrink-0`})]},e.id)})})]})]})}function Kr(){return(0,z.useContext)(zr)}Xe.use(Ze).use(Ae).init({resources:{en:{translation:{app:{name:`Ahmed etap`,fullName:`Ahmed etap Engineering Platform`,description:`Intelligent Electrical Engineering Platform`,version:`2.0.0`},sidebar:{dashboard:`Dashboard`,studies:`Studies`,gridEditor:`Grid Editor`,assistant:`AI Assistant`,projects:`Projects`,results:`Results`,reports:`Reports`,settings:`Settings`,administration:`Administration`,rbacAdmin:`RBAC Admin`,emailDashboard:`Email Dashboard`,emailDigest:`Email Digest`,agentsControlPanel:`Agents Control Panel`,aiPlayground:`AI/ML Playground`,diagnostics:`Diagnostics`,etapIntegration:`ETAP Integration`,gisIntegration:`GIS Integration`,scadaIntegration:`SCADA Connection`,digitalTwin:`Digital Twin`,assetManagement:`Asset Management`,equipment:`Equipment`,dataImport:`Data Import`,dataExport:`Data Export`,logs:`Logs`,codeGuard:`Code Guard`,cuaMonitor:`CUA Monitor`,dualControl:`Dual-Control`,darkMode:`Dark Mode`,lightMode:`Light Mode`,logout:`Logout`,collapse:`Collapse`,expand:`Expand`,engineering:`Engineering`,integration:`Integration`,system:`System`,studyVersions:`Study Versions`,emailOtp:`Email OTP`,magicLinks:`Magic Links`,mfa:`MFA`},navbar:{welcome:`Welcome`,searchPlaceholder:`Search studies, reports, settings...`,notifications:`Notifications`,noNotifications:`No new notifications`,markAllRead:`Mark all as read`},voiceInput:{start:`Start voice input`,stop:`Stop voice input`,listening:`Listening...`,speakNow:`Speak now`,notSupported:`Speech recognition is not supported in this browser. Please use Chrome or Edge.`,microphoneDenied:`Microphone access denied. Please allow microphone access to use voice typing.`,recognitionFailed:`Voice recognition failed`},dashboard:{title:`Dashboard`,welcomeMessage:`Welcome to Ahmed etap Platform`,subtitle:`Enterprise-grade autonomous engineering intelligence for power-system analysis`,quickActions:`Quick Actions`,recentStudies:`Recent Studies`,systemStatus:`System Status`,totalStudies:`Total Studies`,activeStudies:`Active Studies`,completedStudies:`Completed Studies`,systemHealth:`System Health`,online:`Online`,offline:`Offline`,checking:`Checking`,newStudy:`New Study`,viewAll:`View All`,runStudy:`Run Study`,agents:`AI Agents`,engineeringService:`Engineering Service`,studyCapabilities:`Study Capabilities`,configured:`Configured`,healthy:`Healthy`,latency:`Latency`,version:`Version`,uptime:`Uptime`},studies:{title:`Engineering Studies`,subtitle:`Select a study type to run real engineering computations powered by the Python engine.`,newStudy:`New Study`,searchPlaceholder:`Search studies...`,filterByType:`Filter by Type`,filterByStatus:`Filter by Status`,allTypes:`All Types`,allStatuses:`All Statuses`,noStudiesFound:`No studies found`,deleteConfirm:`Are you sure you want to delete this study?`,deleteSuccess:`Study deleted successfully`,runStudy:`Run Study`,standard:`Standard`,parameters:`Parameters`},studyRun:{title:`Run Study`,backToStudies:`Back to Studies`,dryRun:`Dry Run (validate only, no computation)`,runStudy:`Run Study`,validateStudy:`Validate Study`,running:`Running...`,studyResult:`Study Result`,completed:`Completed`,failed:`Failed`,dryRunCompleted:`Dry-run completed`},results:{title:`Results`,allResults:`All Results`,filterByStudy:`Filter by Study`,filterByType:`Filter by Type`,noResultsFound:`No results found`,export:`Export`,delete:`Delete`},reports:{title:`Reports`,generateReport:`Generate Report`,reportType:`Report Type`,dateRange:`Date Range`,generate:`Generate`,noReportsFound:`No reports found`},settings:{title:`Settings`,general:`General`,appearance:`Appearance`,language:`Language`,theme:`Theme`,api:`API`,baseUrl:`Base URL`,timeout:`Timeout`,notifications:`Notifications`,enableNotifications:`Enable Notifications`,save:`Save`,saved:`Saved successfully`,reset:`Reset`,import:`Import`,export:`Export`,authentication:`Authentication`,openaiProvider:`OpenAI Provider`,nvidiaProvider:`NVIDIA Provider`,fallbackProviders:`Fallback Providers`,engineeringService:`Engineering Service`,database:`Database`,observability:`Observability`,rateLimiting:`Rate Limiting & Circuit Breaker`,etapIntegration:`ETAP Integration`,vaultSecrets:`Vault & Secrets`,emailAlerts:`Email Alerts`,featureFlags:`Feature Flags`,performance:`Performance`},common:{loading:`Loading...`,error:`An error occurred`,retry:`Retry`,noData:`No data available`,confirm:`Confirm`,cancel:`Cancel`,yes:`Yes`,no:`No`,back:`Back`,next:`Next`,previous:`Previous`,close:`Close`,success:`Success`,failed:`Failed`,save:`Save`,delete:`Delete`,edit:`Edit`,create:`Create`,search:`Search`},studyTypes:{load_flow:`Load Flow`,short_circuit:`Short Circuit`,harmonic_analysis:`Harmonic Analysis`,opf:`Optimal Power Flow`,protection_coordination:`Protection Coordination`,arc_flash:`Arc Flash`,motor_starting:`Motor Starting`,transient_stability:`Transient Stability`},statuses:{pending:`Pending`,running:`Running`,completed:`Completed`,failed:`Failed`,cancelled:`Cancelled`},auth:{loginTitle:`Sign In`,loginSubtitle:`Secure access to the Power Systems Engineering Analysis Platform`,emailLabel:`Email or Username`,emailPlaceholder:`you@company.com or username`,passwordLabel:`Password`,passwordPlaceholder:`••••••••`,rememberMe:`Remember me on this device`,forgotPassword:`Forgot password?`,loginButton:`Sign In`,loggingIn:`Verifying and authenticating...`,noAccount:`Don't have an account?`,registerLink:`Create Engineer Account`,errorMissingFields:`Please enter email/username and password`,resetPasswordTitle:`Reset Password`,resetEmailPlaceholder:`your@email.com`,sendResetLink:`Send Reset Link`,sending:`Sending...`,backToLogin:`Back to Login`,cancel:`Cancel`,securityBadge:`Connection secured with JWT + bcrypt • SOC2 compliant audit logs`,secureLogin:`Secured with TLS 1.3`,registerTitle:`Create New Engineer Account`,registerSubtitle:`Start analyzing and designing electrical grids to international standards`,fullNameLabel:`Full Name`,fullNamePlaceholder:`Eng. Ahmed Elbaz`,confirmPasswordLabel:`Confirm Password`,confirmPasswordPlaceholder:`Re-type password`,passwordsMatch:`Passwords match`,createAccountButton:`Create Engineering Account`,creatingAccount:`Creating account and syncing...`,hasAccount:`Already have an account?`,loginLink:`Sign In`,errorPasswordsMismatch:`Passwords do not match`,errorPasswordLength:`Password must be at least 8 characters long`,errorRegisterFields:`Please fill in all required fields correctly`},adminPages:{common:{result:`Result`,success:`Success`,failed:`Failed`,verified:`Verified`,message:`Message`,error:`Error`,traceId:`Trace ID`,expiresIn:`Expires in`,retryAfter:`Retry after`,testToken:`Test token`,testCode:`Test code`,testMode:`test mode`,emailAddress:`Email address`,userId:`User ID`,username:`Username`,role:`Role`,accessToken:`Access token`,refreshToken:`Refresh token`,invalidated:`Invalidated`,user:`user`,unknownError:`unknown error`},magicLinks:{title:`Magic Links`,subtitle:`Passwordless authentication via one-time-use email links (public request/verify · admin-only invalidate)`,tabs:{request:`Request`,verify:`Verify`,invalidate:`Invalidate`},request:{cardTitle:`Request Magic Link`,cardSubtitle:`POST /request — public, always returns 200 (no enumeration)`,help:`If the email exists, a magic link will be sent. Always returns 200 to prevent user enumeration.`,submit:`Request Magic Link`,resultSubtitle:`Response from POST /request`,loading:`Sending magic link…`,emptyTitle:`No request yet`,emptyDescription:`Fill the email and submit to request a magic link.`,success:`Magic link requested for {{email}}{{note}}`,failed:`Request failed: {{error}}`},verify:{cardTitle:`Verify Magic Link`,cardSubtitle:`POST /verify — public, mints JWT on success`,tokenLabel:`Magic-link token`,tokenPlaceholder:`Paste the token from the magic-link URL (e.g. ?token=…)`,help:`Tokens are 32-byte URL-safe random strings, valid for 15 minutes, single-use.`,submit:`Verify Token`,resultSubtitle:`Response from POST /verify`,loading:`Verifying magic link…`,emptyTitle:`No verification yet`,emptyDescription:`Paste a token and submit to verify it.`,success:`Magic link verified for {{email}}.`,failed:`Verify failed: {{error}}`},invalidate:{cardTitle:`Invalidate Pending Links`,cardSubtitle:`POST /invalidate — requires JWT`,help:`Requires JWT. All unused (pending) magic links for this email will be invalidated. Used links are unaffected.`,submit:`Invalidate Pending Links`,resultSubtitle:`Response from POST /invalidate`,loading:`Invalidating…`,emptyTitle:`No invalidation yet`,emptyDescription:`Enter an email and submit to invalidate its pending links.`,success:`Invalidated {{count}} pending magic link(s) for {{email}}.`,failed:`Invalidate failed: {{error}}`}},mfa:{title:`MFA`,subtitle:`Multi-factor authentication — TOTP setup, verify, and backup code recovery (all endpoints require JWT)`,tabs:{setup:`Setup TOTP`,verifyTotp:`Verify TOTP`,verifyBackup:`Verify Backup`},common:{valid:`valid`,invalid:`invalid`},setup:{cardTitle:`Setup TOTP`,cardSubtitle:`POST /totp/setup — requires JWT, auto-enables MFA`,description:`Generates a new TOTP secret for your account and returns a QR code URI. Scan it with your authenticator app (Google Authenticator, Authy, 1Password, etc.). Backup codes are also generated server-side (stored hashed, not exposed in the response).`,warning:`This will overwrite any existing TOTP secret for your account. MFA is automatically enabled after setup (V-10 fix).`,submit:`Generate TOTP Secret`,resultSubtitle:`Response from POST /totp/setup`,loading:`Generating TOTP secret…`,emptyTitle:`No setup yet`,emptyDescription:`Click the button to generate a TOTP secret and QR code.`,success:`MFA setup complete — QR code generated. MFA auto-enabled on your account.`,failed:`Setup failed: {{error}}`,mfaEnabledBadge:`MFA enabled`,qrUri:`QR URI`,qrAriaLabel:`TOTP QR code — scan with your authenticator app to import the secret for {{account}}`,thisAccount:`this account`,scanHelp:`Scan with your authenticator app`,errors:`Errors`},verifyTotp:{cardTitle:`Verify TOTP Code`,cardSubtitle:`POST /totp/verify — requires JWT, brute-force protected`,codeLabel:`TOTP code`,help:`6-digit code from your authenticator app. Codes are valid for 30 seconds and can only be used once (V-12 replay protection). 5 failed attempts trigger a 15-minute lockout.`,submit:`Verify Code`,resultSubtitle:`Response from POST /totp/verify`,loading:`Verifying TOTP code…`,emptyTitle:`No verification yet`,emptyDescription:`Enter a code and submit to verify it.`,success:`TOTP code verified successfully.`,failed:`Verify failed: {{error}}`},verifyBackup:{cardTitle:`Verify Backup Code`,cardSubtitle:`POST /backup/verify — requires JWT, recovery flow`,codeLabel:`Backup recovery code`,help:`8-16 character backup code shown once during TOTP setup. Codes are SHA-256 hashed before comparison (V-9). Same brute-force lockout as TOTP applies.`,submit:`Verify Backup Code`,resultSubtitle:`Response from POST /backup/verify`,loading:`Verifying backup code…`,emptyTitle:`No verification yet`,emptyDescription:`Enter a backup code and submit to verify it.`,success:`Backup code verified successfully.`,failed:`Verify failed: {{error}}`}},emailOtp:{send:{success:`OTP sent to {{email}}{{note}}`,failed:`Send failed: {{error}}`},verify:{success:`OTP verified for {{email}}.`,failed:`Verify failed: {{error}}`},invalidate:{success:`OTP invalidated for {{email}} ({{purpose}}).`,failed:`Invalidate failed: {{error}}`}},emailDigest:{generate:{success:`Digest generated for {{email}} ({{period}}).`,failed:`Generate failed: {{error}}`},scheduleRun:{success:`Schedule run complete: {{sent}} sent, {{failed}} failed.`,failed:`Schedule run failed: {{error}}`},config:{loadFailed:`Failed to load config: {{error}}`},preview:{loadFailed:`Failed to load preview: {{error}}`}}}}},ar:{translation:{app:{name:`Ahmed etap`,fullName:`منصة Ahmed etap الهندسية`,description:`منصة الهندسة الكهربائية الذكية`,version:`2.0.0`},sidebar:{dashboard:`لوحة التحكم`,studies:`الدراسات`,gridEditor:`محرر الشبكة`,assistant:`مساعد الذكاء الاصطناعي`,projects:`المشاريع`,results:`النتائج`,reports:`التقارير`,settings:`الإعدادات`,administration:`الإدارة`,rbacAdmin:`إدارة الصلاحيات`,emailDashboard:`لوحة البريد`,emailDigest:`ملخص البريد`,agentsControlPanel:`لوحة العملاء الأذكياء`,aiPlayground:`ساحة الذكاء الاصطناعي`,diagnostics:`التشخيصات`,etapIntegration:`تكامل ETAP`,gisIntegration:`تكامل GIS`,scadaIntegration:`اتصال إسكادا (زينون)`,digitalTwin:`التوأم الرقمي`,assetManagement:`إدارة الأصول`,equipment:`المعدات`,dataImport:`استيراد البيانات`,dataExport:`تصدير البيانات`,logs:`السجلات`,codeGuard:`حارس الكود`,cuaMonitor:`مراقب CUA`,dualControl:`التحكم المزدوج`,darkMode:`الوضع الداكن`,lightMode:`الوضع الفاتح`,logout:`تسجيل الخروج`,collapse:`طي`,expand:`توسيع`,engineering:`الهندسة`,integration:`التكامل`,system:`النظام`,studyVersions:`إصدارات الدراسة`,emailOtp:`OTP البريد`,magicLinks:`الروابط السحرية`,mfa:`المصادقة الثنائية`},navbar:{welcome:`مرحباً`,searchPlaceholder:`بحث دراسات، تقارير، إعدادات...`,notifications:`الإشعارات`,noNotifications:`لا توجد إشعارات جديدة`,markAllRead:`تحديد الكل كمقروء`},voiceInput:{start:`بدء الإدخال الصوتي`,stop:`إيقاف الإدخال الصوتي`,listening:`جاري الاستماع...`,speakNow:`تحدث الآن`,notSupported:`التعرف على الصوت غير مدعوم في هذا المتصفح. يرجى استخدام Chrome أو Edge.`,microphoneDenied:`تم رفض الوصول إلى الميكروفون. يرجى السماح بالوصول لاستخدام الكتابة بالصوت.`,recognitionFailed:`فشل التعرف على الصوت`},dashboard:{title:`لوحة التحكم`,welcomeMessage:`مرحباً بك في منصة Ahmed etap`,subtitle:`نظام هندسي ذكي بمستوى المؤسسات لتحليل أنظمة الطاقة`,quickActions:`إجراءات سريعة`,recentStudies:`الدراسات الأخيرة`,systemStatus:`حالة النظام`,totalStudies:`إجمالي الدراسات`,activeStudies:`دراسات نشطة`,completedStudies:`دراسات مكتملة`,systemHealth:`حالة النظام`,online:`متصل`,offline:`غير متصل`,checking:`جاري الفحص`,newStudy:`دراسة جديدة`,viewAll:`عرض الكل`,runStudy:`تشغيل الدراسة`,agents:`وكلاء الذكاء الاصطناعي`,engineeringService:`خدمة الهندسة`,studyCapabilities:`قدرات الدراسة`,configured:`مُكوّن`,healthy:`سليم`,latency:`زمن الاستجابة`,version:`الإصدار`,uptime:`وقت التشغيل`},studies:{title:`الدراسات الهندسية`,subtitle:`اختر نوع الدراسة لتشغيل حسابات هندسية حقيقية باستخدام محرك Python.`,newStudy:`دراسة جديدة`,searchPlaceholder:`بحث عن دراسة...`,filterByType:`تصفية حسب النوع`,filterByStatus:`تصفية حسب الحالة`,allTypes:`جميع الأنواع`,allStatuses:`جميع الحالات`,noStudiesFound:`لم يتم العثور على دراسات`,deleteConfirm:`هل أنت متأكد من حذف هذه الدراسة؟`,deleteSuccess:`تم حذف الدراسة بنجاح`,runStudy:`تشغيل الدراسة`,standard:`المعيار`,parameters:`المعلمات`},studyRun:{title:`تشغيل الدراسة`,backToStudies:`العودة إلى الدراسات`,dryRun:`تشغيل تجريبي (تحقق فقط، بدون حساب)`,runStudy:`تشغيل الدراسة`,validateStudy:`التحقق من الدراسة`,running:`جاري التنفيذ...`,studyResult:`نتيجة الدراسة`,completed:`مكتمل`,failed:`فشل`,dryRunCompleted:`اكتمل التشغيل التجريبي`},results:{title:`النتائج`,allResults:`جميع النتائج`,filterByStudy:`تصفية حسب الدراسة`,filterByType:`تصفية حسب النوع`,noResultsFound:`لم يتم العثور على نتائج`,export:`تصدير`,delete:`حذف`},reports:{title:`التقارير`,generateReport:`إنشاء تقرير`,reportType:`نوع التقرير`,dateRange:`نطاق التاريخ`,generate:`إنشاء`,noReportsFound:`لم يتم العثور على تقارير`},settings:{title:`الإعدادات`,general:`عام`,appearance:`المظهر`,language:`اللغة`,theme:`السمة`,api:`API`,baseUrl:`عنوان API`,timeout:`وقت الانتظار`,notifications:`الإشعارات`,enableNotifications:`تمكين الإشعارات`,save:`حفظ`,saved:`تم الحفظ بنجاح`,reset:`إعادة تعيين`,import:`استيراد`,export:`تصدير`,authentication:`المصادقة`,openaiProvider:`مزود OpenAI`,nvidiaProvider:`مزود NVIDIA`,fallbackProviders:`مزودون احتياطيون`,engineeringService:`خدمة الهندسة`,database:`قاعدة البيانات`,observability:`المراقبة`,rateLimiting:`الحد من الطلبات وقاطع الدائرة`,etapIntegration:`تكامل ETAP`,vaultSecrets:`Vault والأسرار`,emailAlerts:`تنبيهات البريد`,featureFlags:`علامات الميزات`,performance:`الأداء`},common:{loading:`جاري التحميل...`,error:`حدث خطأ`,retry:`إعادة المحاولة`,noData:`لا توجد بيانات`,confirm:`تأكيد`,cancel:`إلغاء`,yes:`نعم`,no:`لا`,back:`رجوع`,next:`التالي`,previous:`السابق`,close:`إغلاق`,success:`نجح`,failed:`فشل`,save:`حفظ`,delete:`حذف`,edit:`تعديل`,create:`إنشاء`,search:`بحث`},studyTypes:{load_flow:`تدفق الأحمال`,short_circuit:`الدوائر القصيرة`,harmonic_analysis:`تحليل التوافقيات`,opf:`تدفق الطاقة الأمثل`,protection_coordination:`تنسيق الحماية`,arc_flash:`وميض القوس`,motor_starting:`بدء المحركات`,transient_stability:`استقرار عابر`},statuses:{pending:`في الانتظار`,running:`جاري التنفيذ`,completed:`مكتمل`,failed:`فشل`,cancelled:`ملغى`},auth:{loginTitle:`تسجيل الدخول`,loginSubtitle:`الوصول الآمن لمنصة تحليل هندسة النظم الكهربائية`,emailLabel:`البريد الإلكتروني أو اسم المستخدم`,emailPlaceholder:`you@company.com أو اسم المستخدم`,passwordLabel:`كلمة المرور`,passwordPlaceholder:`••••••••`,rememberMe:`تذكر تسجيل الدخول على هذا الجهاز`,forgotPassword:`نسيت كلمة المرور؟`,loginButton:`دخول`,loggingIn:`جاري التحقق والمصادقة...`,noAccount:`لا تملك حساباً؟`,registerLink:`إنشاء حساب مهندس`,errorMissingFields:`يرجى إدخال البريد الإلكتروني/اسم المستخدم وكلمة المرور`,resetPasswordTitle:`إعادة تعيين كلمة المرور`,resetEmailPlaceholder:`your@email.com`,sendResetLink:`إرسال رابط إعادة التعيين`,sending:`جاري الإرسال...`,backToLogin:`العودة لصفحة الدخول`,cancel:`إلغاء`,securityBadge:`اتصال مؤمن بتشفير JWT + bcrypt • سجلات تدقيق متوافقة مع SOC2`,secureLogin:`مؤمن بـ TLS 1.3`,registerTitle:`إنشاء حساب مهندس جديد`,registerSubtitle:`ابدأ تحليل وتصميم الشبكات الكهربائية وفقاً للمعايير الدولية`,fullNameLabel:`الاسم الكامل`,fullNamePlaceholder:`المهندس أحمد الباز`,confirmPasswordLabel:`تأكيد كلمة المرور`,confirmPasswordPlaceholder:`أعد كتابة كلمة المرور`,passwordsMatch:`كلمتا المرور متطابقتان`,createAccountButton:`إنشاء الحساب الهندسـي`,creatingAccount:`جاري إنشاء الحساب والمزامنة...`,hasAccount:`لديك حساب بالفعل؟`,loginLink:`تسجيل الدخول`,errorPasswordsMismatch:`كلمتا المرور غير متطابقتين`,errorPasswordLength:`يجب أن لا تقل كلمة المرور عن 8 خانات`,errorRegisterFields:`يرجى تعبئة جميع الحقول المطلوبة بشكل صحيح`},adminPages:{common:{result:`النتيجة`,success:`نجاح`,failed:`فشل`,verified:`تم التحقق`,message:`الرسالة`,error:`الخطأ`,traceId:`معرف التتبع`,expiresIn:`تنتهي خلال`,retryAfter:`أعد المحاولة بعد`,testToken:`رمز اختبار`,testCode:`رمز اختبار`,testMode:`وضع اختبار`,emailAddress:`البريد الإلكتروني`,userId:`معرف المستخدم`,username:`اسم المستخدم`,role:`الدور`,accessToken:`رمز الوصول`,refreshToken:`رمز التحديث`,invalidated:`تم الإلغاء`,user:`مستخدم`,unknownError:`خطأ غير معروف`},magicLinks:{title:`الروابط السحرية`,subtitle:`مصادقة بدون كلمة مرور عبر روابط بريد إلكتروني أحادية الاستخدام (طلب/تحقق عام · إلغاء للمشرفين فقط)`,tabs:{request:`طلب`,verify:`تحقق`,invalidate:`إلغاء`},request:{cardTitle:`طلب رابط سحري`,cardSubtitle:`POST /request — عام، يُرجع 200 دائماً (منع التعداد)`,help:`إذا كان البريد موجوداً، سيُرسل رابط سحري. يُرجع 200 دائماً لمنع تعداد المستخدمين.`,submit:`طلب رابط سحري`,resultSubtitle:`استجابة من POST /request`,loading:`جاري إرسال الرابط السحري…`,emptyTitle:`لا يوجد طلب بعد`,emptyDescription:`املأ البريد وأرسل لطلب رابط سحري.`,success:`تم طلب رابط سحري لـ {{email}}{{note}}`,failed:`فشل الطلب: {{error}}`},verify:{cardTitle:`تحقق من الرابط السحري`,cardSubtitle:`POST /verify — عام، يُصدر JWT عند النجاح`,tokenLabel:`رمز الرابط السحري`,tokenPlaceholder:`الصق الرمز من عنوان URL للرابط السحري (مثل ?token=…)`,help:`الرموز سلاسل عشوائية آمنة للـ URL بطول 32 بايت، صالحة لمدة 15 دقيقة، للاستخدام مرة واحدة.`,submit:`تحقق من الرمز`,resultSubtitle:`استجابة من POST /verify`,loading:`جاري التحقق من الرابط السحري…`,emptyTitle:`لا يوجد تحقق بعد`,emptyDescription:`الصق رمزاً وأرسل للتحقق منه.`,success:`تم التحقق من الرابط السحري لـ {{email}}.`,failed:`فشل التحقق: {{error}}`},invalidate:{cardTitle:`إلغاء الروابط المعلّقة`,cardSubtitle:`POST /invalidate — يتطلب JWT`,help:`يتطلب JWT. جميع الروابط السحرية غير المستخدمة (المعلّقة) لهذا البريد سيتم إلغاؤها. الروابط المستخدمة غير متأثرة.`,submit:`إلغاء الروابط المعلّقة`,resultSubtitle:`استجابة من POST /invalidate`,loading:`جاري الإلغاء…`,emptyTitle:`لا يوجد إلغاء بعد`,emptyDescription:`أدخل بريداً وأرسل لإلغاء روابطه المعلّقة.`,success:`تم إلغاء {{count}} رابط سحري معلّق لـ {{email}}.`,failed:`فشل الإلغاء: {{error}}`}},mfa:{title:`المصادقة الثنائية`,subtitle:`مصادقة متعددة العوامل — إعداد TOTP، تحقق، واستعادة رمز النسخ الاحتياطي (جميع النقاط تتطلب JWT)`,tabs:{setup:`إعداد TOTP`,verifyTotp:`تحقق TOTP`,verifyBackup:`تحقق النسخ الاحتياطي`},common:{valid:`صالح`,invalid:`غير صالح`},setup:{cardTitle:`إعداد TOTP`,cardSubtitle:`POST /totp/setup — يتطلب JWT، يُفعّل MFA تلقائياً`,description:`يُنشئ سرّ TOTP جديد لحسابك ويُرجع URI لرمز QR. امسحه بتطبيق المصادقة الخاص بك (Google Authenticator، Authy، 1Password، إلخ). تُنشأ رموز النسخ الاحتياطي أيضاً من جهة الخادم (مخزّنة مجزّأة، غير مكشوفة في الاستجابة).`,warning:`سيؤدي هذا إلى استبدال أي سرّ TOTP موجود لحسابك. يتم تفعيل MFA تلقائياً بعد الإعداد (إصلاح V-10).`,submit:`توليد سرّ TOTP`,resultSubtitle:`استجابة من POST /totp/setup`,loading:`جاري توليد سرّ TOTP…`,emptyTitle:`لا يوجد إعداد بعد`,emptyDescription:`انقر الزر لتوليد سرّ TOTP ورمز QR.`,success:`اكتمل إعداد MFA — تم توليد رمز QR. تم تفعيل MFA تلقائياً على حسابك.`,failed:`فشل الإعداد: {{error}}`,mfaEnabledBadge:`MFA مُفعّل`,qrUri:`URI رمز QR`,qrAriaLabel:`رمز QR لـ TOTP — امسحه بتطبيق المصادقة لاستيراد السرّ لـ {{account}}`,thisAccount:`هذا الحساب`,scanHelp:`امسحه بتطبيق المصادقة الخاص بك`,errors:`الأخطاء`},verifyTotp:{cardTitle:`تحقق من رمز TOTP`,cardSubtitle:`POST /totp/verify — يتطلب JWT، محمي من الهجوم العنيف`,codeLabel:`رمز TOTP`,help:`رمز من 6 أرقام من تطبيق المصادقة الخاص بك. الرموز صالحة لمدة 30 ثانية ويمكن استخدامها مرة واحدة فقط (حماية V-12 من إعادة التشغيل). 5 محاولات فاشلة تُفعّل قفل 15 دقيقة.`,submit:`تحقق من الرمز`,resultSubtitle:`استجابة من POST /totp/verify`,loading:`جاري التحقق من رمز TOTP…`,emptyTitle:`لا يوجد تحقق بعد`,emptyDescription:`أدخل رمزاً وأرسل للتحقق منه.`,success:`تم التحقق من رمز TOTP بنجاح.`,failed:`فشل التحقق: {{error}}`},verifyBackup:{cardTitle:`تحقق من رمز النسخ الاحتياطي`,cardSubtitle:`POST /backup/verify — يتطلب JWT، تدفق الاستعادة`,codeLabel:`رمز الاستعادة الاحتياطي`,help:`رمز نسخ احتياطي من 8-16 حرف يُعرض مرة واحدة أثناء إعداد TOTP. تُجزّأ الرموز بـ SHA-256 قبل المقارنة (V-9). نفس قفل الهجوم العنيف كـ TOTP ينطبق.`,submit:`تحقق من رمز النسخ الاحتياطي`,resultSubtitle:`استجابة من POST /backup/verify`,loading:`جاري التحقق من رمز النسخ الاحتياطي…`,emptyTitle:`لا يوجد تحقق بعد`,emptyDescription:`أدخل رمز نسخ احتياطي وأرسل للتحقق منه.`,success:`تم التحقق من رمز النسخ الاحتياطي بنجاح.`,failed:`فشل التحقق: {{error}}`}},emailOtp:{send:{success:`تم إرسال OTP إلى {{email}}{{note}}`,failed:`فشل الإرسال: {{error}}`},verify:{success:`تم التحقق من OTP لـ {{email}}.`,failed:`فشل التحقق: {{error}}`},invalidate:{success:`تم إلغاء OTP لـ {{email}} ({{purpose}}).`,failed:`فشل الإلغاء: {{error}}`}},emailDigest:{generate:{success:`تم توليد الملخص لـ {{email}} ({{period}}).`,failed:`فشل التوليد: {{error}}`},scheduleRun:{success:`اكتمل تشغيل الجدولة: تم إرسال {{sent}}، فشل {{failed}}.`,failed:`فشل تشغيل الجدولة: {{error}}`},config:{loadFailed:`فشل تحميل التكوين: {{error}}`},preview:{loadFailed:`فشل تحميل المعاينة: {{error}}`}}}}}},fallbackLng:`en`,detection:{order:[`localStorage`,`navigator`],caches:[`localStorage`]},interpolation:{escapeValue:!1}});var qr=()=>(0,B.jsx)(`div`,{className:`flex items-center justify-center h-64`,children:(0,B.jsxs)(`div`,{className:`flex flex-col items-center gap-3`,children:[(0,B.jsx)(`div`,{className:`w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin`}),(0,B.jsx)(`span`,{className:`text-sm text-[var(--text-muted)]`,children:`Loading...`})]})});function $(e){let t=(0,z.lazy)(e);return function(e){return(0,B.jsx)(z.Suspense,{fallback:(0,B.jsx)(qr,{}),children:(0,B.jsx)(t,{...e})})}}var Jr=$(()=>N(()=>import(`./Dashboard-CvYfdE1t.js`),__vite__mapDeps([0,1,2,3,4,5,6,7]))),Yr=$(()=>N(()=>import(`./Studies-CLBl7QZ1.js`),__vite__mapDeps([8,1,2,3,4,5,6,7]))),Xr=$(()=>N(()=>import(`./GridEditor-BsDDvvZ6.js`),__vite__mapDeps([9,1,2,3,4,10,5]))),Zr=$(()=>N(()=>import(`./StudyRun-BtZgWjyK.js`),__vite__mapDeps([11,1,2,3,4,5,6,7]))),Qr=$(()=>N(()=>import(`./AssetManagement-Ce8DTCVA.js`),__vite__mapDeps([12,1,2,3,4,10,5,6,13]))),$r=$(()=>N(()=>import(`./AIAssistant-cYyrnaXf.js`),__vite__mapDeps([14,1,2,3,4,15,10,5,6]))),ei=$(()=>N(()=>import(`./Projects-CB3dFVri.js`),__vite__mapDeps([16,1,2,3,4,5,6,13]))),ti=$(()=>N(()=>import(`./VisionKeys-CCblJxQd.js`),__vite__mapDeps([17,1,2,3,4,5]))),ni=$(()=>N(()=>import(`./GuardReview-2gxT_k0v.js`),__vite__mapDeps([18,1,2,3,4,5]))),ri=$(()=>N(()=>import(`./AgentMetrics-CIgT7LLr.js`),__vite__mapDeps([19,1,2,3,4,5]))),ii=$(()=>N(()=>import(`./AuditLogs-CTfoD7fN.js`),__vite__mapDeps([20,1,2,3,4,5]))),ai=$(()=>N(()=>import(`./EtapIntegration-CoZbO5Nv.js`),__vite__mapDeps([21,2,1,3,4,5,6]))),oi=$(()=>N(()=>import(`./GisIntegration-DCaQY6Pi.js`),__vite__mapDeps([22,2,1,3,4,5,6]))),si=$(()=>N(()=>import(`./ScadaIntegration-nIdDyoYv.js`),__vite__mapDeps([23,1,2,3,4,10,5]))),ci=$(()=>N(()=>import(`./Reports-Db1YWUsO.js`),__vite__mapDeps([24,1,2,3,4,10,5,6]))),li=$(()=>N(()=>import(`./Settings-CWTlEd1V.js`),__vite__mapDeps([15,1,2,3,4,10,5,6]))),ui=$(()=>N(()=>import(`./Administration-A-2Z-YPt.js`),__vite__mapDeps([25,1,2,3,4,5,6]))),di=$(()=>N(()=>import(`./Diagnostics-Dtj-y2Ud.js`),__vite__mapDeps([26,1,2,3,4,5,6]))),fi=$(()=>N(()=>import(`./DigitalTwin-B0pAU2c9.js`),__vite__mapDeps([27,1,2,3,4,10,5,6]))),pi=$(()=>N(()=>import(`./DataImport-JVu88pMJ.js`),__vite__mapDeps([28,1,2,3,4,10,5,6]))),mi=$(()=>N(()=>import(`./DataExport-Bxm7t7bG.js`),__vite__mapDeps([29,1,2,3,4,10,5,6]))),hi=$(()=>N(()=>import(`./Logs-DvJSwUuT.js`),__vite__mapDeps([30,1,2,3,4,5,6]))),gi=$(()=>N(()=>import(`./CuaMonitor-DzJU_xGJ.js`),__vite__mapDeps([31,1,2,3,4,10,5]))),_i=$(()=>N(()=>import(`./CodeGuard-CMCru6eG.js`),__vite__mapDeps([32,1,2,3,4,5,6]))),vi=$(()=>N(()=>import(`./ContextEngine-D27Jra0r.js`),__vite__mapDeps([33,1,2,3,4,10,5,6]))),yi=$(()=>N(()=>import(`./Templates-BmeDxf7u.js`),__vite__mapDeps([34,1,2,3,4,10,5,6]))),bi=$(()=>N(()=>import(`./AssetLibrary-C3P96iZz.js`),__vite__mapDeps([35,1,2,3,4,10,5,6]))),xi=$(()=>N(()=>import(`./RbacAdmin-DlhiZrde.js`),__vite__mapDeps([36,1,2,3,4,10,5]))),Si=$(()=>N(()=>import(`./EquipmentManagement-hNIrWPAW.js`),__vite__mapDeps([37,1,2,3,4,10,5]))),Ci=$(()=>N(()=>import(`./EmailDashboard-neDe4qX7.js`),__vite__mapDeps([38,1,2,3,4,10,5]))),wi=$(()=>N(()=>import(`./EmailWebhooks-3PWPxbiS.js`),__vite__mapDeps([39,1,2,3,4,5]))),Ti=$(()=>N(()=>import(`./EmailDigest-D1lwkBdO.js`),__vite__mapDeps([40,1,2,3,4,5,41,10]))),Ei=$(()=>N(()=>import(`./StudyVersions-CgHzCj1o.js`),__vite__mapDeps([42,1,2,3,4,10,5]))),Di=$(()=>N(()=>import(`./EmailOtp-CHbe4FhA.js`),__vite__mapDeps([43,1,2,3,4,5,41,10]))),Oi=$(()=>N(()=>import(`./AIPlayground-BmuUCAVw.js`),__vite__mapDeps([44,1,2,3,4,5,6]))),ki=$(()=>N(()=>import(`./MagicLinks-3zBGme3S.js`),__vite__mapDeps([45,1,2,3,4,5,41,10]))),Ai=$(()=>N(()=>import(`./Mfa-BX33TrtN.js`),__vite__mapDeps([46,1,2,3,4,5,41,10]))),ji=$(()=>N(()=>import(`./AgentsControlPanel-OzfJIBKU.js`),__vite__mapDeps([47,1,2,3,4,10,5]))),Mi=$(()=>N(()=>import(`./Login-DFAAq8CE.js`),__vite__mapDeps([48,1,2,3,4,10]))),Ni=$(()=>N(()=>import(`./Register-DscMU31y.js`),__vite__mapDeps([49,1,2,3,4])));function Pi(){return ar(),null}function Fi(){let{i18n:e}=P(),{lastError:t,setLastError:n}=ot(),[r,i]=(0,z.useState)(!1),[a,o]=(0,z.useState)(),[s,c]=(0,z.useState)(!1);return(0,z.useEffect)(()=>{document.documentElement.dir=e.language===`ar`?`rtl`:`ltr`,document.documentElement.lang=e.language},[e.language]),(0,z.useEffect)(()=>{window.electronAPI&&window.electronAPI.onNavigate(e=>{window.location.hash=e})},[]),(0,z.useEffect)(()=>{let e=e=>{e.key===`F1`&&(e.preventDefault(),i(e=>!e),o(void 0)),(e.ctrlKey||e.metaKey)&&e.key===`h`&&(e.preventDefault(),i(e=>!e),o(void 0))};return globalThis.addEventListener(`keydown`,e),()=>globalThis.removeEventListener(`keydown`,e)},[]),(0,z.useEffect)(()=>{let e=()=>c(e=>!e);return globalThis.addEventListener(`toggle-shortcuts-panel`,e),()=>globalThis.removeEventListener(`toggle-shortcuts-panel`,e)},[]),(0,z.useEffect)(()=>{let e=()=>{let e=document.documentElement.classList.contains(`dark`)?`dark`:`light`,t=e===`dark`?`light`:`dark`;document.documentElement.classList.remove(e),document.documentElement.classList.add(t),localStorage.setItem(`etap-theme`,t)};return globalThis.addEventListener(`toggle-theme`,e),()=>globalThis.removeEventListener(`toggle-theme`,e)},[]),(0,z.useEffect)(()=>{let t=()=>{let t=e.language===`ar`?`en`:`ar`;e.changeLanguage(t),document.documentElement.dir=t===`ar`?`rtl`:`ltr`,document.documentElement.lang=t};return globalThis.addEventListener(`toggle-language`,t),()=>globalThis.removeEventListener(`toggle-language`,t)},[e]),(0,z.useEffect)(()=>{let e=e=>{let t=e;t.detail?.contextId&&(o(t.detail.contextId),i(!0))};return globalThis.addEventListener(`open-smart-help`,e),()=>globalThis.removeEventListener(`open-smart-help`,e)},[]),(0,z.useEffect)(()=>{let e=()=>{i(e=>!e),o(void 0)};return globalThis.addEventListener(`toggle-smart-help`,e),()=>globalThis.removeEventListener(`toggle-smart-help`,e)},[]),(0,B.jsx)(on,{children:(0,B.jsx)(Gr,{children:(0,B.jsxs)(Jn,{children:[(0,B.jsxs)(Ne,{children:[(0,B.jsxs)(Be,{children:[(0,B.jsx)(F,{path:`/login`,element:(0,B.jsx)(Mi,{})}),(0,B.jsx)(F,{path:`/register`,element:(0,B.jsx)(Ni,{})}),(0,B.jsxs)(F,{element:(0,B.jsx)(Yn,{children:(0,B.jsx)(Bn,{})}),children:[(0,B.jsx)(F,{path:`/`,element:(0,B.jsx)(k,{to:`/dashboard`,replace:!0})}),(0,B.jsx)(F,{path:`/dashboard`,element:(0,B.jsx)(Jr,{})}),(0,B.jsx)(F,{path:`/studies`,element:(0,B.jsx)(Yr,{})}),(0,B.jsx)(F,{path:`/grid-editor`,element:(0,B.jsx)(Xr,{})}),(0,B.jsx)(F,{path:`/studies/:studyType`,element:(0,B.jsx)(Zr,{})}),(0,B.jsx)(F,{path:`/asset-management`,element:(0,B.jsx)(Qr,{})}),(0,B.jsx)(F,{path:`/assistant`,element:(0,B.jsx)($r,{})}),(0,B.jsx)(F,{path:`/projects`,element:(0,B.jsx)(ei,{})}),(0,B.jsx)(F,{path:`/vision-keys`,element:(0,B.jsx)(ti,{})}),(0,B.jsx)(F,{path:`/guard-review`,element:(0,B.jsx)(ni,{})}),(0,B.jsx)(F,{path:`/agent-metrics`,element:(0,B.jsx)(ri,{})}),(0,B.jsx)(F,{path:`/audit-logs`,element:(0,B.jsx)(ii,{})}),(0,B.jsx)(F,{path:`/etap`,element:(0,B.jsx)(ai,{})}),(0,B.jsx)(F,{path:`/gis`,element:(0,B.jsx)(oi,{})}),(0,B.jsx)(F,{path:`/scada`,element:(0,B.jsx)(si,{})}),(0,B.jsx)(F,{path:`/reports`,element:(0,B.jsx)(ci,{})}),(0,B.jsx)(F,{path:`/settings`,element:(0,B.jsx)(li,{})}),(0,B.jsx)(F,{path:`/admin`,element:(0,B.jsx)(ui,{})}),(0,B.jsx)(F,{path:`/diagnostics`,element:(0,B.jsx)(di,{})}),(0,B.jsx)(F,{path:`/digital-twin`,element:(0,B.jsx)(fi,{})}),(0,B.jsx)(F,{path:`/data-import`,element:(0,B.jsx)(pi,{})}),(0,B.jsx)(F,{path:`/data-export`,element:(0,B.jsx)(mi,{})}),(0,B.jsx)(F,{path:`/logs`,element:(0,B.jsx)(hi,{})}),(0,B.jsx)(F,{path:`/code-guard`,element:(0,B.jsx)(_i,{})}),(0,B.jsx)(F,{path:`/context-engine`,element:(0,B.jsx)(vi,{})}),(0,B.jsx)(F,{path:`/templates`,element:(0,B.jsx)(yi,{})}),(0,B.jsx)(F,{path:`/asset-library`,element:(0,B.jsx)(bi,{})}),(0,B.jsx)(F,{path:`/admin/cua-monitor`,element:(0,B.jsx)(gi,{})}),(0,B.jsx)(F,{path:`/admin/rbac`,element:(0,B.jsx)(xi,{})}),(0,B.jsx)(F,{path:`/admin/email-dashboard`,element:(0,B.jsx)(Ci,{})}),(0,B.jsx)(F,{path:`/admin/email-digest`,element:(0,B.jsx)(Ti,{})}),(0,B.jsx)(F,{path:`/admin/study-versions`,element:(0,B.jsx)(Ei,{})}),(0,B.jsx)(F,{path:`/admin/email-otp`,element:(0,B.jsx)(Di,{})}),(0,B.jsx)(F,{path:`/admin/magic-links`,element:(0,B.jsx)(ki,{})}),(0,B.jsx)(F,{path:`/admin/mfa`,element:(0,B.jsx)(Ai,{})}),(0,B.jsx)(F,{path:`/admin/agents`,element:(0,B.jsx)(ji,{})}),(0,B.jsx)(F,{path:`/admin/ai-playground`,element:(0,B.jsx)(Oi,{})}),(0,B.jsx)(F,{path:`/equipment`,element:(0,B.jsx)(Si,{})}),(0,B.jsx)(F,{path:`/admin/email/webhooks`,element:(0,B.jsx)(wi,{})}),(0,B.jsx)(F,{path:`/admin/email-digest`,element:(0,B.jsx)(Ti,{})}),(0,B.jsx)(F,{path:`*`,element:(0,B.jsx)(k,{to:`/dashboard`,replace:!0})})]})]}),(0,B.jsx)(Pi,{}),(0,B.jsx)(er,{}),(0,B.jsx)(Rr,{}),(0,B.jsx)(Ir,{open:r,onClose:()=>{i(!1),o(void 0)},initialContextId:a}),(0,B.jsx)(ur,{open:s,onClose:()=>c(!1)}),(0,B.jsx)(Cr,{})]}),(0,B.jsx)(fr,{error:t,onDismiss:()=>n(null),onRetry:()=>globalThis.location.reload()})]})})})}var Ii=class extends z.Component{state={hasError:!1,error:null};static getDerivedStateFromError(e){return{hasError:!0,error:e}}render(){return this.state.hasError?(0,B.jsx)(`div`,{className:`flex items-center justify-center h-screen bg-surface-950`,children:(0,B.jsxs)(`div`,{className:`bg-surface-800 rounded-xl p-8 border border-red-500/30 max-w-md text-center`,children:[(0,B.jsx)(`h2`,{className:`text-xl font-bold text-white mb-2`,children:`Application Error`}),(0,B.jsx)(`p`,{className:`text-sm text-red-400 mb-4`,children:this.state.error?.message||`An unexpected error occurred`}),(0,B.jsx)(`button`,{type:`button`,onClick:()=>{this.setState({hasError:!1,error:null}),globalThis.location.reload()},className:`px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white rounded-lg text-sm font-medium transition-colors`,children:`Reload Application`})]})}):this.props.children}},Li=document.getElementById(`root`);if(!Li)throw Error(`Root element #root not found in DOM`);(0,Qe.createRoot)(Li).render((0,B.jsx)(z.StrictMode,{children:(0,B.jsx)(Ii,{children:(0,B.jsx)(Fi,{})})}));export{xn as C,Qt as D,q as E,nt as O,yn as S,$t as T,gn as _,On as a,J as b,dn as c,_n as d,un as f,vn as g,pn as h,En as i,hn as l,mn as m,qn as n,An as o,Sn as p,Tn as r,bn as s,Kr as t,Cn as u,Dn as v,kn as w,fn as x,wn as y};