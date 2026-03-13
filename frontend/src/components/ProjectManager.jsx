import { useEffect, useMemo, useRef, useState } from 'react';

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

function ProjectCard({ item, isActive, selected, onSelect, onOpen, onAdvance, onDelete }) {
  return (
    <div className={`project-card ${isActive ? 'active' : ''}`}>
      <div className="project-card-top">
        <label className="project-select-toggle">
          <input type="checkbox" checked={selected} onChange={(event) => onSelect(item.projectId, event.target.checked)} />
          <span>选择</span>
        </label>
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
        <button type="button" className="review-btn" onClick={() => onDelete(item.projectId)}>
          删除
        </button>
      </div>
    </div>
  );
}

export default function ProjectManager({
  projectIds,
  projectSummaries,
  snapshot,
  activeProjectId,
  draftPrompt,
  loadingProjects,
  projectStats,
  actions,
  onOpenProject,
  errorMessage,
  connectionStatus
}) {
  const [keyword, setKeyword] = useState('');
  const [busyProjectId, setBusyProjectId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState('');
  const [selectedProjectIds, setSelectedProjectIds] = useState([]);
  const selectAllRef = useRef(null);
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

  const totalProjectCount =
    typeof projectStats?.total === 'number'
      ? projectStats.total
      : projectIds.length > 0
        ? projectIds.length
        : effectiveProjects.length;

  const stats = useMemo(() => {
    const total = typeof projectStats?.total === 'number' ? projectStats.total : totalProjectCount;
    const running =
      typeof projectStats?.running === 'number'
        ? projectStats.running
        : effectiveProjects.filter((item) => item.status === 'running').length;
    const review =
      typeof projectStats?.waiting_review === 'number'
        ? projectStats.waiting_review
        : effectiveProjects.filter((item) => item.status === 'waiting_review').length;
    const completed =
      typeof projectStats?.completed === 'number'
        ? projectStats.completed
        : effectiveProjects.filter((item) => item.status === 'completed').length;
    return { total, running, review, completed };
  }, [effectiveProjects, totalProjectCount, projectStats]);

  const visibleProjectIds = useMemo(() => filtered.map((item) => item.projectId), [filtered]);
  const selectedVisibleCount = useMemo(
    () => visibleProjectIds.filter((id) => selectedProjectIds.includes(id)).length,
    [visibleProjectIds, selectedProjectIds]
  );
  const allVisibleSelected = visibleProjectIds.length > 0 && selectedVisibleCount === visibleProjectIds.length;
  const selectedCount = selectedProjectIds.length;

  useEffect(() => {
    if (!selectAllRef.current) {
      return;
    }
    const partial = selectedVisibleCount > 0 && selectedVisibleCount < visibleProjectIds.length;
    selectAllRef.current.indeterminate = partial;
  }, [selectedVisibleCount, visibleProjectIds.length]);

  const toggleSelectAllVisible = (checked) => {
    if (checked) {
      setSelectedProjectIds((prev) => [...new Set([...prev, ...visibleProjectIds])]);
      return;
    }
    setSelectedProjectIds((prev) => prev.filter((id) => !visibleProjectIds.includes(id)));
  };

  const handleDeleteSelected = async () => {
    const ids = [...new Set(selectedProjectIds)].filter(Boolean);
    if (ids.length === 0) {
      return;
    }
    const confirmed = window.confirm(
      ids.length === 1
        ? `确认删除项目 ${ids[0]} 吗？删除后不可恢复。`
        : `确认删除选中的 ${ids.length} 个项目吗？删除后不可恢复。`
    );
    if (!confirmed) {
      return;
    }
    try {
      setLocalError('');
      setSubmitting(true);
      await actions.deleteProjects(ids);
      setSelectedProjectIds((prev) => prev.filter((id) => !ids.includes(id)));
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : '删除项目失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteSingle = async (projectId) => {
    const value = String(projectId || '').trim();
    if (!value) {
      return;
    }
    const confirmed = window.confirm(`确认删除项目 ${value} 吗？删除后不可恢复。`);
    if (!confirmed) {
      return;
    }
    try {
      setLocalError('');
      setSubmitting(true);
      setBusyProjectId(value);
      await actions.deleteProjects([value]);
      setSelectedProjectIds((prev) => prev.filter((id) => id !== value));
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : '删除项目失败');
    } finally {
      setBusyProjectId('');
      setSubmitting(false);
    }
  };

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
        <div className="project-filter-hint">
          {loadingProjects
            ? '加载中...'
            : keyword.trim()
              ? `当前筛选 ${filtered.length} 条（已加载 ${effectiveProjects.length} / 总 ${totalProjectCount}）`
              : `已加载 ${effectiveProjects.length} / 总 ${totalProjectCount}`}
        </div>
      </div>

      <div className="project-filter-row">
        <label className="project-select-toggle">
          <input
            type="checkbox"
            ref={selectAllRef}
            checked={allVisibleSelected}
            onChange={(event) => toggleSelectAllVisible(event.target.checked)}
            disabled={visibleProjectIds.length === 0 || submitting}
          />
          <span>全选当前筛选</span>
        </label>
        <div className="project-filter-hint">已选 {selectedCount} 条</div>
        <button type="button" className="review-btn" disabled={selectedCount === 0 || submitting} onClick={handleDeleteSelected}>
          删除选中
        </button>
        <button
          type="button"
          className="review-btn"
          disabled={selectedCount === 0 || submitting}
          onClick={() => setSelectedProjectIds([])}
        >
          清空选择
        </button>
      </div>

      <div className="project-list-grid">
        {filtered.length > 0 ? (
          filtered.map((item) => (
            <div key={item.projectId} className="project-card-wrap">
              <ProjectCard
                item={item}
                isActive={item.projectId === activeProjectId}
                selected={selectedProjectIds.includes(item.projectId)}
                onSelect={(projectId, checked) => {
                  setSelectedProjectIds((prev) => {
                    if (checked) {
                      return [...new Set([...prev, projectId])];
                    }
                    return prev.filter((itemId) => itemId !== projectId);
                  });
                }}
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
                onDelete={handleDeleteSingle}
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
