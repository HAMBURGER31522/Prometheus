// 设置 · 模型 (PLAN 15.4.8, 15.4.10; after CC Switch and ModelGate at a much smaller scale): several
// saved model profiles as cards, one of them in use; an editor with common platforms, the model
// list, the thinking levels the model supports, an eye on the key and 「高级」 limits.
import { useEffect, useRef, useState } from "react";

import { ApiError, type ModelInfo, type ModelProfile, type Settings, api } from "../../shared/api";
import { openExternal } from "../../shared/platform";
import { type Option, Select } from "../../shared/Select";
import { PRESETS, type Preset, presetFields, presetOf } from "./presets";
import { SecretInput } from "./SecretInput";
import { THINKING_HINT, clampThinking, thinkingLevels, thinkingOptions } from "./thinking";
import { visionOf } from "./vision";

type Profiles = Settings["llm_profiles"];

const KIND_LABELS: Record<ModelProfile["kind"], string> = { deepseek: "DeepSeek", zhipu: "智谱", custom: "自定义" };
const PROTOCOLS: Option<ModelProfile["protocol"]>[] = [
  { value: "openai", label: "OpenAI 兼容" },
  { value: "anthropic", label: "Anthropic" },
];

function blankProfile(): ModelProfile {
  return {
    id: `p-${Date.now().toString(36)}`, name: "", kind: "custom", base_url: "", protocol: "openai",
    api_key: "", model: "", supports_images: false, thinking: "medium", context_window: null, max_tokens: null,
  };
}

