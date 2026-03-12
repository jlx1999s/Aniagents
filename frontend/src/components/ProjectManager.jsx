import { useMemo, useState } from 'react';

function StatusChip({ status }) {
  const statusText = {
    running: '进行中',
    waiting_review: '待审核',
    completed: '已完成',
    rejected: '已拒绝',
    failed: '失败'
  };
  return <span className={`project-status-chip ${status}`}>{statusText[status] || status}</span>;
}

function ProjectCard({ item, isActive, onOpen, onAdvance }) {
  return (
    <div className={`project-card ${isActive ? 'active' : ''}`}>
      <div className="project-card-top">
        <div className="project-id">{item.projectId}</div>
        <StatusChip status={item.status} />
      </div>
      <div className="project-prompt">{item.prompt || '暂无描述'}</div>
      <div className="project-meta-grid">
        <div>阶段：{item.stage}</div>
        <div>成本：${item.renderCost}</div>
        <div>ETA：{item.eta}</div>
        <div>门禁：{item.qualityPass}/{item.qualityTotal}</div>
      </div>
      <div className="project-card-actions">
        <button type="button" className="review-btn" onClick={() => onOpen(item.projectId)}>
          打开项目
        </button>
        <button type="button" className="review-btn" onClick={() => onAdvance(item.projectId)}>
          推进一步
        </button>
      </div>
    </div>
  );
}

export default function ProjectManager({
  projectSummaries,
  snapshot,
  activeProjectId,
  draftPrompt,
  loadingProjects,
  actions,
  onOpenProject,
  errorMessage,
  connectionStatus
}) {
  const [keyword, setKeyword] = useState('');
  const [busyProjectId, setBusyProjectId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState('');
  const effectiveProjects = useMemo(() => {
    if (projectSummaries.length > 0) {
      return projectSummaries;
    }
    if (snapshot?.projectId) {
      return [snapshot];
    }
    return [];
  }, [projectSummaries, snapshot]);

  const filtered = useMemo(() => {
    const value = keyword.trim().toLowerCase();
    if (!value) {
      return effectiveProjects;
    }
    return effectiveProjects.filter(
      (item) =>
        item.projectId.toLowerCase().includes(value) || (item.prompt || '').toLowerCase().includes(value)
    );
  }, [keyword, effectiveProjects]);

  const stats = useMemo(() => {
    const total = effectiveProjects.length;
    const running = effectiveProjects.filter((item) => item.status === 'running').length;
    const review = effectiveProjects.filter((item) => item.status === 'waiting_review').length;
    const completed = effectiveProjects.filter((item) => item.status === 'completed').length;
    return { total, running, review, completed };
  }, [effectiveProjects]);

  return (
    <section className="project-manager">
      <div className="project-manager-header">
        <div>
          <div className="project-manager-title">项目管理</div>
          <div className="project-manager-subtitle">统一管理全部项目生命周期、状态与推进动作</div>
        </div>
        <button
          type="button"
          className="review-btn"
          disabled={loadingProjects || submitting}
          onClick={async () => {
            try {
              setLocalError('');
              setSubmitting(true);
              await actions.refreshProjects();
            } catch (error) {
              setLocalError(error instanceof Error ? error.message : '刷新失败');
            } finally {
              setSubmitting(false);
            }
          }}
        >
          刷新列表
        </button>
      </div>

      <div className="project-health-row">
        <div>实时链路：{connectionStatus === 'online' ? '在线' : connectionStatus === 'offline' ? '离线' : '重连中'}</div>
        <div>{errorMessage || localError || '系统正常'}</div>
      </div>

      <div className="project-stats-row">
        <div className="project-stat-box">总项目：{stats.total}</div>
        <div className="project-stat-box">进行中：{stats.running}</div>
        <div className="project-stat-box">待审核：{stats.review}</div>
        <div className="project-stat-box">已完成：{stats.completed}</div>
      </div>

      <div className="project-create-box">
        <div className="panel-title">新建项目</div>
        <textarea
          className="field-textarea"
          value={draftPrompt}
          onChange={(event) => actions.updateDraftPrompt(event.target.value)}
        />
        <div className="project-create-actions">
          <button
            type="button"
            className="review-btn"
            disabled={submitting}
            onClick={async () => {
              try {
                setLocalError('');
                setSubmitting(true);
                await actions.createNewProject();
              } catch (error) {
                setLocalError(error instanceof Error ? error.message : '创建项目失败');
              } finally {
                setSubmitting(false);
              }
            }}
          >
            创建项目
          </button>
        </div>
      </div>

      <div className="project-filter-row">
        <input
          className="field-input"
          placeholder="按项目ID或提示词筛选"
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
        />
        <div className="project-filter-hint">{loadingProjects ? '加载中...' : `共 ${filtered.length} 条`}</div>
      </div>

      <div className="project-list-grid">
        {filtered.length > 0 ? (
          filtered.map((item) => (
            <div key={item.projectId} className="project-card-wrap">
              <ProjectCard
                item={item}
                isActive={item.projectId === activeProjectId}
                onOpen={async (projectId) => {
                  try {
                    setLocalError('');
                    setBusyProjectId(projectId);
                    await onOpenProject(projectId);
                  } catch (error) {
                    setLocalError(error instanceof Error ? error.message : '打开项目失败');
                  } finally {
                    setBusyProjectId('');
                  }
                }}
                onAdvance={async (projectId) => {
                  try {
                    setLocalError('');
                    setBusyProjectId(projectId);
                    await actions.advanceById(projectId);
                  } catch (error) {
                    setLocalError(error instanceof Error ? error.message : '推进失败');
                  } finally {
                    setBusyProjectId('');
                  }
                }}
              />
              {busyProjectId === item.projectId ? <div className="project-card-loading">处理中...</div> : null}
            </div>
          ))
        ) : (
          <div className="project-empty-state">暂无匹配项目，请调整筛选或创建新项目。</div>
        )}
      </div>
    </section>
  );
}
