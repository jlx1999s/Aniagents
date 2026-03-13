import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  advanceProject,
  connectProjectStream,
  createProject,
  deleteProject,
  deleteProjectsBatch,
  getProjectStats,
  getProjectSnapshot,
  getProjectIntentRouterPolicy,
  listProjects,
  saveProjectIntentRouterPolicy,
  submitProjectChat,
  submitReview
} from '../services/api';

const PROJECT_SUMMARY_FETCH_LIMIT = 40;
const PROJECT_SUMMARY_FETCH_CONCURRENCY = 6;

function normalizeErrorMessage(error, fallback) {
  const message = error instanceof Error ? error.message : '';
  if (
    !message ||
    message === 'Failed to fetch' ||
    message === 'Load failed' ||
    message.includes('did not match the expected pattern')
  ) {
    return fallback;
  }
  return message;
}

function chunkArray(items, size) {
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

export default function useProjectStream() {
  const [snapshot, setSnapshot] = useState({
    projectId: '',
    prompt: '',
    stage: '初始化',
    mode: '人工介入',
    status: '初始化中',
    qualityPass: 0,
    qualityTotal: 5,
    renderCost: 0,
    eta: '00:05:00',
    approvalRequired: false,
    approvalStage: null,
    currentNode: '',
    finalVideoUri: null,
    assets: {
      scriptReady: false,
      styleReady: false,
      characterCount: 0,
      storyboardCount: 0,
      videoCount: 0,
      audioCount: 0,
      finalVideoUri: null
    },
    assetGallery: {
      characters: [],
      storyboards: [],
      videos: []
    },
    nodeMetrics: [],
    latestReview: null,
    reviewLogs: [],
    chatLogs: [],
    activityLogs: [],
    executionPlan: [],
    executionPlanSummary: '',
    suggestedCommands: [],
    targetNodeOptions: [],
    intentRouterPolicy: null,
    history: [],
    errors: []
  });
  const [projectIds, setProjectIds] = useState([]);
  const [projectSummaries, setProjectSummaries] = useState([]);
  const [draftPrompt, setDraftPrompt] = useState('一段关于未来城市守护者的热血漫剧');
  const [activeProjectId, setActiveProjectId] = useState('');
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [projectStats, setProjectStats] = useState({
    total: 0,
    running: 0,
    waiting_review: 0,
    completed: 0,
    rejected: 0,
    failed: 0
  });
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [errorMessage, setErrorMessage] = useState('');
  const streamRef = useRef(null);
  const snapshotRef = useRef(snapshot);

  const bindStream = (projectId) => {
    if (streamRef.current) {
      streamRef.current.close();
    }
    streamRef.current = connectProjectStream(
      projectId,
      (next) => {
        setConnectionStatus('online');
        setErrorMessage('');
        setSnapshot(next);
      },
      (error) => {
        setConnectionStatus('reconnecting');
        setErrorMessage(normalizeErrorMessage(error, '实时流连接中断，正在重连'));
      }
    );
  };

  const upsertSummary = (item) => {
    if (!item?.projectId) {
      return;
    }
    setProjectSummaries((prev) => {
      const next = prev.filter((project) => project.projectId !== item.projectId);
      return [item, ...next];
    });
  };

  const refreshProjectStats = useCallback(async () => {
    try {
      const next = await getProjectStats();
      setProjectStats(next);
      return next;
    } catch {
      return null;
    }
  }, []);

  const loadAllProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const [ids, stats] = await Promise.all([listProjects(), getProjectStats().catch(() => null)]);
      setProjectIds(ids);
      if (stats) {
        setProjectStats(stats);
      } else {
        setProjectStats((prev) => ({
          ...prev,
          total: ids.length
        }));
      }
      const detailIds = ids.slice(0, PROJECT_SUMMARY_FETCH_LIMIT);
      const rows = [];
      const idBatches = chunkArray(detailIds, PROJECT_SUMMARY_FETCH_CONCURRENCY);
      for (const batch of idBatches) {
        const batchRows = await Promise.all(
          batch.map(async (projectId) => {
            try {
              const detail = await getProjectSnapshot(projectId, { compact: true });
              return detail;
            } catch {
              return {
                projectId,
                prompt: '',
                stage: '加载失败',
                status: 'failed',
                renderCost: 0,
                eta: '--:--:--',
                qualityPass: 0,
                qualityTotal: 5
              };
            }
          })
        );
        rows.push(...batchRows);
      }
      const currentSnapshot = snapshotRef.current;
      if (rows.length === 0 && currentSnapshot.projectId) {
        setProjectSummaries([currentSnapshot]);
        setProjectIds([currentSnapshot.projectId]);
        return [currentSnapshot.projectId];
      }
      setProjectSummaries(rows);
      setErrorMessage('');
      return ids;
    } catch (error) {
      setConnectionStatus('offline');
      setErrorMessage(normalizeErrorMessage(error, '项目列表加载失败，请确认后端已启动'));
      return [];
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  useEffect(() => {
    let closed = false;
    async function bootstrap() {
      try {
        setConnectionStatus('connecting');
        const existing = await loadAllProjects();
        if (closed) {
          return;
        }
        const projectId = existing[0];
        if (!projectId) {
          setActiveProjectId('');
          setConnectionStatus('online');
          setErrorMessage('暂无项目，请先创建项目后再进入工作台');
          return;
        }
        if (closed) {
          return;
        }
        setActiveProjectId(projectId);
        const first = await getProjectSnapshot(projectId);
        if (closed) {
          return;
        }
        setSnapshot(first);
        bindStream(projectId);
      } catch (error) {
        setConnectionStatus('offline');
        setErrorMessage(normalizeErrorMessage(error, '连接后端失败，请检查 API 地址与服务状态'));
      }
    }
    bootstrap();
    return () => {
      closed = true;
      if (streamRef.current) {
        streamRef.current.close();
      }
    };
  }, [loadAllProjects]);

  useEffect(() => {
    snapshotRef.current = snapshot;
    upsertSummary(snapshot);
  }, [snapshot]);

  const actions = useMemo(
    () => ({
      resolveProjectId: () => activeProjectId || snapshotRef.current.projectId,
      updateDraftPrompt: (value) => {
        setDraftPrompt(value);
      },
      selectProject: async (projectId) => {
        if (!projectId) {
          return;
        }
        setActiveProjectId(projectId);
        setConnectionStatus('connecting');
        const next = await getProjectSnapshot(projectId);
        setSnapshot(next);
        upsertSummary(next);
        bindStream(projectId);
      },
      createNewProject: async () => {
        const content = draftPrompt.trim();
        if (!content) {
          throw new Error('请输入项目描述后再创建');
        }
        setErrorMessage('');
        setConnectionStatus('connecting');
        const created = await createProject(content);
        const projectId = created.project_id;
        setActiveProjectId(projectId);
        upsertSummary({
          projectId,
          prompt: content,
          stage: '初始化',
          status: 'running',
          renderCost: 0,
          eta: '00:05:00',
          qualityPass: 0,
          qualityTotal: 5
        });
        try {
          const next = await getProjectSnapshot(projectId);
          setSnapshot(next);
          upsertSummary(next);
          bindStream(projectId);
        } catch (error) {
          setConnectionStatus('reconnecting');
          setErrorMessage(normalizeErrorMessage(error, '项目已创建，详情加载失败，正在重试'));
        }
        await loadAllProjects();
        await refreshProjectStats();
      },
      advanceNow: async () => {
        const projectId = activeProjectId || snapshotRef.current.projectId;
        if (!projectId) {
          throw new Error('未选中项目，无法推进');
        }
        const next = await advanceProject(projectId);
        setSnapshot(next);
        upsertSummary(next);
        await refreshProjectStats();
      },
      advanceById: async (projectId) => {
        if (!projectId) {
          return;
        }
        const next = await advanceProject(projectId);
        if (projectId === activeProjectId) {
          setSnapshot(next);
        }
        upsertSummary(next);
        await refreshProjectStats();
      },
      approveReview: async () => {
        const projectId = activeProjectId || snapshotRef.current.projectId;
        if (!projectId) {
          throw new Error('未选中项目，无法审核');
        }
        let next = null;
        try {
          next = await submitReview(projectId, { action: 'approve' });
        } catch (error) {
          const message = error instanceof Error ? error.message : '';
          if (!message.includes('review_not_required')) {
            throw error;
          }
          next = await getProjectSnapshot(projectId);
        }
        setSnapshot(next);
        upsertSummary(next);
        await refreshProjectStats();
      },
      requestRevision: async (form) => {
        const projectId = activeProjectId || snapshotRef.current.projectId;
        if (!projectId) {
          throw new Error('未选中项目，无法提交返修');
        }
        let next = null;
        try {
          next = await submitReview(projectId, {
            action: 'revise',
            target_node: form.targetNode,
            stage: form.stage,
            issue_type: form.issueType,
            priority: form.priority,
            message: form.message,
            operator_id: form.operatorId
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : '';
          if (!message.includes('review_not_required')) {
            throw error;
          }
          next = await getProjectSnapshot(projectId);
        }
        setSnapshot(next);
        upsertSummary(next);
        await refreshProjectStats();
      },
      rejectProject: async (form) => {
        const projectId = activeProjectId || snapshotRef.current.projectId;
        if (!projectId) {
          throw new Error('未选中项目，无法终止');
        }
        let next = null;
        try {
          next = await submitReview(projectId, {
            action: 'reject',
            stage: form.stage,
            issue_type: form.issueType,
            priority: form.priority,
            message: form.message,
            operator_id: form.operatorId
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : '';
          if (!message.includes('review_not_required')) {
            throw error;
          }
          next = await getProjectSnapshot(projectId);
        }
        setSnapshot(next);
        upsertSummary(next);
        await refreshProjectStats();
      },
      chatWithAgent: async (message) => {
        const projectId = activeProjectId || snapshotRef.current.projectId;
        if (!projectId) {
          throw new Error('未选中项目，无法发送消息');
        }
        const content = message.trim();
        if (!content) {
          throw new Error('请输入内容后发送');
        }
        const next = await submitProjectChat(projectId, {
          message: content,
          operator_id: '项目操作员'
        });
        setSnapshot(next);
        upsertSummary(next);
        await refreshProjectStats();
      },
      updateIntentRouterPolicy: async (policyPayload) => {
        const projectId = activeProjectId || snapshotRef.current.projectId;
        if (!projectId) {
          throw new Error('未选中项目，无法更新策略');
        }
        await saveProjectIntentRouterPolicy(projectId, policyPayload);
        const next = await getProjectSnapshot(projectId);
        setSnapshot(next);
        upsertSummary(next);
        return getProjectIntentRouterPolicy(projectId);
      },
      deleteProjects: async (projectIdsToDelete) => {
        const normalizedIds = [...new Set((projectIdsToDelete || []).map((item) => String(item || '').trim()))].filter(
          Boolean
        );
        if (normalizedIds.length === 0) {
          return { deletedCount: 0 };
        }
        if (normalizedIds.length === 1) {
          await deleteProject(normalizedIds[0]);
        } else {
          await deleteProjectsBatch(normalizedIds);
        }
        const currentProjectId = activeProjectId || snapshotRef.current.projectId;
        const activeDeleted = normalizedIds.includes(currentProjectId);
        const ids = await loadAllProjects();
        if (activeDeleted) {
          if (streamRef.current) {
            streamRef.current.close();
          }
          if (ids.length > 0) {
            const nextProjectId = ids[0];
            setActiveProjectId(nextProjectId);
            setConnectionStatus('connecting');
            const next = await getProjectSnapshot(nextProjectId);
            setSnapshot(next);
            upsertSummary(next);
            bindStream(nextProjectId);
          } else {
            setActiveProjectId('');
            setConnectionStatus('online');
            setErrorMessage('暂无项目，请先创建项目后再进入工作台');
          }
        }
        await refreshProjectStats();
        return { deletedCount: normalizedIds.length };
      },
      refreshProjects: async () => {
        const ids = await loadAllProjects();
        const currentSnapshot = snapshotRef.current;
        if (ids.length === 0 && currentSnapshot.projectId) {
          upsertSummary(currentSnapshot);
          setProjectIds([currentSnapshot.projectId]);
          setConnectionStatus('reconnecting');
          setErrorMessage('列表拉取异常，已回退展示当前项目');
        }
        await refreshProjectStats();
      }
    }),
    [activeProjectId, draftPrompt, loadAllProjects, refreshProjectStats]
  );

  return {
    snapshot,
    projectIds,
    projectSummaries,
    activeProjectId,
    draftPrompt,
    loadingProjects,
    projectStats,
    connectionStatus,
    errorMessage,
    actions
  };
}
