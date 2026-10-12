import React,{useCallback,useEffect,useRef,useState} from 'react';
import {Robot,X,Moon,Sun,List,Bell,ArrowClockwise,SignOut} from '@phosphor-icons/react';
import {OwnerMediaCatalogue,GuestMediaCatalogue,packageMediaDescription} from './MediaCatalogue.jsx';
import GuestEntry from './GuestEntry.jsx';
import PortalExport from './PortalExport.jsx';
import VoucherStock from './VoucherStock.jsx';
import VoucherBatch from './VoucherBatch.jsx';
import VoucherProduction from './VoucherProduction.jsx';
import Dealers from './Dealers.jsx';
import AccountSessions from './AccountSessions.jsx';
import PlatformConsole from './PlatformConsole.jsx';
import AuditExplorer from './AuditExplorer.jsx';
import InternetPlanning from './InternetPlanning.jsx';
import NetworkPlanning from './NetworkPlanning.jsx';
import {staffPaths,staffPages,STAFF_ACCESS_CLOSED_PAGE} from './staff-access.mjs';
import SubscriptionControls from './SubscriptionControls.jsx';
import StaffControls from './StaffControls.jsx';
import SubscriptionBilling from './SubscriptionBilling.jsx';
import SubscriptionRenewal from './SubscriptionRenewal.jsx';
import DeveloperDashboard from './DeveloperDashboard.jsx';
import AgentWorkspace,{AGENT_PAGES,AgentApplication} from './AgentWorkspace.jsx';
import BusinessOnboarding,{PasswordChange} from './BusinessOnboarding.jsx';
import ReviewIntegrations from './ReviewIntegrations.jsx';
import ReceiptEvidence from './ReceiptEvidence.jsx';
import Knowledge from './Knowledge.jsx';
import AppearanceSettings,{DEFAULT_THEMES} from './AppearanceSettings.jsx';
import RevenueDashboard from './RevenueDashboard.jsx';
import {MagicHubs,RouterOnboarding} from './MagicHubs.jsx';
import {MagicConnectOwner,MagicConnectTechnician} from './MagicConnect.jsx';
import {SiteRegistry,RouterRegistry} from './NetworkRegistry.jsx';
import SiteHours from './SiteHours.jsx';
import SupportReport,{SupportInbox} from './SupportReport.jsx';
import FirstSiteAcceptance from './FirstSiteAcceptance.jsx';
import {SafeRouterChanges} from './SafeRouterChanges.jsx';
import {VoucherInventory} from './Vouchers.jsx';
import VoucherTabs from './VoucherTabs.jsx';
import {RouterAdvanced,RouterSetupSteps,changeNeedsAttention} from './RouterSetup.jsx';
import {passServiceName} from './sme-terms.mjs';
import QuickVoucher from './QuickVoucher.jsx';
import OverviewHealth,{OverviewNetwork} from './OverviewHealth.jsx';
import {NotificationCenter,DailySummary} from './NotificationCenter.jsx';
import {LanguageToggle,SMELocalizationProvider,useSMELocalization,useSmeCopy,useSmeFormat} from './SMELocalization.jsx';
import {PortalEditor,GuestPurchase} from './PortalSettings.jsx';
import {accountClient,revokeCurrentSession} from './account-api.mjs';
import {demoClient,DEMO_PAGES} from './demo-api.mjs';
import GuestAccessStatus from './GuestAccessStatus.jsx';
import {readBatchLink,withoutBatchLink} from './batch-link.mjs';
import {formatMmk} from './sme-format.mjs';
const money=n=>formatMmk(n,'en');
const empty={packages:[],orders:[],entitlements:[],tenants:[],audit:[],revenue:null,portal:null,guestPortal:null,guestAccess:null,vouchers:[],sites:[],routers:[],siteDevices:[],guestSites:[],hubs:[],hubAssignments:[],routerPlans:[],routerChanges:[],sessionSummary:null,appearance:null,effectiveAppearance:null,mediaTitles:[],knowledge:[],reviewCredentials:[],externalReviewActions:[],eventDeliveries:[],businesses:[],passwordResets:[]};
function Panel({title,children}){return <section className="panel"><div className="panelhead"><h2>{title}</h2></div>{children}</section>}
function Field({label,children}){return <label className="field"><span>{label}</span>{children}</label>}
function Table({heads,rows}){return <div className="tablewrap"><table><thead><tr>{heads.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.length?rows.map((r,i)=><tr key={i}>{r.map((v,j)=><td key={j}>{v}</td>)}</tr>):<tr><td colSpan={heads.length}>No records yet.</td></tr>}</tbody></table></div>}
const RENEWAL_PAGES=['Subscription','Account'];
const DEVELOPER_PAGES=['Businesses','Subscriptions','Appearance'];
const SME_GROUPS=[['',['Overview','Notifications']],['sell',['Vouchers','Payments','Revenue','Packages','Media']],['network',['Sites','Routers','Network','Internet','Captive portal']],['business',['Subscription','Integrations','Audit','Account']],['help',['Get help','Did you know?']]];
const names={platform:['Operations','Businesses','Subscriptions','Magic Hubs','Routers','Integrations','Appearance','Guidance','Audit','Account'],sme:SME_GROUPS.flatMap(([,pages])=>pages),guest:['Guest portal','My access','Media','Account'],agent:AGENT_PAGES};
const DEFAULT_BRANDING={app_name:'MikroMagic',default_language:'my',languages:['my','en'],logo:null};
const ANNOUNCEMENT_DISMISSED_KEY='mikromagic.announcement.dismissed';
function Brand({branding,subtitle}){return <div className="brand"><img src={branding.logo||'/assets/brand.png'} alt={branding.app_name+' logo'}/><strong>{branding.app_name}{subtitle&&<small>{subtitle}</small>}</strong></div>}
export default function AccountWorkspace(props){
 const [branding,setBranding]=useState(DEFAULT_BRANDING);
 const refreshBranding=useCallback(()=>{if(props.demo)return;fetch('/v1/branding').then(r=>r.ok?r.json():null).then(b=>{if(b?.app_name)setBranding(b)}).catch(()=>{})},[props.demo]);
 useEffect(refreshBranding,[refreshBranding]);
 useEffect(()=>{document.title=branding.app_name+' — Cloud & Business'},[branding.app_name]);
 return <SMELocalizationProvider languages={branding.languages} defaultLanguage={branding.default_language}><AccountWorkspaceContent {...props} branding={branding} onBranding={refreshBranding}/></SMELocalizationProvider>
}
function AccountWorkspaceContent({onDemo,onPrototype,demo=false,onExitDemo,branding,onBranding}){
 const {t}=useSMELocalization();
 const {money:smeMoney}=useSmeFormat();
 const entrySite=demo?'':new URLSearchParams(window.location.search).get('guest_site')||'';
 const magicConnectEntry=!demo&&new URLSearchParams(window.location.search).get('magic_connect')==='technician';
 const [entryPortal,setEntryPortal]=useState(null);
 const [pendingBatch,setPendingBatch]=useState(()=>demo?null:readBatchLink(window.location.search));
 const clearBatch=useCallback(()=>{setPendingBatch(null);window.history.replaceState(null,'',withoutBatchLink(window.location))},[]);
 const [chatCard,setChatCard]=useState(null);
 const [publicTheme,setPublicTheme]=useState(DEFAULT_THEMES),[health,setHealth]=useState(null),[selectedSite,setSelectedSite]=useState('');
 const [user,setUser]=useState(null),[s,setS]=useState(empty),[page,setPage]=useState('Overview'),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[menu,setMenu]=useState(false),[chat,setChat]=useState(false),[dark,setDark]=useState(false);
 const [billingVersion,setBillingVersion]=useState(0),[applying,setApplying]=useState(false),[dismissedAnnouncement,setDismissedAnnouncement]=useState(()=>{try{return Number(window.localStorage.getItem(ANNOUNCEMENT_DISMISSED_KEY))||0}catch{return 0}});
 const dismissAnnouncement=revision=>{setDismissedAnnouncement(revision);try{window.localStorage.setItem(ANNOUNCEMENT_DISMISSED_KEY,String(revision))}catch{}};
 const onNotifications=useCallback(r=>setS(x=>({...x,notifications:r})),[]);
 const restricted=!demo&&user?.role==='sme'&&!user.staff_profile&&user.subscription_restricted;
 const navigation=demo&&user?DEMO_PAGES:restricted?RENEWAL_PAGES:user?.staff_profile?staffPages(user.staff_profile):user?.platform_owner?[...names.platform.filter(p=>!DEVELOPER_PAGES.includes(p)),'Platform console','Developer Dashboard']:names[user?.role]||[];
 useEffect(()=>{if(user?.staff_profile&&!staffPages(user.staff_profile).includes(page))setPage(staffPages(user.staff_profile)[0])},[user,page]);
 useEffect(()=>{if(restricted&&!RENEWAL_PAGES.includes(page))setPage('Subscription')},[restricted,page]);
 const client=useRef(null);if(!client.current)client.current=demo?demoClient():accountClient(()=>{setUser(null);setS(empty);setNotice('Your session ended. Sign in again.')});const api=client.current;
 useEffect(()=>{if(demo)signIn({username:'demo-owner',password:'demo'})},[]);
 useEffect(()=>{let active=true;api.request('health').then(()=>{if(active)setHealth(true)}).catch(()=>{if(active)setHealth(false)});return ()=>{active=false;api.clear()}},[api]);
 useEffect(()=>{if(user)return;let active=true;api.request('appearance/public').then(theme=>{if(active)setPublicTheme(theme)}).catch(()=>{});return ()=>{active=false}},[api,user]);
 useEffect(()=>{const themes=user?(s.effectiveAppearance||DEFAULT_THEMES):publicTheme;const c=themes[dark?'dark':'light'];Object.entries(c).forEach(([k,v])=>document.documentElement.style.setProperty('--'+k,v));return ()=>{Object.keys(c).forEach(k=>document.documentElement.style.removeProperty('--'+k))}},[dark,user,s.effectiveAppearance,publicTheme]);
 useEffect(()=>{if(entrySite)api.request('public/sites/'+encodeURIComponent(entrySite)).then(setEntryPortal).catch(e=>setNotice(e.message))},[api,entrySite]);
 async function registerGuest(body){setBusy(true);try{await api.request('public/sites/'+encodeURIComponent(entrySite)+'/register',body);setNotice('Guest account created. Sign in to continue.');return true}catch(e){setNotice(e.message);return false}finally{setBusy(false)}}
 async function load(u,site=selectedSite){
  const paths=u.subscription_restricted||u.role==='agent'?[]:u.staff_profile?staffPaths(u.staff_profile):u.role==='platform'?['platform/businesses','platform/password-resets','tenants','audit','sites','routers','hubs','hub-assignments','router-plans','appearance','appearance/effective','knowledge']:['tenants','packages','orders','entitlements','audit','appearance/effective','media/titles',...(u.role==='sme'?['event-deliveries','review-credentials','external-review-actions','knowledge','revenue','vouchers','sites','routers','hubs','router-plans','router-changes',...(!u.staff_profile?['site-devices','hotspot-sessions/summary',...(demo?[]:['subscription','announcement','notifications','media/settings'])]:[])]:['guest-sites','my-access/diagnosis'])];
  const values=await Promise.all(paths.map(p=>api.request(p))),next={...empty};paths.forEach((p,i)=>{next[({'hub-assignments':'hubAssignments','router-plans':'routerPlans','router-changes':'routerChanges','site-devices':'siteDevices','appearance/effective':'effectiveAppearance','media/titles':'mediaTitles','review-credentials':'reviewCredentials','external-review-actions':'externalReviewActions','event-deliveries':'eventDeliveries','media/settings':'mediaSettings','platform/businesses':'businesses','platform/password-resets':'passwordResets','my-access/diagnosis':'guestAccess','hotspot-sessions/summary':'sessionSummary'})[p]||p]=values[i]});
  if(u.role==='sme'&&!u.staff_profile&&!u.subscription_restricted)next.portal=await api.request(site?'sites/'+site+'/portal':'portal');
  if(u.role==='guest')next.guestPortal=await api.request('portal/public'+(site?'?site_id='+encodeURIComponent(site):''));if(next['guest-sites']){next.guestSites=next['guest-sites'];delete next['guest-sites']}setS(next)
 }
 async function signIn(credentials){setBusy(true);setNotice('');try{const d=await api.request('auth/login',credentials);api.setToken(d.access_token);const u=await api.request('me');if(entrySite){const sites=await api.request('guest-sites');if(u.role!=='guest'||!sites.some(x=>x.id===entrySite)){await revokeCurrentSession(api);throw Error('Use a guest account belonging to this business.')}}setSelectedSite(entrySite);if(!u.must_change_password)await load(u,entrySite);setUser(u);setPage(u.subscription_restricted?'Subscription':u.role==='platform'?'Operations':u.role==='agent'?'Agent overview':u.role==='guest'?'Guest portal':pendingBatch&&!u.staff_profile?'Vouchers':'Overview');if(pendingBatch&&(u.role!=='sme'||u.staff_profile)){clearBatch();setNotice('Batch QR codes open only for the business Owner/Admin account.')}}catch(e){api.clear();setNotice(e.message)}finally{setBusy(false)}}
 async function changePassword(body){setBusy(true);setNotice('');try{const result=await api.request('auth/password',body);api.setToken(result.access_token);const next=await api.request('me');setUser(next);await load(next);setNotice('Password changed. Other signed-in sessions remain active.');return true}catch(e){setNotice(e.message);return false}finally{setBusy(false)}}
 async function act(path,body){setBusy(true);setNotice('');try{const result=await api.request(path,body);await load(user);setNotice(demo?t('shell','demoSaved'):user.role==='sme'?t('shell','saved'):'Saved to your business records.');return result}catch(e){setNotice(e.message);return null}finally{setBusy(false)}}
 async function logout(){if(demo){onExitDemo?.();return}setBusy(true);setNotice('');try{await revokeCurrentSession(api);setUser(null);setS(empty);setNotice('Signed out.')}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 async function reload(){const u=await api.request('me');setUser(u);await load(u);setBillingVersion(v=>v+1)}
 async function selectSite(site){setBusy(true);try{await load(user,site);setSelectedSite(site)}catch(e){setNotice(e.message)}finally{setBusy(false)}}
 const business=user?.role==='platform'?'Platform operations':user?.role==='agent'?'Agent workspace':s.tenants[0]?.name||'MikroMagic';const localizeSme=user?.role==='sme';const displayPage=p=>localizeSme?t('navigation',p):p;const go=p=>{if(demo&&!DEMO_PAGES.includes(p))return;setPage(p);setMenu(false)};
 if(magicConnectEntry)return <MagicConnectTechnician/>;
 if(!user)return <div className="app accountsignin"><Brand branding={branding} subtitle="Cloud & business management"/><div className="title"><div><h1>Your network.<br/><em>Your business.</em></h1><p>Sign in to your account. Your assigned role and business determine what you can access.</p></div></div><Panel title="Account sign-in"><p role="status">{health===null?'Checking sign-in service…':health?'Sign-in service available':'Sign-in service unavailable. Try again later.'}</p>{entrySite?(entryPortal?<GuestEntry portal={entryPortal} busy={busy} onRegister={registerGuest} onLogin={signIn}/>:<p>Guest site unavailable or loading.</p>):<>{pendingBatch&&<p role="status">Sign in as the business owner to open the voucher batch you scanned.</p>}<Login busy={busy} unavailable={health!==true} signIn={signIn}/></>}{notice&&<p role="alert">{notice}</p>}<p className="muted">Business accounts are provisioned by the platform operator. Guest registration is available only through a published site link. Sign out to revoke the current session.</p></Panel><Panel title="New to MikroMagic?"><p>Try the business workspace with sample data. No account, sign-in or payment needed. Nothing you do in the demo affects real businesses, payments or routers.</p><button className="button" onClick={onDemo}>Try the demo</button>{import.meta.env.DEV&&<button className="button secondary" onClick={onPrototype}>Development prototype</button>}</Panel><Panel title="Become a MikroMagic Agent"><p>Agents register new businesses for MikroMagic and earn 20% of each monthly and 30% of each annual subscription payment those businesses make. Applications are reviewed by MikroMagic before you can register businesses.</p>{applying?<AgentApplication onDone={message=>{setApplying(false);setNotice(message)}}/>:<button className="button secondary" onClick={()=>{setApplying(true);setNotice('')}}>Apply to become an Agent</button>}</Panel></div>;
 if(demo&&!user)return <div className="app accountsignin"><p role="status">{notice||'Opening the demo…'}</p></div>;
 if(user.must_change_password)return <div className="app accountsignin"><Brand branding={branding}/>{notice&&<p role="alert">{notice}</p>}<PasswordChange user={user} busy={busy} forced onChangePassword={changePassword} onLogout={logout}/></div>;
 const ownerAdmin=user.role==='sme'&&!user.staff_profile;
 const implemented=[STAFF_ACCESS_CLOSED_PAGE,'Overview','Revenue','Packages','Payments','Guest portal','My access','Operations','Businesses','Audit','Captive portal','Vouchers','Sites','Routers','Magic Hubs','Appearance','Media','Guidance','Did you know?','Account','Internet','Network','Subscription','Subscriptions','Get help'].includes(page)||(page==='Notifications'&&ownerAdmin&&!demo)||((page==='Platform console'||page==='Developer Dashboard')&&user.platform_owner)||(page==='Integrations'&&user.role==='sme')||(user.role==='agent'&&AGENT_PAGES.includes(page));
 return <div className={'app '+(menu?'menuopen':'')} aria-busy={busy}>
  <aside>
   <Brand branding={branding} subtitle={user.role==='sme'?t('shell','businessWorkspace'):user.role==='guest'?'Guest access':user.role==='agent'?'Agent workspace':'Cloud operations'}/>
   <div className="workspace">{business}<small>{user.username} · {user.staff_profile||user.role}</small></div>
   <nav>{(user.role==='sme'?SME_GROUPS.map(([g,pages])=>[g,pages.filter(p=>navigation.includes(p))]).filter(([,pages])=>pages.length):[['',navigation]]).map(([g,pages])=><React.Fragment key={g||'main'}>{g&&<div className="navgroup">{t('navGroups',g)}</div>}{pages.map(p=><button key={p} className={p===page?'selected':''} onClick={()=>go(p)}>{displayPage(p)}{p==='Payments'&&s.revenue?.pending_orders>0&&<b className="count">{s.revenue.pending_orders}</b>}{p==='Notifications'&&s.notifications?.unread>0&&<b className="count">{s.notifications.unread}</b>}</button>)}</React.Fragment>)}</nav>
   {demo&&<div className="sidebarfoot"><span className="pill">{t('shell','sampleData')}</span></div>}
  </aside>
  <div className="shell">
   <header>
    <button className="mobilemenu" aria-label={localizeSme?t('shell','toggleNavigation'):'Toggle navigation'} onClick={()=>setMenu(!menu)}><List size={24}/></button>
    <div className="breadcrumb">{business}<span> / {displayPage(page)}</span></div>
    <div className="headtools">
     {localizeSme&&<LanguageToggle className="workspace-language"/>}
     {ownerAdmin&&!demo&&!restricted&&<button className="iconbutton notification-bell" aria-label={t('notifications','title')+(s.notifications?.unread?' ('+s.notifications.unread+')':'')} onClick={()=>go('Notifications')}><Bell size={21}/>{s.notifications?.unread>0&&<b className="count">{s.notifications.unread}</b>}</button>}
     <button className="iconbutton" aria-label={localizeSme?t('shell','colorMode'):'Toggle color mode'} onClick={()=>setDark(!dark)}>{dark?<Sun size={21}/>:<Moon size={21}/>}</button>
     <button className="button secondary headbutton" disabled={busy} aria-label={localizeSme?t('shell','refresh'):'Refresh'} onClick={()=>reload().catch(e=>setNotice(e.message))}><ArrowClockwise size={18}/><span>{localizeSme?t('shell','refresh'):'Refresh'}</span></button>
     <button className="button secondary headbutton" disabled={busy} aria-label={demo?t('shell','exitDemo'):localizeSme?t('shell','signOut'):'Sign out'} onClick={logout}><SignOut size={18}/><span>{demo?t('shell','exitDemo'):localizeSme?t('shell','signOut'):'Sign out'}</span></button>
    </div>
   </header>
   <main>
    {demo&&<div className="demo-banner" role="note"><span className="pill warn">{t('shell','demoLabel')}</span><p>{t('shell','demoBanner')}</p><button className="button secondary" onClick={logout}>{t('shell','exitDemo')}</button></div>}
    {!demo&&!restricted&&s.announcement&&s.announcement.revision!==dismissedAnnouncement&&<div className="demo-banner" role={s.announcement.level==='warning'?'alert':'note'}><span className={'pill'+(s.announcement.level==='warning'?' warn':'')}>{t('shell','announcement')}</span><p>{s.announcement.text}</p><button className="button secondary" onClick={()=>dismissAnnouncement(s.announcement.revision)}>{t('shell','dismissNotification')}</button></div>}
    {!demo&&!restricted&&s.subscription?.warning&&<div className="demo-banner" role="alert"><span className="pill warn">{t('navigation','Subscription')}</span><p>{t('renewal','warning')(s.subscription.expires_on,s.subscription.days_left)}</p>{page!=='Subscription'&&<button className="button" onClick={()=>go('Subscription')}>{t('renewal','renewNow')}</button>}</div>}
    <div className="title"><div><h1>{page==='Overview'?(localizeSme?<>{t('overview','networkTitle')}<br/><em>{t('overview','businessTitle')}</em></>:<>Your network.<br/><em>Your business.</em></>):displayPage(page)}</h1><p>{demo?business+' · '+t('shell','sampleData'):business}</p></div></div>
    {notice&&<div className="notice" role="status">{notice}<button aria-label={localizeSme?t('shell','dismissNotification'):'Dismiss notification'} onClick={()=>setNotice('')}><X size={18}/></button></div>}
 {page==='Overview'&&<>{user.role==='sme'&&!user.staff_profile&&<OverviewHealth sites={s.sites} routers={s.routers} pendingPayments={s.revenue?.pending_orders} navigate={go}/>}{user.role==='sme'&&<QuickVoucher packages={s.packages} sites={s.sites} vouchers={s.vouchers} act={act} busy={busy} selectedSite={selectedSite}/>}{ownerAdmin&&!demo&&<DailySummary api={api} go={go}/>}{user.role==='sme'&&!user.staff_profile&&<OverviewNetwork sites={s.sites} routers={s.routers} devices={s.siteDevices} vouchers={s.vouchers} netCollections={smeMoney(s.revenue?.net_collections)} sessionSummary={s.sessionSummary} navigate={go}/>}</>}
 {(page==='Guidance'||page==='Did you know?')&&<Knowledge cards={s.knowledge} platform={user.role==='platform'} act={act} busy={busy} go={go} explain={c=>{setChatCard(c);setChat(true)}}/>}
 {page==='Integrations'&&user.role==='sme'&&<ReviewIntegrations credentials={s.reviewCredentials} actions={s.externalReviewActions} deliveries={s.eventDeliveries} act={act} busy={busy}/>}
 {page===STAFF_ACCESS_CLOSED_PAGE&&user.staff_profile&&<Panel title="Staff access closed"><p>MikroMagic v1 has one business Owner/Admin. Staff accounts can no longer view or change business, payment, voucher or network records.</p><p>Ask the business Owner/Admin for help, then sign out.</p></Panel>}
 {user.role==='agent'&&page!=='Account'&&AGENT_PAGES.includes(page)&&<AgentWorkspace api={api} page={page}/>}
 {page==='Notifications'&&ownerAdmin&&!demo&&<NotificationCenter api={api} go={go} onChange={onNotifications}/>}
 {page==='Account'&&<PasswordChange user={user} busy={busy} onChangePassword={changePassword}/>}
 {page==='Account'&&<AccountSessions api={api} ownerAdmin={user.role==='sme'&&!user.staff_profile}/>}
 {page==='Account'&&!demo&&!restricted&&user.role==='sme'&&!user.staff_profile&&<StaffControls api={api}/>}
 {page==='Platform console'&&user.platform_owner&&<PlatformConsole api={api}/>}
 {page==='Get help'&&user.role==='sme'&&!user.staff_profile&&<SupportReport api={api} sites={s.sites} demo={demo}/>}
 {page==='Operations'&&user.role==='platform'&&<SupportInbox api={api}/>}
 {page==='Audit'&&<AuditExplorer api={api}/>}
 {page==='Internet'&&user.role==='sme'&&<InternetPlanning api={api} sites={s.sites}/>}
 {page==='Network'&&user.role==='sme'&&<NetworkPlanning api={api} sites={s.sites}/>}
 {page==='Captive portal'&&s.portal&&<PortalExport key={selectedSite} api={api} portal={s.portal} siteId={selectedSite} busy={busy}/>}
 {page==='Vouchers'&&<VoucherTabs label={displayPage('Vouchers')} initial={pendingBatch?'batches':'issue'} tabs={[
  ['issue',t('voucherTabs','issue'),<VoucherInventory view="issue" sites={s.sites} packages={s.packages} vouchers={s.vouchers} act={act} busy={busy}/>],
  ['list',t('voucherTabs','list'),<VoucherInventory view="list" sites={s.sites} packages={s.packages} vouchers={s.vouchers} act={act} busy={busy}/>],
  ['stock',t('voucherTabs','stock'),<VoucherStock sites={s.sites} vouchers={s.vouchers}/>],
  ['batches',t('voucherTabs','batches'),<><VoucherBatch sites={s.sites} packages={s.packages} business={business} act={act} busy={busy}/>{!demo&&user.role==='sme'&&!user.staff_profile&&<VoucherProduction api={api} sites={s.sites} packages={s.packages} business={business} refresh={()=>load(user).catch(e=>setNotice(e.message))} openBatch={pendingBatch} onBatchOpened={clearBatch}/>}</>],
  !demo&&user.role==='sme'&&!user.staff_profile&&['dealers',t('voucherTabs','dealers'),<Dealers api={api} refresh={()=>load(user).catch(e=>setNotice(e.message))}/>]]}/>}
 {page==='Businesses'&&<BusinessOnboarding businesses={s.businesses} resets={s.passwordResets} act={act} busy={busy}/>}
 {page==='Developer Dashboard'&&user.platform_owner&&<DeveloperDashboard api={api} s={s} act={act} busy={busy} onBranding={onBranding}/>}
 {page==='Subscriptions'&&<SubscriptionControls api={api} businesses={s.businesses} platform={user.role==='platform'}/>}
 {page==='Subscription'&&user.role==='sme'&&!user.staff_profile&&<SubscriptionRenewal api={api} onChanged={reload}/>}
 {(page==='Subscriptions'||page==='Subscription')&&!user.staff_profile&&<SubscriptionBilling key={billingVersion} api={api} businesses={s.businesses} platform={user.role==='platform'}/>}
 {page==='Revenue'&&<RevenueDashboard api={api} sites={s.sites} refreshKey={s.revenue}/>}
 {page==='Appearance'&&s.appearance&&<AppearanceSettings key={s.appearance.revision} appearance={s.appearance} act={act} busy={busy}/>}
 {page==='Media'&&user.role==='sme'&&<OwnerMediaCatalogue titles={s.mediaTitles} settings={s.mediaSettings} act={act} busy={busy} go={go}/>}
 {page==='Media'&&user.role==='guest'&&<GuestMediaCatalogue sites={s.guestSites} titles={s.mediaTitles} packages={s.packages} entitlements={s.entitlements} go={go}/>}
 {page==='Packages'&&<Packages titles={s.mediaTitles} packages={s.packages} act={act} busy={busy}/>}
 {page==='Sites'&&<><SiteRegistry sites={s.sites} act={act} busy={busy}/>{user.role==='sme'&&!user.staff_profile&&s.sites.length>0&&<SiteHours api={api} sites={s.sites} refresh={()=>load(user).catch(e=>setNotice(e.message))}/>}{!demo&&user.role==='sme'&&!user.staff_profile&&<FirstSiteAcceptance api={api} sites={s.sites} routers={s.routers}/>}</>}
 {page==='Magic Hubs'&&<MagicHubs hubs={s.hubs} tenants={s.tenants} assignments={s.hubAssignments} act={act} busy={busy} platform/>}
 {page==='Routers'&&<>{!demo&&user.role==='sme'&&!user.staff_profile&&<RouterSetupSteps sites={s.sites} routers={s.routers} navigate={go}/>}<RouterRegistry sites={s.sites} routers={s.routers} act={act} busy={busy} platform={user.role==='platform'} localize={user.role==='sme'}/>{demo&&<Panel title="Connecting a real router"><p>After you sign up, you connect your MikroTik router to MikroMagic through a Magic Hub. The demo has no real router, so connection, onboarding and router changes are not shown here.</p></Panel>}{!demo&&user.role==='platform'&&<RouterOnboarding hubs={s.hubs} routers={s.routers} plans={s.routerPlans} act={act} busy={busy} platform/>}{!demo&&user.role==='sme'&&!user.staff_profile&&<><MagicConnectOwner sites={s.sites} api={api} busy={busy} routers={s.routers} hubs={s.hubs}/><RouterAdvanced open={changeNeedsAttention(s.routerChanges)}><MagicHubs hubs={s.hubs} localize={user.role==='sme'}/><RouterOnboarding hubs={s.hubs} routers={s.routers} plans={s.routerPlans} act={act} busy={busy} localize={user.role==='sme'}/><SafeRouterChanges routers={s.routers} plans={s.routerPlans} changes={s.routerChanges} act={act} busy={busy}/></RouterAdvanced></>}</>}
 {page==='Payments'&&<Payments orders={s.orders} act={act} busy={busy} api={api} canRefund={user.staff_profile!=='cashier'}/>}
 {page==='Guest portal'&&<><Field label="Guest site"><select disabled={busy} value={selectedSite} onChange={e=>selectSite(e.target.value)}><option value="">Business-wide portal</option>{s.guestSites.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><GuestPurchase packages={s.packages} portal={s.guestPortal} act={act} busy={busy} go={go}/></>}
 {page==='Captive portal'&&s.portal&&<><Field label="Guest Wi-Fi page for"><select value={selectedSite} disabled={busy} onChange={e=>selectSite(e.target.value)}><option value="">Existing business-wide page</option>{s.sites.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><p>{selectedSite&&s.portal.published_revision&&<>Guest link: <a href={'?guest_site='+encodeURIComponent(selectedSite)} target="_blank" rel="noreferrer">Open published guest page ↗</a></>}</p><PortalEditor key={selectedSite+':'+s.portal.revision} portal={s.portal} act={(path,body)=>act(selectedSite?'sites/'+selectedSite+'/'+path:path,body)} busy={busy}/></>}
 {page==='My access'&&<><GuestAccessStatus api={api} diagnosis={s.guestAccess} sites={s.guestSites}/><Panel title="Your orders"><Table heads={['Order','Site','Package','Amount','Decision','Provisioning']} rows={s.orders.map(o=>[o.id,s.guestSites.find(x=>x.id===o.site_id)?.name||o.site_id||'Business-wide',o.snapshot.name,money(o.amount),o.status,o.fulfillment])}/>{s.orders.map(o=><div className="pass" key={o.id}><h3>{o.snapshot.name} · {o.id}</h3><ReceiptEvidence key={o.id} order={o} api={api} upload disabled={busy} onChanged={()=>load(user)}/></div>)}{s.orders.filter(o=>o.status==='needs_evidence').map(o=><Evidence key={o.id} order={o} act={act} busy={busy}/>)}</Panel></>}
 {page==='Operations'&&<Panel title="Registered businesses"><Table heads={['Business','Identifier']} rows={s.tenants.map(t=>[t.name,t.id])}/><p className="muted">Business and first-owner creation are available under Businesses. Subscription management remains in development. Magic Hub registration and business assignment are available under Magic Hubs. Platform accounts do not automatically have permission to review SME guest payments.</p></Panel>}
 {!implemented&&<Panel title={page+' · connection work pending'}><p>{({Network:'Topology discovery needs the Magic Hub and your MikroTik devices.',Routers:'WireGuard onboarding needs your hub endpoint, keys, addressing and RouterOS capabilities.',Internet:'Starlink budgets, failover and load balancing need router telemetry and a configuration adapter.','Captive portal':'SME owners will configure portal branding, payment instructions, allowed destinations, login methods and quota policies here. The account-backed settings and router application are pending.',Vouchers:'Voucher issuance and redemption are demonstrated in the demo workspace; account-backed vouchers are pending.',Media:'Jellyfin catalogue integration and the protected streaming gateway are pending.',Appearance:'The platform palette editor is available in the demo. Account-backed publication and scope enforcement are pending.',Integrations:'Telegram, Discord and custom webhook delivery need authenticated reviewers and configured adapters.'})[page]}</p><p className="muted">This section will use your business records when implemented. The separate demo shows the planned layout and configuration options.</p></Panel>}
 </main>{demo&&<footer>Demo · sample data · resets when you leave</footer>}</div>{chat&&<section className="chat" aria-label="Magic Dude chatbot"><div className="chathead"><Robot/><b>Magic Dude</b><button aria-label="Close Magic Dude" onClick={()=>setChat(false)}><X/></button></div><div className="messages">{chatCard&&<><h3>{chatCard.title}</h3><p>{chatCard.fact}</p><p>{chatCard.why}</p><p>{chatCard.requirements}</p><small>Saved guidance, without AI generation. Router compatibility has not been checked.</small></>}<p>AI assistance is not connected yet. You are viewing {page} for {business}. No router commands can be executed here.</p></div></section>}<button className="magic" aria-label="Open Magic Dude" onClick={()=>{setChatCard(null);setChat(!chat)}}><Robot size={27}/></button></div>
}
function Login({signIn,busy,unavailable}){const [username,setUsername]=useState(''),[password,setPassword]=useState('');return <form onSubmit={e=>{e.preventDefault();signIn({username,password});setPassword('')}}><Field label="Username"><input autoComplete="username" required maxLength={160} value={username} onChange={e=>setUsername(e.target.value)}/></Field><Field label="Password"><input type="password" autoComplete="current-password" required maxLength={256} value={password} onChange={e=>setPassword(e.target.value)}/></Field><button className="button" disabled={busy||unavailable}>{busy?'Signing in…':'Sign in'}</button></form>}
function Packages({packages,titles,act,busy}){
 const c=useSmeCopy('packages');const mediaCopy=useSmeCopy('media');const {money}=useSmeFormat();
 const serviceName=s=>s==='internet'?c.internetPass:s==='media'?c.mediaPass:s==='combined'?c.combinedPass:passServiceName(s);
 const modeLabel=m=>c.modes[m]||m;
 const hoursLabel=media=>media?(p.mode==='title'?c.hoursTitle:p.mode==='category'?c.hoursCategory:c.hoursLibrary):c.hoursInternet;
 const policyText=pkg=>{
  if(['media','combined'].includes(pkg.service))return <>{packageMediaDescription(pkg,mediaCopy)}{pkg.service==='combined'&&<small>{c.combinedInternet(pkg.mode,pkg.gb,pkg.hours)}</small>}</>;
  const body=pkg.mode==='data'?c.policyData(pkg.gb):pkg.mode==='time'?c.policyTime(pkg.hours):c.policyBoth(pkg.gb,pkg.hours);
  return modeLabel(pkg.mode)+' · '+body;
 };
 const initial={name:'',service:'internet',mode:'both',price:1000,gb:1,hours:2,media_hours:24,title_hours:48,clock:'elapsed',devices:1,speed:10,title:'',categories:[],vip:false};
 const [p,setP]=useState(initial);const media=p.service==='media',targeted=media&&['title','hybrid'].includes(p.mode),genres=[...new Set(titles.filter(t=>!t.archived&&t.genre).map(t=>t.genre))].sort();
 const fields=[['price',c.price,1],...(!media&&p.mode!=='time'?[['gb',c.dataGb,.001]]:[]),...(p.mode!=='data'?[['hours',hoursLabel(media),.001]]:[]),...(p.service==='combined'?[['media_hours',c.hoursMediaSeparate,.001]]:[]),...(p.mode==='hybrid'?[['title_hours',c.hoursTitleSeparate,.001]]:[]),...(!media?[['speed',c.speed,1],['devices',c.devices,1]]:[])];
 return <><Panel title={c.listTitle}><Table heads={c.heads} rows={packages.map(pkg=>[<>{pkg.name}{pkg.vip&&<small>{c.vipBadge}</small>}</>,serviceName(pkg.service),policyText(pkg),money(pkg.price)])}/></Panel><Panel title={c.createTitle}><form onSubmit={async e=>{e.preventDefault();if(await act('packages',{...p,title:targeted?p.title:null,categories:p.mode==='category'?p.categories:[]}))setP(initial)}}><div className="formgrid"><Field label={c.passName}><input required maxLength={120} value={p.name} onChange={e=>setP({...p,name:e.target.value})}/></Field><Field label={c.service}><select value={p.service} onChange={e=>setP({...p,service:e.target.value,mode:e.target.value==='media'?'library':'both',clock:'elapsed',title:''})}>{[['internet',c.internetPass],['media',c.mediaPass]].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></Field><Field label={c.accessPolicy}><select value={p.mode} onChange={e=>setP({...p,mode:e.target.value,title:'',categories:[]})}>{(media?['library','title','hybrid','category']:['data','time','both']).map(x=><option key={x} value={x}>{modeLabel(x)}</option>)}</select></Field><Field label={c.timeClock}><select value={p.clock} onChange={e=>setP({...p,clock:e.target.value})}><option value="elapsed">{c.clockElapsed}</option>{!media&&<option value="connected">{c.clockConnected}</option>}</select></Field>{fields.map(([k,l,min])=><Field label={l} key={k}><input type="number" step={['gb','hours','media_hours','title_hours'].includes(k)?'any':1} min={min} required value={p[k]} onChange={e=>setP({...p,[k]:Number(e.target.value)})}/></Field>)}{media&&p.mode==='category'&&<fieldset className="field"><span>{c.categories}</span>{genres.length?genres.map(g=><label className="check" key={g}><input type="checkbox" checked={p.categories.includes(g)} onChange={e=>setP({...p,categories:e.target.checked?[...p.categories,g]:p.categories.filter(x=>x!==g)})}/>{g}</label>):<small>{c.categoriesEmpty}</small>}</fieldset>}{targeted&&<Field label={c.purchasedTitle}><select required value={p.title} onChange={e=>setP({...p,title:e.target.value})}><option value="">{c.chooseTitle}</option>{titles.filter(t=>!t.archived).map(t=><option key={t.id} value={t.id}>{t.name}{t.published?'':c.draft}</option>)}</select></Field>}</div><label className="check"><input type="checkbox" checked={p.vip} onChange={e=>setP({...p,vip:e.target.checked})}/>{c.vipCheck}</label><p className="muted">{c.note}</p><button className="button" disabled={busy}>{c.create}</button></form></Panel></>;
}
function Payments({orders,act,busy,api,canRefund=true}){
 const c=useSmeCopy('payments');const {money,when}=useSmeFormat();
 const [id,setId]=useState(''),[reason,setReason]=useState('');const o=orders.find(o=>o.id===id);
 return <><Panel title={c.queueTitle}><Table heads={c.heads} rows={orders.map(o=>[<>{o.snapshot.name}<small>{o.id}</small></>,money(o.amount),<>{o.reference}{orders.some(x=>x.id!==o.id&&x.reference===o.reference)&&<small>{c.repeatedRef}</small>}</>,o.status,<button className="button secondary" onClick={()=>{setId(o.id);setReason('')}}>{c.openReview}</button>])}/></Panel>{o&&<Panel title={c.reviewTitle(o.snapshot.name)}><div className="details">{[[c.order,o.id],[c.shop,o.site_id||c.businessWide],[c.guest,o.guest_id],[c.amountMethod,money(o.amount)+' · '+o.method],[c.destination,o.payment_context?.destination||c.notRecorded],[c.instructions,o.payment_context?.instructions||c.notRecorded],[c.reference,o.reference],[c.submitted,when(o.created)],[c.evidence,o.evidence],[c.policy,o.snapshot.service+' / '+o.snapshot.mode],[c.provisioning,o.fulfillment],[c.previous,o.reason||c.noReason],[c.reviewer,o.reviewer_id||c.notReviewed]].map(([k,v])=><p key={k}><b>{k}</b>{v}</p>)}</div><ReceiptEvidence key={o.id} order={o} api={api} disabled={busy}/><Field label={c.decisionReason}><textarea maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></Field><div className="buttons">{o.status==='pending'?['approved','needs_evidence','rejected'].map(d=><button key={d} disabled={busy||(d!=='approved'&&!reason.trim())} className={'button '+(d==='approved'?'':'secondary')} onClick={()=>act('orders/'+o.id+'/decision',{decision:d,reason,expected_receipt_revision:o.receipt_revision||0})}>{d==='approved'?c.approve:d==='needs_evidence'?c.needEvidence:c.reject}</button>):o.status==='approved'&&canRefund?<button className="button secondary" disabled={busy||!reason.trim()} onClick={()=>act('orders/'+o.id+'/refund',{reason})}>{c.refund}</button>:<span className="pill">{o.status}{o.status==='approved'&&!canRefund?c.refundOwner:''}</span>}</div><p className="muted">{c.reviewNote}</p></Panel>}</>
}
function Evidence({order,act,busy}){const [value,setValue]=useState('');return <form onSubmit={e=>{e.preventDefault();act('orders/'+order.id+'/evidence',{evidence:value})}}><p>{order.snapshot.name}: {order.reason}</p><Field label="Additional payment evidence"><textarea required maxLength={4000} value={value} onChange={e=>setValue(e.target.value)}/></Field><button className="button" disabled={busy}>Resubmit evidence</button></form>}
