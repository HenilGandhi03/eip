export const CATEGORY_META = {
  ELECTIONS:  { label: 'Elections',  color: '#f0b429' },
  POLITICS:   { label: 'Politics',   color: '#8b5cf6' },
  ECONOMY:    { label: 'Economy',    color: '#00c98d' },
  PROTEST:    { label: 'Protest',    color: '#ff4757' },
  CONFLICT:   { label: 'Conflict',   color: '#ff4757' },
  LEGAL:      { label: 'Legal',      color: '#00d4ff' },
  DIPLOMACY:  { label: 'Diplomacy',  color: '#00c98d' },
  CLIMATE:    { label: 'Climate',    color: '#20bf6b' },
  RELIGION:   { label: 'Religion',   color: '#ff8c42' },
  OTHER:      { label: 'Other',      color: '#5a6380' },
  VERBAL_COOPERATION:     { label: 'Cooperation',  color: '#00c98d' },
  MATERIAL_COOPERATION:   { label: 'Aid/Material', color: '#00c98d' },
  PROVIDE_AID:            { label: 'Aid',          color: '#00c98d' },
  CONSULT:                { label: 'Consult',      color: '#8b5cf6' },
  DIPLOMATIC_COOPERATION: { label: 'Diplomacy',    color: '#8b5cf6' },
  ENGAGE_IN_NEGOTIATION:  { label: 'Negotiation',  color: '#8b5cf6' },
  APPEAL:                 { label: 'Appeal',       color: '#00d4ff' },
  DEMAND:                 { label: 'Demand',       color: '#f0b429' },
  DISAPPROVE:             { label: 'Disapproval',  color: '#f0b429' },
  REJECT:                 { label: 'Reject',       color: '#f0b429' },
  THREATEN:               { label: 'Threat',       color: '#ff8c42' },
  PROTEST:                { label: 'Protest',      color: '#ff4757' },
  EXHIBIT_MILITARY_POSTURE: { label: 'Military',   color: '#ff4757' },
  REDUCE_RELATIONS:       { label: 'Sanctions',    color: '#ff8c42' },
  COERCE:                 { label: 'Coercion',     color: '#ff4757' },
  ASSAULT:                { label: 'Assault',      color: '#ff4757' },
  FIGHT:                  { label: 'Fight',        color: '#ff4757' },
  USE_UNCONVENTIONAL_MASS_VIOLENCE: { label: 'Mass Violence', color: '#ff4757' },
}

export const ENTITY_COLORS = {
  politician:   '#f0b429',
  organization: '#8b5cf6',
  institution:  '#00d4ff',
  country:      '#00c98d',
  topic:        '#ff8c42',
  unknown:      '#5a6380',
}

export function getCatMeta(cat) {
  return CATEGORY_META[cat] || CATEGORY_META.OTHER
}

export function getEntityColor(type) {
  return ENTITY_COLORS[type] || ENTITY_COLORS.unknown
}

export function toneClass(tone) {
  if (tone == null) return 'tone-neutral'
  if (tone < -3) return 'tone-neg'
  if (tone > 2)  return 'tone-pos'
  return 'tone-neutral'
}

export function toneLabel(tone) {
  if (tone == null) return '—'
  return (tone > 0 ? '+' : '') + tone.toFixed(1)
}

export function confidenceColor(conf) {
  if (conf >= 0.7) return 'var(--green)'
  if (conf >= 0.4) return 'var(--gold)'
  return 'var(--red)'
}

export function initials(name = '') {
  return name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase()
}

export function formatDate(dateStr) {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleDateString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric'
    })
  } catch { return dateStr }
}
