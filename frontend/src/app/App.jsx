import { useState } from 'react';
import BackgroundCanvas from '../components/BackgroundCanvas';
import { navLinks, pipelineStages } from '../data/pipeline';
import useProjectStream from '../hooks/useProjectStream';
import AppShell from '../layouts/AppShell';

export default function App() {
  const [coords, setCoords] = useState('坐标: 0.000, 0.000');
  const [activeLink, setActiveLink] = useState('总览');
  const [workspaceMode, setWorkspaceMode] = useState(false);
  const isDynamicBackground = activeLink === '总览';
  const {
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
  } = useProjectStream();

  const handleNavChange = (link) => {
    setActiveLink(link);
    if (link !== '项目') {
      setWorkspaceMode(false);
    }
  };

  const handleOpenProject = async (projectId) => {
    await actions.selectProject(projectId);
    setActiveLink('项目');
    setWorkspaceMode(true);
  };

  return (
    <div className="app-root">
      <BackgroundCanvas onCoordsChange={setCoords} isAnimated={isDynamicBackground} />
      <AppShell
        navLinks={navLinks}
        activeLink={activeLink}
        onNavChange={handleNavChange}
        workspaceMode={workspaceMode}
        onOpenProject={handleOpenProject}
        onCloseWorkspace={() => setWorkspaceMode(false)}
        pipelineStages={pipelineStages}
        snapshot={snapshot}
        projectIds={projectIds}
        projectSummaries={projectSummaries}
        activeProjectId={activeProjectId}
        draftPrompt={draftPrompt}
        loadingProjects={loadingProjects}
        projectStats={projectStats}
        connectionStatus={connectionStatus}
        errorMessage={errorMessage}
        actions={actions}
        coords={coords}
      />
    </div>
  );
}
