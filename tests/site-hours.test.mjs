import test from 'node:test';
import assert from 'node:assert/strict';
import {defaultWeek,weekProblem,scheduleSummary,countdown,maintenanceMinutes,hoursBody,hoursProblem} from '../src/site-hours.mjs';

test('weekly schedules validate times and allow closed days and all day',()=>{
 const week={...defaultWeek(),sun:null};
 assert.equal(weekProblem(week),'');
 assert.equal(weekProblem({...week,mon:{open:'00:00',close:'24:00'}}),'');
 assert.match(weekProblem({...week,tue:{open:'8:00',close:'22:00'}}),/Tue: use 24-hour times/);
 assert.match(weekProblem({...week,wed:{open:'24:00',close:'22:00'}}),/Wed: use 24-hour times/);
 assert.match(weekProblem({...week,thu:{open:'09:00',close:'09:00'}}),/Thu: opening and closing times must differ/);
 assert.match(weekProblem(null),/Set a weekly schedule/);
});

test('schedule summary groups equal days and marks overnight hours',()=>{
 assert.equal(scheduleSummary({...defaultWeek(),sun:null}),'Mon–Sat 08:00–22:00 · Sun Closed');
 assert.equal(scheduleSummary({...defaultWeek('18:00','02:00'),mon:null}),'Mon Closed · Tue–Sun 18:00–02:00 (next day)');
 assert.equal(scheduleSummary(null),'Not set');
});

test('maintenance countdown and duration choices',()=>{
 assert.equal(countdown(3725),'1h 02m 05s');
 assert.equal(countdown(59),'0m 59s');
 assert.equal(countdown(-4),'0m 00s');
 assert.equal(maintenanceMinutes('30',''),30);
 assert.equal(maintenanceMinutes('custom','90'),90);
 for(const bad of ['4','1441','12.5','','abc'])assert.equal(maintenanceMinutes('custom',bad),null);
});

test('hours form sends only the schedules the chosen mode needs',()=>{
 const business={...defaultWeek(),sun:null},network=defaultWeek('06:00','23:00');
 assert.deepEqual(hoursBody({businessSet:true,business,mode:'business',network}),{business_hours:business,network_hours_mode:'business',network_hours:null});
 assert.deepEqual(hoursBody({businessSet:false,business,mode:'custom',network}),{business_hours:null,network_hours_mode:'custom',network_hours:network});
 assert.match(hoursProblem({businessSet:false,business,mode:'business',network}),/Set business hours first/);
 assert.match(hoursProblem({businessSet:false,business,mode:'custom',network:{...network,fri:{open:'x',close:'23:00'}}}),/Network hours · Fri/);
 assert.equal(hoursProblem({businessSet:true,business,mode:'always',network}),'');
});

test('week and hours problems accept localized labels',()=>{
 const days={mon:'တနင်္လာ',tue:'အင်္ဂါ',wed:'ဗုဒ္ဓဟူး',thu:'ကြာသပတေး',fri:'သောကြာ',sat:'စနေ',sun:'တနင်္ဂနွေ'};
 const week={...defaultWeek(),tue:{open:'8:00',close:'22:00'}};
 assert.match(weekProblem(week,{dayNames:days,badTimes:d=>`${d} BAD`}),/အင်္ဂါ BAD/);
 assert.equal(scheduleSummary({...defaultWeek(),sun:null},{dayNames:days,closed:'ပိတ်'}),'တနင်္လာ–စနေ 08:00–22:00 · တနင်္ဂနွေ ပိတ်');
 assert.match(hoursProblem({businessSet:false,business:defaultWeek(),mode:'business',network:defaultWeek()},{needBusinessFirst:'လုပ်ငန်း အရင်'}),/လုပ်ငန်း အရင်/);
});
