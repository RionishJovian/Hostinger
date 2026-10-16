import React,{useEffect,useRef,useState} from 'react';
export const REGIONS=['Ayeyarwady Region','Bago Region','Chin State','Kachin State','Kayah State','Kayin State','Magway Region','Mandalay Region','Mon State','Naypyidaw Union Territory','Rakhine State','Sagaing Region','Shan State','Tanintharyi Region','Yangon Region'];
export const MYANMAR={south:9.4,north:28.6,west:92.1,east:101.2};
const round=n=>Math.round(n*1e6)/1e6;
const inside=(lat,lng)=>lat>=MYANMAR.south&&lat<=MYANMAR.north&&lng>=MYANMAR.west&&lng<=MYANMAR.east;
export const pinLink=l=>`https://www.openstreetmap.org/?mlat=${l.latitude}&mlon=${l.longitude}#map=16/${l.latitude}/${l.longitude}`;
export const placeText=l=>[l.township,l.city,l.region].join(', ');

export function LocationPin({value,onChange}){
 const box=useRef(null),map=useRef(null),pick=useRef(null),[open,setOpen]=useState(false),[failed,setFailed]=useState(false),[typed,setTyped]=useState({lat:'',lng:''});
 pick.current=(lat,lng)=>{setTyped({lat:String(round(lat)),lng:String(round(lng))});onChange({latitude:round(lat),longitude:round(lng)})};
 useEffect(()=>{
  if(!open)return;let gone=false;
  Promise.all([import('leaflet'),import('leaflet/dist/leaflet.css')]).then(([{default:L}])=>{
   if(gone||!box.current)return;
   const m=L.map(box.current,{maxBounds:[[MYANMAR.south,MYANMAR.west],[MYANMAR.north,MYANMAR.east]],maxBoundsViscosity:1,minZoom:5}).setView(value?[value.latitude,value.longitude]:[19.75,96.1],value?15:5);
   L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(m);
   m.on('click',e=>pick.current(e.latlng.lat,e.latlng.lng));map.current={m,L,marker:null};show(value);
  }).catch(()=>{if(!gone)setFailed(true)});
  return ()=>{gone=true;map.current?.m.remove();map.current=null};
 },[open]);
 function show(pin){
  const x=map.current;if(!x)return;
  if(!pin){x.marker?.remove();x.marker=null;return}
  if(x.marker)x.marker.setLatLng([pin.latitude,pin.longitude]);else x.marker=x.L.circleMarker([pin.latitude,pin.longitude],{radius:9,color:'#16382b',weight:3,fillColor:'#f2b544',fillOpacity:1}).addTo(x.m);
 }
 useEffect(()=>show(value),[value]);
 function type(k,v){const next={...typed,[k]:v};setTyped(next);const lat=Number(next.lat),lng=Number(next.lng);onChange(next.lat.trim()&&next.lng.trim()&&inside(lat,lng)?{latitude:round(lat),longitude:round(lng)}:null)}
 const typedOutside=typed.lat.trim()&&typed.lng.trim()&&!value;
 return <div className="field locationpin">
  <span>Map pin</span>
  {!open&&<button type="button" className="button secondary" onClick={()=>setOpen(true)}>Choose on map</button>}
  {open&&!failed&&<><div ref={box} className="pinmap" role="application" aria-label="Map of Myanmar. Click to place your pin."/><small className="muted">Click the map to place your pin. Zoom in to place it accurately.</small></>}
  {failed&&<p role="alert">The map could not load. Type the coordinates below instead.</p>}
  <p role="status">{value?`Pin placed at ${value.latitude}, ${value.longitude}`:'No pin placed yet.'}</p>
  <details open={failed}><summary>Type coordinates instead</summary><div className="formgrid">
   <label className="field"><span>Latitude</span><input inputMode="decimal" placeholder="16.8235" value={typed.lat} onChange={e=>type('lat',e.target.value)}/></label>
   <label className="field"><span>Longitude</span><input inputMode="decimal" placeholder="96.1324" value={typed.lng} onChange={e=>type('lng',e.target.value)}/></label>
  </div>{typedOutside&&<p role="alert">Enter a latitude and longitude inside Myanmar.</p>}</details>
 </div>;
}
