import {
  Banknote, BadgeCheck, Building, Building2, Cpu, FileText, Fingerprint, GitMerge, Landmark, Layers, Link2, MapPin,
  Phone, QrCode, ShoppingCart, Store, User, Wallet, type LucideIcon,
} from 'lucide-react'

export const ENTITY_ICONS: Record<string, LucideIcon> = {
  person: User,
  organisation: Building2,
  phone: Phone,
  bank_account: Landmark,
  upi: QrCode,
  imei: Cpu,
  crypto_wallet: Wallet,
  bank_branch: Building,
  bank_official: BadgeCheck,
  location: MapPin,
  document: FileText,
}

export const RULE_META: Record<string, { icon: LucideIcon; tone: string; short: string }> = {
  'CONVERGENCE-v1': { icon: GitMerge, tone: 'rule-money', short: 'Convergence' },
  'LAYERING-v1': { icon: Layers, tone: 'rule-money', short: 'Layering' },
  'CASHOUT-v1': { icon: Banknote, tone: 'rule-exit', short: 'Cash-out' },
  'FACILITATOR-v1': { icon: Building, tone: 'rule-bank', short: 'Facilitator' },
  'FRONT-ENTITY-v1': { icon: Store, tone: 'rule-bank', short: 'Front entity' },
  'SHARED-ID-v1': { icon: Link2, tone: 'rule-link', short: 'Shared identifier' },
  'MO-MATCH-v1': { icon: Fingerprint, tone: 'rule-link', short: 'Similar MO' },
  'ORDINARY-PAYMENT-v1': { icon: ShoppingCart, tone: 'rule-neutral', short: 'Ordinary payment' },
}

export function EntityIcon({ type, size = 14 }: { type: string; size?: number }) {
  const Icon = ENTITY_ICONS[type] ?? FileText
  return <Icon size={size} aria-hidden />
}

export function RuleIcon({ rule, size = 16 }: { rule: string; size?: number }) {
  const Icon = RULE_META[rule]?.icon ?? Link2
  return <Icon size={size} aria-hidden />
}
