import { useEffect, useMemo, useRef, useState } from 'react';
import AgentOfficeBoard from './AgentOfficeBoard';
import { officeCharacterLibrary } from '../config/officeCharacters';

const nodeLabelMap = {
  Scriptwriter_Agent: '分镜拆解',
  Character_Designer_Agent: '角色生成',
  Storyboard_Artist_Agent: '分镜图生成',
  Animation_Artist_Agent: '视频生成'
};

const nodeActorMap = {
  Scriptwriter_Agent: '分镜师',
  Character_Designer_Agent: '角色设计师',
  Storyboard_Artist_Agent: '分镜画师',
  Animation_Artist_Agent: '动画师'
};

const reviewStageByNode = {
  Scriptwriter_Agent: 'script',
  Character_Designer_Agent: 'character',
  Storyboard_Artist_Agent: 'storyboard',
  Animation_Artist_Agent: 'animation'
};

function MediaCard({ item }) {
  if (item.kind === 'video') {
    const isGif = item.previewUri?.toLowerCase().endsWith('.gif');
    return (
      <div className="media-card">
        {isGif ? (
          <img className="media-image" src={item.previewUri} alt={item.assetId} />
        ) : (
          <video className="media-video" src={item.previewUri} controls />
        )}
        <div className="media-caption">{item.sourceUri}</div>
      </div>
    );
  }
  return (
    <div className="media-card">
      <img className="media-image" src={item.previewUri} alt={item.assetId} />
      <div className="media-caption">{item.sourceUri}</div>
    </div>
  );
}

function targetNodeToPrompt(targetNode) {
  if (targetNode.includes('Scriptwriter')) {
    return '分镜拆解';
  }
  if (targetNode.includes('Storyboard')) {
    return '分镜图';
  }
  if (targetNode.includes('Character')) {
    return '角色';
  }
  return '视频';
}

function normalizeWorkspaceError(error, fallback) {
  const message = error instanceof Error ? error.message : '';
  const lower = message.toLowerCase();
  if (
    lower.includes('load failed') ||
    lower.includes('failed to fetch') ||
    lower.includes('networkerror')
  ) {
    return '连接后端失败，请确认后端服务已启动后重试';
  }
  return message || fallback;
}

function resolveReviewNode(snapshot) {
  const reviewStep = (snapshot.executionPlan || []).find((item) => item.status === 'review');
  if (reviewStep?.node) {
    return reviewStep.node;
  }
  const reviewMetric = (snapshot.nodeMetrics || []).find((item) => item.status === 'review');
  if (reviewMetric?.node) {
    return reviewMetric.node;
  }
  return snapshot.currentNode || '';
}

function formatSystemEvent(entry) {
  const payload = entry.payload || {};
  const thought = payload.thought ? `思考：${payload.thought}` : '';
  const reply = payload.reply ? `回复：${payload.reply}` : '';
  const details = [thought, reply].filter(Boolean).join('\n');
  if (entry.kind === 'manager_decision') {
    const action = payload.action || 'unknown';
    const nextNode = payload.next_node ? nodeLabelMap[payload.next_node] || payload.next_node : '无';
    const reason = payload.reason || 'n/a';
    const head = `决策：${action} → ${nextNode}（${reason}）`;
    return details ? `${head}\n${details}` : head;
  }
  if (entry.kind === 'tool_execution') {
    const node = payload.node ? nodeLabelMap[payload.node] || payload.node : '未知节点';
    const latency = Number.isFinite(payload.latency_ms) ? `${payload.latency_ms}ms` : '-';
    const head = `执行：${node}，耗时 ${latency}`;
    return details ? `${head}\n${details}` : head;
  }
  if (entry.kind === 'review_gateway') {
    const reason = payload.reason || 'auto_progress';
    const status = payload.status || 'running';
    const head = `网关：${reason}，状态 ${status}`;
    return details ? `${head}\n${details}` : head;
  }
  if (entry.kind === 'history') {
    const event = payload.event || '';
    const mapped = nodeLabelMap[event];
    if (mapped) {
      return `节点完成：${mapped}`;
    }
    return `流程事件：${event}`;
  }
  return `流程事件：${payload.event || entry.kind || ''}`;
}

