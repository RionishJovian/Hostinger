import React,{useEffect,useRef,useState} from 'react';
const LANGUAGE_NAMES={my:'Burmese (မြန်မာ)',en:'English'};
export default function ApplicationSettings({api,onBranding}){
 const [data,setData]=useState(null),[name,setName]=useState(''),[defaultLanguage,setDefaultLanguage]=useState('my'),[languages,setLanguages]=useState(['my','en']),[text,setText]=useState(''),[level,setLevel]=useState('info'),[file,setFile]=useState(null),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const input=useRef(null),key=useRef(null);
 function show(v){setData(v);setName(v.app_name);setDefaultLanguage(v.default_language);setLanguages(v.languages);setText(v.announcement?.text||'');setLevel(v.announcement?.level||'info')}
 useEffect(()=>{api.request('developer/application').then(show).catch(e=>setNotice(e.message))},[api]);
 async function run(work,message){setBusy(true);setNotice('');try{show(await work());onBranding?.();setNotice(message)}catch(err){setNotice(err.message)}finally{setBusy(false)}}
 function toggle(l){const next=languages.includes(l)?languages.filter(x=>x!==l):[...languages,l];if(!next.length)return;setLanguages(next);if(!next.includes(defaultLanguage))setDefaultLanguage(next[0])}
 const save=e=>{e.preventDefault();run(()=>api.request('developer/application',{expected_revision:data.revision,app_name:name,default_language:defaultLanguage,languages,announcement:text.trim()?{text:text.trim(),level}:null}),'Application settings saved.')};
 const upload=e=>{e.preventDefault();if(!file)return;if(file.size>1024*1024){setNotice('Choose an image up to 1 MiB.');return}key.current??=crypto.randomUUID();run(async()=>{const v=await api.upload('developer/application/logo',file,key.current);key.current=null;setFile(null);if(input.current)input.current.value='';return v},'Logo updated.')};
 const remove=()=>run(()=>api.request('developer/application/logo/remove',{}),'Custom logo removed. The MikroMagic logo is shown again.');
 if(!data)return <section className="panel"><h2>Application configuration</h2><p>{notice||'Loading…'}</p></section>;
 return <section className="panel"><h2>Application configuration</h2><p>The app name and logo appear on the sign-in page, the sidebar and the browser tab. Language choices apply to SME owner workspaces.</p>
  <form onSubmit={save}>
   <label className="field"><span>App name</span><input required maxLength={40} value={name} onChange={e=>setName(e.target.value)}/></label>
   <fieldset className="network-mode"><legend>Languages offered to SME owners</legend>{['my','en'].map(l=><label key={l} className="check"><input type="checkbox" checked={languages.includes(l)} disabled={languages.length===1&&languages.includes(l)} onChange={()=>toggle(l)}/> {LANGUAGE_NAMES[l]}</label>)}<small className="muted">With one language, the language switch is hidden.</small></fieldset>
   <label className="field"><span>Default language</span><select value={defaultLanguage} onChange={e=>setDefaultLanguage(e.target.value)}>{languages.map(l=><option key={l} value={l}>{LANGUAGE_NAMES[l]}</option>)}</select><small className="muted">Used until an owner picks a language on their device.</small></label>
   <label className="field"><span>Announcement to SME owners — leave empty for none</span><textarea maxLength={500} value={text} onChange={e=>setText(e.target.value)}/></label>
   <label className="field"><span>Announcement style</span><select value={level} onChange={e=>setLevel(e.target.value)}><option value="info">Information</option><option value="warning">Warning</option></select><small className="muted">Shown as a banner inside every SME owner workspace until they dismiss it. Saving a changed announcement shows it again. No email, SMS or push message is sent.</small></label>
   <button className="button" disabled={busy}>Save application settings</button>
  </form>
  <h3>Logo</h3>
  <div className="brand"><img src={data.logo?.url||'/assets/brand.png'} alt="Current logo"/><strong>{data.app_name}<small>{data.logo?`Custom logo · ${data.logo.width}×${data.logo.height}`:'Default MikroMagic logo'}</small></strong></div>
  <form onSubmit={upload}>
   <label className="field"><span>Upload a PNG, JPEG or WebP image up to 1 MiB</span><input ref={input} type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>{setFile(e.target.files[0]||null);key.current=null}}/></label>
   <small className="muted">The image is converted to a PNG of at most 256×256 pixels; a square image looks best.</small>
   <div className="buttons"><button className="button" disabled={busy||!file}>Upload logo</button>{data.logo&&<button type="button" className="button secondary" disabled={busy} onClick={remove}>Use the default logo</button>}</div>
  </form>
  {notice&&<p role="status">{notice}</p>}
 </section>
}
