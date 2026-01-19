import { useState } from 'react'
import { api } from '../services/api'

/**
 * Contribute Data Form Component
 * 
 * Allows users to submit missing grant information they discover.
 */

function ContributeDataForm({ grantId, evaluationId, grantName, grantUrl, missingFields, onClose, onSuccess }) {
  const [fieldName, setFieldName] = useState(missingFields?.[0] || '')
  const [fieldValue, setFieldValue] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourceDescription, setSourceDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const fieldLabels = {
    award_amount: 'Award Amount',
    deadline: 'Application Deadline',
    decision_date: 'Decision Date',
    acceptance_rate: 'Acceptance Rate',
    past_recipients: 'Past Recipients',
    eligibility: 'Eligibility Criteria',
    eligibility_criteria: 'Eligibility Criteria',
    preferred_applicants: 'Preferred Applicants',
    application_requirements: 'Application Requirements',
    award_structure: 'Award Structure',
    other: 'Other Information'
  }

  const fieldPlaceholders = {
    award_amount: 'e.g., $50,000 or $25,000 - $100,000',
    deadline: 'e.g., March 15, 2025 or Rolling',
    decision_date: 'e.g., June 1, 2025',
    acceptance_rate: 'e.g., 15% or 1 in 10',
    past_recipients: 'e.g., List of organizations or types of recipients',
    eligibility: 'e.g., Must be registered NGO in Ghana',
    preferred_applicants: 'e.g., Early-stage startups, Women-led organizations',
    application_requirements: 'e.g., Business plan, Financial statements',
    award_structure: 'e.g., One-time payment or Milestone-based',
    other: 'Any other relevant information'
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)

    try {
      const response = await api.post('/api/v1/contributions/submit', {
        grant_id: grantId || null,
        evaluation_id: evaluationId || null,
        grant_name: grantName || null,
        grant_url: grantUrl || null,
        field_name: fieldName,
        field_value: fieldValue,
        source_url: sourceUrl || null,
        source_description: sourceDescription || null
      })

      setSuccess(true)
      if (onSuccess) {
        onSuccess(response.data)
      }
      
      // Auto-close after 2 seconds
      setTimeout(() => {
        if (onClose) onClose()
      }, 2000)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit contribution. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (success) {
    return (
      <div style={{
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
        padding: '1rem'
      }}>
        <div className="card" style={{ maxWidth: '500px', width: '100%', textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✓</div>
          <h2 style={{ marginTop: 0, color: '#28a745' }}>Thank You!</h2>
          <p style={{ color: '#6c757d', marginBottom: '1.5rem' }}>
            Your contribution has been submitted and will be reviewed by our team.
            We'll notify you once it's been processed.
          </p>
          <button onClick={onClose} className="btn btn-primary">
            Close
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{
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
      padding: '1rem'
    }}>
      <div className="card" style={{ maxWidth: '600px', width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: 0 }}>Contribute Grant Data</h2>
          <button 
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.5rem',
              cursor: 'pointer',
              color: '#6c757d',
              padding: '0.25rem 0.5rem'
            }}
          >
            ×
          </button>
        </div>

        <p style={{ color: '#6c757d', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
          Help improve our grant database by sharing information you've discovered. 
          All contributions are reviewed before being added to the system.
        </p>

        {error && (
          <div style={{
            padding: '0.75rem',
            backgroundColor: '#f8d7da',
            color: '#721c24',
            borderRadius: '4px',
            marginBottom: '1rem',
            fontSize: '0.9rem'
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Information Type <span style={{ color: '#dc3545' }}>*</span>
            </label>
            <select
              value={fieldName}
              onChange={(e) => setFieldName(e.target.value)}
              required
              style={{
                width: '100%',
                padding: '0.625rem 0.875rem',
                fontSize: '0.9rem',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                backgroundColor: 'white',
                cursor: 'pointer'
              }}
            >
              <option value="">Select information type...</option>
              {missingFields && missingFields.length > 0 ? (
                missingFields.map(field => (
                  <option key={field} value={field}>
                    {fieldLabels[field] || field}
                  </option>
                ))
              ) : (
                Object.entries(fieldLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))
              )}
            </select>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Value <span style={{ color: '#dc3545' }}>*</span>
            </label>
            <textarea
              value={fieldValue}
              onChange={(e) => setFieldValue(e.target.value)}
              required
              placeholder={fieldPlaceholders[fieldName] || 'Enter the information you found...'}
              style={{
                width: '100%',
                minHeight: '100px',
                padding: '0.625rem 0.875rem',
                fontSize: '0.9rem',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                resize: 'vertical',
                fontFamily: 'inherit'
              }}
            />
            <div style={{ fontSize: '0.75rem', color: '#6c757d', marginTop: '0.25rem' }}>
              Be as specific as possible. Include numbers, dates, or exact text when available.
            </div>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Source URL (optional)
            </label>
            <input
              type="url"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://example.com/grant-page"
              style={{
                width: '100%',
                padding: '0.625rem 0.875rem',
                fontSize: '0.9rem',
                border: '1px solid #d1d5db',
                borderRadius: '4px'
              }}
            />
            <div style={{ fontSize: '0.75rem', color: '#6c757d', marginTop: '0.25rem' }}>
              Where did you find this information? (URL to the source page)
            </div>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
              Additional Context (optional)
            </label>
            <textarea
              value={sourceDescription}
              onChange={(e) => setSourceDescription(e.target.value)}
              placeholder="Any additional context about where or how you found this information..."
              style={{
                width: '100%',
                minHeight: '80px',
                padding: '0.625rem 0.875rem',
                fontSize: '0.9rem',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                resize: 'vertical',
                fontFamily: 'inherit'
              }}
            />
          </div>

          <div style={{
            padding: '1rem',
            backgroundColor: '#e7f3ff',
            borderRadius: '4px',
            marginBottom: '1.5rem',
            fontSize: '0.85rem',
            color: '#004085'
          }}>
            <strong>Note:</strong> Your contribution will be reviewed by our team before being added to the grant database. 
            We'll notify you once it's been processed.
          </div>

          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <button
              type="submit"
              disabled={submitting}
              className="btn btn-primary"
              style={{ flex: 1, minWidth: '120px' }}
            >
              {submitting ? 'Submitting...' : 'Submit Contribution'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
              style={{ flex: 1, minWidth: '120px' }}
              disabled={submitting}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default ContributeDataForm
