const explicitBase = normalizeBaseCandidate((import.meta.env.VITE_API_BASE || '').trim());
const runtimeHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
const runtimeProtocol = typeof window !== 'undefined' ? window.location.protocol : 'http:';
const runtimeOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000';
const defaultCandidates = [
  normalizeBaseCandidate(''),
  normalizeBaseCandidate(runtimeOrigin),
  normalizeBaseCandidate(`${runtimeProtocol}//${runtimeHost}:8000`),
  normalizeBaseCandidate('http://127.0.0.1:8000'),
  normalizeBaseCandidate('http://localhost:8000')
];
const apiBases = [...new Set([explicitBase, ...defaultCandidates].filter((item) => item != null))];
let activeApiBase = apiBases[0];

function normalizeBaseCandidate(base) {
  if (base == null) {
    return null;
  }
  const value = String(base).trim();
  if (!value) {
    return '';
  }
  if (value.startsWith('/')) {
    return value.replace(/\/+$/, '');
  }
  try {
    const parsed = new globalThis.URL(value);
    const pathname = parsed.pathname.replace(/\/+$/, '');
    const lowered = pathname.toLowerCase();
    if (lowered.endsWith('/api/projects')) {
      parsed.pathname = pathname.slice(0, -'/api/projects'.length) || '/';
      return parsed.toString().replace(/\/$/, '');
    }
    if (lowered.endsWith('/api/projects/')) {
      parsed.pathname = pathname.slice(0, -'/api/projects'.length) || '/';
      return parsed.toString().replace(/\/$/, '');
    }
    return value.replace(/\/+$/, '');
  } catch {
    return null;
  }
}

function orderedApiBases() {
  return [activeApiBase, ...apiBases.filter((base) => base !== activeApiBase)];
}

function buildRequestOptions(options = {}) {
  return {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  };
}

function buildApiUrl(base, path) {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  if (!base) {
    return cleanPath;
  }
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base;
  if (normalizedBase.endsWith('/api') && cleanPath.startsWith('/api/')) {
    return `${normalizedBase}${cleanPath.slice(4)}`;
  }
  return `${normalizedBase}${cleanPath}`;
}

function normalizeRequestError(error, base) {
  const raw = error instanceof Error ? error.message : '';
  const message = raw.toLowerCase();
  if (
    message.includes('aborted') ||
    message.includes('aborterror') ||
    message.includes('signal is aborted') ||
    message.includes('the operation was aborted')
  ) {
    return new Error(`请求超时（${base}），请稍后重试或检查后端模型响应速度`);
  }
  if (
    message.includes('failed to fetch') ||
    message.includes('load failed') ||
    message.includes('networkerror') ||
    message.includes('network request failed')
  ) {
    return new Error(`无法连接后端接口（${base}），请确认后端服务已启动`);
  }
  if (error instanceof Error) {
    return error;
  }
  return new Error('请求失败，请稍后重试');
}

async function fetchWithTimeout(url, options, timeoutMs = 12000) {
  const controller = new globalThis.AbortController();
  const timer = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    globalThis.clearTimeout(timer);
  }
}

function classifyHttpError(status, bodyText) {
  const text = (bodyText || '').trim();
  const lower = text.toLowerCase();
  if (status === 404 || status === 405) {
    if (lower.includes('project_not_found') || lower.includes('"detail":"project_not_found"')) {
      return { kind: 'business', message: '项目不存在，请刷新项目列表后重试' };
    }
    if (lower.includes('"detail":"not found"')) {
      return { kind: 'route_miss', message: `request_failed_${status}` };
    }
    if (lower.startsWith('<!doctype') || lower.startsWith('<html')) {
      return { kind: 'route_miss', message: `request_failed_${status}` };
    }
    if (lower.includes('not found')) {
      return { kind: 'route_miss', message: `request_failed_${status}` };
    }
  }
  return { kind: 'business', message: text || `request_failed_${status}` };
}

