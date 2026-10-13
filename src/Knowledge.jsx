import React,{useState} from 'react';
import {useSmeCopy} from './SMELocalization.jsx';
import {matchesKnowledgeCard} from './knowledge-search.mjs';

const blank={title:'',category:'MikroTik',fact:'',why:'',requirements:'',action:'Routers',source_url:'',verified_on:''};
const CATEGORY_KEYS=['MikroTik','Internet access','Media','Business'];
const PAGE_KEYS=['Routers','Packages','Revenue','Media'];

export default function Knowledge({cards,platform=false,act,busy=false,go,explain}){
 // Platform Guidance publishing stays English; SME Did you know? follows workspace language.
 const c=useSmeCopy('didYouKnow',!platform);
 const [query,setQuery]=useState(''),[category,setCategory]=useState('All'),[editing,setEditing]=useState(null),[draft,setDraft]=useState(blank);
 const topicName=key=>(c.categories&&c.categories[key])||key;
 const pageName=key=>(c.pageLabel&&c.pageLabel[key])||key;
 const filtered=cards.filter(card=>matchesKnowledgeCard(card,query,category,{topicName}));
 const clearFilters=()=>{setQuery('');setCategory('All')};
 const hasFilters=Boolean(String(query||'').trim())||category!=='All';
 const field=(label,key,area=false)=><label className="field"><span>{label}</span>{area?<textarea required maxLength={2000} value={draft[key]} onChange={e=>setDraft({...draft,[key]:e.target.value})}/>:<input required type={key==='verified_on'?'date':key==='source_url'?'url':'text'} maxLength={key==='title'?120:1000} value={draft[key]} onChange={e=>setDraft({...draft,[key]:e.target.value})}/>}</label>;
 const state=(card,operation)=>act('knowledge/'+card.id+'/state',{expected_revision:card.revision,operation});
 if(platform){
  return <><section className="panel"><h2>Guidance publishing</h2><p>Publish short, sourced explanations for SME owners. You attest that the source was checked on the date entered.</p><p className="muted">Guidance does not verify your router. Model, license, version and live capabilities have not been checked.</p><div className="formgrid"><label className="field"><span>Search guidance</span><input type="search" value={query} onChange={e=>setQuery(e.target.value)}/></label><label className="field"><span>Topic</span><select value={category} onChange={e=>setCategory(e.target.value)}>{['All',...CATEGORY_KEYS].map(x=><option key={x}>{x}</option>)}</select></label></div></section>
   <section className="panel"><h2>{editing?'Edit guidance card':'Create guidance card'}</h2><form onSubmit={async e=>{e.preventDefault();const result=await act(editing?'knowledge/'+editing.id:'knowledge',editing?{expected_revision:editing.revision,settings:draft}:draft);if(result){setEditing(null);setDraft(blank)}}}><div className="formgrid">{field('Title','title')}<label className="field"><span>Topic</span><select value={draft.category} onChange={e=>setDraft({...draft,category:e.target.value})}>{CATEGORY_KEYS.map(x=><option key={x}>{x}</option>)}</select></label>{field('Fact','fact',true)}{field('Why it matters','why',true)}{field('Requirements and limits','requirements',true)}<label className="field"><span>Related page</span><select value={draft.action} onChange={e=>setDraft({...draft,action:e.target.value})}>{PAGE_KEYS.map(x=><option key={x} value={x}>{x==='Packages'?'Passes':x}</option>)}</select></label>{field('Source URL (HTTPS)','source_url')}{field('Source checked on','verified_on')}</div><p className="muted">Saving an edit withdraws the published card. Review and publish it again. Retiring a card removes it from SME guidance; its record is retained.</p><div className="buttons"><button className="button" disabled={busy}>Save draft</button>{editing&&<button type="button" className="button secondary" onClick={()=>{setEditing(null);setDraft(blank)}}>Cancel edit</button>}</div></form></section>
   <div className="knowledgegrid">{filtered.map(card=><section className="panel" key={card.id}><div className="eyebrow">{card.category}</div><h2>{card.title}</h2><span className="pill">{card.archived?'Retired':card.published?'Published':'Draft'} · revision {card.revision}</span><p>{card.fact}</p><h3>Why it matters</h3><p>{card.why}</p><h3>Requirements and limits</h3><p>{card.requirements}</p><p className="muted">Router compatibility: not checked</p><p><a href={card.source_url} target="_blank" rel="noopener noreferrer">Read source ↗</a><small>Source checked: {card.verified_on}</small></p><div className="buttons">{!card.archived&&<button className="button secondary" disabled={busy} onClick={()=>{setEditing(card);const next=Object.fromEntries(Object.keys(blank).map(k=>[k,card[k]]));if(!PAGE_KEYS.includes(next.action))next.action='Routers';setDraft(next)}}>Edit</button>}{(card.archived?['restore']:card.published?['unpublish','archive']:['publish','archive']).map(operation=><button key={operation} className="button secondary" disabled={busy} onClick={()=>state(card,operation)}>{({archive:'Retire',restore:'Restore to draft',publish:'Publish',unpublish:'Unpublish'})[operation]}</button>)}</div></section>)}</div>{!filtered.length&&<section className="panel"><p>No guidance matches these filters.{!cards.length?' No cards have been published yet.':''}</p>{hasFilters&&cards.length>0&&<div className="buttons"><button type="button" className="button secondary" onClick={clearFilters}>Clear search and topic</button></div>}</section>}</>;
 }
 return <>
  <section className="panel knowledge-search">
   <h2>{c.title}</h2><p>{c.intro}</p><p className="muted">{c.note}</p>
   <div className="formgrid">
    <label className="field"><span>{c.search}</span><input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder={c.searchHint||''} autoComplete="off"/></label>
    <label className="field"><span>{c.topic}</span><select value={category} onChange={e=>setCategory(e.target.value)}><option value="All">{c.all}</option>{CATEGORY_KEYS.map(x=><option key={x} value={x}>{topicName(x)}</option>)}</select></label>
   </div>
   <p className="muted knowledge-result-count" role="status">{c.results(filtered.length)}</p>
  </section>
  <div className="knowledgegrid">{filtered.map(card=><article className="panel knowledge-card" key={card.id}>
   <div className="eyebrow">{topicName(card.category)}</div>
   <h2>{card.title}</h2>
   <p className="knowledge-tip">{card.fact}</p>
   <div className="buttons knowledge-card-actions">
    {PAGE_KEYS.includes(card.action)&&<button type="button" className="button" onClick={()=>go(card.action)}>{c.openPage(pageName(card.action))}</button>}
    <button type="button" className="button secondary" onClick={()=>explain(card)}>{c.explain}</button>
   </div>
   <details>
    <summary>{c.moreDetails}</summary>
    <h3>{c.whyTitle}</h3><p>{card.why}</p>
    <h3>{c.limitsTitle}</h3><p>{card.requirements}</p>
    <p className="muted">{c.compatibility}</p>
    <p className="muted">{c.explainNote}</p>
    <p><a href={card.source_url} target="_blank" rel="noopener noreferrer">{c.readSource}</a><small>{c.sourceChecked(card.verified_on)}</small></p>
   </details>
  </article>)}</div>
  {!filtered.length&&<section className="panel knowledge-empty" role="status">
   <p>{c.empty}{!cards.length?c.emptyNone:''}</p>
   {hasFilters&&cards.length>0&&<><p className="muted">{c.emptyHint}</p><div className="buttons"><button type="button" className="button secondary" onClick={clearFilters}>{c.clearFilters}</button></div></>}
  </section>}
 </>;
}
