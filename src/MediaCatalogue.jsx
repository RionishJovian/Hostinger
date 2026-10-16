import React,{useState} from 'react';
import {useSmeCopy,useSmeFormat} from './SMELocalization.jsx';

const Field=({label,children})=><label className="field"><span>{label}</span>{children}</label>;

const EN_MEDIA={
 selectedTitle:'Selected title',
 libraryCombined:h=>`Library access: ${h} hours, independent of internet limits`,
 categories:(list,h)=>`Categories (${list}): ${h} hours`,
 hybrid:(libH,name,titleH)=>`Library: ${libH} hours + ${name}: ${titleH} hours`,
 titleHours:(name,h)=>`${name}: ${h} hours`,
 libraryAccess:h=>`Library access: ${h} hours`,
 revoked:'Revoked',
 activeUntil:when=>`Active until ${when}`,
 expired:when=>`Expired ${when}`,
 startsFirstUse:'Starts at your first use',
 awaitingActivation:'Awaiting media activation'
};

export function packageMediaDescription(p,c=EN_MEDIA){
 if(p.service==='combined')return (c.libraryCombined||EN_MEDIA.libraryCombined)(p.media_hours);
 if(p.service!=='media')return '';
 if(p.mode==='category')return (c.categories||EN_MEDIA.categories)((p.categories||[]).join(', '),p.hours);
 const name=p.title_snapshot?.name||p.title||(c.selectedTitle||EN_MEDIA.selectedTitle);
 if(p.mode==='hybrid')return (c.hybrid||EN_MEDIA.hybrid)(p.hours,name,p.title_hours??48);
 if(p.mode==='title')return (c.titleHours||EN_MEDIA.titleHours)(name,p.hours);
 return (c.libraryAccess||EN_MEDIA.libraryAccess)(p.hours);
}

export function passStatus(e,c=EN_MEDIA,formatWhen=t=>new Date(t*1000).toLocaleString()){
 const m=e.media_policy||{};
 if(e.revoked)return c.revoked||EN_MEDIA.revoked;
 if(m.state==='active')return (c.activeUntil||EN_MEDIA.activeUntil)(formatWhen(m.valid_until));
 if(m.state==='expired')return (c.expired||EN_MEDIA.expired)(formatWhen(m.valid_until));
 return m.state==='not_started'?(c.startsFirstUse||EN_MEDIA.startsFirstUse):(c.awaitingActivation||EN_MEDIA.awaitingActivation);
}

function TitleEditor({title,act,busy,c}){
 const [form,setForm]=useState(title?Object.fromEntries(['name','description','genre','runtime_minutes','release_year'].map(k=>[k,title[k]??''])):{name:'',description:'',genre:'',runtime_minutes:90,release_year:''});
 return <section className="panel"><h2>{title?c.editTitle(title.name):c.addTitle}</h2><form onSubmit={e=>{e.preventDefault();const settings={...form,release_year:form.release_year===''?null:Number(form.release_year)};act(title?'media/titles/'+title.id:'media/titles',title?{expected_revision:title.revision,settings}:settings)}}><div className="formgrid"><Field label={c.titleName}><input required maxLength={120} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></Field><Field label={c.genre}><input maxLength={80} value={form.genre} onChange={e=>setForm({...form,genre:e.target.value})}/></Field><Field label={c.runtime}><input required type="number" min={1} max={1440} value={form.runtime_minutes} onChange={e=>setForm({...form,runtime_minutes:Number(e.target.value)})}/></Field><Field label={c.releaseYear}><input type="number" min={1888} max={2100} value={form.release_year} onChange={e=>setForm({...form,release_year:e.target.value})}/></Field></div><Field label={c.description}><textarea maxLength={4000} value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></Field><button className="button" disabled={busy||title?.archived}>{title?c.saveTitle:c.createDraft}</button></form><p className="muted">{c.editorNote}</p></section>;
}

function PreviewSettings({settings,act,busy,c}){
 const [value,setValue]=useState(settings.catalog_preview);
 return <section className="panel"><h2>{c.previewTitle}</h2><form onSubmit={e=>{e.preventDefault();act('media/settings',{expected_revision:settings.revision,catalog_preview:value})}}><label className="check"><input type="radio" name="preview" checked={value==='full'} onChange={()=>setValue('full')}/>{c.previewFull}</label><label className="check"><input type="radio" name="preview" checked={value==='featured'} onChange={()=>setValue('featured')}/>{c.previewFeatured}</label><button className="button" disabled={busy||value===settings.catalog_preview}>{c.savePreview}</button></form></section>;
}

