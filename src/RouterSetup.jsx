import React from 'react';
import {ArrowRight,CheckCircle,Circle} from '@phosphor-icons/react';
import {useSMELocalization} from './SMELocalization.jsx';

const ATTENTION_PHASES=['configuration_conflict','recovery_required','failed','rolling_back'];
export const changeNeedsAttention=changes=>changes.some(change=>ATTENTION_PHASES.includes(change.phase));

export function routerSetupSteps({sites=[],routers=[]}){
 const steps=[
  {id:'shop',done:sites.length>0,count:sites.length,page:'Sites'},
  {id:'register',done:routers.length>0,count:routers.length,target:'register-router'},
  {id:'connect',done:routers.some(router=>router.connection_state==='connected'),page:'Get help'},
  {id:'check',done:false}
 ];
 const next=steps.findIndex(step=>!step.done);
 return steps.map((step,index)=>({...step,state:step.done?'done':index===next?'next':'later'}));
}

export function RouterSetupSteps({sites,routers,navigate}){
 const {t}=useSMELocalization();const m=key=>t('routerSetup',key);
 const go=step=>step.target?document.getElementById(step.target)?.scrollIntoView({behavior:'smooth',block:'start'}):navigate(step.page);
 return <section className="panel router-setup" aria-labelledby="router-setup-title">
  <div className="panelhead"><h2 id="router-setup-title">{m('title')}</h2></div>
  <p className="muted">{m('intro')}</p>
  <ol className="router-steps">{routerSetupSteps({sites,routers}).map((step,index)=><li key={step.id} className={'router-step is-'+step.state}>
   <span className="router-step-mark" aria-hidden="true">{step.done?<CheckCircle size={22} weight="fill"/>:<Circle size={22}/>}</span>
   <div><strong>{index+1}. {m(step.id+'Title')}</strong> <span className={'pill'+(step.state==='next'?' warn':'')}>{m(step.state)}</span><p>{step.done&&step.count?m(step.id+'Done')(step.count):m(step.id+'Todo')}</p>
    {step.state==='next'&&(step.page||step.target)&&<button type="button" className="button secondary" onClick={()=>go(step)}>{m(step.id+'Action')}<ArrowRight size={16}/></button>}</div>
  </li>)}</ol>
 </section>;
}

export function RouterAdvanced({open=false,children}){
 const {t}=useSMELocalization();
 return <details className="router-advanced" open={open}><summary>{t('routerSetup','advanced')}</summary><p className="muted">{t('routerSetup','advancedNote')}</p>{children}</details>;
}
