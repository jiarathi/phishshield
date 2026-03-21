import { useMemo, useState } from "react";

const API_ENDPOINT = "http://127.0.0.1:8000/api/analyze";

// Threshold mapping (tune later)
const THRESH_WARNING = 0.5;
const THRESH_DANGER = 0.75;

// Adapter: map the new "sophisticated" backend response schema into the legacy UI shape
function adaptBackendResponse(raw) {
  if (!raw || typeof raw !== "object") return raw;

  // If it already looks like the legacy shape, return as-is.
  if (typeof raw.spam_score === "number" || raw.overall_risk_score != null || Array.isArray(raw.urls)) {
    return raw;
  }

  // New backend shape: { risk_label, risk_score, is_scam, summary, reasons, url_findings, model, intent, ... }
  const riskScore = typeof raw.risk_score === "number" ? raw.risk_score : 0;
  const riskLabel = typeof raw.risk_label === "string" ? raw.risk_label : "unknown";

  const urlFindings = Array.isArray(raw.url_findings) ? raw.url_findings : [];
  const urls = urlFindings.map((u) => ({
    url: u?.url ?? "",
    final_url_risk_level: (u?.risk_label ?? "unknown").toString(),
    final_url_risk_score: typeof u?.risk_score === "number" ? u.risk_score : null,
  }));

  const signals = Array.isArray(raw.reasons) ? raw.reasons : [];
  const signalsStr = signals.length ? signals.join("; ") : "";

  const urlSummary = `URL analysis found ${urls.length} link(s); highest URL risk level is '${(urls[0]?.final_url_risk_level || "unknown").toLowerCase()}'.`;
  const explanation = `${raw.summary ? raw.summary : "Analysis completed."} Signals: ${signalsStr}${signalsStr ? "." : ""} ${urlSummary} Model risk_score=${safeFixed(riskScore)}.`;

  return {
    spam_score: riskScore,
    overall_risk_score: riskScore,
    overall_risk_label: riskLabel,
    explanation,
    urls,
    // keep the raw payload too, in case UI wants it later
    _raw: raw,
  };
}


const brandData = {
  usps: {
    name: "USPS / FedEx / UPS",
    icon: "fa-truck",
    color: "text-blue-900",
    safe: [
      "Tracking numbers entered on official websites.",
      "Emails from verified domains (e.g., @usps.com) ONLY if you signed up for alerts.",
    ],
    danger: [
      "Texts about 'suspended deliveries' asking for a small fee ($0.30) to redeliver.",
      "Links to 'usps-track-package.com' or other unofficial URLs.",
      "Requests for credit card info via text to release a package.",
    ],
    advice:
      "USPS will NEVER send a text message asking for a redelivery fee or personal information. If you didn't request a text update specifically, it is a scam.",
  },
  amazon: {
    name: "Amazon",
    icon: "fa-box-open",
    color: "text-yellow-600",
    safe: ["Notifications inside the official Amazon App.", "Emails confirming orders you actually placed."],
    danger: [
      "Calls claiming a suspicious iPhone/MacBook purchase was made on your account.",
      "Requests to buy gift cards to pay for 'account unlocking'.",
      "Links asking you to login to verify your identity.",
    ],
    advice:
      "Amazon will not call you about suspicious activity unexpectedly. Never pay over the phone. Always check 'Your Orders' on the real Amazon.com website/app.",
  },
  bank: {
    name: "Banks (Chase, Wells Fargo, etc.)",
    icon: "fa-building-columns",
    color: "text-red-600",
    safe: ["Alerts you set up for low balances.", "Two-factor codes you REQUESTED while logging in."],
    danger: [
      "Texts asking, 'Did you spend $500?' followed by a call asking for your login code/PIN.",
      "Requests to Zelle money to 'yourself' to reverse fraud.",
      "URL links in texts claiming your account is locked.",
    ],
    advice:
      "Banks NEVER ask for your PIN, password, or one-time login code over the phone or text. If unsure, hang up and call the number on the back of your card.",
  },
  irs: {
    name: "IRS / Government",
    icon: "fa-landmark",
    color: "text-slate-700",
    safe: ["Letters sent via postal mail."],
    danger: [
      "Any text message claiming to be the IRS.",
      "Threats of immediate arrest or lawsuit.",
      "Demands for payment via gift card, crypto, or wire transfer.",
    ],
    advice:
      "The IRS does not initiate contact with taxpayers by email, text messages, or social media channels to request personal or financial information.",
  },
  netflix: {
    name: "Netflix / Streaming Services",
    icon: "fa-play",
    color: "text-red-600",
    safe: ["In-app notifications on your TV or verified login."],
    danger: [
      "Texts saying 'Payment Failed' or 'Membership Expired' with a link.",
      "Asking for payment info via email.",
    ],
    advice: "Go directly to Netflix.com (type it in your browser) to check your account status. Never click links in 'payment failed' texts.",
  },
  tech: {
    name: "Microsoft / Apple Tech Support",
    icon: "fa-laptop-medical",
    color: "text-blue-500",
    safe: ["Support you initiated via official channels."],
    danger: [
      "Pop-ups on your computer saying 'VIRUS DETECTED' with a phone number.",
      "Calls claiming your IP address is compromised.",
    ],
    advice: "Tech companies will never contact you out of the blue to fix your computer. Real virus warnings never ask you to call a phone number.",
  },
};

