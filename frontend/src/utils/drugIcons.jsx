/**
 * drugIcons.jsx
 * Centralised, dynamic icon mapping for drug forms and categories.
 * Uses Lucide React (already installed as a dependency).
 *
 * API:
 *   getFormIcon(form: string)       → Lucide icon component (constructor)
 *   getCategoryIcon(category: str)  → Lucide icon component (constructor)
 *
 * Adding a new category: just add an entry to CATEGORY_ICON_MAP below.
 * The fallback (Stethoscope) will be used for anything not mapped.
 */

import {
  Pill,
  Syringe,
  Wind,
  FlaskConical,
  Layers,
  Droplets,
  Activity,
  Heart,
  Zap,
  Dna,
  Brain,
  ShieldCheck,
  Stethoscope,
  ClipboardList,
} from 'lucide-react';

// ─── Form → Icon ─────────────────────────────────────────────────────────────
const FORM_ICON_MAP = {
  tablet:    Pill,
  tablets:   Pill,
  capsule:   Layers,
  capsules:  Layers,
  injection: Syringe,
  injections:Syringe,
  inhaler:   Wind,
  inhalers:  Wind,
  solution:  FlaskConical,
  solutions: FlaskConical,
  liquid:    Droplets,
  syrup:     Droplets,
  drops:     Droplets,
  spray:     Wind,
  patch:     Activity,
  cream:     Activity,
  gel:       Activity,
  ointment:  Activity,
};

// ─── Category / class → Icon ──────────────────────────────────────────────────
const CATEGORY_ICON_MAP = {
  antibiotics:    ShieldCheck,
  antibiotic:     ShieldCheck,
  cardiovascular: Heart,
  cardiac:        Heart,
  pain:           Zap,
  analgesic:      Zap,
  diabetes:       Dna,
  diabetic:       Dna,
  respiratory:    Wind,
  neuro:          Brain,
  neurology:      Brain,
  psychiatric:    Brain,
  oncology:       Activity,
  general:        Stethoscope,
  all:            ClipboardList,
};

/**
 * Returns the Lucide icon **component** (not JSX) for a drug form string.
 * Falls back to Pill for unknown forms.
 */
export function getFormIcon(form) {
  if (!form) return Pill;
  const key = form.toLowerCase().trim();
  if (FORM_ICON_MAP[key]) return FORM_ICON_MAP[key];
  const partial = Object.keys(FORM_ICON_MAP).find((k) => key.includes(k));
  return partial ? FORM_ICON_MAP[partial] : Pill;
}

/**
 * Returns the Lucide icon **component** for a drug category / class string.
 * Falls back to Stethoscope for unknown categories.
 */
export function getCategoryIcon(category) {
  if (!category) return Stethoscope;
  const key = category.toLowerCase().trim();
  if (CATEGORY_ICON_MAP[key]) return CATEGORY_ICON_MAP[key];
  const partial = Object.keys(CATEGORY_ICON_MAP).find((k) => key.includes(k));
  return partial ? CATEGORY_ICON_MAP[partial] : Stethoscope;
}