async function request(path, options = {}) {
  const fetchOptions = buildRequestOptions(options);
  const timeoutMs = Number.isFinite(options.timeoutMs) ? options.timeoutMs : 12000;
  let lastError = null;
  const attemptedUrls = [];
  for (const base of orderedApiBases()) {
    try {
      const targetUrl = buildApiUrl(base, path);
      attemptedUrls.push(targetUrl);
      const response = await fetchWithTimeout(targetUrl, fetchOptions, timeoutMs);
      if (!response.ok) {
        const bodyText = await response.text();
        const parsed = classifyHttpError(response.status, bodyText);
        if (parsed.kind === 'route_miss') {
          lastError = new Error(parsed.message);
          continue;
        }
        throw new Error(parsed.message);
      }
      activeApiBase = base;
      return response.json();
    } catch (error) {
      lastError = normalizeRequestError(error, base);
    }
  }
  if (lastError instanceof Error && lastError.message.startsWith('request_failed_404')) {
    const attempted = attemptedUrls.slice(0, 3).join(' | ');
    throw new Error(`接口路径不可用，请确认前端连接到了后端服务地址。已尝试：${attempted}`);
  }
  throw (lastError instanceof Error ? lastError : new Error('后端不可用，请检查服务是否启动'));
}

export function createProject(userPrompt) {
  return request('/api/projects', {
    method: 'POST',
    body: JSON.stringify({ user_prompt: userPrompt })
  });
}

export function listProjects() {
  return request('/api/projects', {
    timeoutMs: 40000
  });
}

export function getProjectStats() {
  return request('/api/projects/stats', {
    timeoutMs: 15000
  });
}

export function getProjectSnapshot(projectId, options = {}) {
  const compact = Boolean(options.compact);
  const suffix = compact ? '?compact=1' : '';
  return request(`/api/projects/${projectId}${suffix}`, {
    timeoutMs: 30000
  });
}

export function deleteProject(projectId) {
  return request(`/api/projects/${projectId}`, {
    method: 'DELETE',
    timeoutMs: 15000
  });
}

export function deleteProjectsBatch(projectIds) {
  return request('/api/projects/delete-batch', {
    method: 'POST',
    body: JSON.stringify({ project_ids: projectIds }),
    timeoutMs: 30000
  });
}

export function advanceProject(projectId) {
  return request(`/api/projects/${projectId}/advance`, {
    method: 'POST'
  });
}

export function submitReview(projectId, payload) {
  return request(`/api/projects/${projectId}/review`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function submitProjectChat(projectId, payload) {
  return request(`/api/projects/${projectId}/chat`, {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: 40000
  }).catch((error) => {
    const message = error instanceof Error ? error.message : '';
    if (message.includes('接口路径不可用') || message.includes('request_failed_404')) {
      throw new Error('当前后端服务未提供聊天接口 /api/projects/{project_id}/chat，请重启并更新后端服务');
    }
    throw error;
  });
}

export function getProjectIntentRouterPolicy(projectId) {
  return request(`/api/projects/${projectId}/intent-router-policy`, {
    timeoutMs: 15000
  });
}

export function saveProjectIntentRouterPolicy(projectId, payload) {
  return request(`/api/projects/${projectId}/intent-router-policy`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    timeoutMs: 15000
  });
}

export function connectProjectStream(projectId, onSnapshot, onError) {
  let source = null;
  let closed = false;
  let connected = false;
  const bases = orderedApiBases();

  const openStream = (index) => {
    if (closed || index >= bases.length) {
      onError(new Error('实时流连接失败，请确认后端服务已启动'));
      return;
    }
    const base = bases[index];
    let nextSource = null;
    try {
      nextSource = new EventSource(buildApiUrl(base, `/api/projects/${projectId}/stream`));
    } catch {
      openStream(index + 1);
      return;
    }
    source = nextSource;
    source.addEventListener('snapshot', (event) => {
      try {
        activeApiBase = base;
        connected = true;
        onSnapshot(JSON.parse(event.data));
      } catch (error) {
        onError(error);
      }
    });
    source.onerror = () => {
      if (closed) {
        return;
      }
      if (!connected) {
        source.close();
        openStream(index + 1);
        return;
      }
      onError(new Error('实时链路中断，正在重连'));
    };
  };

  openStream(0);
  return {
    close() {
      closed = true;
      if (source) {
        source.close();
      }
    }
  };
}

export function getModelRoutes() {
  return request('/api/settings/model-routes');
}

export function saveModelRoutes(payload) {
  return request('/api/settings/model-routes', {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export function getIntentRouterPolicy() {
  return request('/api/settings/intent-router-policy');
}

export function saveIntentRouterPolicy(payload) {
  return request('/api/settings/intent-router-policy', {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}