function resolveEventActor(entry) {
  const payload = entry.payload || {};
  if (payload.actor) {
    return payload.actor;
  }
  if (entry.kind === 'history') {
    const event = payload.event || '';
    if (nodeActorMap[event]) {
      return nodeActorMap[event];
    }
  }
  return '系统';
}

function resolveActiveActor(snapshot) {
  const executionPlan = snapshot.executionPlan || [];
  const runningStep = executionPlan.find((item) => item.status === 'running');
  if (runningStep?.node && nodeActorMap[runningStep.node]) {
    return nodeActorMap[runningStep.node];
  }
  const nextStep = executionPlan.find((item) => item.status === 'next');
  if (nextStep?.node && nodeActorMap[nextStep.node]) {
    return nodeActorMap[nextStep.node];
  }
  if (snapshot.currentNode && nodeActorMap[snapshot.currentNode]) {
    return nodeActorMap[snapshot.currentNode];
  }
  return '导演';
}

const roleVisualByActor = {
  导演: {
    sprite: officeCharacterLibrary.director.sprite,
    accent: 'director'
  },
  分镜师: {
    sprite: officeCharacterLibrary.Scriptwriter_Agent.sprite,
    accent: officeCharacterLibrary.Scriptwriter_Agent.accent
  },
  角色设计师: {
    sprite: officeCharacterLibrary.Character_Designer_Agent.sprite,
    accent: officeCharacterLibrary.Character_Designer_Agent.accent
  },
  分镜画师: {
    sprite: officeCharacterLibrary.Storyboard_Artist_Agent.sprite,
    accent: officeCharacterLibrary.Storyboard_Artist_Agent.accent
  },
  动画师: {
    sprite: officeCharacterLibrary.Animation_Artist_Agent.sprite,
    accent: officeCharacterLibrary.Animation_Artist_Agent.accent
  }
};

function resolveRoleVisual(role) {
  if (roleVisualByActor[role]) {
    return roleVisualByActor[role];
  }
  if (role.includes('审核')) {
    return { sprite: officeCharacterLibrary.director.sprite, accent: 'reviewer' };
  }
  if (role.includes('系统')) {
    return { sprite: officeCharacterLibrary.director.sprite, accent: 'system' };
  }
  return { sprite: officeCharacterLibrary.director.sprite, accent: 'generic' };
}

