import { useState, useEffect } from 'react'
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
  const [loadingMessage, setLoadingMessage] = useState('')
  const [showDataContribution, setShowDataContribution] = useState(false)
  const [isProcessingRegistration, setIsProcessingRegistration] = useState(false)
  const [projectData, setProjectData] = useState({
    name: '',
    description: '',
    stage: '',
    funding_need: '',
    urgency: 'moderate',
    founder_type: '',
    timeline_constraints: '',
  })
  const { user, logout, login } = useAuth()
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

    // If user is already logged in, proceed directly to evaluation
    if (user) {
      const isFirstTime = await checkIsFirstTime()
      if (isFirstTime) {
        // Store grant URL and name in sessionStorage for dashboard to use
        sessionStorage.setItem('pending_grant_url', grantUrl)
        sessionStorage.setItem('pending_grant_name', grantName || '')
        // Navigate to dashboard with flag to show data contribution
        navigate('/dashboard?show_data_contribution=true')
        return
      }
      await handleEvaluateGrant()
      return
    }

    // Show registration form for new users
    setShowRegistration(true)
  }

  // Check if user is first-time (no evaluations)
  const checkIsFirstTime = async () => {
    try {
      const response = await api.get('/api/v1/evaluations/')
      const evaluations = Array.isArray(response.data) ? response.data : []
      return evaluations.length === 0
    } catch (err) {
      // If error, assume first-time to be safe
      return true
    }
  }

  const handleEvaluateGrant = async (projectId = null) => {
    setError('')
    setLoading(true)
    setLoadingMessage('Extracting grant information...')

    try {
      // Step 1: Create grant from URL
      setLoadingMessage('Extracting grant information from URL...')
      const grantResponse = await api.post('/api/v1/grants/from-url', {
        source_url: grantUrl,
        name: grantName || null,
      })

      // Step 2: Create evaluation
      setLoadingMessage('Creating your assessment...')
      const evaluationResponse = await api.post('/api/v1/evaluations/', {
        grant_id: grantResponse.data.id,
        project_id: projectId,
        use_llm: true,
      })

      // Step 3: Navigate to dashboard - Dashboard will handle loading/polling
      // The evaluation is created synchronously, but Dashboard will show loading state
      // and poll if needed until the evaluation is fully ready
      navigate(`/dashboard?evaluation=${evaluationResponse.data.id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to process grant evaluation')
      setLoading(false)
      setLoadingMessage('')
    }
  }

  const handleCreateProjectAndEvaluate = async () => {
    setError('')
    setLoading(true)
    setLoadingMessage('Creating your project profile...')

    try {
      // Create project first
      const projectResponse = await api.post('/api/v1/projects/', projectData)
      const projectId = projectResponse.data.id

      // Then create evaluation with this project
      await handleEvaluateGrant(projectId)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create project')
      setLoading(false)
      setLoadingMessage('')
    }
  }

  const handleRegisterAndEvaluate = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      let registrationSucceeded = false

      // Try to register user first
      try {
        await api.post('/api/v1/auth/register', {
          email,
          password,
          full_name: fullName || null,
        })
        registrationSucceeded = true
      } catch (registerErr) {
        // If registration fails because email already exists, try to login instead
        if (registerErr.response?.status === 400 && 
            registerErr.response?.data?.detail === 'Email already registered') {
          // User already exists - will try to login below
          registrationSucceeded = false
        } else {
          // Other registration errors, re-throw
          throw registerErr
        }
      }

      // Login user (either new user after registration, or existing user)
      // This updates AuthContext and sets the user state
      await login(email, password)

      // Store grant URL and name in sessionStorage for dashboard to use
      sessionStorage.setItem('pending_grant_url', grantUrl)
      sessionStorage.setItem('pending_grant_name', grantName || '')
      
      // Check if first-time user - navigate to dashboard with flag to show data contribution
      const isFirstTime = await checkIsFirstTime()
      if (isFirstTime) {
        // Navigate to dashboard - it will show data contribution modal
        navigate('/dashboard?show_data_contribution=true')
        return
      }

      // For existing users, proceed with grant evaluation directly
      await handleEvaluateGrant()
    } catch (err) {
      // Handle login errors specifically
      if (err.response?.status === 401) {
        setError('Incorrect password. Please try again or use a different email.')
      } else {
        setError(err.response?.data?.detail || err.message || 'Failed to process grant evaluation')
      }
      setLoading(false)
    }
  }

  // Data Contribution Modal for First-Time Users
  if (showDataContribution) {
    return (
      <div className="landing-page">
        <div className="landing-card" style={{ maxWidth: '600px' }}>
          <h2>Make Your First Assessment More Comprehensive</h2>
          <p style={{ color: '#6b7280', marginBottom: '1.5rem' }}>
            Help us understand your project better. This will make your assessment more accurate and personalized.
            You can skip this and use default settings, but providing project details will give you better insights.
          </p>
          
          <form onSubmit={(e) => { e.preventDefault(); handleCreateProjectAndEvaluate(); }}>
            <div className="form-group">
              <label htmlFor="projectName">Project Name *</label>
              <input
                type="text"
                id="projectName"
                value={projectData.name}
                onChange={(e) => setProjectData({...projectData, name: e.target.value})}
                placeholder="e.g., Community Health Initiative"
                required
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="projectDescription">Project Description *</label>
              <textarea
                id="projectDescription"
                value={projectData.description}
                onChange={(e) => setProjectData({...projectData, description: e.target.value})}
                placeholder="Describe what your project does, who it serves, and what problem it solves..."
                required
                rows={4}
                style={{ fontFamily: 'inherit', resize: 'vertical' }}
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="projectStage">Project Stage *</label>
              <select
                id="projectStage"
                value={projectData.stage}
                onChange={(e) => setProjectData({...projectData, stage: e.target.value})}
                required
              >
                <option value="">Select stage...</option>
                <option value="Idea">Idea</option>
                <option value="Early Development">Early Development</option>
                <option value="Pilot">Pilot</option>
                <option value="Established">Established</option>
                <option value="Scaling">Scaling</option>
              </select>
            </div>
            
            <div className="form-group">
              <label htmlFor="fundingNeed">Funding Need *</label>
              <select
                id="fundingNeed"
                value={projectData.funding_need}
                onChange={(e) => setProjectData({...projectData, funding_need: e.target.value})}
                required
              >
                <option value="">Select funding need...</option>
                <option value="Seed funding">Seed funding</option>
                <option value="Growth capital">Growth capital</option>
                <option value="Operational support">Operational support</option>
                <option value="Research funding">Research funding</option>
                <option value="Program expansion">Program expansion</option>
                <option value="Other">Other</option>
              </select>
            </div>
            
            <div className="form-group">
              <label htmlFor="urgency">Urgency</label>
              <select
                id="urgency"
                value={projectData.urgency}
                onChange={(e) => setProjectData({...projectData, urgency: e.target.value})}
              >
                <option value="low">Low - Flexible timeline</option>
                <option value="moderate">Moderate - Some time pressure</option>
                <option value="high">High - Urgent need</option>
              </select>
            </div>
            
            {error && <div className="landing-error">{error}</div>}
            {loading && loadingMessage && (
              <div style={{ 
                padding: '1rem', 
                backgroundColor: '#f0f9ff', 
                borderRadius: '8px', 
                marginBottom: '1rem',
                textAlign: 'center',
                color: '#1e40af',
                fontWeight: '500'
              }}>
                {loadingMessage}
              </div>
            )}
            
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
              <button 
                type="submit" 
                className="landing-cta" 
                disabled={loading}
                style={{ flex: 1 }}
              >
                {loading ? (loadingMessage || 'Processing...') : 'Continue with Project Details'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowDataContribution(false)
                  handleEvaluateGrant()
                }}
                className="btn-secondary"
                disabled={loading}
                style={{ flex: 1 }}
              >
                Skip & Use Defaults
              </button>
            </div>
          </form>
        </div>
      </div>
    )
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
                {showPassword ? 'Hide' : 'Show'}
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
            {loading && loadingMessage && (
              <div style={{ 
                padding: '1rem', 
                backgroundColor: '#f0f9ff', 
                borderRadius: '8px', 
                marginBottom: '1rem',
                textAlign: 'center',
                color: '#1e40af',
                fontWeight: '500'
              }}>
                {loadingMessage}
              </div>
            )}
            <button type="submit" className="landing-cta" disabled={loading}>
              {loading ? (loadingMessage || 'Processing...') : 'Analyze Grant'}
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
          <div style={{
            marginTop: '0.5rem',
            padding: '0.75rem',
            backgroundColor: '#f0f9ff',
            borderRadius: '8px',
            border: '1px solid #bfdbfe',
            fontSize: '0.85rem',
            color: '#1e40af'
          }}>
            <div style={{ fontWeight: '500', marginBottom: '0.25rem' }}>
              Best Practice Example:
            </div>
            <div style={{ 
              fontFamily: 'monospace', 
              fontSize: '0.8rem', 
              color: '#4a77e8',
              wordBreak: 'break-all',
              marginTop: '0.25rem',
              padding: '0.5rem',
              backgroundColor: 'white',
              borderRadius: '4px',
              border: '1px solid #bfdbfe'
            }}>
              https://www.funder-website.org/grants/program-name
            </div>
            <div style={{ 
              fontSize: '0.75rem', 
              color: '#64748b', 
              marginTop: '0.5rem',
              lineHeight: '1.4'
            }}>
              <strong>Best results:</strong> Use official funder pages (the organization's own website) rather than aggregator sites. Official pages contain complete grant details, eligibility criteria, and application requirements.
            </div>
          </div>
          {error && <div className="landing-error">{error}</div>}
          {loading && loadingMessage && (
            <div style={{ 
              padding: '1rem', 
              backgroundColor: '#f0f9ff', 
              borderRadius: '8px', 
              marginBottom: '1rem',
              textAlign: 'center',
              color: '#1e40af',
              fontWeight: '500'
            }}>
              {loadingMessage}
            </div>
          )}
          <button 
            type="submit" 
            className="landing-cta"
            disabled={loading}
          >
            {loading ? (loadingMessage || 'Processing...') : 'Analyze Grant'}
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


