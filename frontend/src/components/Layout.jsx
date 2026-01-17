import { useState } from 'react'
import { Outlet, Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import ReportIssue from './ReportIssue'
import './Layout.css'

function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [showReportIssue, setShowReportIssue] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="layout">
      <nav className="navbar">
        <div className="nav-container">
          <Link to="/" className="nav-brand">
            GrantPool
          </Link>
          <div className="nav-links">
            <Link to="/dashboard" className="nav-link">Dashboard</Link>
            <Link to="/dashboard/projects" className="nav-link">Projects</Link>
            <Link to="/dashboard/grants" className="nav-link">Grants</Link>
            <Link to="/dashboard/settings" className="nav-link">Settings</Link>
          </div>
          <div className="nav-user">
            <button 
              onClick={() => setShowReportIssue(true)}
              className="btn btn-secondary"
              style={{ marginRight: '0.5rem', fontSize: '0.9rem' }}
            >
              Report an Issue
            </button>
            <span className="user-email">{user?.email}</span>
            <button onClick={handleLogout} className="btn btn-secondary">
              Logout
            </button>
          </div>
        </div>
      </nav>
      <main className="main-content">
        <Outlet />
      </main>
      {showReportIssue && (
        <ReportIssue onClose={() => setShowReportIssue(false)} />
      )}
    </div>
  )
}

export default Layout

