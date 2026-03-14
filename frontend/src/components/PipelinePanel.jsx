import { useState } from 'react';

function SectionTitle({ children }) {
  return <div className="panel-title">{children}</div>;
}

function PipelineNode({ item }) {
  const statusMap = {
    queued: '排队中',
    running: '执行中',
    review: '待审核',
    completed: '已完成'
  };
  const nodeLabelMap = {
    Scriptwriting: '剧本生成',
    'Style Definition': '风格定义',
    'Character Review': '角色审核',
    'Storyboard Review': '分镜审核',
    'Animation Render': '动画渲染',
    'Audio Align': '音频对齐',
    Compositor: '合成输出'
  };
  return (
    <div className="pipeline-node">
      <div className={`node-dot ${item.status}`} />
      <div className="node-main">
        <div className="node-name">{nodeLabelMap[item.label] || item.label}</div>
        <div className="node-meta">
          <span>{statusMap[item.status] || item.status}</span>
          <span>执行 {item.runCount} 次</span>
          <span>${item.cost}</span>
        </div>
      </div>
    </div>
  );
}

function AssetRow({ label, value }) {
  return (
    <div className="asset-row">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}

const reviewNodeOptions = [
  { value: 'Scriptwriter_Agent', label: '剧本生成节点' },
  { value: 'Art_Director_Agent', label: '美术风格节点' },
  { value: 'Character_Designer_Agent', label: '角色设计节点' },
  { value: 'Scene_Designer_Agent', label: '场景设计节点' },
  { value: 'Storyboard_Artist_Agent', label: '分镜节点' },
  { value: 'Animation_Artist_Agent', label: '动画节点' },
  { value: 'Sound_Director_Agent', label: '音频节点' },
  { value: 'Compositor_Agent', label: '合成节点' }
];

export default function PipelinePanel({
  stages,
  snapshot,
  projectIds,
  activeProjectId,
  draftPrompt,
  connectionStatus,
  errorMessage,
  actions
}) {
  const [reviewForm, setReviewForm] = useState({
    stage: 'storyboard',
    issueType: '构图与节奏',
    priority: 'high',
    targetNode: 'Storyboard_Artist_Agent',
    operatorId: '审核员-演示',
    message: '镜头节奏和角色站位需要重排'
  });
  const canReview = snapshot.approvalRequired;
  const modeMap = {
    'Human-in-the-loop': '人工介入',
    'Human-in-loop': '人工介入',
    'human-in-the-loop': '人工介入'
  };
  const stageMap = {
    Scriptwriting: '剧本生成',
    'Style Definition': '风格定义',
    'Character Review': '角色审核',
    'Storyboard Review': '分镜审核',
    'Animation Render': '动画渲染',
    'Audio Align': '音频对齐',
    Compositor: '合成输出',
    Queued: '排队中'
  };
  const connectionMap = {
    connecting: '连接中',
    online: '在线',
    reconnecting: '重连中',
    offline: '离线'
  };
  const reviewActionMap = {
    approve: '通过',
    revise: '返修',
    reject: '拒绝'
  };

  const setField = (key, value) => {
    setReviewForm((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <aside className="data-panel">
      <div>
        <div className="panel-section">
          <SectionTitle>项目控制台</SectionTitle>
          <div className="panel-body-gold">
            项目ID: {snapshot.projectId || '无'}
            <br />
            阶段: {stageMap[snapshot.stage] || snapshot.stage}
            <br />
            连接: {connectionMap[connectionStatus] || connectionStatus}
            <br />
            模式: {modeMap[snapshot.mode] || snapshot.mode}
          </div>
          <select
            className="field-select"
            value={activeProjectId}
            onChange={(event) => actions.selectProject(event.target.value)}
          >
            <option value="">请选择项目</option>
            {projectIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          <textarea
            className="field-textarea"
            value={draftPrompt}
            onChange={(event) => actions.updateDraftPrompt(event.target.value)}
          />
          <div className="review-action-row">
            <button className="review-btn" type="button" onClick={() => actions.createNewProject()}>
              新建项目
            </button>
            <button className="review-btn" type="button" onClick={() => actions.advanceNow()}>
              手动推进
            </button>
            <button className="review-btn" type="button" disabled={!canReview} onClick={() => actions.approveReview()}>
              快速通过
            </button>
          </div>
          {errorMessage ? <div className="panel-error">{errorMessage}</div> : null}
        </div>

        <div className="panel-section">
          <SectionTitle>生产线视图</SectionTitle>
          <div className="panel-text">
            参考 OIIOII 风格改为任务中心视角：状态流、节点耗费、审核入口统一在同屏可控。
          </div>
          <div className="stage-list">
            {snapshot.nodeMetrics.map((metric) => (
              <PipelineNode key={metric.node} item={metric} />
            ))}
            {snapshot.nodeMetrics.length === 0
              ? stages.map((item) => (
                  <div className="semiotic-item-el" key={item.key}>
                    <div className="stage-title">{item.title}</div>
                    <div className="stage-desc">{item.desc}</div>
                  </div>
                ))
              : null}
          </div>
        </div>

        <div className="panel-section">
          <SectionTitle>审核台</SectionTitle>
          <div className="field-grid">
            <select
              className="field-select"
              value={reviewForm.stage}
              onChange={(event) => setField('stage', event.target.value)}
            >
              <option value="character">角色</option>
              <option value="scene">场景</option>
              <option value="storyboard">分镜</option>
              <option value="animation">动画</option>
              <option value="audio">音频</option>
              <option value="compositor">合成</option>
            </select>
            <input
              className="field-input"
              value={reviewForm.issueType}
              onChange={(event) => setField('issueType', event.target.value)}
            />
            <select
              className="field-select"
              value={reviewForm.priority}
              onChange={(event) => setField('priority', event.target.value)}
            >
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select>
            <select
              className="field-select"
              value={reviewForm.targetNode}
              onChange={(event) => setField('targetNode', event.target.value)}
            >
              {reviewNodeOptions.map((node) => (
                <option key={node.value} value={node.value}>
                  {node.label}
                </option>
              ))}
            </select>
            <input
              className="field-input"
              value={reviewForm.operatorId}
              onChange={(event) => setField('operatorId', event.target.value)}
            />
            <textarea
              className="field-textarea small"
              value={reviewForm.message}
              onChange={(event) => setField('message', event.target.value)}
            />
          </div>
          <div className="review-action-row">
            <button className="review-btn" disabled={!canReview} onClick={() => actions.approveReview()} type="button">
              通过
            </button>
            <button
              className="review-btn"
              disabled={!canReview}
              onClick={() => actions.requestRevision(reviewForm)}
              type="button"
            >
              返修
            </button>
            <button
              className="review-btn danger"
              disabled={!canReview}
              onClick={() => actions.rejectProject(reviewForm)}
              type="button"
            >
              拒绝
            </button>
          </div>
        </div>
      </div>

      <div className="panel-section panel-bottom">
        <SectionTitle>资产与观测</SectionTitle>
        <div className="panel-body-light">
          质量门禁: {snapshot.qualityPass}/{snapshot.qualityTotal} 通过
          <br />
          渲染成本: ${snapshot.renderCost}
          <br />
          预计完成: {snapshot.eta}
        </div>
        <div className="asset-grid">
          <AssetRow label="剧本" value={snapshot.assets.scriptReady ? '已就绪' : '待生成'} />
          <AssetRow label="风格" value={snapshot.assets.styleReady ? '已就绪' : '待生成'} />
          <AssetRow label="角色资产" value={snapshot.assets.characterCount} />
          <AssetRow label="场景资产" value={snapshot.assets.sceneCount} />
          <AssetRow label="分镜资产" value={snapshot.assets.storyboardCount} />
          <AssetRow label="视频片段" value={snapshot.assets.videoCount} />
          <AssetRow label="音频轨道" value={snapshot.assets.audioCount} />
        </div>
        <div className="stage-desc">成片地址: {snapshot.assets.finalVideoUri || '尚未生成'}</div>
        <div className="stage-desc">
          最近审核: {reviewActionMap[snapshot.latestReview?.action] || '暂无'}
        </div>
      </div>
    </aside>
  );
}
