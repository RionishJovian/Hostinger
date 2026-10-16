export function todayIn(timezone,now=new Date()){
 try{return new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(now)}catch{return null}
}
export function methodSummary(methods){
 return Object.entries(methods||{}).filter(([,amount])=>amount!==0).sort(([a],[b])=>a.localeCompare(b));
}
export function voucherReturns(row){return (row.vouchers_cancelled||0)+(row.vouchers_refunded||0)}
