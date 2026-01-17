import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../services/api'
import '../App.css'

function Settings() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [deleteSuccess, setDeleteSuccess] = useState(false)

  const handleDeleteAccount = async () => {
    if (deleteConfirmation !== 'DELETE') {
      setDeleteError('Please type DELETE to confirm')
      return
    }

    setDeleteError('')
    setDeleteLoading(true)

    try {
      await api.delete('/api/v1/users/me')
      setDeleteSuccess(true)
      
      // Logout and redirect after a short delay
      setTimeout(() => {
        logout()
        navigate('/', { replace: true })
      }, 2000)
    } catch (err) {
      console.error('Delete account error:', err)
      setDeleteError(err.response?.data?.detail || 'Failed to delete account. Please try again or contact support.')
      setDeleteLoading(false)
    }
  }

  return (
    <div className="container" style={{ maxWidth: '800px', margin: '2rem auto', padding: '2rem' }}>
      <h1 style={{ marginBottom: '2rem' }}>Account Settings</h1>

      <div className="card" style={{ marginBottom: '2rem' }}>
        <h2 style={{ marginBottom: '1rem', color: '#333' }}>Account Information</h2>
        <div style={{ marginBottom: '0.5rem' }}>
          <strong>Email:</strong> {user?.email}
        </div>
        <div style={{ marginBottom: '0.5rem' }}>
          <strong>Name:</strong> {user?.full_name || 'Not set'}
        </div>
        <div style={{ marginBottom: '0.5rem' }}>
          <strong>Account Created:</strong> {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
        </div>
      </div>

      <div className="card" style={{ border: '2px solid #dc3545', backgroundColor: '#fff5f5' }}>
        <h2 style={{ marginBottom: '1rem', color: '#dc3545' }}>Danger Zone</h2>
        
        {!showDeleteConfirm && !deleteSuccess && (
          <div>
            <p style={{ marginBottom: '1rem', color: '#666' }}>
              Once you delete your account, there is no going back. This action is permanent and will:
            </p>
            <ul style={{ marginBottom: '1.5rem', paddingLeft: '1.5rem', color: '#666' }}>
              <li>Delete all your projects</li>
              <li>Delete all your grant evaluations</li>
              <li>Delete all your assessment purchases</li>
              <li>Delete all your support requests</li>
              <li>Delete all your payment records</li>
            </ul>
            <p style={{ marginBottom: '1.5rem', fontSize: '0.9rem', color: '#888', fontStyle: 'italic' }}>
              Note: GrantPool does not store your payment card details. All payments are processed securely through Paystack, and we only store payment transaction metadata (amount, status, reference number).
            </p>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="btn"
              style={{
                backgroundColor: '#dc3545',
                color: 'white',
                border: 'none'
              }}
            >
              Delete My Account
            </button>
          </div>
        )}

        {showDeleteConfirm && !deleteSuccess && (
          <div>
            <p style={{ marginBottom: '1rem', color: '#dc3545', fontWeight: 'bold' }}>
              ⚠️ This action cannot be undone!
            </p>
            <p style={{ marginBottom: '1rem', color: '#666' }}>
              To confirm, please type <strong>DELETE</strong> in the box below:
            </p>
            <input
              type="text"
              value={deleteConfirmation}
              onChange={(e) => {
                setDeleteConfirmation(e.target.value)
                setDeleteError('')
              }}
              placeholder="Type DELETE to confirm"
              style={{
                width: '100%',
                padding: '0.75rem',
                marginBottom: '1rem',
                border: '2px solid #dc3545',
                borderRadius: '4px',
                fontSize: '1rem'
              }}
              disabled={deleteLoading}
            />
            {deleteError && (
              <div style={{ 
                marginBottom: '1rem', 
                padding: '0.75rem', 
                backgroundColor: '#fee', 
                color: '#c33',
                borderRadius: '4px'
              }}>
                {deleteError}
              </div>
            )}
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button
                onClick={handleDeleteAccount}
                disabled={deleteLoading || deleteConfirmation !== 'DELETE'}
                className="btn"
                style={{
                  backgroundColor: deleteConfirmation === 'DELETE' ? '#dc3545' : '#ccc',
                  color: 'white',
                  border: 'none',
                  cursor: deleteConfirmation === 'DELETE' && !deleteLoading ? 'pointer' : 'not-allowed',
                  opacity: deleteLoading ? 0.6 : 1
                }}
              >
                {deleteLoading ? 'Deleting...' : 'Confirm Deletion'}
              </button>
              <button
                onClick={() => {
                  setShowDeleteConfirm(false)
                  setDeleteConfirmation('')
                  setDeleteError('')
                }}
                disabled={deleteLoading}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {deleteSuccess && (
          <div style={{ textAlign: 'center', padding: '2rem' }}>
            <p style={{ color: '#28a745', fontSize: '1.1rem', marginBottom: '1rem' }}>
              ✓ Your account has been deleted successfully.
            </p>
            <p style={{ color: '#666' }}>
              You will be redirected to the home page shortly...
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Settings
