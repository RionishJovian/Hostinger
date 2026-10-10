export function prioritizePackages(packages=[],vouchers=[]){
 const counts=new Map(),recent=new Map();
 for(const voucher of vouchers){
  if(!voucher.package_id)continue;
  counts.set(voucher.package_id,(counts.get(voucher.package_id)||0)+1);
  recent.set(voucher.package_id,Math.max(recent.get(voucher.package_id)||0,voucher.created||0));
 }
 return packages.map((pkg,index)=>({...pkg,quickVoucherCount:counts.get(pkg.id)||0,quickVoucherRecent:recent.get(pkg.id)||0,_index:index}))
  .sort((a,b)=>b.quickVoucherCount-a.quickVoucherCount||b.quickVoucherRecent-a.quickVoucherRecent||a._index-b._index)
  .map(({_index,...pkg})=>pkg);
}
