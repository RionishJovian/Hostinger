export function accountClient(onExpired=()=>{},fetcher=fetch){
 let token='';
 const headers=()=>token?{Authorization:'Bearer '+token}:{};
 async function checked(path,options){
  const response=await fetcher('/v1/'+path,{...options,headers:{...options?.headers,...headers()}});
  if(!response.ok){const data=await response.json().catch(()=>({detail:'Service unavailable. Try again.'}));if(response.status===401&&path!=='auth/login'){token='';onExpired()};throw Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(x=>x.msg).join('; '):data.detail?.message?`${data.detail.message}${data.detail.code?` (${data.detail.code})`:''}`:'Request failed')};return response;
 }
 return {setToken:value=>{token=value},clear:()=>{token=''},async request(path,body){return (await checked(path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})})).json()},async logout(){const result=await (await checked('auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();if(result?.signed_out!==true)throw Error('Server did not confirm sign-out. Try again.');return result},async download(path,body){return (await checked(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).blob()},async upload(path,file,key){return (await checked(path,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Upload-Key':key},body:file})).json()},async blob(path){return (await checked(path,{method:'GET'})).blob()}};
}

export async function revokeCurrentSession(api){
 await api.logout();
 api.clear();
}
