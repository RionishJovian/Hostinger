import {isSecurePairingContext} from './magic-connect-url.mjs';
const JOB_ID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function batchLink(location,jobId,sheet){
 if(!isSecurePairingContext(location)||!JOB_ID.test(jobId))return null;
 const url=new URL('/',location.origin);url.searchParams.set('batch',jobId);if(sheet)url.searchParams.set('sheet',String(sheet));return url.href;
}
export function readBatchLink(search){
 const params=new URLSearchParams(search),jobId=params.get('batch')||'';
 if(!JOB_ID.test(jobId))return null;
 const sheet=Number(params.get('sheet'));
 return {jobId:jobId.toLowerCase(),sheet:Number.isInteger(sheet)&&sheet>=1&&sheet<=10000?sheet:null};
}
export function withoutBatchLink(location){
 const url=new URL(location.href);url.searchParams.delete('batch');url.searchParams.delete('sheet');return url.pathname+url.search+url.hash;
}
export async function batchQrCodes(toSvg,location,job,sheets){
 if(job.settings?.batch_qr===false)return {};
 const entries=await Promise.all(sheets.map(async n=>{const link=batchLink(location,job.id,n);return link?[n,await toSvg(link)]:null}));
 return Object.fromEntries(entries.filter(Boolean));
}
