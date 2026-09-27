// An API key field with an eye to show or hide it (PLAN 15.4.8); model profiles and the
// custom transcription endpoint both use it.
import { useState } from "react";

export function SecretInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const [shown, setShown] = useState(false);
  return (
    <label className="field">
      <span>{label}</span>
      <span className="secret">
        <input
          className="input"
          type={shown ? "text" : "password"}
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="button"
          className="eye"
          aria-label={shown ? `隐藏 ${label}` : `显示 ${label}`}
          aria-pressed={shown}
          onClick={() => setShown(!shown)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
            <circle cx="12" cy="12" r="2.8" />
            {!shown && <path d="M4 20 20 4" />}
          </svg>
        </button>
      </span>
    </label>
  );
}
