import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import '../App.css'

function ForgotPassword() {
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [step, setStep] = useState('request') // 'request' or 'reset'
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  // Check if token and email are in URL (from email link)
  useEffect(() => {
    const token = searchParams.get('token')
    const emailParam = searchParams.get('email')
    if (token && emailParam) {
      setResetToken(token)
      setEmail(emailParam)
      setStep('reset')
    }
  }, [searchParams])

  const handleRequestReset = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      const response = await api.post('/api/v1/auth/forgot-password', { email })
      setSuccess(response.data.message || 'Password reset instructions have been sent to your email. Please check your inbox and click the link to reset your password.')
      // Don't auto-switch to reset step - user should click email link
      // If in development and token is returned, show it
      if (response.data.reset_token) {
        setResetToken(response.data.reset_token)
        setStep('reset')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send reset email')
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      await api.post('/api/v1/auth/reset-password', {
        email,
        reset_token: resetToken,
        new_password: newPassword,
      })
      setSuccess('Password reset successfully! You can now login with your new password.')
      setTimeout(() => {
        window.location.href = '/login'
      }, 2000)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reset password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ maxWidth: '400px', width: '100%' }}>
        <h2>Reset Password</h2>
        
        {step === 'request' ? (
          <form onSubmit={handleRequestReset}>
            <p style={{ color: '#6b7280', marginBottom: '1.5rem' }}>
              Enter your email address and we'll send you instructions to reset your password.
            </p>
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
            {error && <div className="error">{error}</div>}
            {success && <div style={{ padding: '0.75rem', backgroundColor: '#d1fae5', color: '#065f46', borderRadius: '6px', marginBottom: '1rem' }}>{success}</div>}
            <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
              {loading ? 'Sending...' : 'Send Reset Instructions'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleResetPassword}>
            <p style={{ color: '#6b7280', marginBottom: '1.5rem' }}>
              {resetToken ? 'Enter your new password below.' : 'Enter the reset token from your email and your new password.'}
            </p>
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled
              />
            </div>
            {!resetToken && (
              <div className="form-group">
                <label htmlFor="resetToken">Reset Token</label>
                <input
                  type="text"
                  id="resetToken"
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                  required
                  placeholder="Enter token from email"
                />
              </div>
            )}
            <div className="form-group" style={{ position: 'relative' }}>
              <label htmlFor="newPassword">New Password</label>
              <input
                type={showPassword ? 'text' : 'password'}
                id="newPassword"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
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
            {success && <div style={{ padding: '0.75rem', backgroundColor: '#d1fae5', color: '#065f46', borderRadius: '6px', marginBottom: '1rem' }}>{success}</div>}
            <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
              {loading ? 'Resetting...' : 'Reset Password'}
            </button>
            <button
              type="button"
              onClick={() => setStep('request')}
              className="btn btn-secondary"
              style={{ width: '100%', marginTop: '0.5rem' }}
            >
              Back
            </button>
          </form>
        )}
        
        <p style={{ marginTop: '1rem', textAlign: 'center' }}>
          <Link to="/login">Back to Login</Link>
        </p>
      </div>
    </div>
  )
}

export default ForgotPassword

