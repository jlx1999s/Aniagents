import HeroCenter from '../components/HeroCenter';
import PipelinePanel from '../components/PipelinePanel';
import ProjectManager from '../components/ProjectManager';
import ProjectWorkspace from '../components/ProjectWorkspace';
import SettingsPage from '../components/SettingsPage';
import SpineBar from '../components/SpineBar';
import TopNav from '../components/TopNav';

export default function AppShell({
  navLinks,
  activeLink,
  onNavChange,
  workspaceMode,
  onOpenProject,
  onCloseWorkspace,
  pipelineStages,
  snapshot,
  projectIds,
  projectSummaries,
  activeProjectId,
  draftPrompt,
  loadingProjects,
  projectStats,
  connectionStatus,
  errorMessage,
  actions,
  coords
}) {
  if (activeLink === '项目') {
    return (
      <div className="project-screen">
        <TopNav links={navLinks} coords={coords} activeLink={activeLink} onChange={onNavChange} />
        <div className="project-screen-main">
          {workspaceMode ? (
            <ProjectWorkspace snapshot={snapshot} actions={actions} onBack={onCloseWorkspace} />
          ) : (
            <ProjectManager
              projectIds={projectIds}
              projectSummaries={projectSummaries}
              snapshot={snapshot}
              activeProjectId={activeProjectId}
              draftPrompt={draftPrompt}
              loadingProjects={loadingProjects}
              projectStats={projectStats}
              actions={actions}
              onOpenProject={onOpenProject}
              errorMessage={errorMessage}
              connectionStatus={connectionStatus}
            />
          )}
        </div>
      </div>
    );
  }

  if (activeLink === '设置') {
    return (
      <div className="project-screen">
        <TopNav links={navLinks} coords={coords} activeLink={activeLink} onChange={onNavChange} />
        <div className="project-screen-main">
          <SettingsPage />
        </div>
      </div>
    );
  }

  return (
    <div className="ui-layer">
      <SpineBar />
      <main className="main-stage">
        <TopNav links={navLinks} coords={coords} activeLink={activeLink} onChange={onNavChange} />
        <HeroCenter />
      </main>
      <PipelinePanel
        stages={pipelineStages}
        snapshot={snapshot}
        projectIds={projectIds}
        activeProjectId={activeProjectId}
        draftPrompt={draftPrompt}
        connectionStatus={connectionStatus}
        errorMessage={errorMessage}
        actions={actions}
      />
    </div>
  );
}
