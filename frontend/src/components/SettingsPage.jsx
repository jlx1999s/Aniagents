import { useEffect, useMemo, useState } from 'react';
import { createDefaultModelRoutes, modelStages, normalizeModelRoutes } from '../config/modelRoutes';
import { getModelRoutes, saveModelRoutes } from '../services/api';

const STORAGE_KEY = 'aniagents.modelRoutes.v1';

const providerChoices = [
  { value: 'mock', label: 'Mock' },
  { value: 'vectorengine', label: 'VectorEngine' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google' },
  { value: 'local', label: 'Local' },
  { value: 'custom', label: 'Custom' }
];

function safeParse(jsonText) {
  try {
    return JSON.parse(jsonText);
  } catch {
    return null;
  }
}

function getStorage() {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage || null;
}

export default function SettingsPage() {
  const [routes, setRoutes] = useState(() => {
    const storage = getStorage();
    const local = safeParse(storage ? storage.getItem(STORAGE_KEY) || '' : '');
    return normalizeModelRoutes(local);
  });
  const [status, setStatus] = useState('idle');
  const [message, setMessage] = useState('');
  const [activeStage, setActiveStage] = useState('scriptwriter');
  const stageInfo = useMemo(() => modelStages.find((item) => item.key === activeStage) || modelStages[0], [activeStage]);

  useEffect(() => {
    let canceled = false;
    async function bootstrap() {
      setStatus('loading');
      setMessage('');
      try {
        const remote = await getModelRoutes();
        if (canceled) {
          return;
        }
        const normalized = normalizeModelRoutes(remote);
        setRoutes(normalized);
        const storage = getStorage();
        if (storage) {
          storage.setItem(STORAGE_KEY, JSON.stringify(normalized));
        }
        setStatus('ready');
      } catch (error) {
        if (canceled) {
          return;
        }
        setStatus('ready');
        setMessage(error instanceof Error ? error.message : '加载设置失败');
      }
    }
    bootstrap();
    return () => {
      canceled = true;
    };
  }, []);

  const updateDefaults = (patch) => {
    setRoutes((prev) => ({
      ...prev,
      updatedAt: new Date().toISOString(),
      defaults: {
        ...prev.defaults,
        ...patch
      }
    }));
  };

  const updateRoute = (stageKey, taskKey, patch) => {
    setRoutes((prev) => ({
      ...prev,
      updatedAt: new Date().toISOString(),
      routes: {
        ...prev.routes,
        [stageKey]: {
          ...(prev.routes[stageKey] || {}),
          [taskKey]: {
            ...(prev.routes[stageKey]?.[taskKey] || {}),
            ...patch
          }
        }
      }
    }));
  };

  const applyDefaultsToAll = () => {
    setRoutes((prev) => {
      const next = { ...prev, updatedAt: new Date().toISOString(), routes: { ...prev.routes } };
      modelStages.forEach((stage) => {
        next.routes[stage.key] = { ...(next.routes[stage.key] || {}) };
        stage.tasks.forEach((task) => {
          const current = next.routes[stage.key][task.key] || {};
          next.routes[stage.key][task.key] = {
            ...current,
            provider: prev.defaults.provider,
            baseUrl: prev.defaults.baseUrl
          };
        });
      });
      return next;
    });
  };

  const resetAll = () => {
    const next = createDefaultModelRoutes();
    setRoutes(next);
    const storage = getStorage();
    if (storage) {
      storage.setItem(STORAGE_KEY, JSON.stringify(next));
    }
    setMessage('已恢复默认配置');
  };

  const handleSave = async () => {
    setStatus('saving');
    setMessage('');
    const payload = normalizeModelRoutes(routes);
    try {
      await saveModelRoutes(payload);
      const storage = getStorage();
      if (storage) {
        storage.setItem(STORAGE_KEY, JSON.stringify(payload));
      }
      setStatus('ready');
      setMessage('已保存');
    } catch (error) {
      setStatus('ready');
      setMessage(error instanceof Error ? error.message : '保存失败');
    }
  };

  return (
    <section className="settings-page">
      <div className="settings-head">
        <div>
          <div className="settings-title">设置</div>
          <div className="settings-subtitle">配置各阶段 API 与模型路由，支持随时切换。</div>
        </div>
        <div className="settings-head-actions">
          <button type="button" className="review-btn" disabled={status === 'saving'} onClick={handleSave}>
            保存配置
          </button>
          <button type="button" className="review-btn" disabled={status === 'saving'} onClick={resetAll}>
            恢复默认
          </button>
        </div>
      </div>

      <div className="settings-status">
        <div>状态：{status === 'loading' ? '加载中' : status === 'saving' ? '保存中' : '就绪'}</div>
        <div>{message || '配置将优先从后端读取，若不可用则使用本地缓存。'}</div>
      </div>

      <div className="settings-grid">
        <aside className="settings-aside">
          <div className="panel-title">全局默认</div>
          <div className="settings-field">
            <div className="settings-label">Provider</div>
            <select
              className="field-select"
              value={routes.defaults.provider}
              onChange={(event) => updateDefaults({ provider: event.target.value })}
            >
              {providerChoices.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div className="settings-field">
            <div className="settings-label">Base URL</div>
            <input
              className="field-input"
              value={routes.defaults.baseUrl}
              placeholder="例如：https://api.openai.com 或 http://127.0.0.1:11434"
              onChange={(event) => updateDefaults({ baseUrl: event.target.value })}
            />
          </div>
          <button type="button" className="review-btn settings-apply-btn" disabled={status === 'saving'} onClick={applyDefaultsToAll}>
            应用到所有阶段
          </button>

          <div className="panel-title settings-stage-title">阶段</div>
          <div className="settings-stage-list">
            {modelStages.map((stage) => (
              <button
                key={stage.key}
                type="button"
                className={`settings-stage-btn ${stage.key === activeStage ? 'active' : ''}`}
                onClick={() => setActiveStage(stage.key)}
              >
                {stage.title}
              </button>
            ))}
          </div>
        </aside>

        <div className="settings-main">
          <div className="settings-stage-header">
            <div className="settings-stage-name">{stageInfo.title}</div>
            <div className="settings-stage-hint">Stage Key：{stageInfo.key}</div>
          </div>

          <div className="settings-route-table">
            {stageInfo.tasks.map((task) => {
              const current = routes.routes?.[stageInfo.key]?.[task.key] || {};
              return (
                <div key={task.key} className="settings-route-row">
                  <div className="settings-route-title">
                    <div className="settings-route-task">{task.title}</div>
                    <div className="settings-route-key">{stageInfo.key}.{task.key}</div>
                  </div>
                  <div className="settings-route-controls">
                    <select
                      className="field-select"
                      value={current.provider || routes.defaults.provider}
                      onChange={(event) => updateRoute(stageInfo.key, task.key, { provider: event.target.value })}
                    >
                      {providerChoices.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                    <input
                      className="field-input"
                      value={current.baseUrl || routes.defaults.baseUrl}
                      placeholder="Base URL"
                      onChange={(event) => updateRoute(stageInfo.key, task.key, { baseUrl: event.target.value })}
                    />
                    <input
                      className="field-input"
                      value={current.model || ''}
                      placeholder="Model"
                      onChange={(event) => updateRoute(stageInfo.key, task.key, { model: event.target.value })}
                    />
                    <label className="settings-toggle">
                      <input
                        type="checkbox"
                        checked={Boolean(current.enabled)}
                        onChange={(event) => updateRoute(stageInfo.key, task.key, { enabled: event.target.checked })}
                      />
                      <span>启用</span>
                    </label>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="settings-json-box">
            <div className="panel-title">路由表（JSON）</div>
            <textarea className="field-textarea settings-json" value={JSON.stringify(routes, null, 2)} readOnly />
          </div>
        </div>
      </div>
    </section>
  );
}