export function OwnerMediaCatalogue({titles,act,busy,go,settings}){
 const c=useSmeCopy('media');
 const [selected,setSelected]=useState('');
 const title=titles.find(t=>t.id===selected);
 const published=titles.filter(t=>t.published&&!t.archived).length;
 const drafts=titles.filter(t=>!t.published&&!t.archived).length;
 const archived=titles.filter(t=>t.archived).length;
 return <>
  <section className="panel"><div className="panelhead"><h2>{c.catalogueTitle}</h2><button className="button secondary" disabled={busy} onClick={()=>{setSelected('');go?.('Packages')}}>{c.setPassPrices}</button></div>
   <p>{c.publishedCount(published,drafts,archived)}</p>
   <div className="tablewrap"><table><thead><tr>{c.heads.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>
    {titles.map(t=><tr key={t.id}><td>{t.name}<small>{t.id}</small></td><td>{t.genre||c.uncategorized} · {c.minutes(t.runtime_minutes)}<small>{t.release_year||c.yearMissing} · {c.revision(t.revision)}</small></td><td>{t.archived?c.archived:t.published?c.published:c.draft}{t.featured&&<small>{c.featured}</small>}</td><td><div className="buttons">{!t.archived&&<button className="button secondary" disabled={busy} onClick={()=>setSelected(t.id)}>{c.edit}</button>}{(t.archived?['restore']:[...(t.published?['unpublish']:['publish']),t.featured?'unfeature':'feature','archive']).map(operation=><button className="button secondary" key={operation} disabled={busy} onClick={()=>act('media/titles/'+t.id+'/state',{expected_revision:t.revision,operation})}>{c.ops[operation]}</button>)}</div></td></tr>)}
    {!titles.length&&<tr><td colSpan={4}>{c.empty}</td></tr>}
   </tbody></table></div>
   <p className="muted">{c.catalogueNote}</p>
   {title&&<button className="button secondary" onClick={()=>setSelected('')}>{c.addAnother}</button>}
  </section>
  <TitleEditor key={(title?.id||'new')+':'+(title?.revision||0)} title={title} act={act} busy={busy} c={c}/>
  {settings&&<PreviewSettings key={settings.revision} settings={settings} act={act} busy={busy} c={c}/>}
  <section className="panel"><h2>{c.rulesTitle}</h2><p>{c.rulesBody1}</p><p>{c.rulesBody2}</p><p className="muted">{c.rulesNote}</p></section>
  <section className="panel"><h2>{c.playbackTitle}</h2><span className="pill warn">{c.serverDisconnected}</span><p>{c.playbackBody}</p></section>
 </>;
}

export function GuestMediaCatalogue({titles,packages,entitlements,go,sites=[]}){
 const c=useSmeCopy('media');
 const {money,when}=useSmeFormat();
 const [search,setSearch]=useState('');
 const shown=titles.filter(t=>(t.name+' '+t.genre+' '+t.description).toLowerCase().includes(search.toLowerCase()));
 const passes=entitlements.filter(e=>e.media_policy);
 return <>
  <section className="panel"><div className="panelhead"><h2>{c.guestBrowseTitle}</h2><button className="button secondary" onClick={()=>go('Guest portal')}>{c.buyOrRedeem}</button></div>
   <Field label={c.search}><input type="search" maxLength={160} value={search} onChange={e=>setSearch(e.target.value)}/></Field>
   <div className="formgrid">{shown.map(t=><article className="previewbox" key={t.id}><h3>{t.name}</h3><small>{t.genre||c.genreFallback} · {c.minutes(t.runtime_minutes)}{t.release_year?' · '+t.release_year:''}</small><p>{t.description}</p><span className="pill warn">{c.playbackUnavailable}</span></article>)}</div>
   {!shown.length&&<p>{c.noMatch}</p>}
  </section>
  <section className="panel"><h2>{c.packagesTitle}</h2>
   {packages.filter(p=>['media','combined'].includes(p.service)).map(p=><div className="pass" key={p.id}><h3>{p.name}</h3><p>{packageMediaDescription(p,c)}</p><small>{money(p.price)} · {c.packageMeta}</small></div>)}
   <p className="muted">{c.packagesNote}</p>
  </section>
  <section className="panel"><h2>{c.storedTitle}</h2>
   {passes.map(e=><div className="pass" key={e.id}><h3>{e.policy.name}</h3><small>{c.site} {sites.find(s=>s.id===e.site_id)?.name||e.site_id||c.businessWide}</small><p>{packageMediaDescription(e.policy,c)}</p><span className={'pill '+(e.revoked||e.media_policy.state==='expired'?'warn':'')}>{passStatus(e,c,when)}</span>{e.media_policy.device_limit&&<small>{c.oneDevice}</small>}{e.media_policy.title&&!titles.some(t=>t.id===e.media_policy.title.id)&&<p className="muted">{c.titleMissing}</p>}<p className="muted">{c.passPlaybackNote}</p></div>)}
   {!passes.length&&<p>{c.noPasses}</p>}
  </section>
 </>;
}
