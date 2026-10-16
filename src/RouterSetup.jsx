import React from 'react';
import {ArrowRight,CheckCircle,Circle} from '@phosphor-icons/react';
import {useSMELocalization} from './SMELocalization.jsx';
import {routerSetupSteps,changeNeedsAttention} from './router-setup.mjs';

export {routerSetupSteps,changeNeedsAttention};

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
