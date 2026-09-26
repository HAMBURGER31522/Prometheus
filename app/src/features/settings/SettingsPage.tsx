// Settings: 模型 / 转写 / 网络 / 数据, one save button (PLAN 9.3).

import { useEffect, useState } from "react";

import { ApiError, api } from "../../shared/api";
import type { Settings } from "../../shared/api";
import { pickDirectory, pickFile } from "../../shared/platform";

export default function SettingsPage(props: { onDataDirChanged: (dir: string | null) => void }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [message, setMessage] = useState("");
  const [dataDir, setDataDir] = useState<string | null>(null);
  const [asrState, setAsrState] = useState("");

  useEffect(() => {
    api.getSettings().then(setSettings, (e) => setMessage(String(e)));
    api.getDataDir().then((r) => setDataDir(r.data_dir), () => undefined);
    api.asrStatus().then((r) => setAsrState(r.detail), () => undefined);
  }, []);

  if (!settings) {
    return <section className="settings"><h2>设置</h2><p>加载中…</p></section>;
  }

  const update = (patch: Partial<Settings>) => setSettings({ ...settings, ...patch });
  const cloud = settings.asr.backend === "cloud";

  const save = async () => {
    setMessage("");
    if (cloud && !settings.asr.dashscope_api_key.trim()) {
      setMessage("请填写 DashScope API Key");
      return;
    }
    try {
      const saved = await api.putSettings(settings);
      setSettings(saved);
      setMessage("已保存");
    } catch (e) {
      setMessage(e instanceof ApiError ? `保存失败（${e.code ?? e.status}）` : String(e));
    }
  };

  return (
    <section className="settings">
      <h2>设置</h2>

      <fieldset>
        <legend>模型</legend>
        <label>
          提供商
          <select
            value={settings.llm.provider}
            onChange={(e) => update({ llm: { ...settings.llm, provider: e.target.value } })}
          >
            <option value="deepseek">deepseek</option>
            <option value="zhipu">zhipu</option>
            <option value="custom">custom（OpenAI 兼容）</option>
          </select>
        </label>
        <label>
          模型
          <input
            value={settings.llm.model}
            onChange={(e) => update({ llm: { ...settings.llm, model: e.target.value } })}
          />
        </label>
        <label>
          API Key
          <input
            type="password"
            value={settings.llm.api_key}
            onChange={(e) => update({ llm: { ...settings.llm, api_key: e.target.value } })}
          />
        </label>
        <label>
          推理档位
          <select
            value={settings.llm.thinking}
            onChange={(e) => update({ llm: { ...settings.llm, thinking: e.target.value } })}
          >
            <option value="off">off</option>
            <option value="low">low</option>
            <option value="high">high</option>
          </select>
        </label>
        {settings.llm.provider === "custom" && (
          <>
            <label>
              Base URL
              <input
                value={settings.llm.custom.base_url}
                onChange={(e) =>
                  update({ llm: { ...settings.llm, custom: { ...settings.llm.custom, base_url: e.target.value } } })
                }
              />
            </label>
            <label>
              <input
                type="checkbox"
                checked={settings.llm.custom.supports_images}
                onChange={(e) =>
                  update({
                    llm: {
                      ...settings.llm,
                      custom: { ...settings.llm.custom, supports_images: e.target.checked },
                    },
                  })
                }
              />
              支持看图
            </label>
          </>
        )}
        <button
          type="button"
          onClick={async () => {
            setMessage("");
            try {
              const saved = await api.putSettings(settings);
              const result = await api.testModel();
              setSettings(saved);
              setMessage(result.ok ? `模型可用 · ${result.detail}` : `模型不可用 · ${result.detail}`);
            } catch (e) {
              setMessage(e instanceof ApiError ? `测试失败（${e.code ?? e.status}）` : String(e));
            }
          }}
        >
          测试模型
        </button>
      </fieldset>

      <fieldset>
        <legend>转写</legend>
        <label>
          <input
            type="radio"
            name="asr-backend"
            checked={!cloud}
            onChange={() => update({ asr: { ...settings.asr, backend: "local" } })}
          />
          本地
        </label>
        <label>
          <input
            type="radio"
            name="asr-backend"
            checked={cloud}
            onChange={() => update({ asr: { ...settings.asr, backend: "cloud" } })}
          />
          云端
        </label>
        <button
          type="button"
          disabled={cloud}
          onClick={async () => {
            await api.installAsr();
            setMessage("本地转写组件开始安装");
          }}
        >
          启用本地转写
        </button>
        {asrState && <span className="row-sub">{asrState}</span>}
        <label>
          DashScope API Key
          <input
            type="password"
            disabled={!cloud}
            value={settings.asr.dashscope_api_key}
            onChange={(e) =>
              update({ asr: { ...settings.asr, dashscope_api_key: e.target.value } })
            }
          />
        </label>
        <label>
          云端模型
          <input
            disabled={!cloud}
            value={settings.asr.cloud_model}
            onChange={(e) => update({ asr: { ...settings.asr, cloud_model: e.target.value } })}
          />
        </label>
      </fieldset>

      <fieldset>
        <legend>网络</legend>
        <label>
          代理
          <input
            value={settings.network.proxy}
            onChange={(e) => update({ network: { ...settings.network, proxy: e.target.value } })}
          />
        </label>
        <label>
          YouTube cookies.txt
          <input
            value={settings.network.youtube_cookies_file}
            onChange={(e) =>
              update({ network: { ...settings.network, youtube_cookies_file: e.target.value } })
            }
          />
          <button
            type="button"
            onClick={async () => {
              const file = await pickFile();
              if (file) update({ network: { ...settings.network, youtube_cookies_file: file } });
            }}
          >
            选择文件
          </button>
        </label>
      </fieldset>

      <fieldset>
        <legend>数据</legend>
        <p className="row-sub">{dataDir ?? "未设置"}</p>
        <button
          type="button"
          onClick={async () => {
            const dir = await pickDirectory();
            if (!dir) return;
            const result = await api.setDataDir(dir);
            setDataDir(result.data_dir);
            props.onDataDirChanged(result.data_dir);
          }}
        >
          选择数据目录
        </button>
      </fieldset>

      <button type="button" className="primary" onClick={save}>保存</button>
      {message && <p className="notice">{message}</p>}
    </section>
  );
}
