export const navLinks = ['总览', '项目', '流水线', '资产', '质检'];

export const pipelineStages = [
  {
    key: 'scriptwriter',
    title: '剧本生成',
    desc: '将用户意图拆解为分镜结构、台词与节奏分布。'
  },
  {
    key: 'art-director',
    title: '美术总监',
    desc: '定义色板、光照与镜头语言的统一风格基线。'
  },
  {
    key: 'character',
    title: '角色设计',
    desc: '输出角色三视图与一致性锚点，供全局渲染复用。'
  },
  {
    key: 'storyboard',
    title: '分镜设计',
    desc: '生成分镜草图，绑定台词与时长，准备动画并行。'
  },
  {
    key: 'animation',
    title: '动画生成',
    desc: '由分镜生成动态片段，保持构图与动作连续性。'
  },
  {
    key: 'sound',
    title: '音频设计',
    desc: '配音、音效与 BGM 的时间轴设计与对齐。'
  },
  {
    key: 'compositor',
    title: '合成输出',
    desc: '合成、字幕、混音并输出可交付成片。'
  }
];
