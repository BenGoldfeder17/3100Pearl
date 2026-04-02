import { useState, useEffect, useCallback } from "react";

const FLOOR_PLANS = {
  studios: [
    { id: "S1R", name: "S1R", type: "Studio", beds: 0, baths: 1, sqft: 573 },
  ],
  oneBed: [
    { id: "A1R", name: "A1R", type: "1 Bed", beds: 1, baths: 1, sqft: 636 },
    { id: "A2R", name: "A2R", type: "1 Bed", beds: 1, baths: 1, sqft: 702 },
    { id: "A3R", name: "A3R", type: "1 Bed", beds: 1, baths: 1, sqft: 716 },
    { id: "A4R", name: "A4R", type: "1 Bed", beds: 1, baths: 1, sqft: 774 },
    { id: "A5R", name: "A5R", type: "1 Bed", beds: 1, baths: 1, sqft: 812 },
  ],
};

const CONFIG = {
  maxRent: 2000,
  preferredRent: 1800,
  moveInAfter: "2025-07-01",
  address: "3100 Pearl St, Boulder, CO 80301",
  phone: "(844) 472-4270",
  website: "https://live3100pearl.com",
  checkAvail: "https://live3100pearl.com/check-availability/",
  aptsDotCom: "https://www.apartments.com/3100-pearl-boulder-co/rycnge1/",
};

function PriceTag({ price, preferred, max }) {
  if (!price) return <span style={styles.priceTBD}>TBD</span>;
  const isPref = price <= preferred;
  const isOk = price <= max;
  const color = isPref ? "#22c55e" : isOk ? "#eab308" : "#ef4444";
  const label = isPref ? "SWEET SPOT" : isOk ? "IN BUDGET" : "OVER";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ ...styles.priceAmount, color }}>${price.toLocaleString()}</span>
      <span style={{ ...styles.priceBadge, background: color + "18", color, border: `1px solid ${color}40` }}>
        {label}
      </span>
    </div>
  );
}

function StatusDot({ status }) {
  const map = {
    available: { color: "#22c55e", label: "Available", pulse: true },
    waitlist: { color: "#eab308", label: "Waitlist", pulse: false },
    unavailable: { color: "#64748b", label: "Unavailable", pulse: false },
    new: { color: "#3b82f6", label: "New!", pulse: true },
  };
  const s = map[status] || map.unavailable;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{
        width: 8, height: 8, borderRadius: "50%", background: s.color,
        boxShadow: s.pulse ? `0 0 8px ${s.color}60` : "none",
        animation: s.pulse ? "pulse 2s ease-in-out infinite" : "none",
      }} />
      <span style={{ fontSize: 11, color: s.color, fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
        {s.label}
      </span>
    </div>
  );
}

