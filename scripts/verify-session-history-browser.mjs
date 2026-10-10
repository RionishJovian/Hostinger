import assert from 'node:assert/strict';
import {chromium} from 'playwright';

const origin=process.env.MM_BROWSER_ORIGIN||'http://127.0.0.1:14173';
const username=process.env.MM_BROWSER_USERNAME;
const password=process.env.MM_BROWSER_PASSWORD;
assert.ok(username&&password,'Synthetic browser-test credentials must be provided through environment variables.');
const browser=await chromium.launch({headless:true,executablePath:process.env.MM_BROWSER_EXECUTABLE||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
try{
 const page=await browser.newPage();const responses=[];
 page.setDefaultTimeout(8000);
 page.on('response',response=>{if(response.url().includes('/v1/'))responses.push({path:new URL(response.url()).pathname,status:response.status()})});
 await page.goto(origin,{waitUntil:'networkidle'});
 await page.getByLabel('Username').fill(username);await page.getByLabel('Password').fill(password);
 await page.getByRole('button',{name:'Sign in'}).click();
 await page.getByRole('button',{name:'English',exact:true}).click();
 await page.getByRole('button',{name:'Account',exact:true}).waitFor();
 await page.getByRole('button',{name:'Account',exact:true}).click();
 await page.getByRole('heading',{name:'Signed-in devices'}).waitFor();
 await page.getByRole('heading',{name:'Login history · past 7 days'}).waitFor();
 await page.getByText(/Reported desktop/).first().waitFor();
 await page.getByText('Successful sign-in',{exact:true}).first().waitFor();
 await page.screenshot({path:'/private/tmp/mm-build21-session-history-browser.png',fullPage:true});
 const required=['/v1/auth/login','/v1/me','/v1/account/sessions','/v1/account/login-history'];
 for(const path of required)assert.ok(responses.some(item=>item.path===path&&item.status===200),`${path} must return HTTP 200`);
 await page.getByRole('button',{name:'Sign out'}).click();await page.getByLabel('Username').waitFor();
 await page.getByLabel('Username').fill(username);await page.getByLabel('Password').fill(password);
 await page.getByRole('button',{name:'Sign in'}).click();await page.getByRole('button',{name:'Account',exact:true}).waitFor();
 await page.getByRole('button',{name:'Account',exact:true}).click();
 await page.getByRole('heading',{name:'Login history · past 7 days'}).waitFor();
 await page.getByText('Successful sign-in',{exact:true}).first().waitFor();
 console.log(JSON.stringify({result:'PASS',browser:'Chromium',flows:['login','session detail/history display','logout','re-login/history persistence'],http:responses.filter(item=>required.includes(item.path))}));
}finally{await browser.close()}