function scoreToStatus(score) {
  const s = typeof score === "number" ? score : 0;
  if (s >= THRESH_DANGER) return "danger";
  if (s >= THRESH_WARNING) return "warning";
  return "safe";
}

// Map backend label -> UI status
function labelToStatus(label) {
  const l = (label || "").toLowerCase();
  if (l === "high") return "danger";
  if (l === "medium") return "warning";
  if (l === "low") return "safe";
  return null;
}

function statusCopy(status) {
  if (status === "danger") {
    return {
      border: "border-red-500",
      box: "bg-red-50 border-red-200 text-red-900",
      icon: "fa-triangle-exclamation text-red-600",
      title: "High Risk Detected",
      message: "This message is likely a scam. Do not click links or reply.",
    };
  }
  if (status === "warning") {
    return {
      border: "border-orange-500",
      box: "bg-orange-50 border-orange-200 text-orange-900",
      icon: "fa-circle-exclamation text-orange-600",
      title: "Suspicious - Proceed with Caution",
      message:
        "This message looks suspicious based on text patterns. Verify independently via the official app/site (type the address yourself).",
    };
  }
  return {
    border: "border-green-500",
    box: "bg-green-50 border-green-200 text-green-900",
    icon: "fa-check-circle text-green-600",
    title: "Low Risk Detected",
    message:
      "No strong scam signals detected. Still be cautious with unexpected links and never share codes/passwords.",
  };
}

function formatLabel(label) {
  const l = (label || "").toLowerCase();
  if (!l) return "N/A";
  return l.toUpperCase();
}

function safeFixed(n) {
  return typeof n === "number" && Number.isFinite(n) ? n.toFixed(2) : "n/a";
}

function parseSignalsFromExplanation(explanation) {
  // Attempts to extract the "Signals: ..." portion into bullets.
  // Expected pattern: "... Signals: A; B; C. URL analysis found ..."
  if (!explanation || typeof explanation !== "string") return [];
  const idx = explanation.indexOf("Signals:");
  if (idx === -1) return [];

  let tail = explanation.slice(idx + "Signals:".length).trim();

  // Stop before "URL analysis" if present
  const stopIdx = tail.indexOf("URL analysis");
  if (stopIdx !== -1) tail = tail.slice(0, stopIdx).trim();

  // Strip trailing punctuation
  tail = tail.replace(/\.\s*$/, "").trim();

  const parts = tail.split(";").map((s) => s.trim()).filter(Boolean);
  return parts;
}

function pickRecommendedAction(status) {
  if (status === "danger") {
    return {
      title: "Recommended action",
      bullets: [
        "Do not click links or reply.",
        "If this claims to be a bank/brand, call the official number (card/app/website).",
        "Forward suspicious texts to 7726 (SPAM) and report to the FTC if needed.",
      ],
    };
  }
  if (status === "warning") {
    return {
      title: "Recommended action",
      bullets: [
        "Do not click the link if this message was unexpected.",
        "Open the official app or type the official website address yourself.",
        "If it mentions money, passwords, codes, or account verification — treat as high risk.",
      ],
    };
  }
  return {
    title: "Recommended action",
    bullets: [
      "If you were expecting this message, it’s likely okay.",
      "Still avoid sharing passwords or verification codes.",
      "When unsure, verify via the official app/site rather than clicking links.",
    ],
  };
}

