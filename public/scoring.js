(function (root, factory) {
  const scoring = factory();
  if (typeof module === 'object' && module.exports) module.exports = scoring;
  else root.HireloomScoring = scoring;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function atsScoreForProfile(profile = {}) {
    const hasText = (value) => String(value || '').trim().length > 0;
    const experiences = Array.isArray(profile.experience) ? profile.experience : [];
    const educationEntries = Array.isArray(profile.educationEntries) ? profile.educationEntries : [];
    const skills = Array.isArray(profile.skills) ? profile.skills.filter(skill => typeof skill === 'string' && hasText(skill)) : [];
    let score = 67;
    if (hasText(profile.name)) score += 4;
    if (hasText(profile.email)) score += 4;
    if (hasText(profile.phone)) score += 3;
    if (experiences.some((item) => item && Object.values(item).some(hasText))) score += 8;
    if (educationEntries.some((item) => item && Object.values(item).some(hasText)) || hasText(profile.education)) score += 5;
    if (new Set(skills.map((skill) => skill.trim().toLowerCase())).size >= 3) score += 7;
    return Math.min(98, score);
  }
  function workModePenalty(preferredModes, jobMode) {
    const preferences = Array.isArray(preferredModes) ? preferredModes : [];
    if (!jobMode || !preferences.length || ['Flexible', 'Not listed'].includes(jobMode) || preferences.includes(jobMode)) return 0;
    return -6;
  }
  const strings = value => Array.isArray(value) ? value.filter(v => typeof v === 'string' && v.trim()) : [];
  const clean = value => String(value || '').normalize('NFKC').toLowerCase()
    .replace(/\bjs\b/g,'javascript').replace(/\bts\b/g,'typescript').replace(/\bk8s\b/g,'kubernetes')
    .replace(/\bsr\b\.?/g,'senior').replace(/\bjr\b\.?/g,'junior');
  function mentions(text, term) {
    const literal = clean(term).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return !!literal && new RegExp('(?:^|[^\\p{L}\\p{N}+#])'+literal+'(?:$|[^\\p{L}\\p{N}+#])','u').test(clean(text));
  }
  const ignored = new Set('a an the at to of in for with and or our your you will on as by from is are be a new team teams role position roles work working who their this we all job jobs m f d'.split(' '));
  function words(value) {
    return [...new Set((clean(value).match(/[\p{L}\p{N}+#]+/gu)||[]).filter(w=>!ignored.has(w)))];
  }
  function titleCoverage(required, actual) {
    const tokens = words(required);
    return tokens.length ? tokens.filter(term=>mentions(actual,term)).length/tokens.length : 0;
  }
  const monthNames='jan feb mar apr may jun jul aug sep oct nov dec'.split(' ');
  function employmentMonths(dates, today) {
    const match=String(dates||'').trim().match(/^(?:(\w+)\s+)?(\d{4})\s*(?:[-–—]|to)\s*(?:(?:(\w+)\s+)?(\d{4})|(present|current|now|ongoing))$/i);
    if(!match)return null;
    const month=s=>s?monthNames.indexOf(s.slice(0,3).toLowerCase()):0;
    const startMonth=month(match[1]),endMonth=month(match[3]);
    if(startMonth<0||endMonth<0)return null;
    const current=today.getUTCFullYear()*12+today.getUTCMonth();
    const start=Number(match[2])*12+startMonth;
    const end=match[5]?current:Math.min(current,Number(match[4])*12+endMonth+(match[3]?1:0));
    return start<end?[start,end]:null;
  }
  function relatedMonths(entries,title,skills,today) {
    const role=clean(title).replace(/\b(?:junior|senior|staff|lead|principal|intern|entry[- ]level)\b/g,' ');
    const spans=entries.filter(e=>skills.length
      ? skills.every(skill=>mentions(e.title,skill)||mentions(e.detail,skill))
      : titleCoverage(role,e.title)>=0.5)
      .map(e=>employmentMonths(e.dates,today)).filter(Boolean).sort((a,b)=>a[0]-b[0]);
    let total=0,lastEnd=0;
    for(const [start,end] of spans){
      total+=Math.max(0,end-Math.max(start,lastEnd));
      lastEnd=Math.max(lastEnd,end);
    }
    return total;
  }

  function jdMatch(job={}, profile={}, today=new Date()) {
    const experience=(Array.isArray(profile.experience)?profile.experience:[]).filter(e=>e&&typeof e==='object');
    const background=[profile.summary,...strings(profile.achievements),...experience.map(e=>e.detail)].filter(Boolean);
    const evidence=[...strings(profile.skills),...background,...experience.map(e=>e.title)];
    const credentials=strings(profile.certifications);
    const rows=[];
    const signals=job.jdSignals;
    const excerpts=job.jdRequirements||{};
    const tags=[...new Set(strings(job.skills))];
    const excerptSkills=group=>tags.filter(tag=>strings(excerpts[group]).some(line=>mentions(line,tag)));
    const required=signals?strings(signals.requiredSkills):excerptSkills('required');
    const preferred=(signals?strings(signals.preferredSkills):excerptSkills('preferred')).filter(v=>!required.includes(v));
    function checkRow(label,weight,terms,check) {
      if(!terms.length)return;
      const matches=terms.filter(check);
      const missing=terms.filter(term=>!matches.includes(term));
      rows.push({label,weight,fraction:matches.length/terms.length,
        detail:[matches.length?'CV evidence: '+matches.join(', '):'',missing.length?'No evidence found: '+missing.join(', '):''].filter(Boolean).join('. ')});
    }
    const hasEvidence=term=>evidence.some(text=>mentions(text,term));
    checkRow('Required skills',40,required,hasEvidence);
    if(!signals&&!required.length&&!preferred.length)checkRow('Mentioned skills (older listing)',15,tags,hasEvidence);
    const title=String(job.title||'').trim();
    const entryRole=signals?.minYears===0||/\b(?:intern(?:ship)?|trainee|fresher|new grad(?:uate)?|entry[- ]level)\b/i.test(title);
    if(words(title).length&&(!entryRole||experience.some(e=>e.title))){
      let best=0,source='';
      for(const entry of experience){
        const coverage=titleCoverage(title,entry.title);
        if(coverage>best){best=coverage;source=entry.title;}
      }
      rows.push({label:'Role title',weight:20,fraction:best,
        detail:source?'Closest documented title: '+source+' · '+Math.round(best*100)+'% of posting title terms.':'No overlapping title found in work or internship history.'});
    }
    const legacyYears=String(job.years||'').match(/^(\d+)(?:\+|\s*[-–]\s*\d+)?\s*years?\b/i);
    const min=signals?signals.minYears:legacyYears?Number(legacyYears[1]):null;
    if(Number.isFinite(min)&&min>=0){
      const skills=strings(signals?.experienceSkills);
      const duration=relatedMonths(experience,title,skills,today);
      rows.push({label:'Relevant experience estimate',weight:25,fraction:min===0?1:Math.min(1,duration/(min*12)),
        detail:min===0?'The employer accepts zero prior experience.':min+' years requested. CV shows '+duration+' dated months in '+(skills.length?'roles mentioning '+skills.join(', '):'roles sharing at least half the role-title terms')+'.'+(signals?.experienceSource?' JD: '+signals.experienceSource:'')});
    }
    const qualifications=new Map();
    for(const cert of strings(signals?.credentials))qualifications.set(cert,credentials.some(t=>mentions(t,cert)));
    const entries=Array.isArray(profile.educationEntries)?profile.educationEntries:[];
    const education=entries.filter(Boolean).map(e=>[e.qualification,e.details].filter(Boolean).join(' '));
    if(!education.length&&profile.education)education.push(...String(profile.education).split(/\n/));
    const degrees={bachelor:/\b(?:bachelor|b\.?\s?(?:tech|sc|eng|com|a))\b/i,
      master:/\b(?:master|m\.?\s?(?:tech|sc|eng|ba|a))\b/i,phd:/\b(?:ph\.?d|doctorate)\b/i,doctorate:/\b(?:ph\.?d|doctorate)\b/i};
    for(const item of Array.isArray(signals?.degrees)?signals.degrees:[]){
      if(!Object.hasOwn(degrees,item?.level))continue;
      const field=words(item.field);
      qualifications.set([item.level,item.field].filter(Boolean).join(' in '),education.some(e=>
        degrees[item.level].test(e)&&field.every(term=>mentions(e,term))));
    }
    const languages=Array.isArray(profile.languageEntries)?profile.languageEntries:[];
    for(const name of strings(signals?.languages)){
      qualifications.set(name+' proficiency',languages.some(e=>e&&mentions(e.name,name)&&
        /^(?:fluent|native|bilingual|professional|proficient|advanced|C[12])\b/i.test(e.proficiency||'')));
    }
    checkRow('Education, credentials and languages',15,[...qualifications.keys()],term=>qualifications.get(term));
    const duties=strings(excerpts.responsibilities);
    const assessable=duties.map(line=>({line,terms:words(line).filter(t=>t.length>2)})).filter(d=>d.terms.length>=2);
    if(assessable.length){
      const matched=assessable.filter(d=>background.some(text=>d.terms.filter(t=>mentions(text,t)).length>=Math.max(2,Math.ceil(d.terms.length/2))));
      rows.push({label:'Responsibility wording',weight:10,fraction:matched.length/assessable.length,
        detail:matched.length+' of '+assessable.length+' employer duties have overlapping wording in a CV summary, achievement or work detail.'+
          (matched.length?' Example: '+matched[0].line:'')});
    }
    const total=rows.reduce((n,row)=>n+row.weight,0);
    const earned=rows.reduce((n,row)=>n+row.weight*row.fraction,0);
    const optional=preferred.filter(term=>evidence.some(text=>mentions(text,term)));
    const bonus=preferred.length?5*optional.length/preferred.length:0;
    const hasProfileEvidence=evidence.some(text=>typeof text==='string' && text.trim())||
      credentials.length>0||education.some(t=>t.trim())||languages.some(e=>e?.name);
    const score=total&&hasProfileEvidence?Math.min(100,Math.round(100*earned/total+bonus)):null;
    return {score,rows,total,earned,bonus,preferred,optional,legacy:!signals,hasProfileEvidence};
  }
  return { atsScoreForProfile, workModePenalty, jdMatch };
});
