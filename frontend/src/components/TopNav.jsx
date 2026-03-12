export default function TopNav({ links, coords, activeLink, onChange }) {
  return (
    <div className="top-meta">
      <nav className="top-nav">
        {links.map((link) => (
          <a
            key={link}
            href="#"
            className={`nav-link-el ${activeLink === link ? 'active' : ''}`}
            onClick={(event) => {
              event.preventDefault();
              onChange(link);
            }}
          >
            {link}
          </a>
        ))}
      </nav>
      <div className="coords-label">{coords}</div>
    </div>
  );
}