export default function ProjectWorkspace({ snapshot, actions, onBack }) {
  const [activeTab, setActiveTab] = useState('table');
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [canvasBottomCollapsed, setCanvasBottomCollapsed] = useState(false);
  const [message, setMessage] = useState('继续生成，保持热血少年漫风格');
  const [submitting, setSubmitting] = useState(false);
  const [chatError, setChatError] = useState('');
  const [chatPanelWidth, setChatPanelWidth] = useState(520);
  const [isResizing, setIsResizing] = useState(false);
  const [policyOpen, setPolicyOpen] = useState(false);
  const [policyMode, setPolicyMode] = useState('hybrid');
  const [policyLlmMinConfidence, setPolicyLlmMinConfidence] = useState(0.75);
  const [policyRuleBypass, setPolicyRuleBypass] = useState(0.91);
  const [policyForceRuleReview, setPolicyForceRuleReview] = useState(true);
  const chatFeedRef = useRef(null);
  const workspaceMainRef = useRef(null);
  const stageText = {
    分镜拆解: '分镜拆解',
    角色生成: '角色生成',
    分镜图生成: '分镜图生成',
    视频生成: '视频生成',
    'Style Review': '风格确认'
  };

  const feed = useMemo(() => {
    const timeline = snapshot.activityLogs || [];
    if (timeline.length > 0) {
      return timeline.map((entry, index) => {
        if (entry.kind === 'chat') {
          const rawRole = entry.payload?.role || 'Agent';
          const role = rawRole === 'Agent' ? '导演' : rawRole;
          return {
            id: `a-chat-${entry.index ?? index}`,
            role,
            text: entry.payload?.message || ''
          };
        }
        if (entry.kind === 'review') {
          return {
            id: `a-review-${entry.index ?? index}`,
            role: entry.payload?.operator_id || '审核员',
            text: `${entry.payload?.action || 'review'} · ${entry.payload?.message || '无备注'}`
          };
        }
        return {
          id: `a-history-${entry.index ?? index}`,
          role: resolveEventActor(entry),
          text: formatSystemEvent(entry)
        };
      });
    }
    const chat = (snapshot.chatLogs || []).map((entry, index) => ({
      id: `c-${index}`,
      role: (entry.role || 'Agent') === 'Agent' ? '导演' : entry.role || 'Agent',
      text: entry.message || ''
    }));
    const base = snapshot.history.map((entry, index) => ({
      id: `h-${index}`,
      role: '系统',
      text: `流程事件：${entry}`
    }));
    const review = (snapshot.reviewLogs || []).map((entry, index) => ({
      id: `r-${index}`,
      role: entry.operator_id || '审核员',
      text: `${entry.action} · ${entry.message || '无备注'}`
    }));
    return [...chat, ...base, ...review];
  }, [snapshot.activityLogs, snapshot.chatLogs, snapshot.history, snapshot.reviewLogs]);

  const gallery = snapshot.assetGallery || { characters: [], storyboards: [], videos: [] };
  const storyboardTable = snapshot.storyboardTable || [];
  const activeItems = activeTab === 'table' ? [] : gallery[activeTab] || [];
  const reviewNode = useMemo(() => resolveReviewNode(snapshot), [snapshot]);
  const reviewNodeLabel = nodeLabelMap[reviewNode] || '当前节点';
  const fallbackNode = snapshot.currentNode || 'Character_Designer_Agent';
  const commandTargetNode = reviewNode || fallbackNode;
  const activeActor = useMemo(() => resolveActiveActor(snapshot), [snapshot]);
  const highlightedChatId = useMemo(() => {
    for (let i = feed.length - 1; i >= 0; i -= 1) {
      if (feed[i].role === activeActor) {
        return feed[i].id;
      }
    }
    return feed.length > 0 ? feed[feed.length - 1].id : '';
  }, [feed, activeActor]);

  useEffect(() => {
    const container = chatFeedRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [feed]);

  useEffect(() => {
    const policy = snapshot.intentRouterPolicy || {};
    const rules = policy.rules || {};
    const mode = typeof rules.mode === 'string' ? rules.mode : 'hybrid';
    const llmMinConfidence = Number.isFinite(Number(rules.llmMinConfidence))
      ? Number(rules.llmMinConfidence)
      : 0.75;
    const ruleBypass = Number.isFinite(Number(rules.ruleHighConfidenceBypass))
      ? Number(rules.ruleHighConfidenceBypass)
      : 0.91;
    setPolicyMode(mode);
    setPolicyLlmMinConfidence(Math.max(0, Math.min(llmMinConfidence, 1)));
    setPolicyRuleBypass(Math.max(0, Math.min(ruleBypass, 1)));
    setPolicyForceRuleReview(Boolean(rules.forceRuleWhenAwaitingReview));
  }, [snapshot.intentRouterPolicy]);

  useEffect(() => {
    const clampWidth = () => {
      const container = workspaceMainRef.current;
      if (!container) {
        return;
      }
      const nextMax = Math.max(420, container.clientWidth - 560);
      setChatPanelWidth((prev) => Math.min(Math.max(prev, 420), nextMax));
    };
    clampWidth();
    window.addEventListener('resize', clampWidth);
    return () => window.removeEventListener('resize', clampWidth);
  }, []);

  const handleResizeStart = (event) => {
    const container = workspaceMainRef.current;
    if (!container) {
      return;
    }
    event.preventDefault();
    const rect = container.getBoundingClientRect();
    const minWidth = 420;
    const maxWidth = Math.max(minWidth, rect.width - 560);
    setIsResizing(true);
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    const handleMouseMove = (moveEvent) => {
      const nextWidth = Math.min(Math.max(moveEvent.clientX - rect.left, minWidth), maxWidth);
      setChatPanelWidth(nextWidth);
    };
    const handleMouseUp = () => {
      setIsResizing(false);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const handleResizerKeyDown = (event) => {
    const container = workspaceMainRef.current;
    if (!container) {
      return;
    }
    const minWidth = 420;
    const maxWidth = Math.max(minWidth, container.clientWidth - 560);
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      setChatPanelWidth((prev) => Math.max(minWidth, prev - 24));
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      setChatPanelWidth((prev) => Math.min(maxWidth, prev + 24));
    }
  };

  const handleChatSubmit = async () => {
    if (submitting) {
      return;
    }
    setSubmitting(true);
    try {
      setChatError('');
      await actions.chatWithAgent(message);
      setMessage('');
    } catch (error) {
      setChatError(normalizeWorkspaceError(error, '发送失败，请稍后重试'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleQuickCommand = async (command) => {
    if (submitting) {
      return;
    }
    setSubmitting(true);
    try {
      setChatError('');
      await actions.chatWithAgent(command);
    } catch (error) {
      setChatError(normalizeWorkspaceError(error, '指令发送失败，请稍后重试'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReviseShot = async (row, index) => {
    const shotNo = row?.shotNo || index + 1;
    const beat = row?.beat || row?.visual || '当前镜头';
    await handleQuickCommand(`重做分镜图第${shotNo}镜头，重点：${beat}，强化情绪与节奏`);
  };
  const handleApproveReview = async () => {
    if (submitting) {
      return;
    }
    setSubmitting(true);
    try {
      setChatError('');
      await actions.approveReview();
    } catch (error) {
      setChatError(normalizeWorkspaceError(error, '审核通过失败，请稍后重试'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveIntentPolicy = async () => {
    if (submitting) {
      return;
    }
    setSubmitting(true);
    try {
      setChatError('');
      await actions.updateIntentRouterPolicy({
        rules: {
          mode: policyMode,
          llmMinConfidence: Number(policyLlmMinConfidence.toFixed(2)),
          ruleHighConfidenceBypass: Number(policyRuleBypass.toFixed(2)),
          forceRuleWhenAwaitingReview: policyForceRuleReview
        }
      });
      setPolicyOpen(false);
    } catch (error) {
      setChatError(normalizeWorkspaceError(error, '策略更新失败，请稍后重试'));
    } finally {
      setSubmitting(false);
    }
  };
  const handleReviseReviewNode = async () => {
    if (submitting) {
      return;
    }
    setSubmitting(true);
    try {
      setChatError('');
      const reviseTargetNode = commandTargetNode;
      await actions.requestRevision({
        stage: reviewStageByNode[reviseTargetNode] || snapshot.approvalStage || 'manual',
        issueType: `${reviewNodeLabel}需调整`,
        priority: 'high',
        targetNode: reviseTargetNode,
        operatorId: '项目操作员',
        message: `返修${reviewNodeLabel}，强化质量与可用性`
      });
    } catch (error) {
      setChatError(normalizeWorkspaceError(error, '提交返修失败，请稍后重试'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="project-workspace">
      <div className="workspace-header">
        <div>
          <div className="project-manager-title">项目工作台</div>
          <div className="project-manager-subtitle">
            当前项目：{snapshot.projectId} ｜ 阶段：{stageText[snapshot.stage] || snapshot.stage}
          </div>
        </div>
        <button type="button" className="review-btn" onClick={onBack}>
          返回项目列表
        </button>
      </div>

      <div
        className={`workspace-main ${chatCollapsed ? 'is-chat-collapsed' : ''}`}
        ref={workspaceMainRef}
        style={{ '--chat-panel-width': `${chatPanelWidth}px` }}
      >
        <aside className="workspace-chat">
          <div className="workspace-chat-inner">
            <div className="workspace-title-row">
              <div className="workspace-title">Agent 对话与操作</div>
              <div className="workspace-title-actions">
                <button
                  type="button"
                  className="intent-policy-btn"
                  disabled={submitting}
                  onClick={() => setPolicyOpen((open) => !open)}
                >
                  策略开关
                </button>
                <button
                  type="button"
                  className="panel-collapse-triangle"
                  onClick={() => setChatCollapsed((prev) => !prev)}
                  aria-label={chatCollapsed ? '展开Agent对话区' : '收起Agent对话区'}
                >
                  {chatCollapsed ? '▸' : '◂'}
                </button>
              </div>
            </div>
            {policyOpen ? (
              <div className="intent-policy-panel">
                <div className="intent-policy-title">当前项目策略</div>
                <div className="intent-policy-grid">
                  <label className="intent-policy-field">
                    <span>路由模式</span>
                    <select
                      className="field-select"
                      value={policyMode}
                      onChange={(event) => setPolicyMode(event.target.value)}
                    >
                      <option value="rule_only">仅规则</option>
                      <option value="hybrid">混合路由</option>
                      <option value="model_first">模型优先</option>
                    </select>
                  </label>
                  <label className="intent-policy-field">
                    <span>模型置信度阈值：{policyLlmMinConfidence.toFixed(2)}</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={policyLlmMinConfidence}
                      onChange={(event) => setPolicyLlmMinConfidence(Number(event.target.value))}
                    />
                  </label>
                  <label className="intent-policy-field">
                    <span>规则直通阈值：{policyRuleBypass.toFixed(2)}</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={policyRuleBypass}
                      onChange={(event) => setPolicyRuleBypass(Number(event.target.value))}
                    />
                  </label>
                  <label className="intent-policy-check">
                    <input
                      type="checkbox"
                      checked={policyForceRuleReview}
                      onChange={(event) => setPolicyForceRuleReview(event.target.checked)}
                    />
                    审核中强制规则路由
                  </label>
                </div>
                <button type="button" className="review-btn" disabled={submitting} onClick={handleSaveIntentPolicy}>
                  保存本项目策略
                </button>
              </div>
            ) : null}
            <div className="workspace-chat-hint">
              先输入小说文本，流程会按「分镜拆解 → 角色生成（风格确认）→ 分镜图生成 → 视频生成」推进。
            </div>
            <div className="chat-feed" ref={chatFeedRef}>
              {feed.map((item) => {
                const roleVisual = resolveRoleVisual(item.role);
                return (
                  <div
                    key={item.id}
                    className={`chat-item ${roleVisual.accent} ${item.id === highlightedChatId ? 'is-active' : ''}`}
                  >
                    <div className="chat-avatar-wrap">
                      <img className="chat-avatar" src={roleVisual.sprite} alt={item.role} loading="lazy" />
                    </div>
                    <div className="chat-main">
                      <div className="chat-role">{item.role}</div>
                      <div className="chat-text">{item.text}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            <textarea
              className="field-textarea"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="输入小说文本或修改指令，例如：修改风格为赛博朋克霓虹"
            />
            <div className="workspace-quick-actions">
              {snapshot.approvalRequired ? (
                <>
                  <button type="button" className="review-btn" disabled={submitting} onClick={handleApproveReview}>
                    通过{reviewNodeLabel}审核
                  </button>
                  <button type="button" className="review-btn" disabled={submitting} onClick={handleReviseReviewNode}>
                    返修{reviewNodeLabel}
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    className="review-btn"
                    disabled={submitting}
                    onClick={() => handleQuickCommand('开始下一阶段')}
                  >
                    推进到下一阶段
                  </button>
                  <button
                    type="button"
                    className="review-btn"
                    disabled={submitting}
                    onClick={() => handleQuickCommand('修改风格为赛博朋克霓虹，角色更锐利')}
                  >
                    修改风格
                  </button>
                </>
              )}
              <button
                type="button"
                className="review-btn"
                disabled={submitting}
                onClick={() => handleQuickCommand(`重做${targetNodeToPrompt(commandTargetNode)}，强化节奏与表现力`)}
              >
                重做当前阶段
              </button>
            </div>
            <button type="button" className="review-btn" disabled={submitting} onClick={handleChatSubmit}>
              发送给 Agent
            </button>
            {chatError ? <div className="workspace-chat-error">{chatError}</div> : null}
          </div>
        </aside>
        <div
          className={`workspace-resizer ${isResizing ? 'is-dragging' : ''}`}
          onMouseDown={handleResizeStart}
          role="separator"
          aria-label="调整对话栏宽度"
          aria-orientation="vertical"
          tabIndex={0}
          onKeyDown={handleResizerKeyDown}
        />
        <div className={`workspace-canvas ${canvasBottomCollapsed ? 'is-bottom-collapsed' : ''}`}>
          <div className="workspace-title">实时画布</div>
          <AgentOfficeBoard snapshot={snapshot} onQuickCommand={handleQuickCommand} disabled={submitting} />
          <div className={`workspace-canvas-bottom ${canvasBottomCollapsed ? 'is-collapsed' : ''}`}>
            <div className="canvas-bottom-toggle-row">
              <button
                type="button"
                className="panel-collapse-triangle panel-collapse-triangle-bottom"
                onClick={() => setCanvasBottomCollapsed((prev) => !prev)}
                aria-label={canvasBottomCollapsed ? '展开中控台下方区域' : '收起中控台下方区域'}
              >
                {canvasBottomCollapsed ? '▾' : '▴'}
              </button>
            </div>
            {canvasBottomCollapsed ? null : (
              <>
                <div className="canvas-tabs">
                  <button
                    type="button"
                    className={`canvas-tab ${activeTab === 'table' ? 'active' : ''}`}
                    onClick={() => setActiveTab('table')}
                  >
                    分镜表
                  </button>
                  <button
                    type="button"
                    className={`canvas-tab ${activeTab === 'characters' ? 'active' : ''}`}
                    onClick={() => setActiveTab('characters')}
                  >
                    人物图
                  </button>
                  <button
                    type="button"
                    className={`canvas-tab ${activeTab === 'storyboards' ? 'active' : ''}`}
                    onClick={() => setActiveTab('storyboards')}
                  >
                    分镜图
                  </button>
                  <button
                    type="button"
                    className={`canvas-tab ${activeTab === 'videos' ? 'active' : ''}`}
                    onClick={() => setActiveTab('videos')}
                  >
                    视频
                  </button>
                </div>
                {activeTab === 'table' ? (
                  <div className="storyboard-table-panel">
                    <div className="storyboard-table-title">分镜表</div>
                    <div className="storyboard-table-wrap">
                      {storyboardTable.length > 0 ? (
                        <table className="storyboard-table">
                          <thead>
                            <tr>
                              <th>镜头</th>
                              <th>叙事节拍</th>
                              <th>画面说明</th>
                              <th>对白/旁白</th>
                              <th>时长</th>
                              <th>操作</th>
                            </tr>
                          </thead>
                          <tbody>
                            {storyboardTable.map((row, index) => (
                              <tr key={`${row.shotNo || index}-${row.beat || ''}`}>
                                <td>{row.shotNo || index + 1}</td>
                                <td>{row.beat || '-'}</td>
                                <td>{row.visual || '-'}</td>
                                <td>{row.dialogue || '-'}</td>
                                <td>{row.duration || '-'}</td>
                                <td>
                                  <button
                                    type="button"
                                    className="storyboard-action-btn"
                                    disabled={submitting}
                                    onClick={() => handleReviseShot(row, index)}
                                  >
                                    重做本镜头
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <div className="storyboard-table-empty">分镜拆解后会在这里展示镜头表。</div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="media-grid" key={activeTab}>
                    {activeItems.length > 0 ? (
                      activeItems.map((item, index) => (
                        <MediaCard
                          key={`${activeTab}-${item.assetId || 'asset'}-${item.previewUri || item.sourceUri || index}`}
                          item={item}
                        />
                      ))
                    ) : (
                      <div className="media-empty">当前标签暂无可展示素材，流程推进后将实时出现。</div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
