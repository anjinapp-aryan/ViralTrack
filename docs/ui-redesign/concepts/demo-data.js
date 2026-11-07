/* DESIGN CONCEPT DATA - SYNTHETIC (DEMO). Not observations. Approved fields only:
   raw views, likes (null = hidden by the creator), comments, published date, duration, creator name and
   follower count, plus the two ALLOWED derived values engagement rate (omitted when likes are hidden) and
   lifetime views per hour (display only, never a sort). No restricted metric appears anywhere. */
window.VT_DEMO = {
  readAt: "2026-11-07T10:42:00Z",
  videos: [
    { id: "d1", title: "3 ingredient dinner that actually works", creator: "Cooking Shorts Co", followers: 15000, views: 2600000, likes: 118000, comments: 4210, ageDays: 42, duration: 47, category: "Howto & Style", hue: 24 },
    { id: "d2", title: "AI automation nobody talks about", creator: "Mid Tech Review", followers: 48000, views: 1400000, likes: 61200, comments: 3120, ageDays: 1, duration: 1124, category: "Science & Technology", hue: 210 },
    { id: "d3", title: "History's strangest disappearance", creator: "Faceless History", followers: 9400, views: 1100000, likes: null, comments: 2870, ageDays: 18, duration: 1688, category: "Education", hue: 280 },
    { id: "d4", title: "I built an AI that invests for me", creator: "Neural Notes RU", followers: 3200, views: 529000, likes: 22400, comments: 1904, ageDays: 39, duration: 842, category: "Science & Technology", hue: 160 },
    { id: "d5", title: "AI agents just changed everything", creator: "Neural Notes RU", followers: 3200, views: 239000, likes: 9800, comments: 611, ageDays: 32, duration: 615, category: "Science & Technology", hue: 190 },
    { id: "d6", title: "This AI tool replaced my whole workflow", creator: "Tiny AI Lab", followers: 800, views: 225000, likes: 8100, comments: 402, ageDays: 61, duration: 731, category: "Science & Technology", hue: 330 },
    { id: "d7", title: "GPT-5 vs Claude: the honest test", creator: "Tiny AI Lab", followers: 800, views: 58000, likes: 2900, comments: 388, ageDays: 64, duration: 1302, category: "Science & Technology", hue: 45 },
    { id: "d8", title: "Local LLM on a laptop in 10 minutes", creator: "Tiny AI Lab", followers: 800, views: 49000, likes: 2600, comments: 171, ageDays: 2, duration: 603, category: "Science & Technology", hue: 120 }
  ],
  categories: [
    { name: "Science & Technology", views: 2500000, videos: 8 },
    { name: "Howto & Style", views: 2600000, videos: 3 },
    { name: "Education", views: 1100000, videos: 4 },
    { name: "Gaming", views: 532000, videos: 2 }
  ],
  uploadsByWeekday: [3, 5, 4, 6, 7, 2, 1]
};

window.VT_FMT = {
  compact(n) {
    if (n == null) return "—";
    if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, "") + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, "") + "K";
    return String(n);
  },
  duration(s) {
    if (s == null) return "—";
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = String(s % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${r}` : `${m}:${r}`;
  },
  age(d) { return d < 1 ? "today" : d === 1 ? "1 day ago" : d < 30 ? `${d} days ago` : `${Math.round(d / 30)} mo ago`; },
  /* ALLOWED derived value; null when likes are hidden (never counted as zero) */
  engagement(v) { return v.likes == null || !v.views ? null : ((v.likes + v.comments) / v.views * 100); },
  vphLifetime(v) { return v.ageDays ? Math.round(v.views / (v.ageDays * 24)) : null; }
};
