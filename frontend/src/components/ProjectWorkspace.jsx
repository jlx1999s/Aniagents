import { useMemo, useState } from 'react';

const nodeChoices = [
  { value: 'Character_Designer_Agent', label: '角色设计节点' },
  { value: 'Storyboard_Artist_Agent', label: '分镜节点' },
  { value: 'Animation_Artist_Agent', label: '动画节点' },
  { value: 'Sound_Director_Agent', label: '音频节点' },
  { value: 'Compositor_Agent', label: '合成节点' }
];

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

export default function ProjectWorkspace({ snapshot, actions, onBack }) {
  const [activeTab, setActiveTab] = useState('characters');
  const [message, setMessage] = useState('角色服饰细节需要更贴近赛博朋克主题');
  const [targetNode, setTargetNode] = useState('Character_Designer_Agent');
  const canReview = snapshot.approvalRequired;
  const stageText = {
    Scriptwriting: '剧本生成',
    'Style Definition': '风格定义',
    'Character Review': '角色审核',
    'Storyboard Review': '分镜审核',
    'Animation Render': '动画渲染',
    'Audio Align': '音频对齐',
    Compositor: '合成输出'
  };

  const feed = useMemo(() => {
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
    return [...base, ...review];
  }, [snapshot.history, snapshot.reviewLogs]);

  const gallery = snapshot.assetGallery || { characters: [], storyboards: [], videos: [] };
  const activeItems = gallery[activeTab] || [];

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

      <div className="workspace-main">
        <aside className="workspace-chat">
          <div className="workspace-title">对话与操作</div>
          <div className="chat-feed">
            {feed.map((item) => (
              <div key={item.id} className="chat-item">
                <div className="chat-role">{item.role}</div>
                <div className="chat-text">{item.text}</div>
              </div>
            ))}
          </div>
          <textarea className="field-textarea" value={message} onChange={(event) => setMessage(event.target.value)} />
          <select className="field-select" value={targetNode} onChange={(event) => setTargetNode(event.target.value)}>
            {nodeChoices.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <div className="workspace-chat-actions">
            <button
              type="button"
              className="review-btn"
              disabled={!canReview}
              onClick={() =>
                actions.requestRevision({
                  stage: snapshot.approvalStage || 'storyboard',
                  issueType: '人工反馈',
                  priority: 'high',
                  targetNode,
                  operatorId: '项目操作员',
                  message
                })
              }
            >
              提交返修
            </button>
            <button type="button" className="review-btn" disabled={!canReview} onClick={() => actions.approveReview()}>
              审核通过
            </button>
            <button
              type="button"
              className="review-btn danger"
              disabled={!canReview}
              onClick={() =>
                actions.rejectProject({
                  stage: snapshot.approvalStage || 'storyboard',
                  issueType: '人工拒绝',
                  priority: 'high',
                  operatorId: '项目操作员',
                  message
                })
              }
            >
              拒绝
            </button>
          </div>
        </aside>

        <div className="workspace-canvas">
          <div className="workspace-title">实时画布</div>
          <div className="canvas-tabs">
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
            <button type="button" className="review-btn" onClick={() => actions.advanceNow()}>
              推进执行
            </button>
          </div>
          <div className="media-grid">
            {activeItems.length > 0 ? (
              activeItems.map((item) => <MediaCard key={item.assetId + item.sourceUri} item={item} />)
            ) : (
              <div className="media-empty">当前标签暂无可展示素材，流程推进后将实时出现。</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
