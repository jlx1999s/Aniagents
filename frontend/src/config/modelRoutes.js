export const modelStages = [
  { key: 'scriptwriter', title: '剧本生成', tasks: [{ key: 'script', title: '脚本生成' }] },
  { key: 'art-director', title: '美术总监', tasks: [{ key: 'style', title: '风格规划' }] },
  { key: 'character', title: '角色设计', tasks: [{ key: 'image', title: '图像生成' }] },
  { key: 'storyboard', title: '分镜设计', tasks: [{ key: 'image', title: '分镜图像' }] },
  { key: 'animation', title: '动画生成', tasks: [{ key: 'video', title: '视频生成' }] },
  { key: 'sound', title: '音频设计', tasks: [{ key: 'tts', title: '配音' }, { key: 'bgm', title: 'BGM' }] },
  { key: 'compositor', title: '合成输出', tasks: [{ key: 'compose', title: '时间轴合成' }] },
  { key: 'qa', title: '质检', tasks: [{ key: 'qa', title: '质量检测' }] }
];

export function createDefaultModelRoutes() {
  const routes = {};
  modelStages.forEach((stage) => {
    routes[stage.key] = {};
    stage.tasks.forEach((task) => {
      routes[stage.key][task.key] = {
        provider: 'mock',
        baseUrl: '',
        model: `${task.key}-mock`,
        enabled: true,
        params: {}
      };
    });
  });
  return {
    version: 1,
    updatedAt: new Date().toISOString(),
    defaults: {
      provider: 'mock',
      baseUrl: ''
    },
    routes
  };
}

export function normalizeModelRoutes(input) {
  const fallback = createDefaultModelRoutes();
  if (!input || typeof input !== 'object') {
    return fallback;
  }
  const routes = {};
  modelStages.forEach((stage) => {
    const stageInput = input.routes?.[stage.key] || {};
    routes[stage.key] = {};
    stage.tasks.forEach((task) => {
      const taskInput = stageInput?.[task.key] || {};
      routes[stage.key][task.key] = {
        provider: String(taskInput.provider ?? input.defaults?.provider ?? fallback.defaults.provider),
        baseUrl: String(taskInput.baseUrl ?? input.defaults?.baseUrl ?? fallback.defaults.baseUrl),
        model: String(taskInput.model ?? fallback.routes[stage.key][task.key].model),
        enabled: Boolean(taskInput.enabled ?? true),
        params: typeof taskInput.params === 'object' && taskInput.params ? taskInput.params : {}
      };
    });
  });
  return {
    version: Number(input.version ?? fallback.version),
    updatedAt: typeof input.updatedAt === 'string' ? input.updatedAt : fallback.updatedAt,
    defaults: {
      provider: String(input.defaults?.provider ?? fallback.defaults.provider),
      baseUrl: String(input.defaults?.baseUrl ?? fallback.defaults.baseUrl)
    },
    routes
  };
}
