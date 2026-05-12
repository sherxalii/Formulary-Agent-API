import React from 'react';
import { AlertTriangle, ShieldCheck } from 'lucide-react';

/* ── Form-specific SVG icons ── */
const DrugIcons = {
  Tablet: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <rect x="4" y="12" width="24" height="8" rx="4" fill="#1D9E75" />
      <rect x="4" y="12" width="12" height="8" rx="4" fill="#0F6E56" />
      <line x1="16" y1="12" x2="16" y2="20" stroke="#E1F5EE" strokeWidth="1.2" />
    </svg>
  ),
  Capsule: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <rect x="5" y="10" width="22" height="12" rx="6" fill="#F59E0B" />
      <rect x="5" y="10" width="11" height="12" rx="6" fill="#D97706" />
      <line x1="16" y1="10" x2="16" y2="22" stroke="#FEF3C7" strokeWidth="1" />
    </svg>
  ),
  Injection: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <rect x="14" y="4" width="4" height="6" rx="1" fill="#94A3B8" />
      <rect x="12" y="10" width="8" height="14" rx="2" fill="#3B82F6" />
      <rect x="14" y="24" width="4" height="4" rx="0.5" fill="#60A5FA" />
      <line x1="16" y1="28" x2="16" y2="30" stroke="#3B82F6" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="13" y1="14" x2="19" y2="14" stroke="#BFDBFE" strokeWidth="0.8" />
      <line x1="13" y1="17" x2="19" y2="17" stroke="#BFDBFE" strokeWidth="0.8" />
      <line x1="13" y1="20" x2="19" y2="20" stroke="#BFDBFE" strokeWidth="0.8" />
    </svg>
  ),
  Inhaler: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <rect x="10" y="14" width="12" height="14" rx="3" fill="#8B5CF6" />
      <rect x="12" y="6" width="8" height="10" rx="2" fill="#A78BFA" />
      <rect x="14" y="4" width="4" height="4" rx="1" fill="#C4B5FD" />
      <circle cx="16" cy="21" r="2" fill="#DDD6FE" opacity="0.7" />
    </svg>
  ),
  Solution: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <path d="M12 4h8v8l4 14a2 2 0 01-2 2H10a2 2 0 01-2-2l4-14V4z" fill="#06B6D4" />
      <path d="M10 22h12l2 4a2 2 0 01-2 2H10a2 2 0 01-2-2l2-4z" fill="#0891B2" opacity="0.6" />
      <rect x="13" y="2" width="6" height="3" rx="1" fill="#67E8F9" />
    </svg>
  ),
  Cream: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <rect x="8" y="12" width="16" height="16" rx="3" fill="#EC4899" />
      <rect x="10" y="8" width="12" height="6" rx="2" fill="#F472B6" />
      <rect x="13" y="5" width="6" height="4" rx="1.5" fill="#FBCFE8" />
      <rect x="11" y="20" width="10" height="2" rx="1" fill="#FDF2F8" opacity="0.5" />
    </svg>
  ),
  Drops: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <path d="M16 4L10 18a6 6 0 1012 0L16 4z" fill="#2563EB" />
      <ellipse cx="16" cy="20" rx="4" ry="3" fill="#3B82F6" opacity="0.5" />
      <circle cx="14" cy="17" r="1.5" fill="#BFDBFE" opacity="0.7" />
    </svg>
  ),
  Patch: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <rect x="6" y="8" width="20" height="16" rx="4" fill="#F97316" opacity="0.85" />
      <rect x="10" y="12" width="12" height="8" rx="2" fill="#FFEDD5" />
      <circle cx="14" cy="16" r="1" fill="#F97316" />
      <circle cx="18" cy="16" r="1" fill="#F97316" />
    </svg>
  ),
  Suppository: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <ellipse cx="16" cy="20" rx="6" ry="8" fill="#A855F7" />
      <path d="M13 12c0-3 1.5-6 3-8 1.5 2 3 5 3 8" fill="#C084FC" />
    </svg>
  ),
  Default: (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <rect x="4" y="12" width="24" height="8" rx="4" fill="#1D9E75" />
      <rect x="4" y="12" width="12" height="8" rx="4" fill="#0F6E56" />
      <line x1="16" y1="12" x2="16" y2="20" stroke="#E1F5EE" strokeWidth="1.2" />
    </svg>
  ),
};

