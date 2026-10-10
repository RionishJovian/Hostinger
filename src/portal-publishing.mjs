export async function publishPortalContent({act,portal,settings,dirty}) {
  let revision=portal.revision;
  if(dirty){
    const saved=await act('portal/draft',{expected_revision:revision,settings});
    if(!saved)return false;
    revision=saved.revision;
  }
  return Boolean(await act('portal/publish',{expected_revision:revision}));
}