export default function App() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [scamInput, setScamInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null); // { status, triggers[], raw }
  const [copyFeedback, setCopyFeedback] = useState(false);

  const [brandSearch, setBrandSearch] = useState("");
  const [activeBrandKey, setActiveBrandKey] = useState(null);

  const filteredBrandKeys = useMemo(() => {
    const q = brandSearch.trim().toLowerCase();
    const keys = Object.keys(brandData);
    if (!q) return keys;
    return keys.filter((k) => {
      const d = brandData[k];
      return (d.name + " " + d.safe.join(" ") + " " + d.danger.join(" ")).toLowerCase().includes(q);
    });
  }, [brandSearch]);

  const activeBrand = activeBrandKey ? brandData[activeBrandKey] : null;

  async function analyzeText() {
    const input = scamInput.trim();
    if (!input) return;

    setLoading(true);
    setResult(null);

    try {
      const res = await fetch(API_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // IMPORTANT: your backend expects "text"
        body: JSON.stringify({ text: input }),
      });

      if (!res.ok) {
        const body = await res.text();
        throw new Error(`Server Error (${res.status}): ${body.substring(0, 120)}`);
      }

      const raw = await res.json();
      const data = adaptBackendResponse(raw);

      const spamScore = typeof data.spam_score === "number" ? data.spam_score : 0;
      const overallScore = typeof data.overall_risk_score === "number" ? data.overall_risk_score : null;
      const overallLabel = typeof data.overall_risk_label === "string" ? data.overall_risk_label : null;

      // STATUS: prefer overall label/score; fallback to spam_score for backward compatibility
      const statusFromLabel = labelToStatus(overallLabel);
      const statusFromScore = scoreToStatus(overallScore ?? spamScore);
      const status = statusFromLabel ?? statusFromScore;

      // Build clean triggers instead of 1 giant blob
      const triggers = [];

      // Summary line (short)
      const summaryLine = `Overall risk: ${overallLabel ? overallLabel : "n/a"} (${safeFixed(overallScore)}), ML spam_score=${safeFixed(spamScore)}`;
      triggers.push(summaryLine);

      // Signals from explanation (bulletized)
      const signalBullets = parseSignalsFromExplanation(data.explanation);
      if (signalBullets.length > 0) {
        triggers.push("Signals detected:");
        signalBullets.forEach((s) => triggers.push(`• ${s}`));
      }

      // URL summary (short)
      if (Array.isArray(data.urls) && data.urls.length > 0) {
        triggers.push(`Links found: ${data.urls.length}`);
        data.urls.slice(0, 3).forEach((u) => {
          const lvl = (u?.final_url_risk_level || "unknown").toUpperCase();
          const s = safeFixed(u?.final_url_risk_score);
          triggers.push(`• ${lvl} (${s}) — ${u?.url}`);
        });
        if (data.urls.length > 3) triggers.push(`• …and ${data.urls.length - 3} more`);
      } else {
        triggers.push("Links found: 0");
      }

      // Keep explanation narrative as its own line (not a blob)
      if (data.explanation) {
        triggers.push("Explanation:");
        triggers.push(data.explanation);
      }

      setResult({ status, triggers, raw: data });
    } catch (e) {
      setResult({
        status: "danger",
        triggers: [
          "Could not connect to backend or response format changed.",
          `Check that FastAPI is running and reachable at: ${API_ENDPOINT}`,
          String(e?.message || e),
        ],
        raw: null,
      });
    } finally {
      setLoading(false);
    }
  }

  function clearInput() {
    setScamInput("");
    setResult(null);
  }

  async function copyFor7726() {
    const text = scamInput.trim();
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // fallback
      const temp = document.createElement("textarea");
      temp.value = text;
      document.body.appendChild(temp);
      temp.select();
      document.execCommand("copy");
      document.body.removeChild(temp);
    }

    setCopyFeedback(true);
    setTimeout(() => setCopyFeedback(false), 2500);
  }

  const resultBox = result ? statusCopy(result.status) : null;

  const action = result ? pickRecommendedAction(result.status) : null;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navigation */}
      <nav className="bg-brand-900 text-white shadow-lg sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <i className="fa-solid fa-shield-halved text-3xl text-brand-500"></i>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">ScamShield</h1>
              <p className="text-xs text-brand-100 hidden sm:block">Consumer Protection Assistant</p>
            </div>
          </div>

          <div className="hidden md:flex space-x-6 text-lg font-medium">
            <a href="#analyzer" className="hover:text-brand-100 transition">Analyzer</a>
            <a href="#playbooks" className="hover:text-brand-100 transition">Brand Guides</a>
            <a href="#report" className="hover:text-brand-100 transition">Report Scam</a>
          </div>

          <button className="md:hidden text-2xl" onClick={() => setMobileMenuOpen((v) => !v)}>
            <i className="fa-solid fa-bars"></i>
          </button>
        </div>

        {mobileMenuOpen && (
          <div className="bg-brand-800 md:hidden p-4">
            <a href="#analyzer" className="block py-2 text-white font-medium border-b border-brand-700">Analyzer</a>
            <a href="#playbooks" className="block py-2 text-white font-medium border-b border-brand-700">Brand Guides</a>
            <a href="#report" className="block py-2 text-white font-medium">Report Scam</a>
          </div>
        )}
      </nav>

      {/* Hero */}
      <header className="bg-white border-b border-slate-200">
        <div className="container mx-auto px-4 py-12 text-center max-w-4xl">
          <h2 className="text-3xl md:text-5xl font-bold text-brand-900 mb-6 leading-tight">
            Not sure if that message is safe?
          </h2>
          <p className="text-lg md:text-xl text-slate-600 mb-8 leading-relaxed">
            Paste suspicious texts, emails, or links below. Our AI-powered tool scans for hidden danger signs to keep you safe.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <a
              href="#analyzer"
              className="bg-brand-600 hover:bg-brand-700 text-white font-bold py-4 px-8 rounded-full shadow-lg transition transform hover:-translate-y-1 text-lg flex items-center"
            >
              <i className="fa-solid fa-magnifying-glass mr-2"></i> Check a Message
            </a>
            <a
              href="#playbooks"
              className="bg-white hover:bg-slate-50 text-brand-700 border-2 border-brand-200 font-bold py-4 px-8 rounded-full shadow transition text-lg flex items-center"
            >
              <i className="fa-solid fa-book-open mr-2"></i> Browse Safety Guides
            </a>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-grow container mx-auto px-4 py-12 space-y-20">
        {/* Analyzer */}
        <section id="analyzer" className="scroll-mt-24">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 p-6 border-b border-slate-200 flex justify-between items-center flex-wrap gap-4">
              <h3 className="text-2xl font-bold text-brand-900 flex items-center">
                <i className="fa-solid fa-robot text-brand-600 mr-3"></i> Message Analyzer
              </h3>
              <div className="text-sm text-slate-500 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
                <i className="fa-solid fa-lock text-green-500 mr-1"></i> Private & Secure Analysis
              </div>
            </div>

            <div className="p-6 md:p-8">
              <label htmlFor="scamInput" className="block text-lg font-semibold text-slate-700 mb-2">
                Paste the text message, email content, or link here:
              </label>

              <textarea
                id="scamInput"
                rows={6}
                className="w-full p-4 text-lg border-2 border-slate-300 rounded-xl focus:ring-4 focus:ring-brand-100 focus:border-brand-500 transition outline-none resize-none mb-6"
                placeholder="e.g. 'USPS: Your package delivery has been suspended. Click here to update address...'"
                value={scamInput}
                onChange={(e) => setScamInput(e.target.value)}
              />

              <div className="flex flex-col md:flex-row gap-4">
                <button
                  onClick={analyzeText}
                  disabled={loading}
                  className="flex-1 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white text-xl font-bold py-4 px-6 rounded-xl shadow-md transition flex justify-center items-center"
                >
                  {loading ? "Running..." : "Run Safety Check"}
                </button>

                <button
                  onClick={clearInput}
                  className="md:w-auto w-full bg-slate-100 hover:bg-slate-200 text-slate-600 font-semibold py-4 px-6 rounded-xl transition"
                >
                  Clear
                </button>
              </div>

              {/* Result */}
              {result && (
                <div className="mt-8">
                  <div
                    className={`border-l-8 ${resultBox.border} ${resultBox.box} p-6 rounded-r-xl shadow-sm`}
                  >
                    <div className="flex items-start">
                      <i className={`fa-solid ${resultBox.icon} text-4xl mr-4 mt-1`}></i>
                      <div className="flex-1">
                        <h4 className="text-2xl font-bold mb-2">{resultBox.title}</h4>
                        <p className="text-lg leading-relaxed">{resultBox.message}</p>

                        {/* NEW: structured “analysis breakdown” panel */}
                        {result.raw && (
                          <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-4">
                            <div className="bg-white/70 p-4 rounded-lg border">
                              <p className="font-bold text-sm uppercase opacity-70 mb-2">
                                Analysis Breakdown
                              </p>

                              <div className="flex flex-wrap gap-2 mb-3">
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-white border">
                                  Overall: {formatLabel(result.raw.overall_risk_label)} ({safeFixed(result.raw.overall_risk_score)})
                                </span>
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-white border">
                                  ML score: {safeFixed(result.raw.spam_score)}
                                </span>
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-white border">
                                  Links: {Array.isArray(result.raw.urls) ? result.raw.urls.length : 0}
                                </span>
                              </div>

                              <div className="text-sm text-slate-700">
                                <p className="font-semibold mb-1">Recommendation:</p>
                                <ul className="list-disc pl-5 space-y-1">
                                  {action?.bullets?.map((b, i) => (
                                    <li key={i}>{b}</li>
                                  ))}
                                </ul>
                              </div>
                            </div>

                            <div className="bg-white/70 p-4 rounded-lg border">
                              <p className="font-bold text-sm uppercase opacity-70 mb-2">Link Details</p>
                              {Array.isArray(result.raw.urls) && result.raw.urls.length > 0 ? (
                                <div className="space-y-3">
                                  {result.raw.urls.slice(0, 3).map((u, i) => (
                                    <div key={i} className="text-sm">
                                      <div className="font-semibold break-words">{u.url}</div>
                                      <div className="mt-1 flex flex-wrap gap-2">
                                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-white border">
                                          {String(u.final_url_risk_level || "unknown").toUpperCase()} ({safeFixed(u.final_url_risk_score)})
                                        </span>
                                        {u?.heuristic?.risk_level && (
                                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-white border">
                                            heuristic: {String(u.heuristic.risk_level).toUpperCase()}
                                          </span>
                                        )}
                                        {u?.reputation?.reputation_level && (
                                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-white border">
                                            reputation: {String(u.reputation.reputation_level).toUpperCase()}
                                          </span>
                                        )}
                                      </div>
                                      {Array.isArray(u?.heuristic?.reasons) && u.heuristic.reasons.length > 0 && (
                                        <div className="text-xs text-slate-600 mt-1">
                                          Reasons: {u.heuristic.reasons.join(", ")}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                  {result.raw.urls.length > 3 && (
                                    <div className="text-xs text-slate-600">
                                      …and {result.raw.urls.length - 3} more link(s).
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <div className="text-sm text-slate-700">No links detected.</div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Still keep “Why we flagged this”, but now it’s readable bullets */}
                        {result.triggers?.length > 0 && (
                          <div className="mt-5 bg-white/60 p-4 rounded-lg">
                            <p className="font-bold text-sm uppercase opacity-70 mb-2">Why we flagged this:</p>
                            <ul className="space-y-2">
                              {result.triggers.map((t, i) => {
                                const isSection = /:$/.test(t) || t === "Signals detected:" || t === "Explanation:";
                                const isBullet = t.startsWith("• ");
                                return (
                                  <li key={i} className={isSection ? "font-semibold" : isBullet ? "pl-4" : ""}>
                                    {isBullet ? <span className="mr-2">•</span> : null}
                                    {isBullet ? t.replace(/^•\s*/, "") : t}
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>

                    {result.status !== "safe" && (
                      <div className="mt-6 flex flex-col sm:flex-row gap-3">
                        <a
                          href="#report"
                          className="text-center bg-white border border-slate-300 hover:bg-slate-50 text-slate-800 font-bold py-2 px-4 rounded-lg transition"
                        >
                          How to Report This
                        </a>
                        <button
                          onClick={clearInput}
                          className="text-slate-500 hover:text-slate-700 font-medium py-2 px-4"
                        >
                          Check Another
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Report */}
        <section id="report" className="bg-brand-50 rounded-2xl p-8 md:p-12 border border-brand-100 scroll-mt-24">
          <h2 className="text-3xl font-bold text-brand-900 mb-6 text-center">Take Action</h2>
          <div className="grid md:grid-cols-2 gap-8">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-brand-100">
              <div className="flex items-center mb-4">
                <div className="bg-brand-100 text-brand-700 w-10 h-10 rounded-full flex items-center justify-center font-bold text-xl mr-3">1</div>
                <h3 className="text-xl font-bold text-slate-800">Report Text Messages</h3>
              </div>
              <p className="text-slate-600 mb-6">
                Forward the suspicious message to <strong>7726 (SPAM)</strong>. This helps your carrier block future attempts.
              </p>
              <button
                onClick={copyFor7726}
                className="w-full bg-white border-2 border-brand-500 text-brand-700 font-bold py-3 px-4 rounded-lg hover:bg-brand-50 transition flex items-center justify-center"
              >
                <i className="fa-regular fa-copy mr-2"></i> Copy Message to Clipboard
              </button>
              {copyFeedback && (
                <p className="text-center text-sm text-green-600 mt-2 font-semibold">
                  Copied! Now paste into a text to 7726.
                </p>
              )}
            </div>

            <div className="bg-white p-6 rounded-xl shadow-sm border border-brand-100">
              <div className="flex items-center mb-4">
                <div className="bg-brand-100 text-brand-700 w-10 h-10 rounded-full flex items-center justify-center font-bold text-xl mr-3">2</div>
                <h3 className="text-xl font-bold text-slate-800">Report to FTC</h3>
              </div>
              <p className="text-slate-600 mb-6">
                If you lost money or shared info, file a report with the Federal Trade Commission.
              </p>
              <a
                href="https://reportfraud.ftc.gov/"
                target="_blank"
                rel="noreferrer"
                className="block w-full bg-brand-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-brand-700 transition text-center"
              >
                Open FTC Report Assistant <i className="fa-solid fa-external-link-alt ml-2 text-sm"></i>
              </a>
            </div>
          </div>
        </section>

        {/* Playbooks */}
        <section id="playbooks" className="scroll-mt-24">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-brand-900 mb-4">Brand Safety Playbooks</h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              Specific advice for the most commonly impersonated companies. Select a brand to learn how they actually communicate.
            </p>
          </div>

          <div className="relative max-w-md mx-auto mb-10">
            <i className="fa-solid fa-search absolute left-4 top-1/2 transform -translate-y-1/2 text-slate-400"></i>
            <input
              type="text"
              value={brandSearch}
              onChange={(e) => setBrandSearch(e.target.value)}
              placeholder="Search brands (e.g. Amazon)..."
              className="w-full pl-12 pr-4 py-3 rounded-full border-2 border-slate-200 focus:border-brand-500 focus:outline-none text-lg shadow-sm"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredBrandKeys.map((key) => {
              const d = brandData[key];
              const badge =
                key === "usps" ? ["U", "bg-blue-900", "text-white"] :
                key === "amazon" ? ["A", "bg-yellow-500", "text-white"] :
                key === "bank" ? ["B", "bg-red-600", "text-white"] :
                key === "irs" ? ["I", "bg-slate-700", "text-white"] :
                key === "netflix" ? ["N", "bg-black", "text-red-600"] :
                ["T", "bg-blue-500", "text-white"];

              const subtitle =
                key === "usps"
                  ? "Common scams: “Delivery suspended”, “Address incomplete”, “Redelivery fee”."
                  : key === "amazon"
                  ? "Common scams: “Account locked”, “Suspicious purchase”, “Gift card”."
                  : key === "bank"
                  ? "Common scams: “Fraud alert”, “Verify identity”, “Zelle request”."
                  : key === "irs"
                  ? "Common scams: “Refund pending”, “Lawsuit threat”, “SSN suspended”."
                  : key === "netflix"
                  ? "Common scams: “Payment failed”, “Membership expired”, “Update payment info”."
                  : "Common scams: “Virus detected”, “Computer locked”, “Call support now”.";

              return (
                <div
                  key={key}
                  className="brand-card bg-white p-6 rounded-xl shadow-md border border-slate-100 hover:shadow-lg transition cursor-pointer"
                  onClick={() => setActiveBrandKey(key)}
                >
                  <div className="flex items-center mb-4">
                    <div className={`w-12 h-12 ${badge[1]} rounded-lg flex items-center justify-center ${badge[2]} font-bold text-xl mr-4`}>
                      {badge[0]}
                    </div>
                    <h4 className="text-xl font-bold text-slate-800">{d.name}</h4>
                  </div>
                  <p className="text-slate-600 mb-4">{subtitle}</p>
                  <span className="text-brand-600 font-semibold text-sm">View Safety Guide →</span>
                </div>
              );
            })}
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-300 py-12">
        <div className="container mx-auto px-4 text-center">
          <div className="mb-8">
            <i className="fa-solid fa-shield-halved text-4xl text-brand-500 mb-4"></i>
            <h3 className="text-2xl font-bold text-white">ScamShield</h3>
            <p className="max-w-md mx-auto mt-2 text-slate-400">
              Empowering consumers to spot scams and stay safe online. Built for seniors and high-risk groups.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl mx-auto text-sm border-t border-slate-800 pt-8">
            <div>
              <h4 className="font-bold text-white mb-2">Remember</h4>
              <p>Banks never ask for PINs via text.</p>
              <p>Government agencies don&apos;t email about refunds.</p>
            </div>
            <div>
              <h4 className="font-bold text-white mb-2">Resources</h4>
              <a href="https://www.consumer.ftc.gov/scams" target="_blank" rel="noreferrer" className="hover:text-white block">
                FTC Scam Alerts
              </a>
              <a href="https://www.aarp.org/money/scams-fraud/" target="_blank" rel="noreferrer" className="hover:text-white block">
                AARP Fraud Watch
              </a>
            </div>
            <div>
              <h4 className="font-bold text-white mb-2">Emergency</h4>
              <p>
                Identity Theft? Visit{" "}
                <a href="https://www.identitytheft.gov/" target="_blank" rel="noreferrer" className="text-brand-400 hover:underline">
                  IdentityTheft.gov
                </a>
              </p>
            </div>
          </div>

          <p className="mt-12 text-xs text-slate-600">
            © 2024 ScamShield Project. Not affiliated with any brands mentioned. For educational purposes only.
          </p>
        </div>
      </footer>

      {/* Brand Modal */}
      {activeBrand && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setActiveBrandKey(null);
          }}
        >
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl relative">
            <button
              onClick={() => setActiveBrandKey(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 text-2xl bg-slate-100 hover:bg-slate-200 rounded-full w-10 h-10 flex items-center justify-center transition"
            >
              ×
            </button>

            <div className="p-8">
              <div className="flex items-center mb-6 border-b border-slate-100 pb-4">
                <i className={`fa-solid ${activeBrand.icon} text-4xl ${activeBrand.color} mr-4`}></i>
                <h2 className="text-3xl font-bold text-slate-900">{activeBrand.name}</h2>
              </div>

              <div className="space-y-6">
                <div className="bg-red-50 p-5 rounded-xl border border-red-100">
                  <h3 className="text-red-800 font-bold text-lg mb-3 flex items-center">
                    <i className="fa-solid fa-ban mr-2"></i> Warning Signs (Scams)
                  </h3>
                  <ul className="list-disc pl-5 space-y-2 text-red-900">
                    {activeBrand.danger.map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                  </ul>
                </div>

                <div className="bg-green-50 p-5 rounded-xl border border-green-100">
                  <h3 className="text-green-800 font-bold text-lg mb-3 flex items-center">
                    <i className="fa-solid fa-check-circle mr-2"></i> Official Behavior (Safe)
                  </h3>
                  <ul className="list-disc pl-5 space-y-2 text-green-900">
                    {activeBrand.safe.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>

                <div className="bg-slate-100 p-5 rounded-xl">
                  <h3 className="font-bold text-slate-800 mb-2">Golden Rule:</h3>
                  <p className="text-slate-700 italic">"{activeBrand.advice}"</p>
                </div>
              </div>
            </div>

            <div className="bg-slate-50 p-6 border-t border-slate-200 text-center">
              <button
                onClick={() => setActiveBrandKey(null)}
                className="bg-slate-800 text-white font-bold py-3 px-8 rounded-lg hover:bg-slate-900 transition"
              >
                Close Guide
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