const getDrugIcon = (form) => {
  if (!form) return DrugIcons.Default;
  const normalized = form.toLowerCase();
  if (normalized.includes('tablet')) return DrugIcons.Tablet;
  if (normalized.includes('capsule')) return DrugIcons.Capsule;
  if (normalized.includes('inject') || normalized.includes('syringe')) return DrugIcons.Injection;
  if (normalized.includes('inhal') || normalized.includes('aerosol')) return DrugIcons.Inhaler;
  if (normalized.includes('solution') || normalized.includes('syrup') || normalized.includes('liquid') || normalized.includes('suspension')) return DrugIcons.Solution;
  if (normalized.includes('cream') || normalized.includes('ointment') || normalized.includes('gel')) return DrugIcons.Cream;
  if (normalized.includes('drop')) return DrugIcons.Drops;
  if (normalized.includes('patch')) return DrugIcons.Patch;
  if (normalized.includes('suppository')) return DrugIcons.Suppository;
  return DrugIcons.Default;
};

import { motion } from 'framer-motion';

const DrugCard = React.memo(({ drug, onView, onBookmark, onRemove, bookmarked }) => {
  const subText = drug.genericName
    ? `${drug.genericName} • ${drug.form || 'N/A'}`
    : drug.form || 'N/A';

  const uses = drug.uses || [];
  const salt = drug.salt || drug.strength || "—";
  const drugClass = drug.drugClass || drug.class || "General";
  const drugId = drug.atcCode || drug.rxcui || "RX";
  const availability = drug.availability || (drug.isInsured ? 'Formulary' : 'Alternative');

  return (
    <motion.article 
      className="rx-card glass-card hover-lift" 
      role="article"
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4 }}
    >

      {/* ── Top ── */}
      <div className="rx-card-top" style={{ padding: '12px 14px', borderBottom: '1px solid #f8fafc' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
          <span className="rx-num" style={{ margin: 0, fontWeight: 700, color: '#94a3b8', fontSize: '10px' }}>{drugId}</span>
          <div style={{ display: 'flex', gap: '6px' }}>
            <span style={{ 
              fontSize: '10px', 
              fontWeight: 800, 
              padding: '2px 8px', 
              borderRadius: '4px', 
              background: availability === 'Formulary' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
              color: availability === 'Formulary' ? '#10b981' : '#f59e0b',
              textTransform: 'uppercase'
            }}>
              {availability}
            </span>
            {drugClass && drugClass.toLowerCase() !== availability.toLowerCase() && (
              <span style={{ 
                fontSize: '10px', 
                fontWeight: 700, 
                padding: '2px 8px', 
                borderRadius: '4px', 
                background: '#f1f5f9', 
                color: '#64748b',
                textTransform: 'uppercase'
              }}>
                {drugClass}
              </span>
            )}
          </div>
        </div>

        <div className="rx-icon-row" style={{ marginBottom: '8px', gap: '8px' }}>
          <div className="rx-pill-icon" style={{ width: '36px', height: '36px', minWidth: '36px', borderRadius: '8px' }}>
            {getDrugIcon(drug.form)}
          </div>
          <div style={{ overflow: 'hidden' }}>
            <h3 className="rx-drug-name" style={{ fontSize: '0.9rem', marginBottom: '0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {drug.name}
            </h3>
            <span className="rx-drug-sub" style={{ fontSize: '11px', color: '#94a3b8' }}>{subText}</span>
          </div>
        </div>

        {drug.safe && availability === 'Alternative' && (
          <div style={{ 
            display: 'inline-flex', 
            alignItems: 'center', 
            gap: '4px', 
            padding: '3px 8px', 
            background: 'linear-gradient(135deg, #16a085 0%, #10b981 100%)', 
            borderRadius: '100px',
            color: 'white',
            fontSize: '9px',
            fontWeight: 800,
            marginTop: '2px',
            boxShadow: '0 2px 8px rgba(22, 160, 133, 0.15)'
          }}>
            <ShieldCheck size={10} strokeWidth={3} />
            SAFEST ALTERNATIVE
          </div>
        )}
      </div>

      {/* ── Mid ── */}
      <div className="rx-card-mid">
        <div className="rx-field">
          <span className="rx-field-label">Active salt</span>
          <span className="rx-field-value">{salt}</span>
        </div>

        {uses.length > 0 && (
          <div className="rx-field">
            <span className="rx-field-label">Clinical use</span>
            <div className="rx-tags">
              {uses.map((use) => (
                <span key={use} className="rx-tag">{use}</span>
              ))}
            </div>
          </div>
        )}

        {/* Clinical Safety Metrics - New */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
          background: '#f8fafc',
          padding: '12px',
          borderRadius: '12px',
          marginBottom: '16px',
          border: '1px solid #edf2f7'
        }}>
          <div className="rx-field" style={{ marginBottom: 0 }}>
            <span className="rx-field-label">Safety Score</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: `conic-gradient(var(--accent-color) ${drug.safety_score || 0}%, #e2e8f0 0)`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.65rem',
                fontWeight: 800,
                position: 'relative',
                color: '#1e293b'
              }}>
                <div style={{
                  position: 'absolute',
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  background: 'white'
                }} />
                <span style={{ position: 'relative' }}>{drug.safety_score || 0}%</span>
              </div>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: (drug.safety_score || 0) > 80 ? '#10b981' : '#f59e0b' }}>
                {(drug.safety_score || 0) > 80 ? 'High Safety' : 'Review Alerts'}
              </span>
            </div>
          </div>

          <div className="rx-field" style={{ marginBottom: 0 }}>
            <span className="rx-field-label">ML Rating</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '6px' }}>
              <span style={{ fontSize: '1rem', fontWeight: 800, color: '#1e293b' }}>{drug.rating || 'N/A'}</span>
              <div style={{ display: 'flex', color: '#f59e0b' }}>
                {[...Array(5)].map((_, i) => (
                  <svg key={i} width="12" height="12" viewBox="0 0 24 24" fill={i < Math.floor(drug.rating / 2) ? "currentColor" : "none"} stroke="currentColor">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                  </svg>
                ))}
              </div>
            </div>
          </div>
        </div>

        {drug.pregnancy_safe === false && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            background: '#fff1f2',
            borderRadius: '8px',
            border: '1px solid #fecaca',
            marginBottom: '12px',
            color: '#be123c',
            fontSize: '0.75rem',
            fontWeight: 600
          }}>
            <AlertTriangle size={14} />
            Pregnancy Warning: Category risk detected
          </div>
        )}

        {drug.note && (
          <div className="rx-field">
            <span className="rx-field-label">Note</span>
            <span className="rx-field-value">{drug.note}</span>
          </div>
        )}
      </div>

      {/* ── Bottom ── */}
      <div className="rx-card-bot">
        {onView && (
          <button
            className="rx-btn-main"
            onClick={() => onView(drug.name)}
          >
            Quick Formulary
          </button>
        )}
        {onBookmark && (
          <button
            className={`rx-btn-icon${bookmarked ? " starred" : ""}`}
            onClick={() => onBookmark(drug)}
            aria-label={bookmarked ? "Remove bookmark" : "Add bookmark"}
          >
            <svg
              width="15"
              height="17"
              viewBox="0 0 13 15"
              fill={bookmarked ? "#1D9E75" : "none"}
              stroke={bookmarked ? "#0F6E56" : "currentColor"}
              strokeWidth="1.3"
              strokeLinejoin="round"
            >
              <path d="M1 1h11v13l-5.5-3.5L1 14V1z" />
            </svg>
          </button>
        )}
        {onRemove && (
          <button
            className="rx-btn-icon rx-btn-remove"
            onClick={() => onRemove(drug.name)}
            aria-label="Remove"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
      </div>

    </motion.article>
  );
});

export default DrugCard;

