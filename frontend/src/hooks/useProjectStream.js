import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  advanceProject,
  connectProjectStream,
  createProject,
  listProjects,
  getProjectSnapshot,
  submitReview
} from '../services/api';

function normalizeErrorMessage(error, fallback) {
  const message = error instanceof Error ? error.message : '';
  if (!message || message === 'Failed to fetch' || message === 'Load failed') {
    return fallback;
  }
  return message;
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
    history: [],
    errors: []
  });
  const [projectIds, setProjectIds] = useState([]);
  const [projectSummaries, setProjectSummaries] = useState([]);
  const [draftPrompt, setDraftPrompt] = useState('一段关于未来城市守护者的热血漫剧');
  const [activeProjectId, setActiveProjectId] = useState('');
  const [loadingProjects, setLoadingProjects] = useState(false);
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

  const loadAllProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const ids = await listProjects();
      setProjectIds(ids);
      const rows = await Promise.all(
        ids.map(async (projectId) => {
          try {
            const detail = await getProjectSnapshot(projectId);
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
        let projectId = existing[0];
        if (!projectId) {
          const created = await createProject('一段关于未来城市守护者的热血漫剧');
          projectId = created.project_id;
          await loadAllProjects();
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
      },
      advanceNow: async () => {
        if (!activeProjectId) {
          return;
        }
        const next = await advanceProject(activeProjectId);
        setSnapshot(next);
        upsertSummary(next);
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
      },
      approveReview: async () => {
        if (!activeProjectId) {
          return;
        }
        const next = await submitReview(activeProjectId, { action: 'approve' });
        setSnapshot(next);
        upsertSummary(next);
      },
      requestRevision: async (form) => {
        if (!activeProjectId) {
          return;
        }
        const next = await submitReview(activeProjectId, {
          action: 'revise',
          target_node: form.targetNode,
          stage: form.stage,
          issue_type: form.issueType,
          priority: form.priority,
          message: form.message,
          operator_id: form.operatorId
        });
        setSnapshot(next);
        upsertSummary(next);
      },
      rejectProject: async (form) => {
        if (!activeProjectId) {
          return;
        }
        const next = await submitReview(activeProjectId, {
          action: 'reject',
          stage: form.stage,
          issue_type: form.issueType,
          priority: form.priority,
          message: form.message,
          operator_id: form.operatorId
        });
        setSnapshot(next);
        upsertSummary(next);
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
      }
    }),
    [activeProjectId, draftPrompt, loadAllProjects]
  );

  return {
    snapshot,
    projectIds,
    projectSummaries,
    activeProjectId,
    draftPrompt,
    loadingProjects,
    connectionStatus,
    errorMessage,
    actions
  };
}
