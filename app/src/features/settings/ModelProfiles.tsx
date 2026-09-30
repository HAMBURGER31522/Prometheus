// 设置 · 模型 (PLAN 15.4.8, 15.4.10; after CC Switch and ModelGate at a much smaller scale): several
// saved model profiles as cards, one of them in use; an editor with common platforms, the model
// list, the thinking levels the model supports, an eye on the key and 「高级」 limits. Each profile
// first names its Agent and how it connects (PLAN 15.4.13): they decide which fields can be filled.
import { useEffect, useRef, useState } from "react";

import { type AgentId, type AgentRow, ApiError, type ModelInfo, type ModelProfile, type Settings, api } from "../../shared/api";
import { openExternal } from "../../shared/platform";
import { type Option, Select } from "../../shared/Select";
import { AGENTS, AGENT_PROTOCOL, agentProblem, agentThinking, limitHint, presetAllowed } from "./agents";
import { PRESETS, type Preset, presetFields, presetOf } from "./presets";
import { SecretInput } from "./SecretInput";
import { THINKING, THINKING_HINT, clampThinking, thinkingLevels, thinkingOptions } from "./thinking";
import { visionOf } from "./vision";

type Profiles = Settings["llm_profiles"];

const KIND_LABELS: Record<ModelProfile["kind"], string> = { deepseek: "DeepSeek", zhipu: "智谱", custom: "自定义" };
const AGENT_NAMES = Object.fromEntries(AGENTS.map((agent) => [agent.value, agent.label])) as Record<AgentId, string>;
const CUSTOM_PRESET = PRESETS[PRESETS.length - 1];
const PROTOCOL_HINTS: Record<AgentId, string> = {
  pi: "Claude 类中转通常只开放 Anthropic 协议（/v1/messages）。",
  codex: "Codex CLI 只走 OpenAI 协议。",
  claude: "Claude Code 只走 Anthropic 协议（/v1/messages）。",
};
const PROTOCOLS: Option<ModelProfile["protocol"]>[] = [
  { value: "openai", label: "OpenAI 兼容" },
  { value: "anthropic", label: "Anthropic" },
];

