import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../services/api'
import '../App.css'
import './Landing.css'

function Landing() {
  const [grantUrl, setGrantUrl] = useState('')
  const [grantName, setGrantName] = useState('')
  const [showRegistration, setShowRegistration] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    // Navigation will happen automatically via LandingRoute when user state updates
  }

  const handleCheckGrant = async (e) => {
    e.preventDefault()
    setError('')
    
    if (!grantUrl.trim()) {
      setError('Please enter a grant URL')
      return
    }

    // Show registration form
    setShowRegistration(true)
  }

  const handleRegisterAndEvaluate = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // Register user
      const registerResponse = await api.post('/api/v1/auth/register', {
        email,
        password,
        full_name: fullName || null,
      })

      // Login user
      const formData = new FormData()
      formData.append('username', email)
      formData.append('password', password)
      const loginResponse = await api.post('/api/v1/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })

      const { access_token } = loginResponse.data
      localStorage.setItem('token', access_token)
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

      // Create grant from URL
      const grantResponse = await api.post('/api/v1/grants/from-url', {
        source_url: grantUrl,
        name: grantName || null,
      })

      // Create evaluation (will auto-create default project)
      const evaluationResponse = await api.post('/api/v1/evaluations/', {
        grant_id: grantResponse.data.id,
        use_llm: true,
        // project_id not provided - will auto-create default project
      })

      // Navigate to dashboard with evaluation
      navigate(`/dashboard?evaluation=${evaluationResponse.data.id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process grant evaluation')
      setLoading(false)
    }
  }

  if (showRegistration) {
    return (
      <div className="landing-page">
        <div className="landing-card">
          <h2>Create Account</h2>
          <p>
            We'll save this assessment to your account so you can access it anytime.
          </p>
          <form onSubmit={handleRegisterAndEvaluate}>
            <div className="form-group">
              <label htmlFor="fullName">Full Name (optional)</label>
              <input
                type="text"
                id="fullName"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label htmlFor="email">Email *</label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="form-group" style={{ position: 'relative' }}>
              <label htmlFor="password">Password *</label>
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                style={{ paddingRight: '40px' }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '38px',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#6b7280',
                  padding: '4px 8px',
                  fontSize: '0.9rem',
                }}
                tabIndex={-1}
              >
                {showPassword ? '👁️' : '👁️‍🗨️'}
              </button>
            </div>
            {grantUrl && (
              <div className="form-group">
                <label htmlFor="grantName">Grant Name (optional)</label>
                <input
                  type="text"
                  id="grantName"
                  value={grantName}
                  placeholder="Leave blank to auto-generate from URL"
                  onChange={(e) => setGrantName(e.target.value)}
                />
                <small>
                  Grant URL: {grantUrl}
                </small>
              </div>
            )}
            {error && <div className="landing-error">{error}</div>}
            <button type="submit" className="landing-cta" disabled={loading}>
              {loading ? 'Processing...' : 'Analyze Grant'}
            </button>
            <button
              type="button"
              onClick={() => setShowRegistration(false)}
              className="btn-secondary"
              style={{ width: '100%', marginTop: '0.5rem' }}
            >
              Back
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="landing-page">
      {/* Main content card */}
      <div className="landing-card">
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem', gap: '0.5rem' }}>
          {user ? (
            <>
              <span style={{ padding: '0.5rem 1rem', fontSize: '0.9rem', color: '#6b7280', alignSelf: 'center' }}>
                {user.email}
              </span>
              <button 
                onClick={handleLogout}
                className="btn btn-secondary" 
                style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
              >
                Logout
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn-secondary" style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}>
              Log In
            </Link>
          )}
        </div>
        
        <h1 className="landing-title">
          Decide if a grant is worth applying for — <span style={{ fontWeight: '700', color: '#4a77e8' }}>before you waste weeks.</span>
        </h1>
        <p className="landing-subtitle">
          Get a fast analysis of how well your project fits real grant criteria. See fit, risk, and effort in minutes.
        </p>

        {/* How GrantPool Works Section */}
        <div className="how-grantpool-works-section">
          <h2 className="section-heading">How GrantPool Works</h2>
          <div className="how-it-works-steps">
            <div className="works-step-title-only">
              <span className="works-step-number-text">1.</span> <span className="works-step-title-text">Paste a grant link</span>
            </div>
            <div className="works-step-title-only">
              <span className="works-step-number-text">2.</span> <span className="works-step-title-text">Describe your project</span>
            </div>
            <div className="works-step-title-only">
              <span className="works-step-number-text">3.</span> <span className="works-step-title-text">Get your evaluation</span>
            </div>
          </div>
          <p className="works-conclusion">Results in minutes, not days.</p>
        </div>

        <form onSubmit={handleCheckGrant} className="landing-form">
          <div className="input-wrapper">
            <svg className="search-icon" width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M8 4H6C4.89543 4 4 4.89543 4 6V14C4 15.1046 4.89543 16 6 16H14C15.1046 16 16 15.1046 16 14V12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M12 4H16M16 4V8M16 4L8 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <input
              type="url"
              className="landing-input"
              placeholder="Enter the grant URL..."
              value={grantUrl}
              onChange={(e) => setGrantUrl(e.target.value)}
              required
            />
          </div>
          <p className="input-caption">
            Paste any grant listing link to check eligibility instantly.
          </p>
          {error && <div className="landing-error">{error}</div>}
          <button 
            type="submit" 
            className="landing-cta"
          >
            Analyze Grant
          </button>
        </form>

        <p className="landing-disclaimer">
          Get your first assessment free. No credit card required.
        </p>

        {/* Free vs. Paid Assessments Section */}
        <div className="assessments-comparison-section">
          <h2 className="section-heading">Free vs. Paid Assessments</h2>
          <div className="assessments-comparison-card">
            <div className="assessment-column assessment-column-free">
              <div className="assessment-column-header">Free Assessment</div>
              <div className="assessment-features">
                <div className="assessment-feature">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ color: '#10b981', marginRight: '8px' }}>
                    <path d="M13 4L6 11L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Basic relevance check
                </div>
                <div className="assessment-feature">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ color: '#10b981', marginRight: '8px' }}>
                    <path d="M13 4L6 11L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Key red flags
                </div>
                <div className="assessment-feature">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ color: '#10b981', marginRight: '8px' }}>
                    <path d="M13 4L6 11L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Quick overview
                </div>
              </div>
            </div>
            <div className="assessment-column assessment-column-paid">
              <div className="assessment-column-header">Paid Assessment</div>
              <div className="assessment-features">
                <div className="assessment-feature">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ color: '#10b981', marginRight: '8px' }}>
                    <path d="M13 4L6 11L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Full detailed analysis
                </div>
                <div className="assessment-feature">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ color: '#10b981', marginRight: '8px' }}>
                    <path d="M13 4L6 11L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Success probability
                </div>
                <div className="assessment-feature">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ color: '#10b981', marginRight: '8px' }}>
                    <path d="M13 4L6 11L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Framing guidance
                </div>
              </div>
            </div>
          </div>
          <div className="pricing-info">
            <p style={{ margin: 0, fontSize: '1rem' }}>
              <strong>$7</strong> per assessment | <strong style={{ color: '#4a77e8' }}>$19</strong> for 3 assessments
            </p>
            <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#6b7280' }}>
              Prices listed in USD. Billed in local currency at checkout.
            </p>
          </div>
        </div>

        {/* Your Data Stays Private Section */}
        <div className="data-privacy-section">
          <h2 className="section-heading">Your Data Stays Private</h2>
          <div className="privacy-badges">
            <div className="privacy-badge">
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginBottom: '0.75rem' }}>
                <circle cx="16" cy="12" r="6" stroke="currentColor" strokeWidth="2"/>
                <path d="M8 26C8 22 11 19 16 19C21 19 24 22 24 26" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="20" cy="10" r="3" fill="currentColor"/>
              </svg>
              <p style={{ margin: 0, fontSize: '0.95rem', color: '#374151', fontWeight: '500' }}>Private & Encrypted</p>
            </div>
            <div className="privacy-badge">
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginBottom: '0.75rem' }}>
                <path d="M16 4L6 9V16C6 22 10 27 16 28C22 27 26 22 26 16V9L16 4Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M13 16L15 18L19 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <p style={{ margin: 0, fontSize: '0.95rem', color: '#374151', fontWeight: '500' }}>Confidential & Secure</p>
            </div>
            <div className="privacy-badge">
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginBottom: '0.75rem' }}>
                <rect x="4" y="8" width="24" height="18" rx="2" stroke="currentColor" strokeWidth="2"/>
                <path d="M4 12H28M4 16H28M4 20H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="24" cy="20" r="2" fill="currentColor"/>
              </svg>
              <p style={{ margin: 0, fontSize: '0.95rem', color: '#374151', fontWeight: '500' }}>Data Not Resold</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Landing


