/* Internship Radar: browser-local tracking, no accounts or analytics. */
(() => {
  'use strict';
  const KEY = 'internship-radar-tracking-v1';
  const COMPARISON_KEY = 'internship-radar-private-comparison-v1';
  const STATUSES = ['Not started','Saved','Applied','Assessment','Interview','Offer','Rejected','Withdrawn'];
  let data = {jobs:[], health:[],counts:{},updated_at:null};
  let config = {sources:[],manual_watchlist:[]};
  let catalog = {companies:[]};
  let companyLimit = 150;
  let tracking = loadTracking();
  let comparison = {hourly:null,state:''};
  let visible = [];
  let shownLimit = 100;
  let activeTab = 'discover';
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const safeUrl = v => {try{const u = new URL(v);return u.protocol === 'https:' ? u.href : '#';}catch{return '#';}};
  const niceDate = v => {if(!v)return 'Not yet'; const d=new Date(v.length===10?v+'T00:00:00Z':v);return Number.isNaN(+d)?v:d.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'});};
  const daysOld = v => v ? Math.floor((Date.now() - new Date(v+'T00:00:00Z').getTime()) / 86400000) : 99999;
  function loadTracking(){try{const obj=JSON.parse(localStorage.getItem(KEY)||'{}');return obj && typeof obj==='object' && !Array.isArray(obj)?obj:{}}catch{return {}}}
  function persist(){try{localStorage.setItem(KEY,JSON.stringify(tracking))}catch{alert('Browser storage is blocked or full. Export a backup before leaving the page.')}}
  const tracked = j => tracking[j.id]?.status && tracking[j.id].status !== 'Not started';
  function setStatus(job,status){
    if(!STATUSES.includes(status))return;
    const old=tracking[job.id]||{};
    if(status === 'Not started' && !old.note && !old.appliedAt && !old.opportunityReview){delete tracking[job.id]}
    else tracking[job.id]={...old,status,meta:{id:job.id,company:job.company,title:job.title,location:job.location,url:job.url,sector:job.sector,focus:job.focus,score:job.score,first_seen:job.first_seen},changedAt:new Date().toISOString()};
    persist();render();
  }
  function allKnownJobs(){
    const fresh = new Map(data.jobs.map(j=>[j.id,j]));
    Object.keys(tracking).forEach(id=>{if(!fresh.has(id) && tracking[id]?.meta)fresh.set(id,{...tracking[id].meta,status:id.startsWith('manual:')?'manual':'unavailable',reasons:[]})});
    return [...fresh.values()];
  }
  function switchTab(tab){
    activeTab=tab;
    document.querySelectorAll('.nav-button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
    document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id==='view-'+tab));
    $('breadcrumb-current').textContent = tab.replace(/-/g,' ').toUpperCase();
    render();
  }
  // BEA 2024 all-items Regional Price Parity by state, released February 2026.
  // National average = 100. State-level approximation; not a tax or housing calculator.
  const STATE_RPP = {
    AL:['Alabama',88.8],AK:['Alaska',102.4],AZ:['Arizona',100.7],AR:['Arkansas',86.9],
    CA:['California',110.7],CO:['Colorado',103.1],CT:['Connecticut',103.6],DE:['Delaware',99.8],
    DC:['District of Columbia',109.9],FL:['Florida',103.4],GA:['Georgia',96.3],HI:['Hawaii',110.0],
    ID:['Idaho',95.5],IL:['Illinois',100.0],IN:['Indiana',93.3],IA:['Iowa',87.8],
    KS:['Kansas',90.1],KY:['Kentucky',90.2],LA:['Louisiana',88.2],ME:['Maine',97.1],
    MD:['Maryland',105.0],MA:['Massachusetts',105.8],MI:['Michigan',96.2],MN:['Minnesota',98.6],
    MS:['Mississippi',87.0],MO:['Missouri',90.8],MT:['Montana',94.6],NE:['Nebraska',90.1],
    NV:['Nevada',100.0],NH:['New Hampshire',104.2],NJ:['New Jersey',108.8],NM:['New Mexico',92.2],
    NY:['New York',107.9],NC:['North Carolina',94.3],ND:['North Dakota',89.0],OH:['Ohio',92.8],
    OK:['Oklahoma',87.8],OR:['Oregon',103.4],PA:['Pennsylvania',97.6],RI:['Rhode Island',102.3],
    SC:['South Carolina',93.7],SD:['South Dakota',88.6],TN:['Tennessee',91.9],TX:['Texas',97.1],
    UT:['Utah',98.9],VT:['Vermont',98.0],VA:['Virginia',101.1],WA:['Washington',107.0],
    WV:['West Virginia',89.5],WI:['Wisconsin',94.1],WY:['Wyoming',92.7]
  };
  function loadComparison(){
    try {
      const obj=JSON.parse(localStorage.getItem(COMPARISON_KEY)||'{}');
      const hourly=Number(obj.hourly);
      return {hourly:hourly>0 && hourly<500?hourly:null,
              state:STATE_RPP[obj.state]?obj.state:''};
    } catch {return {hourly:null,state:''}}
  }
  function saveComparison(){
    try {localStorage.setItem(COMPARISON_KEY,JSON.stringify(comparison));}
    catch {alert('Browser storage unavailable; comparison settings may not persist.')}
  }
  function jobState(location){
    const loc=String(location||'');
    // An internship offered in multiple states or anywhere remotely has no single RPP.
    const codeMatches=[...loc.matchAll(/(?:^|[,;/]|\s-\s)\s*(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)(?=\b)/gi)]
      .map(x=>x[1].toUpperCase());
    const codes=[...new Set(codeMatches)];
    if(codes.length===1)return codes[0];
    if(codes.length>1)return null;
    const byName=Object.entries(STATE_RPP).filter(([code,v])=>
      new RegExp('\\b'+v[0]+'\\b','i').test(loc)).map(([code])=>code);
    return byName.length===1?byName[0]:null;
  }
  const fmtMoney=v=>Number(v).toLocaleString(undefined,{minimumFractionDigits:0,maximumFractionDigits:2});
  function comparePay(j){
    const p=j.pay||{};
    if(p.hourly_min==null || p.basis==='unknown')return {tier:'unknown'};
    if(p.basis==='annualized_estimate')return {tier:'annual'};
    if(!comparison.hourly || !comparison.state)return {tier:'not_configured'};
    const state=jobState(j.location);
    if(!state)return {tier:'unresolved'};
    const equivalentHourly=comparison.hourly*STATE_RPP[state][1]/STATE_RPP[comparison.state][1];
    const min=Number(p.hourly_min),max=Number(p.hourly_max??min);
    return {tier:min>=equivalentHourly?'meets':max>=equivalentHourly?'possible':'below',
      equivalentHourly,state,referenceEquivalentMin:min*STATE_RPP[comparison.state][1]/STATE_RPP[state][1]};
  }
  // Opportunity triage is browser-local: no personal benchmark or career
  // assessment is written to the repository or published in public job data.
  // These are *signals to review*, never a claim that an offer is better.
  const ADVANCEMENT_FOCUS = new Set([
    'Biostatistics / Statistical Programming', 'Statistics / Statistical Methods',
    'Epidemiology / RWE / HEOR', 'Bioinformatics / Computational Biology'
  ]);
  const ADJACENT_FOCUS = new Set([
    'Data Science / ML', 'Analytics / BI', 'Data Engineering',
    'Applied Research / Modeling', 'Strategy / Consulting'
  ]);
  function opportunityAssessment(j){
    const review=tracking[j.id]?.opportunityReview||'';
    const focus=j.focus||[];
    const specialist=focus.some(f=>ADVANCEMENT_FOCUS.has(f));
    const adjacent=focus.some(f=>ADJACENT_FOCUS.has(f));
    const goodFit=j.fit_tier==='strong'||specialist;
    const pay=comparePay(j).tier;
    const summer=j.season==='summer_confirmed';
    let label='CHECK ROLE DETAILS', rank=3, reason='Confirm duties, eligibility and project scope.';
    if(specialist){
      label='STATISTICAL CAREER FIT';rank=1;
      reason='Statistics-focused work may offer a distinct career direction; confirm substantive methods, mentoring and ownership.';
    } else if(goodFit||adjacent){
      label='RELEVANT CAREER PATH';rank=2;
      reason='Relevant skills or work area; compare the actual project with what you already do.';
    }
    if((specialist||goodFit) && pay==='meets'){
      label='PRIORITY TO REVIEW';rank=0;
      reason='Role direction and estimated local base-pay comparison are promising; assess project quality, benefits, location and eligibility.';
    } else if(specialist && ['unknown','annual','unresolved','not_configured','possible'].includes(pay)){
      label='CAREER FIT · VERIFY PAY';rank=1;
    } else if(pay==='below'){
      label=specialist?'CAREER / PAY TRADE-OFF':'BELOW LOCAL COMPARISON';
      rank=specialist?2:4;
      reason='Advertised base pay is below the configured local comparison; only pursue if the work or mentorship offers a compelling advantage.';
    }
    if(!summer && rank===0){label='VERIFY SUMMER DATES';rank=1;}
    if(review==='advance')return {label:'YOUR PRIORITY',rank:-2,reason:'You marked this as potentially advancing your goals. Verify details before applying.'};
    if(review==='similar')return {label:'YOU MARKED COMPARABLE',rank:4,reason:'Your personal assessment: comparable to your existing opportunity.'};
    if(review==='not')return {label:'YOU MARKED LOWER PRIORITY',rank:5,reason:'Your personal assessment: unlikely to be an improvement.'};
    return {label,rank,reason};
  }
  function payBadge(j){
    const p=j.pay||{}, lo=p.hourly_min, hi=p.hourly_max, c=comparePay(j);
    const range=lo==null?'Pay not listed':`$${fmtMoney(lo)}${hi>lo?'–$'+fmtMoney(hi):''}/hr`;
    let label = range,tip='Advertised employer compensation; verify actual internship base pay.';
    if(c.tier==='annual'){label='ANNUALIZED EST. · '+range;tip='Annual salary divided by 2,080; not confirmed hourly internship compensation.';}
    else if(c.tier==='meets'){label='MEETS LOCAL COMPARISON · '+range;tip=`Estimated local benchmark: $${fmtMoney(c.equivalentHourly)}/hr in ${STATE_RPP[c.state][0]}.`;}
    else if(c.tier==='possible'){label='POSSIBLE MATCH · '+range;tip=`Some of the stated pay range meets approximately $${fmtMoney(c.equivalentHourly)}/hr in ${STATE_RPP[c.state][0]}.`;}
    else if(c.tier==='below'){label='BELOW COMPARISON · '+range;tip=`Below approximately $${fmtMoney(c.equivalentHourly)}/hr in ${STATE_RPP[c.state][0]}.`;}
    else if(c.tier==='unresolved')tip='State is unclear or multiple locations are listed; compare manually.';
    else if(c.tier==='unknown')label='PAY UNLISTED';
    return `<span class="job-badge pay ${esc(c.tier)}" title="${esc(tip)}">${esc(label)}</span>`;
  }
  const NON_TARGET_TITLE = /\b(software engineer|software developer|software development|research engineer|ml engineer|machine learning engineer|ai engineer|platform engineer|frontend|front-end|backend|back-end|full.?stack|devops|firmware|embedded engineer|site reliability|security engineer)\b/i;
  function renderComparison(){
    if(comparison.hourly && comparison.state){
      const caExample = STATE_RPP.CA[1], ref=STATE_RPP[comparison.state][1];
      $('comparison-info').textContent=`Using BEA state-level prices (2024). Reference: $${fmtMoney(comparison.hourly)}/hr in ${STATE_RPP[comparison.state][0]}. A rate in another state is compared using its regional price index. Location-specific taxes, rent and benefits are not included.`;
    } else {
      $('comparison-info').textContent='Enter a reference hourly rate and state to compare estimated purchasing power. Unknown pay and unclear locations remain available for review.';
    }
  }
  function postedTimestamp(j){
    const raw=String(j.posted_at||'').trim();
    if(!/^\d{4}-\d{2}-\d{2}(?:T|$)/.test(raw))return null;
    const timestampHasTimezone=/(?:Z|[+-]\d{2}:?\d{2})$/.test(raw);
    const t=Date.parse(timestampHasTimezone ? raw : raw.slice(0,10)+'T00:00:00Z');
    return Number.isFinite(t) && t<=Date.now()+86400000 ? t : null;
  }
  // Employer publication dates, not when this scanner first encountered the role.
  // Calendar dates without a time cannot support hour-level freshness claims.
  function employerPostingAge(j, nowMs=Date.now()){
    const timestamp=postedTimestamp(j);
    if(timestamp===null)return {known:false,days:null,today:false,exact:false,minutes:null};
    const raw=String(j.posted_at||'').trim();
    const exact=/(?:Z|[+-]\d{2}:?\d{2})$/.test(raw);
    const dayString=exact ? (dt=>`${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-${String(dt.getDate()).padStart(2,'0')}`)(new Date(timestamp)) : raw.slice(0,10);
    const [year,month,day]=dayString.split('-').map(Number);
    const now=new Date(nowMs);
    const todayUTC=Date.UTC(now.getFullYear(),now.getMonth(),now.getDate());
    const postedUTC=Date.UTC(year,month-1,day);
    const days=Math.round((todayUTC-postedUTC)/86400000);
    const minutes=exact && timestamp<=nowMs ? Math.floor((nowMs-timestamp)/60000) : null;
    return {known:true,days,today:days===0 && (!exact || timestamp<=nowMs),exact,minutes};
  }
  function postedText(j){
    const timestamp=postedTimestamp(j);
    if(timestamp===null)return 'Employer posted: date unavailable';
    const info=employerPostingAge(j);
    const label=new Date(timestamp).toLocaleDateString('en-US',{timeZone:'UTC',month:'short',day:'numeric',year:'numeric'});
    const age=info.days===0?'today':info.days===1?'yesterday':info.days>1?`${info.days} days ago`:'date needs verification';
    if(!info.exact)return `Employer posted: ${label} (${age}; date only)`;
    const time=new Date(timestamp).toLocaleTimeString('en-US',{timeZone:'UTC',hour:'2-digit',minute:'2-digit',hour12:false});
    const precise=info.minutes!==null && info.minutes<1440 ? (info.minutes<60?`${info.minutes}m ago`:`${Math.floor(info.minutes/60)}h ago`) : age;
    return `Employer posted: ${label}, ${time} UTC (${precise})`;
  }
  function newestPosted(a,b){
    const left=postedTimestamp(a), right=postedTimestamp(b);
    if(left!==null && right!==null && right!==left)return right-left;
    if(left===null && right!==null)return 1;
    if(right===null && left!==null)return -1;
    return String(b.first_seen_at||b.first_seen||'').localeCompare(String(a.first_seen_at||a.first_seen||''))
       ||(Number(b.score)||0)-(Number(a.score)||0);
  }
  function card(j){
    const letters=String(j.company||'?').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
    const current=tracking[j.id]?.status||'Not started';
    const detectedAt=j.first_seen_at||null;
    const detectedMinutes=detectedAt?Math.floor((Date.now()-Date.parse(detectedAt))/60000):null;
    const publication=employerPostingAge(j);
    const newBadge=publication.today && j.status==='open' ? '<span class="job-badge new">POSTED TODAY</span>':'';
    const postedLabel=postedText(j);
    const detectionLabel=detectedMinutes!==null && detectedMinutes>=0 ? (detectedMinutes<60?`Scanner first saw ${detectedMinutes}m ago`:detectedMinutes<2880?`Scanner first saw ${Math.floor(detectedMinutes/60)}h ago`:`Scanner first saw ${Math.floor(detectedMinutes/1440)}d ago`):'Scanner first saw '+niceDate(j.first_seen);
    const isOpen=j.status==='open';
    const fitBadge=j.fit_tier==='strong'?'<span class="job-badge">STRONG ROLE MATCH</span>':j.fit_tier==='related'?'<span class="job-badge">RELATED ROLE</span>':j.fit_tier==='review'?'<span class="job-badge">REVIEW DESCRIPTION</span>':'';
    const stageBadge=j.stage==='Startup / growth'?'<span class="job-badge stage">STARTUP / GROWTH</span>':'';
    const opportunity=opportunityAssessment(j);
    const opportunityBadge=opportunity.rank<=2?`<span class="job-badge opportunity" title="${esc(opportunity.reason)}">${esc(opportunity.label)}</span>`:'';
    const stateBadge=j.status==='closed'?'<span class="job-badge closed">CLOSED</span>':j.status==='unavailable'?'<span class="job-badge closed">ARCHIVED</span>':j.status==='manual'?'<span class="job-badge">MANUALLY ADDED</span>':'';
    return `<article class="job-card"><div class="job-icon" aria-hidden="true">${esc(letters)}</div><div class="job-main"><div class="company-row">${esc(j.company)} <span>·</span> ${esc(j.sector||j.ats||'Life sciences')} ${stageBadge} ${fitBadge} ${opportunityBadge} ${newBadge} ${stateBadge}</div><h3>${esc(j.title)}</h3><div class="job-meta">${payBadge(j)}<span>${j.season==='summer_confirmed'?'☀ Summer 2027':'◷ Season unconfirmed'}</span><span>⌾ ${esc(j.location||'Not listed')}</span><span>◷ ${esc(postedLabel)}</span><span class="scanner-meta">${esc(detectionLabel)}</span><span class="job-badge score">${Number(j.score)||0}/100 relevance</span></div></div><div class="job-actions"><select data-status="${esc(j.id)}" aria-label="Application status for ${esc(j.title)}">${STATUSES.map(s=>`<option value="${esc(s)}" ${s===current?'selected':''}>${esc(s)}</option>`).join('')}</select><button class="small-icon-btn" data-detail="${esc(j.id)}" aria-label="Notes and details for ${esc(j.title)}" title="Notes and details">✎</button><a class="apply-link" href="${esc(safeUrl(j.url))}" target="_blank" rel="noopener noreferrer">${isOpen?'Apply ↗':'View ↗'}</a></div></article>`;
  }
  function empty(icon,title,explanation){return `<div class="empty"><span class="empty-icon">${icon}</span><h3>${esc(title)}</h3><p>${explanation}</p></div>`}
  function renderDiscover(){
    let jobs=data.jobs.filter(j=>{
      const state=$('filter-state').value;
      if(state!=='all' && j.status!==state)return false;
      const q=$('filter-search').value.trim().toLowerCase();
      if(q && ![j.company,j.title,j.location,j.sector,j.department,j.match_source,...(j.reasons||[]),...(j.focus||[])].join(' ').toLowerCase().includes(q))return false;
      const postFilter=$('filter-posted').value;
      if(postFilter!=='all'){
        const posted=postedTimestamp(j);
        if(postFilter==='unknown'){
          if(posted!==null)return false;
        }else{
          if(posted===null)return false;
          const dayDiff=employerPostingAge(j).days;
          const maxDays=postFilter==='today'?0:Number(postFilter)-1;
          if(dayDiff<0||dayDiff>maxDays)return false;
        }
      }
      const since=$('filter-recency').value;
      if(since!=='all'){
        const discovered=j.first_seen_at && Date.parse(j.first_seen_at);
        const hours=Number(since);
        if(!Number.isFinite(discovered)||discovered>Date.now()||Date.now()-discovered>hours*3600000)return false;
      }
      const focus=$('filter-focus').value;
      if(focus && !(j.focus||[]).includes(focus))return false;
      if(NON_TARGET_TITLE.test(j.title))return false;
      const opportunityFilter=$('filter-opportunity').value;
      const decision=opportunityAssessment(j);
      if(opportunityFilter==='priority' && decision.rank>1)return false;
      if(opportunityFilter==='review' && j.fit_tier!=='review')return false;
      if(opportunityFilter==='career' && !((j.focus||[]).some(f=>ADVANCEMENT_FOCUS.has(f))))return false;
      if(opportunityFilter==='personal' && tracking[j.id]?.opportunityReview!=='advance')return false;
      const pay=$('filter-pay').value;
      const tier=comparePay(j).tier;
      if(pay==='meets' && tier!=='meets')return false;
      if(pay==='possible' && tier!=='possible')return false;
      if(pay==='below' && tier!=='below')return false;
      if(pay==='unknown' && tier!=='unknown')return false;
      if(pay==='annual' && tier!=='annual')return false;
      if(pay==='unresolved' && tier!=='unresolved')return false;
      const companyStage=$('filter-stage').value;
      if(companyStage==='startup' && j.stage!=='Startup / growth')return false;
      if(companyStage==='established' && j.stage!=='Established / other')return false;
      if(companyStage==='mixed' && j.stage!=='Mixed')return false;
      if(companyStage==='unclassified' && j.stage!=='Unclassified')return false;
      if($('filter-season').value && j.season!==$('filter-season').value)return false;
      const loc=$('filter-location').value;
      const v=(j.location||'').toLowerCase();
      const isRemote=v.includes('remote'); const geoState=jobState(j.location);
      if(loc==='remote'&&!isRemote)return false;
      if(['ca','ny','ma','wa'].includes(loc) && geoState!==loc.toUpperCase())return false;
      if(loc==='other'&&(geoState==='CA'||geoState==='NY'||geoState==='MA'||geoState==='WA'||isRemote))return false;
      return true;
    });
    const mode=$('filter-sort').value;
    if(mode==='posted')jobs.sort(newestPosted);
    if(mode==='opportunity')jobs.sort((a,b)=>opportunityAssessment(a).rank-opportunityAssessment(b).rank||(b.score||0)-(a.score||0)||(b.first_seen_at||b.first_seen||'').localeCompare(a.first_seen_at||a.first_seen||''));
    if(mode==='score')jobs.sort((a,b)=>(b.score||0)-(a.score||0)||(b.first_seen_at||b.first_seen||'').localeCompare(a.first_seen_at||a.first_seen||''));
    if(mode==='new')jobs.sort((a,b)=>(b.first_seen_at||b.first_seen||'').localeCompare(a.first_seen_at||a.first_seen||'')||(b.score||0)-(a.score||0));
    if(mode==='company')jobs.sort((a,b)=>a.company.localeCompare(b.company));
    if(mode==='pay')jobs.sort((a,b)=>(b.pay?.hourly_min??-1)-(a.pay?.hourly_min??-1));
    visible=jobs;
    $('results-label').textContent=`Showing ${jobs.length} of ${data.jobs.length} roles`;
    $('job-list').innerHTML=jobs.length?jobs.slice(0,shownLimit).map(card).join(''):empty('⌕',data.updated_at?'No roles match these filters.':'Your first scan hasn’t run yet.',data.updated_at?'Try “All disciplines” or check <strong>Source health</strong> for failed boards. You can broaden matching rules in <code>config/preferences.json</code>.':'Once you publish the repository, run the <strong>Update internships</strong> workflow in GitHub Actions. Open the <strong>Company watchlist</strong> tab for useful career sites in the meantime.');
    if(jobs.length>shownLimit){$('job-list').insertAdjacentHTML('beforeend',`<button class="outline-btn show-more" id="more-jobs" type="button">Show ${Math.min(100,jobs.length-shownLimit)} more of ${jobs.length} opportunities ↓</button>`);}
  }
  function renderApplications(){
    const jobs=allKnownJobs().filter(j=>tracked(j));
    const buckets=['Saved','Applied','Assessment','Interview','Offer','Rejected'];
    $('pipeline').innerHTML=buckets.map(s=>`<div class="pipeline-tile"><span>${esc(s)}</span><strong>${jobs.filter(j=>tracking[j.id]?.status===s).length}</strong></div>`).join('');
    jobs.sort((a,b)=>(tracking[b.id]?.changedAt||'').localeCompare(tracking[a.id]?.changedAt||''));
    $('applications-label').textContent=`${jobs.length} tracked roles · stored on this browser`;
    $('application-list').innerHTML=jobs.length?jobs.map(card).join(''):empty('▤','Nothing tracked yet.','In Discover, select <strong>Saved</strong> or <strong>Applied</strong> next to a job. You can add notes, interview dates, and next steps using the pencil button.');
  }
  function renderWatchlist(){
    const rows=config.manual_watchlist||[];
    $('manual-watchlist').innerHTML=rows.length?rows.map(w=>`<article class="watch-card"><div><div class="kicker">${esc(w.sector||'COMPANY')}</div><h3>${esc(w.name)}</h3><p>${esc(w.note||'Review careers page for relevant openings.')}</p></div><a href="${esc(safeUrl(w.url))}" target="_blank" rel="noopener noreferrer">Visit ↗</a></article>`).join(''):empty('◎','No companies added','Edit config/companies.json to add direct career sites.');
  }
  function boardUrl(s){
    const slug=encodeURIComponent(s.slug||'');
    if(!slug)return '#';
    if(s.ats==='greenhouse')return 'https://job-boards.greenhouse.io/'+slug;
    if(s.ats==='ashby')return 'https://jobs.ashbyhq.com/'+slug;
    if(s.ats==='lever')return 'https://jobs.lever.co/'+slug;
    if(s.ats==='workday'&&s.host&&s.site)return 'https://'+encodeURIComponent(s.host)+'/en-US/'+encodeURIComponent(s.site);
    return '#';
  }
  function renderCompanies(){
    const q=($('company-search').value||'').trim().toLowerCase(), ats=$('company-ats').value;
    const all=[...(config.sources||[]).filter(s=>s.slug),...(catalog.companies||[])];
    const companies=new Map();
    all.forEach(c=>{const key=c.ats+':'+(c.slug||'').toLowerCase();if(!companies.has(key))companies.set(key,c)});
    const healthById=new Map((data.health||[]).map(h=>[h.id,h]));
    const filtered=[...companies.values()].filter(c=>(!ats||c.ats===ats)&&(!q||[c.name,c.sector,c.ats,c.slug].join(' ').toLowerCase().includes(q)));
    $('company-results').textContent=`${filtered.length.toLocaleString()} matching of ${companies.size.toLocaleString()} registered ATS boards · ${data.counts?.sources_scheduled??0} sources attempted in most recent scan`;
    $('company-list').innerHTML=filtered.slice(0,companyLimit).map(c=>{
      const h=healthById.get(c.id);
      const status=h?(h.status==='ok'?'Scanned':'Error'):'In rotation';
      const info=h?(h.status==='ok'?`${h.scanned} postings · ${h.matches} relevant internships`:(h.message||'Board unavailable')):'Not scanned in latest batch';
      const url=boardUrl(c);
      return `<div class="source-row"><div><strong>${esc(c.name)}</strong><small>${esc(c.sector||'Unclassified')} · ${esc(info)}</small></div><span>${esc(c.ats.toUpperCase())}</span><span class="source-status ${h?.status==='ok'?'ok':h?'error':'wait'}">${esc(status)}</span><a href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Open ATS board for ${esc(c.name)}">Board ↗</a></div>`;
    }).join('')||empty('◫','No companies match','The large directory will populate after the first GitHub Actions scan.');
    $('company-more').style.display=filtered.length>companyLimit?'':'none';
  }
  function renderSources(){
    const list=data.health||[];
    $('source-summary').textContent=`${data.scan_mode==='broad'?'Hourly directory rotation':'Priority scan'} · ${data.counts?.sources_scanned??0} successful · ${data.counts?.sources_failed??0} failed · ${data.counts?.sources_scheduled??(config.sources||[]).length} attempted this scan · ${data.counts?.registered_boards??(config.sources||[]).length} registered total`;
    $('source-list').innerHTML=list.map(h=>{
      const details=h.status==='ok'?`${h.scanned} postings scanned · ${h.matches} matches`:h.message||'Source unavailable';
      return `<div class="source-row"><div><strong>${esc(h.company)}</strong><small>${esc(details)}</small></div><span>${esc((h.ats||'ATS').toUpperCase())}</span><span class="source-status ${esc(h.status)}">${h.status==='ok'?'Checked':'Error'}</span></div>`;
    }).join('')||empty('⟲','No scan has run','Launch Update internships in GitHub Actions.');
  }
  function renderStats(){
    const open=data.jobs.filter(j=>j.status==='open');
    $('metric-open').textContent=data.updated_at?open.length:'—';
    $('metric-new').textContent=data.updated_at?open.filter(j=>employerPostingAge(j).today).length:'—';
    $('metric-tracked').textContent=Object.keys(tracking).filter(id=>tracking[id]?.status && tracking[id].status!=='Not started').length;
    $('metric-boards').textContent=data.updated_at?(data.counts?.registered_boards??0).toLocaleString():'—';
    $('metric-health').textContent=data.updated_at?`${data.counts?.sources_scanned??0} checked successfully · ${data.counts?.sources_failed??0} errors`:'Waiting for first scan';
    $('side-results').textContent=open.length||'—';
    $('side-applications').textContent=$('metric-tracked').textContent;
    if(data.updated_at){$('sync-text').textContent=`Last scan attempted ${niceDate(data.updated_at)}`;$('sync-dot').className='sync-dot '+((data.counts?.sources_scanned||0)>0?'ok':'warn');}
  }
  function render(){renderStats();if(activeTab==='discover')renderDiscover();if(activeTab==='applications')renderApplications();if(activeTab==='watchlist')renderWatchlist();if(activeTab==='companies')renderCompanies();if(activeTab==='sources')renderSources()}
  function openDetail(id){
    const job=allKnownJobs().find(j=>j.id===id);if(!job)return;
    const t=tracking[id]||{};
    const wrapper=$('detail-content');
    wrapper.innerHTML=`<div class="kicker">${esc(job.company)} · ${esc(job.ats||'Employer board')}</div><h2>${esc(job.title)}</h2><p>${esc(job.location||'Not listed')} · ${esc(postedText(job))} · First detected ${esc(job.first_seen_at ? niceDate(job.first_seen_at) : niceDate(job.first_seen))}</p><div class="job-meta">${payBadge(job)}${(job.focus||[]).map(s=>`<span class="job-badge">${esc(s)}</span>`).join('')}</div><div class="source-info" style="margin-top:15px">${(job.reasons||[]).map(esc).join(' · ')||'Relevance score is a suggestion, not an eligibility check.'} · Description: ${esc(job.description_status||'unverified')}</div><div class="source-info opportunity-explainer"><strong>Opportunity review:</strong> ${esc(opportunityAssessment(job).label)}. ${esc(opportunityAssessment(job).reason)} This is not a verified improvement; check mentoring, autonomy, project methods, team, eligibility, and total compensation.</div><label for="detail-upgrade">Personal career assessment (stored on this device)</label><select id="detail-upgrade"><option value="">Not yet assessed</option><option value="advance" ${t.opportunityReview==='advance'?'selected':''}>Potential step forward</option><option value="similar" ${t.opportunityReview==='similar'?'selected':''}>Comparable to current opportunity</option><option value="not" ${t.opportunityReview==='not'?'selected':''}>Not an improvement</option></select><div class="detail-status"><label for="detail-stage">Application stage</label><select id="detail-stage">${STATUSES.map(s=>`<option ${s===(t.status||'Not started')?'selected':''}>${esc(s)}</option>`).join('')}</select></div><label for="detail-date">Date applied</label><input id="detail-date" type="date" value="${esc(t.appliedAt||'')}"><label for="detail-note">Notes, contacts, next steps</label><textarea id="detail-note" placeholder="Resume version, recruiter, interview dates, follow-ups...">${esc(t.note||'')}</textarea><div class="modal-actions"><p>Autosaved on this device</p><a href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener noreferrer">Employer posting ↗</a></div>`;
    const save=()=>{
      const status=$('detail-stage').value,note=$('detail-note').value,appliedAt=$('detail-date').value,opportunityReview=$('detail-upgrade').value;
      if(status==='Not started'&&!note&&!appliedAt&&!opportunityReview)delete tracking[id];
      else tracking[id]={...tracking[id],status,note,appliedAt,opportunityReview,changedAt:new Date().toISOString(),meta:{id:job.id,company:job.company,title:job.title,location:job.location,url:job.url,sector:job.sector,focus:job.focus,score:job.score,first_seen:job.first_seen}};
      persist();render();
    };
    ['change','input'].forEach(type=>['detail-stage','detail-date','detail-note','detail-upgrade'].forEach(field=>$(field).addEventListener(type,save)));
    $('detail-dialog').showModal();
  }
  function csvEscape(v){return `"${String(v??'').replace(/"/g,'""')}"`}
  function download(filename, content, mime){const blob=new Blob([content],{type:mime});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
  function exportJobs(){const heads=['company','title','location','sector','stage','season','opportunity_signal','personal_assessment','hourly_min','hourly_max','pay_basis','comparison','score','focus','employer_posted_at','first_seen_at','first_seen','job_status','application_status','source','url'];const rows=visible.map(j=>[j.company,j.title,j.location,j.sector,j.stage,j.season,opportunityAssessment(j).label,tracking[j.id]?.opportunityReview||'',j.pay?.hourly_min??'',j.pay?.hourly_max??'',j.pay?.basis||'',comparePay(j).tier,j.score,(j.focus||[]).join('; '),j.posted_at||'',j.first_seen_at||'',j.first_seen,j.status,tracking[j.id]?.status||'',j.source,j.url]);download('internship-radar-jobs.csv','\ufeff'+[heads,...rows].map(row=>row.map(csvEscape).join(',')).join('\r\n'),'text/csv;charset=utf-8')}
  function exportTracking(){download('biodata-radar-private-tracking.json',JSON.stringify({version:1,exportedAt:new Date().toISOString(),tracking},null,2),'application/json')}
  async function importTracking(file){if(!file)return;try{if(file.size>5_000_000)throw Error('File is too large');const parsed=JSON.parse(await file.text());if(parsed.version!==1 || !parsed.tracking || typeof parsed.tracking!=='object'||Array.isArray(parsed.tracking))throw Error('Not a BioData Radar backup');const entries=Object.entries(parsed.tracking);if(entries.length>10000)throw Error('Too many entries');for(const [id,v] of entries){if(!id||typeof v!=='object'||v===null||!STATUSES.includes(v.status||'Not started'))throw Error('Invalid tracking entry')};if(!confirm(`Import ${entries.length} tracking entries? Existing entries with the same job IDs will be replaced.`))return;tracking={...tracking,...parsed.tracking};persist();render();alert('Tracking restored on this browser.')}catch(e){alert('Could not import backup: '+e.message)}finally{$('import-tracking').value=''}}
  function wire(){
    const menu=$('comparison-state');
    menu.innerHTML='<option value="">Choose a state</option>'+Object.entries(STATE_RPP)
      .sort((a,b)=>a[1][0].localeCompare(b[1][0]))
      .map(([code,details])=>`<option value="${code}">${esc(details[0])}</option>`).join('');
    $('comparison-hourly').value=comparison.hourly||'';
    menu.value=comparison.state;
    $('comparison-hourly').addEventListener('change',()=>{
      const entered=Number($('comparison-hourly').value);
      comparison.hourly=entered>0 && entered<500?entered:null;
      saveComparison();renderComparison();renderDiscover();
    });
    menu.addEventListener('change',()=>{
      comparison.state=menu.value;
      saveComparison();renderComparison();renderDiscover();
    });
    $('comparison-clear').addEventListener('click',()=>{
      comparison={hourly:null,state:''};
      $('comparison-hourly').value='';menu.value='';
      try{localStorage.removeItem(COMPARISON_KEY)}catch{}
      renderComparison();renderDiscover();
    });
    renderComparison();
    document.querySelectorAll('.nav-button').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));
    ['filter-search','filter-posted','filter-recency','filter-focus','filter-state','filter-location','filter-sort','filter-pay','filter-stage','filter-season','filter-opportunity'].forEach(id=>$(id).addEventListener(id==='filter-search'?'input':'change',()=>{shownLimit=100;renderDiscover();}));
    $('job-list').addEventListener('click',e=>{if(e.target.closest('#more-jobs')){shownLimit+=100;renderDiscover();}});
    [$('job-list'),$('application-list')].forEach(el=>{
      el.addEventListener('change',e=>{const id=e.target?.dataset?.status;if(!id)return;const job=allKnownJobs().find(j=>j.id===id);if(job)setStatus(job,e.target.value)});
      el.addEventListener('click',e=>{const button=e.target.closest('[data-detail]');if(button)openDetail(button.dataset.detail)})
    });
    $('company-search').addEventListener('input',()=>{companyLimit=150;renderCompanies()});
    $('company-ats').addEventListener('change',()=>{companyLimit=150;renderCompanies()});
    $('company-more').addEventListener('click',()=>{companyLimit+=150;renderCompanies()});
    $('add-manual').addEventListener('click',()=>$('manual-dialog').showModal());
    $('close-manual').addEventListener('click',()=>$('manual-dialog').close());
    $('manual-form').addEventListener('submit',e=>{
      e.preventDefault();
      const url=$('manual-url').value.trim();if(safeUrl(url)==='#'){alert('Use a valid HTTPS employer posting URL.');return;}
      const id='manual:'+Date.now()+'-'+Math.random().toString(36).slice(2,8);
      const meta={id,company:$('manual-company').value.trim(),title:$('manual-title').value.trim(),
          location:$('manual-location').value.trim()||'Not listed',url,sector:'Manual',focus:[],score:0,
          first_seen:new Date().toISOString().slice(0,10)};
      if(!meta.company||!meta.title)return;
      tracking[id]={status:'Saved',note:$('manual-note').value,appliedAt:'',changedAt:new Date().toISOString(),meta};
      persist();$('manual-form').reset();$('manual-dialog').close();render();
    });
    $('download-jobs').addEventListener('click',exportJobs);
    $('export-tracking').addEventListener('click',exportTracking);
    $('import-tracking').addEventListener('change',e=>importTracking(e.target.files[0]));
  }
  async function start(){
    comparison=loadComparison();
    wire();
    const responses=await Promise.allSettled([fetch('data/jobs.json',{cache:'no-store'}),fetch('config/companies.json',{cache:'no-store'}),fetch('data/board_catalog.json',{cache:'no-store'})]);
    if(responses[0].status==='fulfilled' && responses[0].value.ok){try{data=await responses[0].value.json()}catch{}}
    if(responses[1].status==='fulfilled' && responses[1].value.ok){try{config=await responses[1].value.json()}catch{}}
    if(responses[2].status==='fulfilled' && responses[2].value.ok){try{catalog=await responses[2].value.json()}catch{}}
    if(responses.some(x=>x.status==='rejected'||!x.value?.ok)){$('sync-text').textContent='Could not load feed · open through a web server';$('sync-dot').classList.add('warn')}
    const priorities=['Biostatistics / Statistical Programming','Statistics / Statistical Methods','Epidemiology / RWE / HEOR','Bioinformatics / Computational Biology','Data Science / ML','Analytics / BI','Data Engineering','Applied Research / Modeling','Strategy / Consulting'];
    const focuses=[...new Set(data.jobs.flatMap(j=>j.focus||[]))].sort((a,b)=>{
      const ai=priorities.indexOf(a),bi=priorities.indexOf(b);
      return (ai<0?99:ai)-(bi<0?99:bi)||a.localeCompare(b);
    });
    $('filter-focus').innerHTML='<option value="">All disciplines</option>'+focuses.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
    render();
  }
  start();
})();
