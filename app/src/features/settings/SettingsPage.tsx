// 设置 (PLAN 8.9, 15.2, 15.4.8): model profiles, 本地 / 云端 transcription, network.
import { type FormEvent, useEffect, useState } from "react";

import { type Settings, api } from "../../shared/api";
import { pickDirectory, pickFile } from "../../shared/platform";
import { ScrollArea } from "../../shared/ScrollArea";
import { ModelProfiles } from "./ModelProfiles";

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [status, setStatus] = useState("");
  const [testing, setTesting] = useState("");
  const [asr, setAsr] = useState<{ state: string; detail: string } | null>(null);
  const [dataDir, setDataDir] = useState<string | null>(null);

  useEffect(() => {
    api.settings().then(setSettings).catch(() => setStatus("读取设置失败"));
    api.dataDir().then((value) => setDataDir(value.data_dir)).catch(() => undefined);
    api.asrStatus().then(setAsr).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (asr?.state !== "installing") return;
    const timer = setInterval(() => api.asrStatus().then(setAsr).catch(() => undefined), 2000);
    return () => clearInterval(timer);
  }, [asr?.state]);

  if (!settings) return <p className="empty">{status || "正在读取设置…"}</p>;

  const update = (next: Partial<Settings>) => {
    setSettings({ ...settings, ...next });
    setStatus("");
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    try {
      setSettings(await api.saveSettings(settings));
      setStatus("已保存");
    } catch {
      setStatus("保存失败，请检查填写的内容。");
    }
  };

  return (
    <ScrollArea>
      <form className="page settings" onSubmit={save}>
        <div className="page-head">
          <div>
            <h1>设置</h1>
            <p>模型、转写方式和网络。API Key 只保存在本机的数据目录里。</p>
          </div>
          <div className="row">
            <span role="status" className="muted">
              {status}
            </span>
            <button type="submit" className="btn primary">
              保存
            </button>
          </div>
        </div>

        <section className="section card">
          <h2>模型</h2>
          <ModelProfiles profiles={settings.llm_profiles} onChange={(llm_profiles) => update({ llm_profiles })} />
          <div className="row" style={{ marginTop: 16 }}>
            <button
              type="button"
              className="btn"
              onClick={async () => {
                setTesting("正在测试…");
                const result = await api.testModel().catch(() => ({ ok: false, detail: "请求失败" }));
                setTesting(result.ok ? `可用：${result.detail}` : `不可用：${result.detail}`);
              }}
            >
              测试当前模型
            </button>
            <span className="muted">{testing || "先保存，再测试；会向当前使用的配置发送一次真实请求。"}</span>
          </div>
        </section>

        <section className="section card">
          <h2>转写</h2>
          <div className="choices" role="radiogroup" aria-label="转写方式">
            <label className="choice">
              <input
                type="radio"
                name="asr"
                checked={settings.asr.backend === "local"}
                onChange={() => update({ asr: { backend: "local" } })}
              />
              <span>
                <b>本地</b>
                <small>中文用 FunASR（CPU 即可），其他语言用 Whisper（有 NVIDIA 显卡更快）。</small>
              </span>
            </label>
            <label className="choice">
              <input
                type="radio"
                name="asr"
                checked={settings.asr.backend === "cloud"}
                onChange={() => update({ asr: { backend: "cloud" } })}
              />
              <span>
                <b>云端（必剪）</b>
                <small>免费，不需要任何配置；不可用时自动改用本地转写。</small>
              </span>
            </label>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button
              type="button"
              className="btn"
              disabled={asr?.state === "installing"}
              onClick={async () => {
                await api.installAsr();
                setAsr(await api.asrStatus());
              }}
            >
              安装本地转写组件
            </button>
            <span className="muted">{asr?.detail ?? ""}</span>
          </div>
        </section>

        <section className="section card">
          <h2>网络</h2>
          <label className="field">
            <span>代理</span>
            <input
              className="input"
              placeholder="http://127.0.0.1:7890（不用代理就留空）"
              value={settings.network.proxy}
              onChange={(e) => update({ network: { ...settings.network, proxy: e.target.value } })}
            />
          </label>
          <label className="field">
            <span>YouTube cookies.txt</span>
            <div className="row">
              <input
                className="input grow"
                value={settings.network.youtube_cookies_file}
                onChange={(e) => update({ network: { ...settings.network, youtube_cookies_file: e.target.value } })}
              />
              <button
                type="button"
                className="btn"
                onClick={async () => {
                  const file = await pickFile();
                  if (file) update({ network: { ...settings.network, youtube_cookies_file: file } });
                }}
              >
                选择文件
              </button>
            </div>
            <small>下载 YouTube 视频需要浏览器导出的 cookies 文件。</small>
          </label>
        </section>

        <section className="section card">
          <h2>其他</h2>
          <label className="switch-label field">
            <button
              type="button"
              role="switch"
              className="switch"
              aria-checked={settings.figures_default}
              aria-label="默认配图"
              onClick={() => update({ figures_default: !settings.figures_default })}
            />
            新任务默认配图
          </label>
          <div className="field">
            <span>数据目录（知识库就在这里）</span>
            <div className="row">
              <code className="path">{dataDir ?? "未设置"}</code>
              <button
                type="button"
                className="btn"
                onClick={async () => {
                  const chosen = await pickDirectory();
                  if (chosen) setDataDir((await api.setDataDir(chosen)).data_dir);
                }}
              >
                更换
              </button>
            </div>
          </div>
        </section>
      </form>
    </ScrollArea>
  );
}
