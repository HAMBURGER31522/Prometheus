// 设置 · 模型 (PLAN 15.4.8, after CC Switch at a much smaller scale): several saved model
// profiles as cards, one of them in use; an editor with the model list and an eye on the key.
import { useEffect, useRef, useState } from "react";

import { type ModelProfile, type Settings, api } from "../../shared/api";
import { type Option, Select } from "../../shared/Select";
import { SecretInput } from "./SecretInput";
import { visionOf } from "./vision";

type Profiles = Settings["llm_profiles"];

const KINDS: Option<ModelProfile["kind"]>[] = [
  { value: "deepseek", label: "DeepSeek" },
  { value: "zhipu", label: "智谱" },
  { value: "custom", label: "自定义" },
];
const PROTOCOLS: Option<ModelProfile["protocol"]>[] = [
  { value: "openai", label: "OpenAI 兼容" },
  { value: "anthropic", label: "Anthropic" },
];
const THINKING: Option<string>[] = [
  { value: "off", label: "关" },
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
];

const kindLabel = (kind: ModelProfile["kind"]) => KINDS.find((option) => option.value === kind)?.label ?? kind;

function blankProfile(): ModelProfile {
  return {
    id: `p-${Date.now().toString(36)}`, name: "", kind: "custom", base_url: "", protocol: "openai",
    api_key: "", model: "", supports_images: false, thinking: "medium",
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
                  {kindLabel(profile.kind)}
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

function ProfileEditor({ initial, onSave, onCancel }: {
  initial: ModelProfile;
  onSave: (profile: ModelProfile) => void;
  onCancel: () => void;
}) {
  const [profile, setProfile] = useState(initial);
  const update = (next: Partial<ModelProfile>) => setProfile((current) => ({ ...current, ...next }));
  const custom = profile.kind === "custom";

  const finish = () => {
    const name = profile.name.trim() || (custom ? hostOf(profile.base_url) : kindLabel(profile.kind)) || profile.model;
    onSave({ ...profile, name });
  };

  return (
    <section className="profile-editor card" aria-label="编辑模型配置">
      <label className="field">
        <span>名称</span>
        <input className="input" placeholder="例如：Claude 中转" value={profile.name} onChange={(e) => update({ name: e.target.value })} />
      </label>
      <div className="field">
        <span>类型</span>
        <Select label="类型" value={profile.kind} options={KINDS} onChange={(kind) => update({ kind })} />
      </div>
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
      <SecretInput label="API Key" value={profile.api_key} onChange={(api_key) => update({ api_key })} />
      <div className="field">
        <span>模型</span>
        <ModelPicker
          profile={profile}
          onPick={(model) => {
            const images = visionOf(model);
            update({ model, ...(images === null ? {} : { supports_images: images }) });
          }}
        />
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
        <Select label="思考强度" value={profile.thinking} options={THINKING} onChange={(thinking) => update({ thinking })} />
        <small>模型动笔前想多久。越高越仔细，但更慢、更费 token；精读用「中」最均衡。</small>
      </div>
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

function hostOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
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
    } catch {
      setError("获取失败：请检查接口地址、协议和 API Key。");
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
