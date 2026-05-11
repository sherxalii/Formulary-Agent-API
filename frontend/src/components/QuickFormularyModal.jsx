import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MdClose } from "react-icons/md";
import { AlertCircle, ShieldAlert, Activity, CheckCircle2, Info, BookOpen, Loader2 } from "lucide-react";
import { checkDrugSafety } from "../api/apiService";

const QuickFormularyModal = ({ open, onClose, drug }) => {
  const [safetyData, setSafetyData] = useState(null);
  const [loadingSafety, setLoadingSafety] = useState(false);

  useEffect(() => {
    if (open && drug) {
      const fetchSafety = async () => {
        setLoadingSafety(true);
        try {
          const res = await checkDrugSafety(drug.name || drug.drug_name);
          if (res.success && res.report) {
            setSafetyData(res.report);
          }
        } catch (err) {
          console.error("Failed to fetch safety info:", err);
        } finally {
          setLoadingSafety(false);
        }
      };
      fetchSafety();
    } else if (!open) {
      setSafetyData(null);
    }
  }, [open, drug]);

  if (!drug) return null;

  const isSafe = safetyData ? safetyData.safe : (drug.safe !== false);
  const isInsured = drug.covered === true || drug.isInsured === true || drug.availability === 'Formulary';

  const salt = drug.salt || drug.strength || drug.generic_name || drug.genericName || "-";
  const uses = drug.uses || drug.clinical_uses || [];
  const sideEffects = drug.sideEffects || drug.side_effects || [];
  const potential = drug.potential || drug.clinical_potential || "Standard therapeutic potential based on clinical guidelines.";
  const drugClass = drug.class || drug.drugClass || "General";

  const contraindications = safetyData?.risks || drug.contraindications || [];
  const alternatives = safetyData?.alternatives || drug.alternatives || [];


  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-backdrop"
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: "rgba(0,0,0,0.5)",
              backdropFilter: "blur(4px)",
              zIndex: 9998,
            }}
            onClick={onClose}
          />

          {/* Modal Content */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="quick-modal-card"
            style={{
              position: "fixed",
              top: "10%",
              left: "50%",
              transform: "translateX(-50%)",
              background: "#fff",
              padding: "2rem",
              borderRadius: "16px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
              width: "90%",
              maxWidth: "600px",
              zIndex: 9999,
              maxHeight: "80vh",
              overflowY: "auto"
            }}
          >
            <button
              onClick={onClose}
              style={{
                position: "absolute",
                top: "1rem",
                right: "1rem",
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: "8px",
                borderRadius: "50%",
                display: "flex",
              }}
              className="modal-close-btn"
            >
              <MdClose size={24} color="#6b7280" />
            </button>

            <div style={{ marginBottom: "1.5rem" }}>
              <div style={{display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap'}}>
                <h2 style={{ margin: 0, color: "#111827", fontSize: "1.5rem", fontWeight: 700 }}>
                  {drug.name || drug.drug_name}
                </h2>
                {isInsured ? (
                    <span style={{background: '#dcfce7', color: '#166534', padding: '4px 10px', borderRadius: 'full', fontSize: '0.875rem', fontWeight: 600}}>Formulary Covered</span>
                ) : (
                    <span style={{background: '#fee2e2', color: '#991b1b', padding: '4px 10px', borderRadius: 'full', fontSize: '0.875rem', fontWeight: 600}}>Not Covered</span>
                )}
              </div>
              
              <p style={{ margin: 0, color: "#6b7280", fontSize: "1rem" }}>
                {drug.genericName || drug.generic_name || "-"} • {drug.form || drug.medicine_form || "-"}
              </p>
              <p style={{ margin: "4px 0 0", color: "#4f46e5", fontSize: "0.875rem", fontWeight: 500 }}>
                {drugClass}
              </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
              <div style={{ background: "#f9fafb", padding: "12px", borderRadius: "8px" }}>
                <div style={{ fontSize: "0.75rem", color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>Active Salt</div>
                <div style={{ fontSize: "1rem", color: "#111827", marginTop: "4px" }}>{salt}</div>
              </div>
              <div style={{ background: "#f9fafb", padding: "12px", borderRadius: "8px" }}>
                 <div style={{ fontSize: "0.75rem", color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>ATC / RxNorm</div>
                <div style={{ fontSize: "1rem", color: "#111827", marginTop: "4px" }}>{drug.atc || drug.atcCode || drug.rxnorm || drug.rxcui || "Unknown"}</div>
              </div>
            </div>

            <div style={{ marginBottom: "1.5rem" }}>
              <h3 style={{ fontSize: "1.125rem", color: "#111827", display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                <Info size={20} color="#3b82f6" />
                Clinical Information
              </h3>
              <div style={{ background: "#eff6ff", padding: "16px", borderRadius: "8px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div>
                  <span style={{ fontWeight: 600, color: "#1e3a8a", fontSize: "0.875rem", display: "block", marginBottom: "4px" }}>Clinical Potential</span>
                  <span style={{ color: "#3b82f6", fontSize: "0.875rem", lineHeight: "1.4" }}>{potential}</span>
                </div>
                {uses.length > 0 && (
                  <div>
                    <span style={{ fontWeight: 600, color: "#1e3a8a", fontSize: "0.875rem", display: "block", marginBottom: "4px" }}>Common Uses</span>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {uses.map((u, i) => (
                        <span key={i} style={{ background: "#dbeafe", color: "#1d4ed8", padding: "2px 8px", borderRadius: "4px", fontSize: "0.75rem" }}>{u}</span>
                      ))}
                    </div>
                  </div>
                )}
                {sideEffects.length > 0 && (
                  <div>
                    <span style={{ fontWeight: 600, color: "#1e3a8a", fontSize: "0.875rem", display: "block", marginBottom: "4px" }}>Side Effects</span>
                    <ul style={{ margin: 0, paddingLeft: "20px", color: "#3b82f6", fontSize: "0.875rem" }}>
                      {sideEffects.map((se, i) => (
                        <li key={i}>{se}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            <div style={{ marginBottom: "1.5rem" }}>
              <h3 style={{ fontSize: "1.125rem", color: "#111827", display: "flex", alignItems: "center", gap: "8px" }}>
                <ShieldAlert size={20} color={isSafe ? "#10b981" : "#ef4444"} />
                Safety & Contraindications {loadingSafety && <Loader2 size={16} className="animate-spin" color="#3b82f6" />}
              </h3>
              
              {loadingSafety ? (
                <div style={{ padding: '12px', color: '#6b7280', fontSize: '0.875rem' }}>Analyzing safety profiles with ML models...</div>
              ) : contraindications.length === 0 ? (
                 <div style={{ display: "flex", alignItems: "center", gap: "8px", background: "#ecfdf5", color: "#065f46", padding: "12px", borderRadius: "8px", marginTop: "8px" }}>
                    <CheckCircle2 size={16} />
                    <span>No known contraindications for this patient.</span>
                 </div>
              ) : (
                <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "8px" }}>
                  {contraindications.map((ci, idx) => (
                    <div key={idx} style={{ 
                        background: ci.severity === "high" ? "#fee2e2" : "#fef3c7", 
                        borderLeft: `4px solid ${ci.severity === "high" ? "#ef4444" : "#f59e0b"}`,
                        padding: "12px", 
                        borderRadius: "0 8px 8px 0",
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "12px"
                    }}>
                        <AlertCircle size={20} color={ci.severity === "high" ? "#dc2626" : "#d97706"} style={{flexShrink: 0}} />
                        <div>
                            <div style={{ fontWeight: 600, color: ci.severity === "high" ? "#991b1b" : "#92400e", fontSize: "0.875rem" }}>
                                {ci.type ? ci.type.toUpperCase() + " ALERT" : "ALERT"}
                            </div>
                            <div style={{ color: ci.severity === "high" ? "#7f1d1d" : "#78350f", fontSize: "0.875rem", marginTop: "2px" }}>
                                {ci.message}
                            </div>
                        </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* AI Alternatives Section */}
            {(loadingSafety || !isSafe || !isInsured || alternatives.length > 0) && (
                <div style={{ marginTop: '2rem', borderTop: '1px solid #e5e7eb', paddingTop: '1.5rem' }}>
                    <h3 style={{ fontSize: "1.125rem", color: "#111827", display: "flex", alignItems: "center", gap: "8px", marginBottom: '1rem' }}>
                        <Activity size={20} color="#4f46e5" />
                        AI Suggested Alternatives
                    </h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                        {loadingSafety ? (
                          <div style={{ padding: '12px', color: '#6b7280', fontSize: '0.875rem' }}>Searching for safer formulary alternatives...</div>
                        ) : alternatives.length > 0 ? alternatives.map((alt, idx) => (
                            <div key={idx} style={{ border: '1px solid #e5e7eb', borderRadius: '8px', padding: '16px', background: '#f8fafc' }}>
                                <div style={{fontWeight: 600, color: '#111827', fontSize: '1rem'}}>{alt.drug_name || alt.name || alt.generic_name}</div>
                                <div style={{color: '#4b5563', fontSize: '0.875rem', marginTop: '4px'}}>{alt.reason || alt.note || "Suggested as a viable formulary alternative based on ML clustering."}</div>
                                {alt.rating && <div style={{fontSize: '0.75rem', color: '#1d9e75', marginTop: '4px'}}>Patient Satisfaction: {alt.rating}/10</div>}
                            </div>
                        )) : (
                          <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', padding: '16px', background: '#f8fafc' }}>
                              <div style={{color: '#4b5563', fontSize: '0.875rem'}}>No specific alternatives listed. Please consult with the prescriber for formulary equivalents.</div>
                          </div>
                        )}
                    </div>
                </div>
            )}

            
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default QuickFormularyModal;
