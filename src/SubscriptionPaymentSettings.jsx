import React,{useEffect,useState} from 'react';
export default function SubscriptionPaymentSettings({api}){
 const [revision,setRevision]=useState(0),[destination,setDestination]=useState(''),[instructions,setInstructions]=useState(''),[methods,setMethods]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 function show(v){setRevision(v.revision);setDestination(v.destination||'');setInstructions(v.instructions||'');setMethods((v.methods||[]).join('\n'))}
 useEffect(()=>{api.request('platform/subscription-payment').then(show).catch(e=>setNotice(e.message))},[api]);
 async function save(e){e.preventDefault();setBusy(true);setNotice('');try{show(await api.request('platform/subscription-payment',{expected_revision:revision,destination,instructions,methods:methods.split('\n').map(x=>x.trim()).filter(Boolean)}));setNotice('Payment details saved. SME owners see them on their Subscription page.')}catch(err){setNotice(err.message)}finally{setBusy(false)}}
 return <section className="panel"><h2>Subscription payment details</h2><p>Where SME owners pay MikroMagic for their subscription. These are the platform's own receiving details, separate from each business's guest payment methods. Requests stay pending until you confirm the money arrived and approve them.</p>
  <form onSubmit={save}>
   <label className="field"><span>Receiving account</span><input required maxLength={500} value={destination} onChange={e=>setDestination(e.target.value)}/></label>
   <label className="field"><span>Payment instructions</span><textarea required maxLength={2000} value={instructions} onChange={e=>setInstructions(e.target.value)}/></label>
   <label className="field"><span>Accepted payment methods — one per line</span><textarea required value={methods} onChange={e=>setMethods(e.target.value)}/></label>
   <button className="button" disabled={busy}>Save payment details</button>
  </form>
  {notice&&<p role="status">{notice}</p>}
 </section>
}
