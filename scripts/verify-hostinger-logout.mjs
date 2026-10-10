// Focused real-browser logout/re-login check for the isolated Hostinger RC.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {chromium} from 'playwright';

const folder=process.argv[2];
assert.match(folder||'',/^\/private\/tmp\/mm-build21-rc\.[A-Za-z0-9]+$/);
const credentials=JSON.parse(await readFile(folder+'/login.json','utf8'));
const prior=JSON.parse(await readFile(folder+'/browser-result.json','utf8'));
const origin=process.env.MM_RC_ORIGIN||'http://127.0.0.1:18081';
const result={origin,workflows:{},http:{},secrets_printed:false};
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
let page;
try{
 page=await browser.newPage({viewport:{width:1440,height:900}});
 result.stage='initial_browser_login';
 await page.goto(origin+'/');
 await page.getByLabel('Username').fill(credentials.username);
 await page.getByLabel('Password').fill(credentials.password);
 let responsePromise=page.waitForResponse(r=>r.url().endsWith('/v1/auth/login')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 let response=await responsePromise;
 assert.equal(response.status(),200);
 const oldToken=(await response.json()).access_token;
 await page.getByRole('heading',{name:'Operations',exact:true}).waitFor();
 result.workflows.platform_browser_login='PASS';

 result.stage='ui_logout';
 responsePromise=page.waitForResponse(r=>r.url().endsWith('/v1/auth/logout')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Sign out',exact:true}).click();
 response=await responsePromise;
 assert.equal(response.status(),200);
 assert.equal((await response.json()).signed_out,true);
 await page.getByRole('heading',{name:'Account sign-in',exact:true}).waitFor();
 result.http.logout=response.status();
 const revoked=await page.request.get(origin+'/v1/me',{headers:{Authorization:'Bearer '+oldToken}});
 assert.equal(revoked.status(),401);
 result.http.revoked_session=revoked.status();
 result.workflows.ui_logout_and_session_revocation='PASS';

 result.stage='relogin_form';
 await page.getByLabel('Username').fill(credentials.username);
 await page.getByLabel('Password').fill(credentials.password);
 responsePromise=page.waitForResponse(r=>r.url().endsWith('/v1/auth/login')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 response=await responsePromise;
 assert.equal(response.status(),200);
 result.http.relogin=response.status();
 result.stage='relogin_landing';
 await page.getByRole('heading',{name:'Operations',exact:true}).waitFor();
 await response.json();
 result.stage='business_navigation';
 await page.getByRole('button',{name:'Businesses',exact:true}).click();
 result.stage='persisted_business_read';
 const businessText=await page.locator('body').innerText();
 assert.ok(businessText.includes('RC Cafe A '+prior.run_id));
 assert.ok(businessText.includes('RC Cafe B '+prior.run_id));
 result.workflows.browser_relogin_and_persisted_business_read='PASS';
 result.status='PASS';
}catch(error){
 result.status='FAIL';
 result.failure=error instanceof Error?error.message.split('\n')[0]:'unknown';
 if(page)result.failure_ui=(await page.locator('body').innerText().catch(()=>'' )).slice(0,1200);
}finally{
 await browser.close();
 await writeFile(folder+'/logout-relogin-result.json',JSON.stringify(result,null,2)+'\n',{mode:0o600});
 console.log(JSON.stringify(result,null,2));
 if(result.status!=='PASS')process.exitCode=1;
}
