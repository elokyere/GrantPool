import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import '../App.css'

function Register() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register, login, user } = useAuth()
  const navigate = useNavigate()

  // Redirect to dashboard when user is authenticated
  useEffect(() => {
    if (user) {
      navigate('/dashboard', { replace: true })
    }
  }, [user, navigate])

  const [showVerificationMessage, setShowVerificationMessage] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // Register user
      await register(email, password, fullName)
      
      // Show verification message instead of auto-login
      setShowVerificationMessage(true)
      setLoading(false)
    } catch (err) {
      console.error('Registration error:', err)
      setError(err.response?.data?.detail || err.message || 'Registration failed. Please try again.')
      setLoading(false)
    }
  }

  if (showVerificationMessage) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="card" style={{ maxWidth: '500px', width: '100%', textAlign: 'center' }}>
          <h2>Check Your Email</h2>
          <p style={{ color: '#6b7280', marginBottom: '1.5rem' }}>
            We've sent a verification email to <strong>{email}</strong>
          </p>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1.5rem' }}>
            Please click the verification link in the email to activate your account. 
            The link will expire in 24 hours.
          </p>
          <div style={{ marginTop: '1.5rem' }}>
            <Link to="/resend-verification" className="btn btn-secondary" style={{ marginRight: '0.5rem' }}>
              Resend Email
            </Link>
            <Link to="/login" className="btn btn-primary">
              Go to Login
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ maxWidth: '400px', width: '100%' }}>
        <h2>Register for GrantPool</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="fullName">Full Name</label>
            <input
              type="text"
              id="fullName"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-group" style={{ position: 'relative' }}>
            <label htmlFor="password">Password</label>
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
          {error && <div className="error">{error}</div>}
          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Registering...' : 'Register'}
          </button>
        </form>
        <p style={{ marginTop: '1rem', textAlign: 'center' }}>
          Already have an account? <Link to="/login">Login</Link>
        </p>
      </div>
    </div>
  )
}

export default Register
