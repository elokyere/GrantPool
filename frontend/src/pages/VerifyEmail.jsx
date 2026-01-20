import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { api } from '../services/api'
import '../App.css'

function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState('verifying') // 'verifying', 'success', 'error'
  const [message, setMessage] = useState('Verifying your email...')
  const navigate = useNavigate()

  useEffect(() => {
    const token = searchParams.get('token')
    const email = searchParams.get('email')

    if (!token || !email) {
      setStatus('error')
      setMessage('Invalid verification link. Please check your email for the correct link.')
      return
    }

    // Verify email
    const verifyEmail = async () => {
      try {
        const response = await api.post('/api/v1/auth/verify-email', {
          email,
          token,
        })
        setStatus('success')
        setMessage(response.data.message || 'Email verified successfully!')
        
        // Redirect to login after 3 seconds
        setTimeout(() => {
          navigate('/login')
        }, 3000)
      } catch (err) {
        setStatus('error')
        setMessage(err.response?.data?.detail || 'Verification failed. The link may have expired.')
      }
    }

    verifyEmail()
  }, [searchParams, navigate])

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ maxWidth: '500px', width: '100%', textAlign: 'center' }}>
        {status === 'verifying' && (
          <>
            <div style={{ 
              display: 'inline-block',
              width: '60px',
              height: '60px',
              border: '4px solid #f3f4f6',
              borderTop: '4px solid #4a77e8',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              marginBottom: '1rem'
            }}></div>
            <h2>Verifying Email</h2>
            <p>{message}</p>
            <style>{`
              @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
              }
            `}</style>
          </>
        )}
        
        {status === 'success' && (
          <>
            <div style={{ fontSize: '4rem', marginBottom: '1rem', color: '#10b981' }}>✓</div>
            <h2 style={{ color: '#10b981' }}>Email Verified!</h2>
            <p>{message}</p>
            <p style={{ color: '#6b7280', fontSize: '0.9rem', marginTop: '1rem' }}>
              Redirecting to login page...
            </p>
            <Link to="/login" className="btn btn-primary" style={{ marginTop: '1rem' }}>
              Go to Login
            </Link>
          </>
        )}
        
        {status === 'error' && (
          <>
            <div style={{ fontSize: '4rem', marginBottom: '1rem', color: '#ef4444' }}>✗</div>
            <h2 style={{ color: '#ef4444' }}>Verification Failed</h2>
            <p>{message}</p>
            <div style={{ marginTop: '1.5rem' }}>
              <Link to="/resend-verification" className="btn btn-primary" style={{ marginRight: '0.5rem' }}>
                Resend Verification Email
              </Link>
              <Link to="/login" className="btn btn-secondary">
                Go to Login
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default VerifyEmail
