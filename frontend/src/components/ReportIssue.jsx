import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import '../App.css'

function ReportIssue({ onClose, initialData = {} }) {
  const [formData, setFormData] = useState({
    issue_type: initialData.issue_type || '',
    description: '',
    payment_id: initialData.payment_id ? String(initialData.payment_id) : '',
    evaluation_id: initialData.evaluation_id ? String(initialData.evaluation_id) : '',
  })

  // Update form data when initialData changes
  useEffect(() => {
    if (initialData.issue_type) {
      setFormData(prev => ({ ...prev, issue_type: initialData.issue_type }))
    }
    if (initialData.evaluation_id) {
      setFormData(prev => ({ ...prev, evaluation_id: String(initialData.evaluation_id) }))
    }
    if (initialData.payment_id) {
      setFormData(prev => ({ ...prev, payment_id: String(initialData.payment_id) }))
    }
  }, [initialData])
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const queryClient = useQueryClient()

  // Fetch user's payments and evaluations for selection
  const { data: payments } = useQuery({
    queryKey: ['payments'],
    queryFn: async () => {
      try {
        const response = await api.get('/api/v1/payments/history')
        return response.data || []
      } catch {
        return []
      }
    },
  })

  const { data: evaluations } = useQuery({
    queryKey: ['evaluations'],
    queryFn: async () => {
      try {
        const response = await api.get('/api/v1/evaluations/')
        return response.data || []
      } catch {
        return []
      }
    },
  })

  const createRequestMutation = useMutation({
    mutationFn: async (data) => {
      const response = await api.post('/api/v1/support/request', data)
      return response.data
    },
    onSuccess: (data) => {
      setSuccess('Support request submitted successfully! You will receive a confirmation email shortly.')
      queryClient.invalidateQueries(['supportRequests'])
      setFormData({
        issue_type: '',
        description: '',
        payment_id: '',
        evaluation_id: '',
      })
      // Close modal after 2 seconds
      setTimeout(() => {
        onClose()
      }, 2000)
    },
    onError: (error) => {
      setError(error.response?.data?.detail || 'Failed to submit support request. Please try again.')
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    // Validate form
    if (!formData.issue_type) {
      setError('Please select an issue type')
      return
    }

    if (!formData.description.trim()) {
      setError('Please provide a description')
      return
    }

    // Prepare request data
    const requestData = {
      issue_type: formData.issue_type,
      description: formData.description.trim(),
    }

    // Add payment_id if provided and relevant
    if (formData.payment_id && ['duplicate_payment', 'payment_issue'].includes(formData.issue_type)) {
      requestData.payment_id = parseInt(formData.payment_id)
    }

    // Add evaluation_id if provided and relevant
    if (formData.evaluation_id && formData.issue_type === 'technical_error') {
      requestData.evaluation_id = parseInt(formData.evaluation_id)
    }

    createRequestMutation.mutate(requestData)
  }

  const issueTypeOptions = [
    { value: 'duplicate_payment', label: 'Duplicate Payment', description: 'I was charged multiple times for the same assessment' },
    { value: 'technical_error', label: 'Technical Error', description: 'Assessment failed to generate or contains errors' },
    { value: 'payment_issue', label: 'Payment Processing Issue', description: 'Payment was processed incorrectly' },
    { value: 'other', label: 'Other', description: 'General support request' },
  ]

  return (
    <div 
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '1rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div 
        className="card" 
        style={{
          maxWidth: '600px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          position: 'relative',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: 0 }}>Report an Issue</h2>
          <button 
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.5rem',
              cursor: 'pointer',
              color: '#666',
              padding: '0',
              width: '30px',
              height: '30px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="issue_type">Issue Type *</label>
            <select
              id="issue_type"
              value={formData.issue_type}
              onChange={(e) => setFormData({ ...formData, issue_type: e.target.value, payment_id: '', evaluation_id: '' })}
              required
            >
              <option value="">Select issue type</option>
              {issueTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} - {option.description}
                </option>
              ))}
            </select>
          </div>

          {/* Show payment selection for relevant issue types */}
          {formData.issue_type && ['duplicate_payment', 'payment_issue'].includes(formData.issue_type) && payments && payments.length > 0 && (
            <div className="form-group">
              <label htmlFor="payment_id">Related Payment (Optional)</label>
              <select
                id="payment_id"
                value={formData.payment_id}
                onChange={(e) => setFormData({ ...formData, payment_id: e.target.value })}
              >
                <option value="">Select payment</option>
                {payments.map((payment) => (
                  <option key={payment.id} value={payment.id}>
                    Payment #{payment.id} - ${(payment.amount / 100).toFixed(2)} {payment.currency} - {payment.status} - {new Date(payment.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Show evaluation selection for technical errors */}
          {formData.issue_type === 'technical_error' && evaluations && evaluations.length > 0 && (
            <div className="form-group">
              <label htmlFor="evaluation_id">Related Evaluation (Optional)</label>
              <select
                id="evaluation_id"
                value={formData.evaluation_id}
                onChange={(e) => setFormData({ ...formData, evaluation_id: e.target.value })}
              >
                <option value="">Select evaluation</option>
                {evaluations.map((evaluation) => (
                  <option key={evaluation.id} value={evaluation.id}>
                    Evaluation #{evaluation.id} - Grant {evaluation.grant_id} - {evaluation.recommendation}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="description">Description *</label>
            <textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Please describe the issue in detail. Include any relevant information that will help us resolve it quickly."
              required
              rows={6}
            />
          </div>

          {error && <div className="error">{error}</div>}
          {success && <div className="success">{success}</div>}

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1.5rem' }}>
            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={createRequestMutation.isLoading}
              style={{ flex: 1 }}
            >
              {createRequestMutation.isLoading ? 'Submitting...' : 'Submit Request'}
            </button>
            <button 
              type="button" 
              onClick={onClose}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </form>

        <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px', fontSize: '0.875rem' }}>
          <strong>Note:</strong> You can also contact us directly at{' '}
          <a href="mailto:hello@grantpool.org" style={{ color: '#007bff', textDecoration: 'underline' }}>
            hello@grantpool.org
          </a>
          {' '}for support requests.
          <br /><br />
          Eligible refunds (duplicate payments, technical errors, payment issues) are automatically verified and processed. 
          You'll receive a credit for future assessments or a refund via the original payment method. 
          General support requests are reviewed within 48 hours.
        </div>
      </div>
    </div>
  )
}

export default ReportIssue

