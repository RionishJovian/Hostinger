/** Pure Did you know? / Guidance card filter helpers (G05 / U09). */

export function matchesKnowledgeCard(card,query,category,{topicName}={}){
 const topic=category==='All'||card.category===category;
 if(!topic)return false;
 const q=String(query||'').trim().toLowerCase();
 if(!q)return true;
 const hay=[card.title,card.fact,card.why,card.requirements,card.category,card.action,topicName?.(card.category)].filter(Boolean).join(' ').toLowerCase();
 return hay.includes(q);
}
