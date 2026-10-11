// Real Chrome -> Vite -> FastAPI -> isolated PostgreSQL acceptance.
// Synthetic credentials stay in a private temporary directory, never stdout.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {randomBytes} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {chromium} from 'playwright';

const folder=process.argv[2];
assert.match(folder||'',/^\/private\/tmp\/mm-build21-rc\.[A-Za-z0-9]+$/);
const initial=JSON.parse(await readFile(folder+'/login.json','utf8'));
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const result={browser:'Google Chrome headless',origin:process.env.MM_RC_ORIGIN||'http://127.0.0.1:5173',workflows:{},http:{},secrets_printed:false};
const origin=result.origin;

async function enter(page,username,password,landing){
 await page.goto(origin+'/');
 await page.getByLabel('Username').fill(username);
 await page.getByLabel('Password').fill(password);
 const response=page.waitForResponse(r=>r.url().endsWith('/v1/auth/login')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 const login=await response;
 assert.equal(login.status(),200);
 const token=(await login.json()).access_token;
 if(landing==='owner')await page.getByRole('button',{name:'Shops',exact:true}).waitFor();
 else await page.getByRole('heading',{name:landing,exact:true}).first().waitFor();
 return token;
}
async function api(page,token,method,path,body){
 const response=await page.request.fetch(origin+'/v1/'+path,{method,headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},...(body?{data:body}:{})});
 return {status:response.status(),body:await response.json().catch(()=>null)};
}
async function createBusiness(page,name,username){
 await page.getByRole('button',{name:'Businesses',exact:true}).click();
 await page.getByLabel('Business name', {exact:true}).fill(name);
 await page.getByLabel('Owner username').fill(username);
 const response=page.waitForResponse(r=>r.url().endsWith('/v1/platform/businesses')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Create business & owner'}).click();
 assert.equal((await response).status(),201);
 await page.getByRole('heading',{name:'Owner sign-in handoff'}).waitFor();
 const password=await page.getByLabel('Temporary password — shown once').inputValue();
 assert.ok(password.length>=6);
 await page.getByRole('button',{name:'Hide password'}).click();
 return password;
}
async function ownerPage(username,tempPassword){
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 await enter(page,username,tempPassword,'Set your personal password');
 const next=randomBytes(24).toString('base64url');
 await page.getByLabel('Temporary password',{exact:true}).fill(tempPassword);
 await page.getByLabel('New password (at least 6 characters)').fill(next);
 await page.getByLabel('Repeat new password').fill(next);
 const response=page.waitForResponse(r=>r.url().endsWith('/v1/auth/password')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Set password'}).click();
 const changed=await response;
 assert.equal(changed.status(),200);
 const token=(await changed.json()).access_token;
 await page.getByRole('button',{name:'English',exact:true}).click();
 try{await page.getByRole('button',{name:'Shops',exact:true}).waitFor({timeout:8000})}
 catch(error){result.failure_ui=(await page.locator('body').innerText()).slice(0,1600);throw error}
 return {page,token,password:next};
}
try{
 const platform=await browser.newPage({viewport:{width:1440,height:900}});
 const platformToken=await enter(platform,initial.username,initial.password,'Operations');
 result.workflows.platform_login='PASS';
 const suffix=randomBytes(3).toString('hex');
 result.run_id=suffix;
 const nameA='RC Cafe A '+suffix,nameB='RC Cafe B '+suffix;
 const userA='rc_owner_a_'+suffix,userB='rc_owner_b_'+suffix;
 const temporaryA=await createBusiness(platform,nameA,userA);
 const temporaryB=await createBusiness(platform,nameB,userB);
 result.workflows.two_businesses_created_in_browser='PASS';
 const tenants=await api(platform,platformToken,'GET','platform/businesses');
 assert.equal(tenants.status,200);
 assert.ok(tenants.body.some(x=>x.name===nameA)&&tenants.body.some(x=>x.name===nameB));
 result.http.platform_businesses=tenants.status;

 const ownerA=await ownerPage(userA,temporaryA);
 const ownerB=await ownerPage(userB,temporaryB);
 result.workflows.owner_forced_password_changes='PASS';
 for(const [owner,label] of [[ownerA,'A'],[ownerB,'B']]){
  await owner.page.getByRole('button',{name:'Shops',exact:true}).click();
  await owner.page.getByLabel('Site name').fill('RC Site '+label+' '+suffix);
  const response=owner.page.waitForResponse(r=>r.url().endsWith('/v1/sites')&&r.request().method()==='POST');
  await owner.page.getByRole('button',{name:'Create site'}).click();
  assert.equal((await response).status(),201);
  await owner.page.getByText('RC Site '+label+' '+suffix).first().waitFor();
 }
 result.workflows.site_creation_and_readback_in_browser='PASS';
 const sitesA=await api(ownerA.page,ownerA.token,'GET','sites');
 const sitesB=await api(ownerB.page,ownerB.token,'GET','sites');
 assert.equal(sitesA.status,200);assert.equal(sitesB.status,200);
 assert.equal(sitesA.body.length,1);assert.equal(sitesB.body.length,1);
 const siteA=sitesA.body[0].id,siteB=sitesB.body[0].id;
 assert.notEqual(siteA,siteB);
 result.http.owner_sites=[sitesA.status,sitesB.status];

 await ownerA.page.getByRole('button',{name:'Passes',exact:true}).click();
 await ownerA.page.getByLabel('Package name').fill('RC Internet '+suffix);
 const packageResponse=ownerA.page.waitForResponse(r=>r.url().endsWith('/v1/packages')&&r.request().method()==='POST');
 await ownerA.page.getByRole('button',{name:'Create package'}).click();
 assert.equal((await packageResponse).status(),201);
 await ownerA.page.getByText('RC Internet '+suffix).first().waitFor();
 result.workflows.package_creation_in_browser='PASS';

 await ownerA.page.getByRole('button',{name:'Guest Wi-Fi page',exact:true}).click();
 const welcome='Welcome to RC Cafe A '+suffix;
 await ownerA.page.getByLabel('Welcome message').fill(welcome);
 const draftResponse=ownerA.page.waitForResponse(r=>r.url().endsWith('/v1/portal/draft')&&r.request().method()==='POST');
 await ownerA.page.getByRole('button',{name:'Save draft'}).click();
 assert.equal((await draftResponse).status(),200);
 const portal=await api(ownerA.page,ownerA.token,'GET','portal');
 assert.equal(portal.status,200);assert.equal(portal.body.draft.welcome,welcome);
 result.workflows.portal_update_and_api_readback='PASS';
 result.http.portal_update=200;

 await ownerA.page.getByRole('button',{name:'Routers',exact:true}).click();
 await ownerA.page.getByText('Magic Connect pairing is unavailable in this release.').waitFor();
 assert.equal(await ownerA.page.getByRole('button',{name:'Generate 10-minute pairing QR'}).count(),0);
 await ownerA.page.screenshot({path:folder+'/magic-connect-unavailable.png',fullPage:true});
 const capability=await api(ownerA.page,ownerA.token,'GET','magic-connect/capability');
 assert.equal(capability.status,200);assert.equal(capability.body.pairing_available,false);
 const blocked=await api(ownerA.page,ownerA.token,'POST',`sites/${siteA}/magic-connect/attempts`,{router_name:'Blocked RC pairing'});
 assert.equal(blocked.status,503);
 const blockedClaim=await api(ownerA.page,ownerA.token,'POST','magic-connect/claim',{code:'ABCD-EFGH-IJKL-MNOP-QRST-UVWX-YZ23-4567'});
 assert.equal(blockedClaim.status,503);
 const technician=await browser.newPage({viewport:{width:1100,height:800}});
 await technician.goto(origin+'/?magic_connect=technician');
 await technician.getByText('Magic Connect pairing is unavailable in this release.').waitFor();
 assert.equal(await technician.getByRole('button',{name:'Request owner approval'}).count(),0);
 await technician.screenshot({path:folder+'/technician-pairing-unavailable.png',fullPage:true});
 result.workflows.magic_connect_ui_and_api_fail_closed='PASS';
 result.http.magic_connect=[capability.status,blocked.status,blockedClaim.status];

 const anonymous=await ownerA.page.request.get(origin+'/v1/sites');
 assert.equal(anonymous.status(),401);
 const crossRead=await api(ownerB.page,ownerB.token,'GET',`sites/${siteA}/portal`);
 const crossWrite=await api(ownerB.page,ownerB.token,'POST','routers',{site_id:siteA,name:'Forbidden',model:'synthetic',reported_routeros:''});
 assert.equal(crossRead.status,404);assert.equal(crossWrite.status,404);
 result.workflows.unauthorized_and_cross_tenant_rejected='PASS';
 result.http.isolation=[anonymous.status(),crossRead.status,crossWrite.status];

 await ownerA.page.reload();
 try{await ownerA.page.getByRole('heading',{name:'Account sign-in'}).waitFor({timeout:8000})}
 catch(error){result.failure_stage='after_refresh';result.failure_ui=(await ownerA.page.locator('body').innerText()).slice(0,1400);throw error}
 const relogin=await enter(ownerA.page,userA,ownerA.password,'owner');
 await ownerA.page.getByRole('button',{name:'Shops',exact:true}).click();
 await ownerA.page.getByText('RC Site A '+suffix).first().waitFor();
 await ownerA.page.getByRole('button',{name:'Passes',exact:true}).click();
 await ownerA.page.getByText('RC Internet '+suffix).first().waitFor();
 const after=await api(ownerA.page,relogin,'GET','portal');
 assert.equal(after.status,200);assert.equal(after.body.draft.welcome,welcome);
 result.workflows.refresh_relogin_and_persisted_records='PASS';
 result.http.relogin_portal=after.status;
 await ownerA.page.screenshot({path:folder+'/owner-records-after-relogin.png',fullPage:true});
 const sql=`SELECT (SELECT version_num FROM alembic_version),`+
  `(SELECT count(*) FROM tenants WHERE name IN ('${nameA}','${nameB}')),`+
  `(SELECT count(*) FROM sites WHERE name IN ('RC Site A ${suffix}','RC Site B ${suffix}')),`+
  `(SELECT count(*) FROM packages WHERE policy->>'name'='RC Internet ${suffix}'),`+
  `(SELECT count(*) FROM portal_settings WHERE draft->>'welcome'='${welcome}'),`+
  `(SELECT count(*) FROM magic_connect_attempts)`;
 const databaseOutput=process.env.MM_RC_DATABASE_TARGET==='hostinger-rc'
  ?execFileSync('ssh',['-o','BatchMode=yes','mikromagic-mac','docker exec -i mikromagic-build21-rc-db-1 psql -U build21_rc -d build21_rc -X -At'],{input:sql,encoding:'utf8'})
  :execFileSync('/opt/homebrew/opt/postgresql@17/bin/psql',[
   '-h',folder+'/socket','-U','mm_rc_20261009','-d','mm_rc_20261009','-X','-Atqc',sql
  ],{encoding:'utf8'});
 const counts=databaseOutput.trim().split('|');
 assert.deepEqual(counts.slice(0,5),['032','2','2','1','1']);
 assert.equal(counts[5],'0');
 result.postgresql={migration_head:counts[0],run_tenants:Number(counts[1]),run_sites:Number(counts[2]),run_packages:Number(counts[3]),run_updated_portals:Number(counts[4]),public_pairing_attempts:Number(counts[5])};
 result.status='PASS';
}catch(error){
 result.status='FAIL';result.failure=error instanceof Error?error.message.split('\n')[0]:'unknown';
}finally{
 await browser.close();
 await writeFile(folder+'/browser-result.json',JSON.stringify(result,null,2)+'\n',{mode:0o600});
 console.log(JSON.stringify(result,null,2));
 if(result.status!=='PASS')process.exitCode=1;
}