function UnitCard({ plan, unit }) {
  const hasDate = unit?.availableDate;
  const isJulyPlus = !hasDate || new Date(hasDate) >= new Date("2025-07-01");

  return (
    <div style={{
      ...styles.card,
      borderLeft: unit?.status === "available" ? "3px solid #22c55e" :
                  unit?.status === "new" ? "3px solid #3b82f6" : "3px solid #1e293b",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={styles.planName}>{plan.name}</div>
          <div style={styles.planType}>{plan.type} · {plan.baths} Bath · {plan.sqft} SF</div>
        </div>
        <StatusDot status={unit?.status || "unavailable"} />
      </div>

      <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <PriceTag
            price={unit?.price}
            preferred={CONFIG.preferredRent}
            max={CONFIG.maxRent}
          />
          {hasDate && (
            <div style={{ marginTop: 4, fontSize: 12, color: isJulyPlus ? "#94a3b8" : "#ef4444" }}>
              Available {new Date(hasDate).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              {!isJulyPlus && " (before July)"}
            </div>
          )}
          {unit?.unitNum && (
            <div style={{ marginTop: 2, fontSize: 11, color: "#64748b" }}>Unit {unit.unitNum}</div>
          )}
        </div>
        {unit?.status === "available" && (
          <a href={CONFIG.checkAvail} target="_blank" rel="noopener noreferrer"
             style={styles.applyBtn}>
            Apply →
          </a>
        )}
      </div>
    </div>
  );
}

function LogEntry({ time, message, type }) {
  const colors = { info: "#94a3b8", success: "#22c55e", warn: "#eab308", error: "#ef4444", new: "#3b82f6" };
  return (
    <div style={{ display: "flex", gap: 8, fontSize: 12, fontFamily: "'JetBrains Mono', 'SF Mono', monospace", padding: "4px 0" }}>
      <span style={{ color: "#475569", minWidth: 55 }}>{time}</span>
      <span style={{ color: colors[type] || "#94a3b8" }}>●</span>
      <span style={{ color: "#cbd5e1" }}>{message}</span>
    </div>
  );
}

export default function Dashboard() {
  const [lastScan, setLastScan] = useState(null);
  const [scanCount, setScanCount] = useState(0);
  const [isScanning, setIsScanning] = useState(false);
  const [units, setUnits] = useState([]);
  const [logs, setLogs] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [tab, setTab] = useState("all");

  const addLog = useCallback((message, type = "info") => {
    const now = new Date();
    const time = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
    setLogs(prev => [{ time, message, type, id: Date.now() }, ...prev].slice(0, 50));
  }, []);

  const simulateScan = useCallback(async () => {
    setIsScanning(true);
    addLog("Starting scan across all sources...", "info");

    await new Promise(r => setTimeout(r, 800));
    addLog("Checking apartments.com...", "info");
    await new Promise(r => setTimeout(r, 600));
    addLog("Checking apartmentfinder.com...", "info");
    await new Promise(r => setTimeout(r, 500));
    addLog("Checking live3100pearl.com...", "info");
    await new Promise(r => setTimeout(r, 700));

    // Simulate dynamic availability
    const now = new Date();
    const possibleUnits = [
      { planId: "S1R", price: 1745 + Math.floor(Math.random() * 200), availableDate: "2025-07-01", status: "available", unitNum: "108", source: "apartments.com" },
      { planId: "S1R", price: 1789 + Math.floor(Math.random() * 150), availableDate: "2025-08-01", status: "available", unitNum: "215", source: "live3100pearl.com" },
      { planId: "A1R", price: 1850 + Math.floor(Math.random() * 200), availableDate: "2025-07-15", status: "available", unitNum: "312", source: "apartments.com" },
      { planId: "A2R", price: 1920 + Math.floor(Math.random() * 150), availableDate: "2025-07-01", status: "available", unitNum: "204", source: "apartmentfinder.com" },
      { planId: "A3R", price: 1980 + Math.floor(Math.random() * 100), availableDate: "2025-08-15", status: "available", unitNum: "410", source: "apartments.com" },
      { planId: "A4R", price: null, availableDate: null, status: "waitlist", unitNum: null, source: "live3100pearl.com" },
      { planId: "A5R", price: 2050, availableDate: "2025-07-01", status: "unavailable", unitNum: null, source: "" },
    ];

    // Randomly include/exclude some units to simulate changes
    const active = possibleUnits.filter(() => Math.random() > 0.25);

    // Mark new units
    const prevIds = new Set(units.map(u => u.planId + u.unitNum));
    const withNew = active.map(u => ({
      ...u,
      status: !prevIds.has(u.planId + u.unitNum) && u.status === "available" && scanCount > 0
        ? "new" : u.status,
    }));

    const newCount = withNew.filter(u => u.status === "new").length;
    const matchCount = withNew.filter(u =>
      (u.status === "available" || u.status === "new") && u.price && u.price <= CONFIG.maxRent
    ).length;

    setUnits(withNew);
    setLastScan(now);
    setScanCount(c => c + 1);
    setIsScanning(false);

    addLog(`Scan complete — ${active.length} listings found`, "success");
    if (matchCount > 0) addLog(`${matchCount} unit(s) match your filters`, "success");
    if (newCount > 0) addLog(`🆕 ${newCount} NEW unit(s) detected!`, "new");
    if (matchCount === 0) addLog("No matching units found this scan", "warn");
  }, [addLog, units, scanCount]);

  useEffect(() => {
    simulateScan();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(simulateScan, 30000);
    return () => clearInterval(id);
  }, [autoRefresh, simulateScan]);

  const allPlans = [...FLOOR_PLANS.studios, ...FLOOR_PLANS.oneBed];
  const filteredPlans = tab === "studio" ? FLOOR_PLANS.studios :
                        tab === "1bed" ? FLOOR_PLANS.oneBed : allPlans;

  const matchingUnits = units.filter(u =>
    (u.status === "available" || u.status === "new") && u.price && u.price <= CONFIG.maxRent
  );
  const preferredUnits = matchingUnits.filter(u => u.price <= CONFIG.preferredRent);

  return (
    <div style={styles.root}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Outfit:wght@300;400;500;600;700&display=swap');
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes scanline { 0% { transform: translateY(-100%); } 100% { transform: translateY(100vh); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
      `}</style>

      {/* Header */}
      <div style={styles.header}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={styles.logo}>
            <span style={{ fontSize: 20 }}>🏠</span>
          </div>
          <div>
            <h1 style={styles.title}>3100 PEARL</h1>
            <div style={styles.subtitle}>Availability Monitor · Boulder, CO</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            style={{
              ...styles.toggleBtn,
              background: autoRefresh ? "#22c55e18" : "#1e293b",
              borderColor: autoRefresh ? "#22c55e40" : "#334155",
              color: autoRefresh ? "#22c55e" : "#64748b",
            }}
          >
            {autoRefresh ? "⏸ Auto" : "▶ Auto"}
          </button>
          <button
            onClick={simulateScan}
            disabled={isScanning}
            style={{
              ...styles.scanBtn,
              opacity: isScanning ? 0.6 : 1,
            }}
          >
            {isScanning ? "⏳ Scanning..." : "🔍 Scan Now"}
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div style={styles.statsBar}>
        <div style={styles.stat}>
          <div style={styles.statValue}>{matchingUnits.length}</div>
          <div style={styles.statLabel}>Matches</div>
        </div>
        <div style={styles.statDivider} />
        <div style={styles.stat}>
          <div style={{ ...styles.statValue, color: "#22c55e" }}>{preferredUnits.length}</div>
          <div style={styles.statLabel}>Under $1,800</div>
        </div>
        <div style={styles.statDivider} />
        <div style={styles.stat}>
          <div style={styles.statValue}>{scanCount}</div>
          <div style={styles.statLabel}>Scans</div>
        </div>
        <div style={styles.statDivider} />
        <div style={styles.stat}>
          <div style={{ ...styles.statValue, fontSize: 13 }}>
            {lastScan ? lastScan.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }) : "—"}
          </div>
          <div style={styles.statLabel}>Last Scan</div>
        </div>
      </div>

      {/* Filter Banner */}
      <div style={styles.filterBanner}>
        <span style={styles.filterChip}>Studio + 1BR</span>
        <span style={styles.filterChip}>≤ $2,000/mo</span>
        <span style={styles.filterChip}>July 1+</span>
        <span style={{ ...styles.filterChip, background: "#22c55e18", color: "#22c55e", borderColor: "#22c55e40" }}>
          🟢 ≤$1,800 preferred
        </span>
      </div>

      {/* Tabs */}
      <div style={styles.tabs}>
        {[
          { key: "all", label: "All Plans", count: allPlans.length },
          { key: "studio", label: "Studios", count: FLOOR_PLANS.studios.length },
          { key: "1bed", label: "1 Bedroom", count: FLOOR_PLANS.oneBed.length },
        ].map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              ...styles.tab,
              borderBottomColor: tab === t.key ? "#3b82f6" : "transparent",
              color: tab === t.key ? "#e2e8f0" : "#64748b",
            }}
          >
            {t.label} <span style={styles.tabCount}>{t.count}</span>
          </button>
        ))}
      </div>

      {/* Units Grid */}
      <div style={styles.grid}>
        {filteredPlans.map(plan => {
          const planUnits = units.filter(u => u.planId === plan.id);
          if (planUnits.length === 0) {
            return <UnitCard key={plan.id} plan={plan} unit={null} />;
          }
          return planUnits.map((u, i) => (
            <UnitCard key={`${plan.id}-${i}`} plan={plan} unit={u} />
          ));
        })}
      </div>

      {/* Quick Links */}
      <div style={styles.linksRow}>
        <a href={CONFIG.website} target="_blank" rel="noopener noreferrer" style={styles.link}>
          🌐 Official Site
        </a>
        <a href={CONFIG.checkAvail} target="_blank" rel="noopener noreferrer" style={styles.link}>
          📋 Check Availability
        </a>
        <a href={CONFIG.aptsDotCom} target="_blank" rel="noopener noreferrer" style={styles.link}>
          🏢 Apartments.com
        </a>
        <a href={`tel:${CONFIG.phone.replace(/\D/g, "")}`} style={styles.link}>
          📞 {CONFIG.phone}
        </a>
      </div>

      {/* Activity Log */}
      <div style={styles.logSection}>
        <div style={styles.logHeader}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#94a3b8", letterSpacing: "0.05em" }}>ACTIVITY LOG</span>
          <button onClick={() => setLogs([])} style={styles.clearBtn}>Clear</button>
        </div>
        <div style={styles.logBody}>
          {logs.length === 0 ? (
            <div style={{ color: "#475569", fontSize: 12, fontStyle: "italic", padding: 12 }}>No activity yet</div>
          ) : (
            logs.map(l => <LogEntry key={l.id} {...l} />)
          )}
        </div>
      </div>

      {/* Setup Instructions */}
      <div style={styles.setupSection}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#94a3b8", letterSpacing: "0.05em", marginBottom: 12 }}>
          PYTHON BOT SETUP
        </div>
        <div style={{ fontSize: 12, color: "#64748b", lineHeight: 1.7, fontFamily: "'Space Mono', monospace" }}>
          <div style={{ color: "#94a3b8", marginBottom: 4 }}># Run once</div>
          <div style={{ color: "#e2e8f0" }}>python 3100pearl_monitor.py</div>
          <div style={{ color: "#94a3b8", marginTop: 8, marginBottom: 4 }}># Watch mode (every 30 min)</div>
          <div style={{ color: "#e2e8f0" }}>python 3100pearl_monitor.py --watch</div>
          <div style={{ color: "#94a3b8", marginTop: 8, marginBottom: 4 }}># Custom interval (15 min)</div>
          <div style={{ color: "#e2e8f0" }}>python 3100pearl_monitor.py --watch 15</div>
          <div style={{ color: "#94a3b8", marginTop: 8, marginBottom: 4 }}># Crontab (every 30 min)</div>
          <div style={{ color: "#e2e8f0" }}>*/30 * * * * /usr/bin/python3 ~/3100pearl_monitor.py</div>
        </div>
      </div>

      <div style={{ textAlign: "center", padding: "16px 0", fontSize: 11, color: "#334155" }}>
        Dashboard simulates scan results · Pair with Python backend for live data
      </div>
    </div>
  );
}

const styles = {
  root: {
    minHeight: "100vh",
    background: "linear-gradient(180deg, #0c1222 0%, #0f172a 100%)",
    color: "#e2e8f0",
    fontFamily: "'Outfit', -apple-system, sans-serif",
    padding: "0 16px 32px",
    maxWidth: 680,
    margin: "0 auto",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "20px 0 16px",
    borderBottom: "1px solid #1e293b",
  },
  logo: {
    width: 40, height: 40, borderRadius: 10,
    background: "linear-gradient(135deg, #1e3a5f, #0f2440)",
    display: "flex", alignItems: "center", justifyContent: "center",
    border: "1px solid #1e4976",
  },
  title: {
    fontSize: 18, fontWeight: 700, letterSpacing: "0.08em",
    fontFamily: "'Space Mono', monospace",
    background: "linear-gradient(135deg, #e2e8f0, #94a3b8)",
    WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
  },
  subtitle: { fontSize: 11, color: "#64748b", marginTop: 2, letterSpacing: "0.02em" },
  scanBtn: {
    padding: "8px 16px", borderRadius: 8, border: "1px solid #3b82f640",
    background: "#3b82f618", color: "#60a5fa", fontSize: 12, fontWeight: 600,
    cursor: "pointer", fontFamily: "'Outfit', sans-serif", transition: "all 0.2s",
  },
  toggleBtn: {
    padding: "8px 12px", borderRadius: 8, border: "1px solid",
    fontSize: 11, fontWeight: 600, cursor: "pointer",
    fontFamily: "'Outfit', sans-serif", transition: "all 0.2s",
  },
  statsBar: {
    display: "flex", alignItems: "center", justifyContent: "space-around",
    padding: "16px 0", borderBottom: "1px solid #1e293b",
  },
  stat: { textAlign: "center" },
  statValue: { fontSize: 22, fontWeight: 700, fontFamily: "'Space Mono', monospace", color: "#e2e8f0" },
  statLabel: { fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 },
  statDivider: { width: 1, height: 32, background: "#1e293b" },
  filterBanner: {
    display: "flex", flexWrap: "wrap", gap: 8, padding: "14px 0",
    borderBottom: "1px solid #1e293b",
  },
  filterChip: {
    padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 500,
    background: "#1e293b", color: "#94a3b8", border: "1px solid #334155",
  },
  tabs: {
    display: "flex", gap: 0, borderBottom: "1px solid #1e293b", marginTop: 4,
  },
  tab: {
    padding: "12px 16px", border: "none", borderBottom: "2px solid",
    background: "none", fontSize: 13, fontWeight: 500, cursor: "pointer",
    fontFamily: "'Outfit', sans-serif", transition: "all 0.2s",
  },
  tabCount: {
    fontSize: 10, background: "#1e293b", padding: "1px 6px",
    borderRadius: 10, marginLeft: 6, color: "#64748b",
  },
  grid: {
    display: "flex", flexDirection: "column", gap: 10, padding: "16px 0",
  },
  card: {
    background: "#111827", borderRadius: 10, padding: "14px 16px",
    border: "1px solid #1e293b", transition: "all 0.2s",
    animation: "fadeIn 0.3s ease-out",
  },
  planName: {
    fontSize: 16, fontWeight: 700, fontFamily: "'Space Mono', monospace",
    color: "#f1f5f9",
  },
  planType: { fontSize: 12, color: "#64748b", marginTop: 2 },
  priceAmount: { fontSize: 20, fontWeight: 700, fontFamily: "'Space Mono', monospace" },
  priceTBD: {
    fontSize: 14, color: "#475569", fontStyle: "italic",
    fontFamily: "'Space Mono', monospace",
  },
  priceBadge: {
    fontSize: 9, fontWeight: 700, padding: "2px 8px",
    borderRadius: 4, letterSpacing: "0.08em", textTransform: "uppercase",
  },
  applyBtn: {
    padding: "6px 14px", borderRadius: 6, background: "#22c55e18",
    color: "#22c55e", fontSize: 12, fontWeight: 600, textDecoration: "none",
    border: "1px solid #22c55e40", transition: "all 0.2s",
  },
  linksRow: {
    display: "flex", flexWrap: "wrap", gap: 8, padding: "8px 0 16px",
    borderBottom: "1px solid #1e293b",
  },
  link: {
    padding: "6px 12px", borderRadius: 6, background: "#1e293b",
    color: "#94a3b8", fontSize: 11, textDecoration: "none",
    border: "1px solid #334155", transition: "all 0.2s",
  },
  logSection: {
    marginTop: 16, background: "#0a0f1a", borderRadius: 10,
    border: "1px solid #1e293b", overflow: "hidden",
  },
  logHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "10px 14px", borderBottom: "1px solid #1e293b",
  },
  logBody: { padding: "8px 14px", maxHeight: 200, overflowY: "auto" },
  clearBtn: {
    padding: "2px 8px", borderRadius: 4, border: "1px solid #334155",
    background: "none", color: "#475569", fontSize: 10, cursor: "pointer",
    fontFamily: "'Outfit', sans-serif",
  },
  setupSection: {
    marginTop: 16, padding: 16, background: "#0a0f1a",
    borderRadius: 10, border: "1px solid #1e293b",
  },
};
