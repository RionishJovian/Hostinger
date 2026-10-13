import React,{useState} from 'react';
import {GUEST_PREVIEW_PAGE_IDS,previewHotspotPages} from './lantern-leaf-preview.mjs';
import {useSmeCopy} from './SMELocalization.jsx';

export function LanternLeafPreview({settings,dirty}){
 const copy=useSmeCopy('guestPreview');
 const [page,setPage]=useState('login');
 const pages=previewHotspotPages(settings);
 const current=GUEST_PREVIEW_PAGE_IDS.includes(page)?page:'login';
 return <section className="panel guest-preview" aria-label={copy.title}>
  <div className="panelhead"><h2>{copy.title}</h2><span className="pill">{dirty?copy.unsaved:copy.saved}</span></div>
  <p className="muted">{copy.note}</p>
  <div className="guest-preview-pages" role="tablist" aria-label={copy.pagesLabel}>
   {GUEST_PREVIEW_PAGE_IDS.map(id=><button key={id} type="button" role="tab" aria-selected={current===id} className={current===id?'button':'button secondary'} onClick={()=>setPage(id)}>{copy.pages[id]}</button>)}
  </div>
  <div className="guest-phone">
   <iframe title={copy.frame(copy.pages[current])} sandbox="allow-scripts" srcDoc={pages[current]}/>
  </div>
 </section>;
}
