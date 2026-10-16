/** Owner-facing names for what a guest buys. Internal service values stay internet/media/combined. */
export function passServiceName(service){
 if(service==='internet')return 'Internet Pass';
 if(service==='media')return 'Media Pass';
 if(service==='combined')return 'Internet + Media (no longer sold)';
 return service||'';
}
