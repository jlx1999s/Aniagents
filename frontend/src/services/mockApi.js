const baseSnapshot = {
  projectId: 'MANJU_0429',
  stage: '分镜审核',
  mode: '人工介入',
  qualityPass: 4,
  qualityTotal: 5,
  renderCost: 12.84,
  eta: '00:03:42'
};

export function getInitialProjectSnapshot() {
  return { ...baseSnapshot };
}

export function getNextProjectSnapshot(previous, step) {
  const etaMinutes = 3 - Math.min(step, 2);
  const etaSeconds = 42 - (step * 11) % 45;
  const stageList = ['分镜审核', '动画渲染', '音频对齐', '合成输出'];
  return {
    ...previous,
    stage: stageList[step % stageList.length],
    qualityPass: Math.min(5, 3 + (step % 3)),
    renderCost: Number((previous.renderCost + 0.36).toFixed(2)),
    eta: `00:0${Math.max(0, etaMinutes)}:${String(Math.max(5, etaSeconds)).padStart(2, '0')}`
  };
}
