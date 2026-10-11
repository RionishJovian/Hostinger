import React,{useEffect,useState} from 'react';
import AppearanceSettings from './AppearanceSettings.jsx';
import BusinessOnboarding from './BusinessOnboarding.jsx';
import OwnerAccounts from './OwnerAccounts.jsx';
import SubscriptionPaymentSettings from './SubscriptionPaymentSettings.jsx';
import SubscriptionControls from './SubscriptionControls.jsx';
import SubscriptionBilling from './SubscriptionBilling.jsx';
export const DEVELOPER_AREAS=['Application settings','SME owner accounts','Payment system','Roles & permissions'];
const ROLE_TEXT={
 developer:['Developer','The platform owner only. Developer Dashboard, Platform console, and every platform operator permission. Cannot be granted to anyone else.'],
 platform:['Platform operator','Operations, businesses, subscriptions, Magic Hubs, routers, integrations, appearance, guidance and audit. No Developer Dashboard or Platform console.'],
 user:['User (SME owner)','One Owner/Admin account per business. Manages only their own business: shops, packages, vouchers, guest payments and their MikroMagic subscription.'],
 agent:['Agent','Recruits and registers SME Users and earns commission on their subscription payments (20% monthly, 30% annual). Not built yet.']};
function Roles({api}){
 const [data,setData]=useState(null),[notice,setNotice]=useState('');
 useEffect(()=>{api.request('developer/roles').then(setData).catch(e=>setNotice(e.message))},[api]);
 return <section className="panel"><h2>Platform roles & permissions</h2><p>The predefined account types and who holds them.</p>{notice&&<p role="alert">{notice}</p>}
  {data&&<div className="tablewrap"><table><thead><tr><th>Role</th><th>Permissions</th><th>Accounts</th></tr></thead><tbody>{data.roles.map(r=><tr key={r.key}><td>{ROLE_TEXT[r.key][0]}</td><td>{ROLE_TEXT[r.key][1]}</td><td>{r.accounts?(r.accounts.length?r.accounts.map(a=>a.username+(a.active?'':' (disabled)')).join(', '):'None'):r.count}</td></tr>)}</tbody></table></div>}
  {data&&!data.custom_roles.available&&<p className="muted">Custom roles: {data.custom_roles.reason.toLowerCase()}.</p>}
 </section>
}
export default function DeveloperDashboard({api,s,act,busy}){
 const [area,setArea]=useState(DEVELOPER_AREAS[0]);
 return <>
  <div className="buttons" role="tablist" aria-label="Developer Dashboard areas">{DEVELOPER_AREAS.map(a=><button key={a} role="tab" aria-selected={a===area} className={'button '+(a===area?'':'secondary')} onClick={()=>setArea(a)}>{a}</button>)}</div>
  {area==='Application settings'&&<>{s.appearance&&<AppearanceSettings key={s.appearance.revision} appearance={s.appearance} act={act} busy={busy}/>}<section className="panel"><h2>Application configuration</h2><p className="muted">App name, logo, languages and notification defaults are not built yet. SME-owned settings stay in each business's own workspace.</p></section></>}
  {area==='SME owner accounts'&&<><OwnerAccounts api={api}/><BusinessOnboarding businesses={s.businesses} resets={s.passwordResets} act={act} busy={busy}/></>}
  {area==='Payment system'&&<><SubscriptionPaymentSettings api={api}/><SubscriptionControls api={api} businesses={s.businesses} platform/><SubscriptionBilling api={api} businesses={s.businesses} platform/></>}
  {area==='Roles & permissions'&&<Roles api={api}/>}
 </>
}
