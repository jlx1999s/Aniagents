export default function HeroCenter() {
  return (
    <div className="hero-center">
      <h1 className="display-title-el">MANJU</h1>
      <div className="hero-subtitle">多智能体漫剧生产引擎</div>
      <div className="chip-row">
        <div className="chip-el">
          <span className="status-dot" />
          人工审核
        </div>
        <div className="chip-el">
          <span className="status-dot" />
          MCP 已连接
        </div>
        <div className="chip-el">
          <span className="status-dot" />
          渲染队列
        </div>
      </div>
    </div>
  );
}
