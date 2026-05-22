"use client";

import { useState } from "react";
import type { HealthcareProfessional, Shift } from "@/lib/types";

interface Props {
  professional: HealthcareProfessional;
  shift:        Shift | null;
  listView?:    boolean;
}

function ScoreRing({ score }: { score: number }) {
  const size   = 52;
  const stroke = 4;
  const r      = (size - stroke) / 2;
  const circ   = 2 * Math.PI * r;
  const dash   = Math.min(score / 10, 1) * circ;
  const color  = score >= 7 ? "#1FC86E" : score >= 5 ? "#FCC804" : "#EC221F";
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#EDEDE8" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-bold leading-none text-livo-slate">{score.toFixed(1)}</span>
      </div>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 7 ? "bg-livo-success" : value >= 5 ? "bg-livo-warning" : "bg-livo-danger";
  return (
    <div className="flex items-center gap-2 min-w-0">
      <span className="text-xs text-livo-text-muted w-20 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-livo-bg-secondary rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-200`} style={{ width: `${value * 10}%` }} />
      </div>
      <span className="text-xs font-semibold text-livo-text-secondary w-6 text-right">{value.toFixed(1)}</span>
    </div>
  );
}

export default function ProfessionalCard({ professional: p, shift, listView }: Props) {
  const [msgOpen,  setMsgOpen]  = useState(false);
  const [copied,   setCopied]   = useState(false);
  const [phCopied, setPhCopied] = useState(false);

  const handleCopyMsg = async () => {
    if (!p.message_body) return;
    try { await navigator.clipboard.writeText(p.message_body); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch { /* ignore */ }
  };

  const handleCopyPhone = async () => {
    if (!p.phone) return;
    try { await navigator.clipboard.writeText(p.phone); setPhCopied(true); setTimeout(() => setPhCopied(false), 2000); } catch { /* ignore */ }
  };

  // WhatsApp direct link (removes non-digits)
  const whatsappLink = p.phone
    ? `https://wa.me/${p.phone.replace(/\D/g, "")}`
    : null;

  const firstName = p.name.split(" ")[0];

  if (listView) {
    return (
      <div className="bg-white border border-black/10 rounded-lg px-5 py-4 hover:shadow-card transition-shadow duration-200 flex items-center gap-4">
        <ScoreRing score={p.fit_score} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-livo-slate">{p.name}</span>
            {p.recommended && (
              <span className="px-2 py-0.5 bg-livo-primary-light text-livo-primary text-xs font-semibold rounded-full border border-livo-primary/20">
                Recomendado
              </span>
            )}
            <span className="px-2 py-0.5 bg-livo-bg-secondary text-livo-text-secondary text-xs font-semibold rounded-full">
              {p.role}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1 flex-wrap text-xs text-livo-text-muted">
            {p.shifts_at_facility > 0 && (
              <span>🏥 {p.shifts_at_facility} turno(s) en {p.facility_name ?? shift?.facility_name}</span>
            )}
            {p.last_shift_date && <span>📅 Último: {p.last_shift_date}</span>}
            {p.phone && (
              <button onClick={handleCopyPhone} className="text-livo-primary hover:text-livo-primary-hover transition-colors duration-200">
                📞 {phCopied ? "¡Copiado!" : p.phone}
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {p.message_body && (
            <button onClick={handleCopyMsg}
              className="text-xs px-3 py-1.5 rounded-full border border-black/10 text-livo-text-secondary hover:bg-livo-bg-page transition-colors duration-200">
              {copied ? "✓ Copiado" : "Copiar mensaje"}
            </button>
          )}
          {whatsappLink && (
            <a href={whatsappLink} target="_blank" rel="noopener noreferrer"
              className="text-xs px-3 py-1.5 rounded-full bg-[#25D366] text-white font-semibold hover:bg-[#1ebe57] transition-colors duration-200">
              WhatsApp ↗
            </a>
          )}
        </div>
      </div>
    );
  }

  // ── GRID CARD ───────────────────────────────────────────────────────────────
  return (
    <div className="bg-white rounded-lg border border-black/10 shadow-card hover:shadow-card-hover transition-shadow duration-200 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-5 pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-base font-bold text-livo-slate">{p.name}</span>
              {p.recommended && (
                <span className="px-2 py-0.5 bg-livo-primary-light text-livo-primary text-xs font-semibold rounded-full border border-livo-primary/20">
                  Recomendado
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="px-2 py-0.5 bg-livo-bg-secondary text-livo-text-secondary text-xs font-semibold rounded-full">
                {p.role}
              </span>
              {p.unit && (
                <span className="text-xs text-livo-text-muted">{p.unit}</span>
              )}
            </div>
          </div>
          <ScoreRing score={p.fit_score} />
        </div>
      </div>

      {/* Score bars */}
      <div className="px-5 py-2.5 bg-livo-bg-page border-y border-black/5 space-y-1.5">
        <ScoreBar label="Experiencia" value={p.experience_score} />
        <ScoreBar label="Disponibilidad" value={p.availability_score} />
      </div>

      {/* Shift history */}
      <div className="px-5 py-3 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-livo-text-muted uppercase tracking-wide">Historial en centro</span>
          <span className={`text-lg font-bold ${p.shifts_at_facility > 0 ? "text-livo-primary" : "text-livo-text-muted"}`}>
            {p.shifts_at_facility}
            <span className="text-xs font-normal ml-0.5">turnos</span>
          </span>
        </div>
        {p.shifts_in_unit > 0 && shift?.unit && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-livo-text-muted">En {shift.unit}</span>
            <span className="text-sm font-semibold text-livo-primary">{p.shifts_in_unit}</span>
          </div>
        )}
        {p.total_shifts > p.shifts_at_facility && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-livo-text-muted">Total en Livo</span>
            <span className="text-sm font-semibold text-livo-text-secondary">{p.total_shifts}</span>
          </div>
        )}
        {p.last_shift_date && (
          <div className="flex items-center gap-1.5 text-xs text-livo-text-muted">
            <span>📅</span>
            <span>Último turno: <span className="font-medium text-livo-text-secondary">{p.last_shift_date}</span></span>
          </div>
        )}
      </div>

      {/* Contact info */}
      {(p.phone || p.email) && (
        <div className="px-5 pb-3 flex items-center gap-3">
          {p.phone && (
            <button onClick={handleCopyPhone}
              className="flex items-center gap-1.5 text-xs text-livo-primary hover:text-livo-primary-hover transition-colors duration-200">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
              {phCopied ? "¡Copiado!" : p.phone}
            </button>
          )}
          {p.email && (
            <span className="text-xs text-livo-text-muted truncate">{p.email}</span>
          )}
        </div>
      )}

      {/* Rationale */}
      {p.scoring_rationale && (
        <div className="px-5 pb-3">
          <p className="text-xs text-livo-text-secondary leading-relaxed">{p.scoring_rationale}</p>
        </div>
      )}

      {/* WhatsApp message */}
      {p.message_body && (
        <div className="border-t border-black/5">
          <button onClick={() => setMsgOpen(!msgOpen)}
            className="w-full px-5 py-3 flex items-center justify-between text-sm font-medium text-livo-text-secondary hover:bg-livo-bg-page transition-colors duration-200">
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4 text-[#25D366]" fill="currentColor" viewBox="0 0 24 24">
                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
              </svg>
              Mensaje WhatsApp para {firstName}
            </span>
            <svg className={`w-4 h-4 text-livo-text-muted transition-transform duration-200 ${msgOpen ? "rotate-180" : ""}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {msgOpen && (
            <div className="px-5 pb-4 space-y-2">
              <div className="bg-livo-bg-page rounded-lg px-3 py-2.5">
                <p className="text-sm text-livo-text-secondary whitespace-pre-wrap leading-relaxed">{p.message_body}</p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={handleCopyMsg}
                  className="flex-1 py-1.5 px-3 rounded-full border border-black/10 text-xs font-medium text-livo-text-secondary hover:bg-livo-bg-page transition-colors duration-200 flex items-center justify-center gap-1.5">
                  {copied ? (
                    <><svg className="w-3.5 h-3.5 text-livo-success" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg><span className="text-livo-success">¡Copiado!</span></>
                  ) : (
                    <><svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>Copiar</>
                  )}
                </button>
                {whatsappLink && (
                  <a href={whatsappLink} target="_blank" rel="noopener noreferrer"
                    className="flex-1 py-1.5 px-3 rounded-full bg-[#25D366] text-white text-xs font-semibold text-center hover:bg-[#1ebe57] transition-colors duration-200">
                    Abrir en WhatsApp ↗
                  </a>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
