import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {getSmeMessage} from '../src/sme-localization.mjs';
import {matchesKnowledgeCard} from '../src/knowledge-search.mjs';

test('G05 Did you know? search matches tip, topic and related page',()=>{
 const card={title:'Torch traffic detective',category:'MikroTik',fact:'See which devices use the most bandwidth.',why:'Why',requirements:'Limits',action:'Routers'};
 assert.equal(matchesKnowledgeCard(card,'','All'),true);
 assert.equal(matchesKnowledgeCard(card,'torch','All'),true);
 assert.equal(matchesKnowledgeCard(card,'bandwidth','All'),true);
 assert.equal(matchesKnowledgeCard(card,'routers','All'),true);
 assert.equal(matchesKnowledgeCard(card,'media','All'),false);
 assert.equal(matchesKnowledgeCard(card,'torch','Media'),false);
 assert.equal(matchesKnowledgeCard(card,'torch','MikroTik'),true);
 assert.equal(matchesKnowledgeCard(card,'အင်တာနက်','All',{topicName:k=>k==='Internet access'?'အင်တာနက် အသုံးပြုခွင့်':k}),false);
 const internet={...card,category:'Internet access'};
 assert.equal(matchesKnowledgeCard(internet,'အင်တာနက်','All',{topicName:k=>k==='Internet access'?'အင်တာနက် အသုံးပြုခွင့်':k}),true);
});

test('G05 Did you know? SME copy covers expandable details and empty recovery',()=>{
 for(const lang of['en','my']){
  assert.ok(getSmeMessage(lang,'didYouKnow','moreDetails'));
  assert.ok(getSmeMessage(lang,'didYouKnow','clearFilters'));
  assert.ok(getSmeMessage(lang,'didYouKnow','emptyHint'));
  assert.ok(getSmeMessage(lang,'didYouKnow','explainNote'));
  assert.match(getSmeMessage(lang,'didYouKnow','results')(0),/\d/);
  assert.match(getSmeMessage(lang,'didYouKnow','results')(1),/1|၁/);
 }
 assert.match(getSmeMessage('my','didYouKnow','moreDetails'),/[\u1000-\u109F]/);
});

test('G05 Knowledge SME markup uses tip-first expandable cards',()=>{
 const src=readFileSync(new URL('../src/Knowledge.jsx',import.meta.url),'utf8');
 assert.match(src,/className="panel knowledge-card"/);
 assert.match(src,/className="knowledge-tip"/);
 assert.match(src,/c\.moreDetails/);
 assert.match(src,/c\.clearFilters/);
 assert.match(src,/role="status"/);
 assert.match(src,/knowledge-search\.mjs/);
 const css=readFileSync(new URL('../src/styles.css',import.meta.url),'utf8');
 assert.match(css,/knowledge-card details>summary::before/);
 assert.match(css,/G04 stable-page density/);
});
