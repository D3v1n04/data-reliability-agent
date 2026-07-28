import {
  Activity,
  AlertTriangle,
  DatabaseZap,
  GitBranch,
  LayoutDashboard,
  Menu,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { getHealth } from "../api/client";

const navigation = [
  {
    to: "/",
    label: "Overview",
    icon: LayoutDashboard,
    end: true,
  },
  {
    to: "/pipelines",
    label: "Pipelines",
    icon: GitBranch,
  },
  {
    to: "/incidents",
    label: "Incidents",
    icon: AlertTriangle,
  },
];

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;

    getHealth()
      .then((health) => {
        if (active) {
          setApiOnline(health.status === "ok");
        }
      })
      .catch(() => {
        if (active) {
          setApiOnline(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "sidebar--open" : ""}`}>
        <div className="brand">
          <div className="brand__mark" aria-hidden="true">
            <DatabaseZap size={20} strokeWidth={2.2} />
          </div>
          <div>
            <span className="brand__name">Reliability</span>
            <span className="brand__product">Data Agent</span>
          </div>
          <button
            className="icon-button sidebar__close"
            type="button"
            aria-label="Close navigation"
            onClick={() => setMenuOpen(false)}
          >
            <X size={20} />
          </button>
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `nav-link ${isActive ? "nav-link--active" : ""}`
              }
              onClick={() => setMenuOpen(false)}
            >
              <Icon size={19} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="api-status">
            <span
              className={`api-status__dot ${
                apiOnline === false ? "api-status__dot--offline" : ""
              }`}
            />
            <div>
              <span className="api-status__label">API status</span>
              <strong>
                {apiOnline === null
                  ? "Checking"
                  : apiOnline
                    ? "Operational"
                    : "Offline"}
              </strong>
            </div>
          </div>
          <p>Deterministic engine + Bedrock memory</p>
        </div>
      </aside>

      {menuOpen && (
        <button
          className="sidebar-backdrop"
          type="button"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <div className="workspace">
        <header className="mobile-header">
          <button
            className="icon-button"
            type="button"
            aria-label="Open navigation"
            onClick={() => setMenuOpen(true)}
          >
            <Menu size={22} />
          </button>
          <div className="mobile-header__brand">
            <Activity size={18} />
            <span>Reliability</span>
          </div>
          <span className="mobile-header__spacer" />
        </header>

        <Outlet />
      </div>
    </div>
  );
}