export function ModelProfiles({ profiles, onChange }: { profiles: Profiles; onChange: (next: Profiles) => void }) {
  const [editing, setEditing] = useState<ModelProfile | null>(null);
  const save = (profile: ModelProfile) => {
    const exists = profiles.items.some((item) => item.id === profile.id);
    const items = exists ? profiles.items.map((item) => (item.id === profile.id ? profile : item)) : [...profiles.items, profile];
    onChange({ ...profiles, items });
    setEditing(null);
  };
  const remove = (profile: ModelProfile) => {
    if (!window.confirm(`删除模型配置「${profile.name}」？`)) return;
    const items = profiles.items.filter((item) => item.id !== profile.id);
    onChange({ active: profiles.active === profile.id ? items[0].id : profiles.active, items });
  };

  return (
    <div className="profiles">
      <ul aria-label="模型配置" className="profile-list">
        {profiles.items.map((profile) => {
          const inUse = profile.id === profiles.active;
          return (
            <li key={profile.id} className="profile-card" data-active={inUse || undefined}>
              <div className="profile-main">
                <b>{profile.name || "未命名"}</b>
                <small>
                  {KIND_LABELS[profile.kind]}
                  {profile.kind === "custom" && ` · ${profile.protocol === "anthropic" ? "Anthropic" : "OpenAI"}`}
                  {" · "}
                  {profile.model || "未选模型"}
                </small>
              </div>
              <div className="row">
                {inUse ? (
                  <span className="badge accent">使用中</span>
                ) : (
                  <button type="button" className="btn small" onClick={() => onChange({ ...profiles, active: profile.id })}>
                    设为当前
                  </button>
                )}
                <button type="button" className="btn small quiet" onClick={() => setEditing({ ...profile })}>
                  编辑
                </button>
                {profiles.items.length > 1 && (
                  <button type="button" className="btn small quiet danger" onClick={() => remove(profile)}>
                    删除
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      {!editing && (
        <button type="button" className="btn" onClick={() => setEditing(blankProfile())}>
          新增配置
        </button>
      )}
      {editing && <ProfileEditor key={editing.id} initial={editing} onSave={save} onCancel={() => setEditing(null)} />}
    </div>
  );
}

/** What the bundled catalogues know about the model being edited (PLAN 15.4.10), asked a moment after typing stops. */
function useModelInfo({ kind, model, protocol, base_url }: ModelProfile): ModelInfo | null {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      api.modelInfo({ kind, model, protocol, base_url })
        .then((next) => live && setInfo(next))
        .catch(() => live && setInfo(null));
    }, 250);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [kind, model, protocol, base_url]);
  return info;
}

function ProfileEditor({ initial, onSave, onCancel }: {
  initial: ModelProfile;
  onSave: (profile: ModelProfile) => void;
  onCancel: () => void;
}) {
  const [profile, setProfile] = useState(initial);
  const [preset, setPreset] = useState(() => presetOf(initial));
  const info = useModelInfo(profile);
  const update = (next: Partial<ModelProfile>) => setProfile((current) => ({ ...current, ...next }));
  const custom = profile.kind === "custom";
  const levels = thinkingLevels(info);
  const thinking = clampThinking(profile.thinking, levels);
  const keyUrl = preset.key_url;

  // A different model brings its own limits, so the 「高级」 numbers start over.
  const pickModel = (model: string) => {
    const images = visionOf(model);
    update({ model, context_window: null, max_tokens: null, ...(images === null ? {} : { supports_images: images }) });
  };
  const choose = (next: Preset) => {
    setPreset(next);
    const fields = presetFields(next);
    const images = fields.model ? visionOf(fields.model) : null;
    update({ ...fields, ...(images === null ? {} : { supports_images: images }) });
  };
  const finish = () => {
    const fallback = custom && !preset.base_url ? hostOf(profile.base_url) : preset.label;
    onSave({ ...profile, name: profile.name.trim() || fallback || profile.model, thinking });
  };

  return (
    <section className="profile-editor card" aria-label="编辑模型配置">
      <div className="field">
        <span>常用供应商</span>
        <div className="presets" role="group" aria-label="常用供应商">
          {PRESETS.map((item) => (
            <button key={item.label} type="button" className="preset" aria-pressed={item === preset} onClick={() => choose(item)}>
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <label className="field">
        <span>名称</span>
        <input className="input" placeholder="例如：Claude 中转" value={profile.name} onChange={(e) => update({ name: e.target.value })} />
      </label>
      {custom && (
        <>
          <label className="field">
            <span>接口地址</span>
            <input
              className="input"
              placeholder="https://api.example.com/v1"
              value={profile.base_url}
              onChange={(e) => update({ base_url: e.target.value })}
            />
          </label>
          <div className="field">
            <span>接口协议</span>
            <Select label="接口协议" value={profile.protocol} options={PROTOCOLS} onChange={(protocol) => update({ protocol })} />
            <small>Claude 类中转通常只开放 Anthropic 协议（/v1/messages）。</small>
          </div>
        </>
      )}
      <div className="key-field">
        <SecretInput
          label="API Key"
          value={profile.api_key}
          onChange={(api_key) => update({ api_key })}
          reveal={() => api.revealKey({ profile_id: profile.id })}
        />
        {keyUrl && (
          <button type="button" className="key-link" onClick={() => openExternal(keyUrl)}>
            获取 API Key ↗
          </button>
        )}
      </div>
      <div className="field">
        <span>模型</span>
        <ModelPicker profile={profile} onPick={pickModel} />
      </div>
      <label className="switch-label field">
        <button
          type="button"
          role="switch"
          className="switch"
          aria-checked={profile.supports_images}
          aria-label="模型能看图"
          onClick={() => update({ supports_images: !profile.supports_images })}
        />
        模型能看图{visionOf(profile.model) !== null ? "（按 models.dev 自动判断）" : "（未收录的模型请自己确认）"}
      </label>
      <div className="field">
        <span>思考强度</span>
        <Select label="思考强度" value={thinking} options={thinkingOptions(levels)} onChange={(next) => update({ thinking: next })} />
        {!levels && <small>{THINKING_HINT}。</small>}
        {!levels && (thinking === "xhigh" || thinking === "max") && (
          <small>这个模型不在模型目录里：会把所选档位原样发给接口，接口不支持时任务会失败并写明原因。</small>
        )}
        <small>模型动笔前想多久。越高越仔细，但更慢、更费 token；精读用「中」最均衡。</small>
      </div>
      {custom && (
        <details className="advanced">
          <summary>高级</summary>
          <div className="row">
            <LimitField label="上下文窗口（token）" value={profile.context_window} known={info?.context_window ?? null}
              onChange={(context_window) => update({ context_window })} />
            <LimitField label="最大输出（token）" value={profile.max_tokens} known={info?.max_tokens ?? null}
              onChange={(max_tokens) => update({ max_tokens })} />
          </div>
          <small>{limitSource(info)}</small>
        </details>
      )}
      <div className="row">
        <button type="button" className="btn primary" onClick={finish}>
          保存配置
        </button>
        <button type="button" className="btn quiet" onClick={onCancel}>
          取消
        </button>
      </div>
    </section>
  );
}

/** A 「高级」 number: the user's own when set, else what the catalogues know; empty means Pi's default. */
function LimitField({ label, value, known, onChange }: {
  label: string;
  value: number | null;
  known: number | null;
  onChange: (value: number | null) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        className="input"
        type="number"
        min={1}
        step={1}
        inputMode="numeric"
        value={value ?? known ?? ""}
        onChange={(e) => onChange(e.target.value ? Math.max(1, Math.round(Number(e.target.value))) : null)}
      />
    </label>
  );
}

function limitSource(info: ModelInfo | null): string {
  if (info?.source === "pi") return "按随包 Pi 的模型目录预填，可以手动改。";
  if (info?.source === "models.dev") return "按 models.dev 的数据预填，可以手动改。";
  return "目录里没有这个模型：留空就按 Pi 的默认（上下文 128000，输出 16384）。";
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

/** 「获取模型列表」 failed: the HTTP status and the backend's short reason (PLAN 15.4.10). */
function failureText(error: unknown): string {
  const body = error instanceof ApiError ? error.body : undefined;
  const status = typeof body?.status === "number" ? body.status : null;
  const reason = typeof body?.reason === "string" && body.reason ? body.reason : "请检查接口地址、协议和 API Key。";
  return status ? `获取失败（HTTP ${status}）：${reason}` : `获取失败：${reason}`;
}

function ModelPicker({ profile, onPick }: { profile: ModelProfile; onPick: (model: string) => void }) {
  const [models, setModels] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const query = profile.model.trim().toLowerCase();
  const shown = models.filter((model) => !query || models.includes(profile.model) || model.toLowerCase().includes(query));

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);

  const fetchList = async () => {
    setBusy(true);
    setError("");
    try {
      setModels(await api.listModels(profile));
      setOpen(true);
    } catch (failure) {
      setError(failureText(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="model-picker" ref={box}>
      <div className="row">
        <input
          className="input grow"
          role="combobox"
          aria-label="模型"
          aria-autocomplete="list"
          aria-expanded={open && shown.length > 0}
          placeholder="点「获取模型列表」挑选，也可以直接填写"
          value={profile.model}
          onFocus={() => models.length && setOpen(true)}
          onChange={(e) => {
            onPick(e.target.value);
            if (models.length) setOpen(true);
          }}
        />
        <button type="button" className="btn" disabled={busy} onClick={fetchList}>
          {busy ? "获取中…" : "获取模型列表"}
        </button>
      </div>
      {open && shown.length > 0 && (
        <div className="popover model-pop" role="listbox" aria-label="模型列表">
          {shown.map((model) => (
            <div
              key={model}
              role="option"
              aria-selected={model === profile.model}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onPick(model);
                setOpen(false);
              }}
            >
              <span className="grow">{model}</span>
              {visionOf(model) && <span className="badge">能看图</span>}
            </div>
          ))}
        </div>
      )}
      {error && <small className="field-error">{error}</small>}
    </div>
  );
}
