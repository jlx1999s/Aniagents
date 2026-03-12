const explicitBase = (import.meta.env.VITE_API_BASE || '').trim();
const runtimeHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
const runtimeProtocol = typeof window !== 'undefined' ? window.location.protocol : 'http:';
const defaultCandidates = [
  `${runtimeProtocol}//${runtimeHost}:8000`,
  `${runtimeProtocol}//${runtimeHost}:8001`,
  'http://127.0.0.1:8000',
  'http://127.0.0.1:8001',
  'http://localhost:8000',
  'http://localhost:8001'
];
const apiBases = [...new Set([explicitBase, ...defaultCandidates].filter(Boolean))];
let activeApiBase = apiBases[0];

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

async function request(path, options = {}) {
  const fetchOptions = buildRequestOptions(options);
  let lastError = null;
  for (const base of orderedApiBases()) {
    try {
      const response = await fetch(`${base}${path}`, fetchOptions);
      if (!response.ok) {
        if (response.status === 404 || response.status === 405) {
          lastError = new Error(`request_failed_${response.status}`);
          continue;
        }
        const body = await response.text();
        throw new Error(body || `request_failed_${response.status}`);
      }
      activeApiBase = base;
      return response.json();
    } catch (error) {
      lastError = error;
    }
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
  return request('/api/projects');
}

export function getProjectSnapshot(projectId) {
  return request(`/api/projects/${projectId}`);
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
    source = new EventSource(`${base}/api/projects/${projectId}/stream`);
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
