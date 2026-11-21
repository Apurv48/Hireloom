(function (root, factory) {
  const scoring = factory();
  if (typeof module === 'object' && module.exports) module.exports = scoring;
  else root.HireloomScoring = scoring;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function atsScoreForProfile(profile = {}) {
    const hasText = (value) => String(value || '').trim().length > 0;
    const experiences = Array.isArray(profile.experience) ? profile.experience : [];
    const educationEntries = Array.isArray(profile.educationEntries) ? profile.educationEntries : [];
    const skills = Array.isArray(profile.skills) ? profile.skills.filter(hasText) : [];
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
    if (!preferences.length || ['Flexible', 'Not listed'].includes(jobMode) || preferences.includes(jobMode)) return 0;
    return -6;
  }
  return { atsScoreForProfile, workModePenalty };
});
