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
        
        <h1 className="landing-title">Know Before You Apply—Get Your Grant Fit Score in 90 Seconds</h1>
        <p className="landing-subtitle">
          The average grant takes 20+ hours to apply for. Don't start yours until you know you're a top-tier candidate.
        </p>

        {/* How It Works - Step-by-Step Preview */}
        <div className="how-it-works-preview">
          <div className="step-item">
            <div className="step-icon">1</div>
            <div className="step-content">
              <div className="step-title">Paste Link</div>
              <div className="step-description">Share any grant listing URL</div>
            </div>
          </div>
          <div className="step-arrow">→</div>
          <div className="step-item">
            <div className="step-icon">2</div>
            <div className="step-content">
              <div className="step-title">AI Analyzes Criteria</div>
              <div className="step-description">We compare your project to past winners</div>
            </div>
          </div>
          <div className="step-arrow">→</div>
          <div className="step-item">
            <div className="step-icon">3</div>
            <div className="step-content">
              <div className="step-title">Get Your Fit Score</div>
              <div className="step-description">Clear APPLY or PASS recommendation</div>
            </div>
          </div>
        </div>
        
        <form onSubmit={handleCheckGrant} className="landing-form">
          <div className="input-wrapper">
            <svg className="search-icon" width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M9 17A8 8 0 1 0 9 1a8 8 0 0 0 0 16z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="m19 19-4.35-4.35" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <input
              type="url"
              className="landing-input"
              placeholder="https://grants.gov/web/grants/view-opportunity.html..."
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

        {/* Trust Bar - Social Proof */}
        <div className="trust-bar">
          <div className="trust-stat">
            <span className="trust-number">3,400+</span>
            <span className="trust-label">grants analyzed this month</span>
          </div>
          <div className="trust-stat">
            <span className="trust-number">12,000+</span>
            <span className="trust-label">hours of manual research saved</span>
          </div>
        </div>

        <p className="landing-disclaimer">
          Get your first assessment free. No credit card required.
        </p>
      </div>
    </div>
  )
}

export default Landing


