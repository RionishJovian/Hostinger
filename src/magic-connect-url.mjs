const loopbacks=new Set(['localhost','127.0.0.1','[::1]']);
export function isSecurePairingContext(location){return location.protocol==='https:'||loopbacks.has(location.hostname)}
export function technicianPairingUrl(location,code){
 if(!isSecurePairingContext(location))throw new Error('Pairing QR requires HTTPS or localhost.');
 const url=new URL(location.pathname,location.origin);url.searchParams.set('magic_connect','technician');url.hash=new URLSearchParams({pair:code}).toString();return url.href;
}