function blankProfile(): ModelProfile {
  return {
    id: `p-${Date.now().toString(36)}`, name: "", kind: "custom", base_url: "", protocol: "openai",
    api_key: "", model: "", supports_images: false, thinking: "medium", context_window: null, max_tokens: null,
    agent: "pi", access: "key",
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
                  {profile.agent !== "pi" && `${AGENT_NAMES[profile.agent]} · `}
                  {profile.access === "login" ? "官方登录" : KIND_LABELS[profile.kind]}
                  {profile.kind === "custom" && profile.access !== "login" &&
                    ` · ${profile.protocol === "anthropic" ? "Anthropic" : "OpenAI"}`}
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
function useModelInfo({ kind, model, protocol, base_url, agent }: ModelProfile): ModelInfo | null {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  useEffect(() => {
    let live = true;
    const timer = setTimeout(() => {
      api.modelInfo({ kind, model, protocol, base_url, agent })
        .then((next) => live && setInfo(next))
        .catch(() => live && setInfo(null));
    }, 250);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [kind, model, protocol, base_url, agent]);
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
  const login = profile.access === "login";
  const problem = agentProblem(profile);
  // Pi's catalogue only speaks for Pi; the other Agents take every level they can send.
  const levels = profile.agent === "pi" ? thinkingLevels(info) : null;
  const { unavailable, note } = modelThinking(profile, info);
  const allowed = (levels ?? THINKING.map((option) => option.value)).filter((level) => !unavailable.includes(level));
  const thinking = clampThinking(profile.thinking, levels || unavailable.length ? allowed : null);
  const offered = thinkingOptions(levels).map((option) => ({ ...option, disabled: unavailable.includes(option.value) }));
  const keyUrl = login ? undefined : preset.key_url;

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
  const chooseAgent = (agent: AgentId) => {
    const next: Partial<ModelProfile> = { agent };
    const protocol = AGENT_PROTOCOL[agent];
    if (protocol) next.protocol = protocol;
    if (agent !== "codex") next.access = "key";
    if (!presetAllowed(preset, agent)) {
      setPreset(CUSTOM_PRESET);
      Object.assign(next, { kind: "custom", base_url: preset.base_url ? "" : profile.base_url });
    }
    update(next);
  };
  const finish = () => {
    const fallback = custom && !preset.base_url ? hostOf(profile.base_url) : preset.label;
    onSave({ ...profile, name: profile.name.trim() || fallback || profile.model, thinking });
  };

  return (
    <section className="profile-editor card" aria-label="编辑模型配置">
      <div className="row agent-row">
        <div className="field">
          <span>Agent</span>
          <Select label="Agent" value={profile.agent} options={AGENTS} onChange={chooseAgent} />
          <AgentState agent={profile.agent} />
        </div>
        <div className="field">
          <span>接入方式</span>
          <div className="access" role="radiogroup" aria-label="接入方式">
            <label>
              <input type="radio" name={`access-${profile.id}`} checked={!login} onChange={() => update({ access: "key" })} />
              接口 + Key
            </label>
            <label>
              <input
                type="radio"
                name={`access-${profile.id}`}
                checked={login}
                disabled={profile.agent !== "codex"}
                onChange={() => update({ access: "login" })}
              />
              官方登录
            </label>
          </div>
          {profile.agent !== "codex" && <small>官方登录只有 Codex CLI 有（ChatGPT 账户）。</small>}
        </div>
      </div>
      <div className="field">
        <span>常用供应商</span>
        <div className="presets" role="group" aria-label="常用供应商">
          {PRESETS.map((item) => (
            <button
              key={item.label}
              type="button"
              className="preset"
              aria-pressed={item === preset}
              disabled={login || !presetAllowed(item, profile.agent)}
              onClick={() => choose(item)}
            >
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
              disabled={login}
              value={profile.base_url}
              onChange={(e) => update({ base_url: e.target.value })}
            />
          </label>
          <div className="field">
            <span>接口协议</span>
            <Select label="接口协议" value={profile.protocol} options={PROTOCOLS} disabled={login}
              onChange={(protocol) => update({ protocol })} />
            {problem && !login ? (
              <small className="field-error" role="alert">{problem}</small>
            ) : (
              !login && <small>{PROTOCOL_HINTS[profile.agent]}</small>
            )}
          </div>
        </>
      )}
      <div className="key-field">
        <SecretInput
          label="API Key"
          value={profile.api_key}
          onChange={(api_key) => update({ api_key })}
          reveal={() => api.revealKey({ profile_id: profile.id })}
          disabled={login}
        />
        {keyUrl && (
          <button type="button" className="key-link" onClick={() => openExternal(keyUrl)}>
            获取 API Key ↗
          </button>
        )}
      </div>
      {profile.agent === "codex" && login && <CodexLogin />}
      <div className="field">
        <span>模型</span>
        <ModelPicker profile={profile} onPick={pickModel} listable={!login || profile.agent === "codex"} />
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
        <Select label="思考强度" value={thinking} options={offered} onChange={(next) => update({ thinking: next })} />
        {note && <small>{note}。</small>}
        {!levels && <small>{THINKING_HINT}。</small>}
        {profile.agent === "pi" && !levels && (thinking === "xhigh" || thinking === "max") && (
          <small>这个模型不在模型目录里：会把所选档位原样发给接口，接口不支持时任务会失败并写明原因。</small>
        )}
        {profile.agent === "pi" && custom && !levels && (thinking === "xhigh" || thinking === "max") && !profile.max_tokens && (
          <small>
            最大输出按 Pi 的默认 16384 算，思考内容也算在最大输出里：请在「高级」里填这个模型的最大输出。
          </small>
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
          <small>{limitHint(info, profile.agent)}</small>
        </details>
      )}
      {problem && (login || !custom) && <small className="field-error" role="alert">{problem}</small>}
      <div className="row">
        <button type="button" className="btn primary" disabled={problem !== null} onClick={finish}>
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

/** 「已安装 0.151.0」, or 「未安装」 with 「安装」 (PLAN 15.4.13): the app's own copy of the Agent. */
function AgentState({ agent }: { agent: AgentId }) {
  const [rows, setRows] = useState<AgentRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    api.agents().then(setRows).catch(() => setRows(null));
  }, []);
  const row = rows?.find((item) => item.id === agent);
  if (!row) return null;
  const install = async () => {
    setBusy(true);
    setError("");
    try {
      setRows(await api.installAgent(agent));
    } catch {
      setError("安装失败");
    } finally {
      setBusy(false);
    }
  };
  return (
    <small className="agent-state" data-testid="agent-state">
      {row.installed ? `已安装 ${row.version}` : "未安装"}
      {!row.installed && (
        <button type="button" className="btn small" disabled={busy} onClick={install}>
          {busy ? "安装中…" : "安装"}
        </button>
      )}
      {error && <span className="field-error">{error}</span>}
    </small>
  );
}

/** 「官方登录」 for Codex CLI (PLAN 15.4.13): the app's own Codex login, apart from the user's. */
/** The levels an Agent or, in Codex, the chosen model cannot take: greyed out, with the reason. */
function modelThinking(profile: ModelProfile, info: ModelInfo | null): { unavailable: string[]; note: string | null } {
  if (profile.agent === "codex" && info?.source === "codex" && info.levels) {
    const levels = info.levels;
    const names = THINKING.filter((option) => levels.includes(option.value)).map((option) => option.label);
    return {
      unavailable: THINKING.map((option) => option.value).filter((level) => !levels.includes(level)),
      note: `${profile.model} 在 Codex 里支持：${names.join("、")}`,
    };
  }
  return agentThinking(profile.agent);
}

/** Asks every 2 seconds, up to 5 minutes, while the browser sign-in is under way. */
const LOGIN_POLL_MS = 2000;
const LOGIN_POLLS = 150;

function CodexLogin() {
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null);
  const [waiting, setWaiting] = useState(false);
  useEffect(() => {
    api.codexLogin().then((state) => setLoggedIn(state.logged_in)).catch(() => setLoggedIn(false));
  }, []);
  useEffect(() => {
    if (!waiting) return;
    let polls = 0;
    const timer = setInterval(() => {
      polls += 1;
      api.codexLogin().then((state) => {
        setLoggedIn(state.logged_in);
        if (state.logged_in || polls >= LOGIN_POLLS) setWaiting(false);
      }).catch(() => undefined);
    }, LOGIN_POLL_MS);
    return () => clearInterval(timer);
  }, [waiting]);
  return (
    <div className="field" data-testid="codex-login">
      <span>ChatGPT 账户</span>
      <div className="row">
        <span>{loggedIn === null ? "查询中…" : loggedIn ? "已登录" : waiting ? "等待浏览器里登录…" : "未登录"}</span>
        <button
          type="button"
          className="btn small"
          onClick={() =>
            api.startCodexLogin().then((state) => {
              setLoggedIn(state.logged_in);
              setWaiting(!state.logged_in);
            }).catch(() => undefined)}
        >
          登录 ChatGPT 账户
        </button>
      </div>
      <small>会打开 OpenAI 的官方登录页；凭据由这个应用自己的 Codex 保存，和你平时用的 Codex 互不相关。</small>
    </div>
  );
}

function ModelPicker({ profile, onPick, listable }: {
  profile: ModelProfile;
  onPick: (model: string) => void;
  /** 「获取模型列表」 asks the endpoint; an official login has none to ask. */
  listable: boolean;
}) {
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
          placeholder={listable ? "点「获取模型列表」挑选，也可以直接填写" : "填写模型名，例如 gpt-6-astra"}
          value={profile.model}
          onFocus={() => models.length && setOpen(true)}
          onChange={(e) => {
            onPick(e.target.value);
            if (models.length) setOpen(true);
          }}
        />
        {listable && (
          <button type="button" className="btn" disabled={busy} onClick={fetchList}>
            {busy ? "获取中…" : "获取模型列表"}
          </button>
        )}
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
