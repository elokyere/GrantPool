import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '../services/api'
import '../App.css'

function ResendVerification() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess(false)
    setLoading(true)

    try {
      await api.post('/api/v1/auth/resend-verification', {
        email,
      })
      setSuccess(true)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to resend verification email')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="card" style={{ maxWidth: '500px', width: '100%', textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem', color: '#10b981' }}>✓</div>
          <h2>Verification Email Sent</h2>
          <p style={{ color: '#6b7280', marginBottom: '1.5rem' }}>
            If that email exists and is unverified, a verification email has been sent to <strong>{email}</strong>
          </p>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1.5rem' }}>
            Please check your inbox and click the verification link. The link will expire in 24 hours.
          </p>
          <Link to="/login" className="btn btn-primary">
            Go to Login
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ maxWidth: '400px', width: '100%' }}>
        <h2>Resend Verification Email</h2>
        <p style={{ color: '#6b7280', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
          Enter your email address and we'll send you a new verification link.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="your@email.com"
            />
          </div>
          {error && <div className="error">{error}</div>}
          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Sending...' : 'Resend Verification Email'}
          </button>
        </form>
        <p style={{ marginTop: '1rem', textAlign: 'center' }}>
          <Link to="/login">Back to Login</Link>
        </p>
      </div>
    </div>
  )
}

export default ResendVerification
