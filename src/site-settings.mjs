export const SSID_MAX_BYTES=32;
export const ssidBytes=value=>new TextEncoder().encode(String(value??'').trim()).length;
export function ssidProblem(value){
 const v=String(value??'').trim();
 if(/[\u0000-\u001f\u007f]/.test(v))return 'The Wi-Fi name cannot contain control characters.';
 if(ssidBytes(v)>SSID_MAX_BYTES)return `Wi-Fi names are limited to ${SSID_MAX_BYTES} bytes (this one is ${ssidBytes(v)}). Burmese letters use about 3 bytes each.`;
 return '';
}
export const shopSsid=(sites,siteId)=>siteId?(sites||[]).find(s=>s.id===siteId)?.printed_ssid||'':'';
// Replace the printed name only when the owner has not typed their own.
export function ssidForSite(current,sites,fromSite,toSite){
 const typed=String(current??'').trim();
 return !typed||typed===shopSsid(sites,fromSite)?shopSsid(sites,toSite):current;
}
