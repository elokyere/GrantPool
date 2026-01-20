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
  
  // Structured data for different field types
  const [recipients, setRecipients] = useState([{
    organization_name: '',
    organization_type: '',
    country: '',
    career_stage: '',
    project_title: '',
    project_summary: '',
    project_theme: ''
  }])
  
  // Award amount structure
  const [awardAmount, setAwardAmount] = useState({
    currency: 'USD',
    min_amount: '',
    max_amount: '',
    is_range: false,
    single_amount: ''
  })
  
  // Date structures
  const [deadline, setDeadline] = useState({
    type: 'specific', // 'specific' or 'rolling'
    date: '',
    text: ''
  })
  
  const [decisionDate, setDecisionDate] = useState({
    type: 'specific', // 'specific' or 'rolling'
    date: '',
    text: ''
  })
  
  // Acceptance rate structure
  const [acceptanceRate, setAcceptanceRate] = useState({
    percentage: '',
    applications_received: '',
    awards_made: '',
    year: ''
  })
  
  // List structures (for preferred_applicants, application_requirements)
  const [listItems, setListItems] = useState([''])
  
  // Award structure dropdown
  const [awardStructure, setAwardStructure] = useState('')

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
      // Convert structured data to final value based on field type
      let finalValue = fieldValue
      
      if (fieldName === 'past_recipients') {
        // Validate and format recipients array
        const validRecipients = recipients
          .filter(r => r.organization_name || r.organization_type || r.project_title)
          .map(r => {
            const recipient = {}
            if (r.organization_name) recipient.organization_name = r.organization_name.trim()
            if (r.organization_type) recipient.organization_type = r.organization_type.trim()
            if (r.country) recipient.country = r.country.trim()
            if (r.career_stage) recipient.career_stage = r.career_stage.trim()
            if (r.project_title) recipient.project_title = r.project_title.trim()
            if (r.project_summary) recipient.project_summary = r.project_summary.trim()
            if (r.project_theme) {
              const themes = r.project_theme.split(',').map(t => t.trim()).filter(t => t)
              if (themes.length > 0) recipient.project_theme = themes
            }
            return recipient
          })
        
        if (validRecipients.length === 0) {
          setError('Please provide at least one recipient with organization name, type, or project title.')
          setSubmitting(false)
          return
        }
        
        finalValue = JSON.stringify(validRecipients, null, 2)
      } else if (fieldName === 'award_amount') {
        // Format award amount
        if (awardAmount.is_range) {
          if (!awardAmount.min_amount && !awardAmount.max_amount) {
            setError('Please provide at least a minimum or maximum amount for the range.')
            setSubmitting(false)
            return
          }
          const parts = []
          if (awardAmount.min_amount) parts.push(`${awardAmount.currency} ${awardAmount.min_amount}`)
          if (awardAmount.max_amount) parts.push(`${awardAmount.currency} ${awardAmount.max_amount}`)
          finalValue = parts.join(' - ')
        } else {
          if (!awardAmount.single_amount) {
            setError('Please provide an award amount.')
            setSubmitting(false)
            return
          }
          finalValue = `${awardAmount.currency} ${awardAmount.single_amount}`
        }
      } else if (fieldName === 'deadline') {
        // Format deadline
        if (deadline.type === 'rolling') {
          finalValue = deadline.text || 'Rolling'
        } else {
          if (!deadline.date && !deadline.text) {
            setError('Please provide a deadline date or text.')
            setSubmitting(false)
            return
          }
          finalValue = deadline.date || deadline.text
        }
      } else if (fieldName === 'decision_date') {
        // Format decision date
        if (decisionDate.type === 'rolling') {
          finalValue = decisionDate.text || 'Rolling'
        } else {
          if (!decisionDate.date && !decisionDate.text) {
            setError('Please provide a decision date or text.')
            setSubmitting(false)
            return
          }
          finalValue = decisionDate.date || decisionDate.text
        }
      } else if (fieldName === 'acceptance_rate') {
        // Format acceptance rate
        if (acceptanceRate.percentage) {
          finalValue = `${acceptanceRate.percentage}%`
          if (acceptanceRate.applications_received || acceptanceRate.awards_made) {
            const details = []
            if (acceptanceRate.applications_received) details.push(`${acceptanceRate.applications_received} applications`)
            if (acceptanceRate.awards_made) details.push(`${acceptanceRate.awards_made} awards`)
            if (acceptanceRate.year) details.push(`(${acceptanceRate.year})`)
            if (details.length > 0) {
              finalValue = `${finalValue} (${details.join(', ')})`
            }
          }
        } else if (acceptanceRate.applications_received && acceptanceRate.awards_made) {
          const rate = ((acceptanceRate.awards_made / acceptanceRate.applications_received) * 100).toFixed(1)
          finalValue = `${rate}% (${acceptanceRate.awards_made} of ${acceptanceRate.applications_received}${acceptanceRate.year ? `, ${acceptanceRate.year}` : ''})`
        } else {
          setError('Please provide either a percentage or both applications received and awards made.')
          setSubmitting(false)
          return
        }
      } else if (fieldName === 'preferred_applicants' || fieldName === 'application_requirements') {
        // Format list items
        const validItems = listItems.filter(item => item.trim()).map(item => item.trim())
        if (validItems.length === 0) {
          setError('Please provide at least one item.')
          setSubmitting(false)
          return
        }
        finalValue = JSON.stringify(validItems)
      } else if (fieldName === 'award_structure') {
        // Use selected award structure
        if (!awardStructure) {
          setError('Please select an award structure.')
          setSubmitting(false)
          return
        }
        // If "Other" is selected, use the free text input
        finalValue = awardStructure === 'Other' ? fieldValue : awardStructure
        if (awardStructure === 'Other' && !fieldValue.trim()) {
          setError('Please describe the award structure.')
          setSubmitting(false)
          return
        }
      }

      const response = await api.post('/api/v1/contributions/submit', {
        grant_id: grantId || null,
        evaluation_id: evaluationId || null,
        grant_name: grantName || null,
        grant_url: grantUrl || null,
        field_name: fieldName,
        field_value: finalValue,
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
  
  const addRecipient = () => {
    setRecipients([...recipients, {
      organization_name: '',
      organization_type: '',
      country: '',
      career_stage: '',
      project_title: '',
      project_summary: '',
      project_theme: ''
    }])
  }
  
  const removeRecipient = (index) => {
    if (recipients.length > 1) {
      setRecipients(recipients.filter((_, i) => i !== index))
    }
  }
  
  const updateRecipient = (index, field, value) => {
    const updated = [...recipients]
    updated[index] = { ...updated[index], [field]: value }
    setRecipients(updated)
  }
  
  const addListItem = () => {
    setListItems([...listItems, ''])
  }
  
  const removeListItem = (index) => {
    if (listItems.length > 1) {
      setListItems(listItems.filter((_, i) => i !== index))
    }
  }
  
  const updateListItem = (index, value) => {
    const updated = [...listItems]
    updated[index] = value
    setListItems(updated)
  }
  
  // Reset structured data when field name changes
  const handleFieldNameChange = (newFieldName) => {
    setFieldName(newFieldName)
    setFieldValue('')
    setError('')
    // Reset structured data
    setRecipients([{
      organization_name: '',
      organization_type: '',
      country: '',
      career_stage: '',
      project_title: '',
      project_summary: '',
      project_theme: ''
    }])
    setAwardAmount({
      currency: 'USD',
      min_amount: '',
      max_amount: '',
      is_range: false,
      single_amount: ''
    })
    setDeadline({ type: 'specific', date: '', text: '' })
    setDecisionDate({ type: 'specific', date: '', text: '' })
    setAcceptanceRate({ percentage: '', applications_received: '', awards_made: '', year: '' })
    setListItems([''])
    setAwardStructure('')
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
              onChange={(e) => handleFieldNameChange(e.target.value)}
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

          {/* Structured form for past_recipients */}
          {fieldName === 'past_recipients' ? (
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                Past Recipients <span style={{ color: '#dc3545' }}>*</span>
              </label>
              <div style={{ fontSize: '0.75rem', color: '#6c757d', marginBottom: '0.75rem', padding: '0.5rem', backgroundColor: '#f0f9ff', borderRadius: '4px' }}>
                <strong>Format:</strong> Provide structured details for each past recipient. At minimum, include organization name, type, or project title.
              </div>
              
              {recipients.map((recipient, idx) => (
                <div key={idx} style={{ 
                  marginBottom: '1rem', 
                  padding: '1rem', 
                  backgroundColor: '#f9fafb', 
                  borderRadius: '4px', 
                  border: '1px solid #e5e7eb' 
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                    <strong style={{ color: '#374151' }}>Recipient {idx + 1}</strong>
                    {recipients.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeRecipient(idx)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#dc2626',
                          cursor: 'pointer',
                          fontSize: '0.875rem',
                          padding: '0.25rem 0.5rem'
                        }}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                    <div>
                      <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                        Organization Name *
                      </label>
                      <input
                        type="text"
                        value={recipient.organization_name}
                        onChange={(e) => updateRecipient(idx, 'organization_name', e.target.value)}
                        placeholder="e.g., African Wildlife Foundation"
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          fontSize: '0.875rem',
                          border: '1px solid #d1d5db',
                          borderRadius: '4px'
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                        Organization Type
                      </label>
                      <select
                        value={recipient.organization_type}
                        onChange={(e) => updateRecipient(idx, 'organization_type', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          fontSize: '0.875rem',
                          border: '1px solid #d1d5db',
                          borderRadius: '4px',
                          backgroundColor: 'white'
                        }}
                      >
                        <option value="">Select type...</option>
                        <option value="NGO">NGO</option>
                        <option value="University">University</option>
                        <option value="Government">Government</option>
                        <option value="Company">Company</option>
                        <option value="Individual">Individual</option>
                        <option value="Community-based Organization">Community-based Organization</option>
                        <option value="Research Institution">Research Institution</option>
                      </select>
                    </div>
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                    <div>
                      <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                        Country
                      </label>
                      <input
                        type="text"
                        value={recipient.country}
                        onChange={(e) => updateRecipient(idx, 'country', e.target.value)}
                        placeholder="e.g., KE, GH, or country name"
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          fontSize: '0.875rem',
                          border: '1px solid #d1d5db',
                          borderRadius: '4px'
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                        Career Stage
                      </label>
                      <select
                        value={recipient.career_stage}
                        onChange={(e) => updateRecipient(idx, 'career_stage', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          fontSize: '0.875rem',
                          border: '1px solid #d1d5db',
                          borderRadius: '4px',
                          backgroundColor: 'white'
                        }}
                      >
                        <option value="">Select stage...</option>
                        <option value="Early-career">Early-career</option>
                        <option value="Mid-career">Mid-career</option>
                        <option value="Senior">Senior</option>
                        <option value="Established">Established</option>
                      </select>
                    </div>
                  </div>
                  
                  <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid #e5e7eb' }}>
                    <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#374151', marginBottom: '0.5rem' }}>
                      Project Details (if available)
                    </div>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                        Project Title
                      </label>
                      <input
                        type="text"
                        value={recipient.project_title}
                        onChange={(e) => updateRecipient(idx, 'project_title', e.target.value)}
                        placeholder="e.g., Geospatial Monitoring for Community Conservation"
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          fontSize: '0.875rem',
                          border: '1px solid #d1d5db',
                          borderRadius: '4px'
                        }}
                      />
                    </div>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                        Project Summary
                      </label>
                      <textarea
                        value={recipient.project_summary}
                        onChange={(e) => updateRecipient(idx, 'project_summary', e.target.value)}
                        placeholder="1-2 sentence description of what the project does/addresses"
                        style={{
                          width: '100%',
                          minHeight: '60px',
                          padding: '0.5rem',
                          fontSize: '0.875rem',
                          border: '1px solid #d1d5db',
                          borderRadius: '4px',
                          resize: 'vertical',
                          fontFamily: 'inherit'
                        }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                        Project Themes (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={recipient.project_theme}
                        onChange={(e) => updateRecipient(idx, 'project_theme', e.target.value)}
                        placeholder="e.g., climate, biodiversity, geospatial, community"
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          fontSize: '0.875rem',
                          border: '1px solid #d1d5db',
                          borderRadius: '4px'
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))}
              
              <button
                type="button"
                onClick={addRecipient}
                style={{
                  padding: '0.5rem 1rem',
                  fontSize: '0.875rem',
                  backgroundColor: '#f3f4f6',
                  border: '1px solid #d1d5db',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  color: '#374151',
                  fontWeight: '500'
                }}
              >
                + Add Another Recipient
              </button>
            </div>
          ) : fieldName === 'award_amount' ? (
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                Award Amount <span style={{ color: '#dc3545' }}>*</span>
              </label>
              <div style={{ marginBottom: '0.75rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={awardAmount.is_range}
                    onChange={(e) => setAwardAmount({...awardAmount, is_range: e.target.checked})}
                  />
                  <span>This is a range (min - max)</span>
                </label>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr 1fr', gap: '0.75rem', alignItems: 'end' }}>
                <select
                  value={awardAmount.currency}
                  onChange={(e) => setAwardAmount({...awardAmount, currency: e.target.value})}
                  style={{
                    padding: '0.5rem',
                    fontSize: '0.875rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px',
                    backgroundColor: 'white'
                  }}
                >
                  <option value="USD">USD</option>
                  <option value="GHS">GHS</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                </select>
                {awardAmount.is_range ? (
                  <>
                    <input
                      type="text"
                      value={awardAmount.min_amount}
                      onChange={(e) => setAwardAmount({...awardAmount, min_amount: e.target.value})}
                      placeholder="Min amount"
                      style={{
                        padding: '0.5rem',
                        fontSize: '0.875rem',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px'
                      }}
                    />
                    <input
                      type="text"
                      value={awardAmount.max_amount}
                      onChange={(e) => setAwardAmount({...awardAmount, max_amount: e.target.value})}
                      placeholder="Max amount"
                      style={{
                        padding: '0.5rem',
                        fontSize: '0.875rem',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px'
                      }}
                    />
                  </>
                ) : (
                  <input
                    type="text"
                    value={awardAmount.single_amount}
                    onChange={(e) => setAwardAmount({...awardAmount, single_amount: e.target.value})}
                    placeholder="e.g., 50,000"
                    style={{
                      gridColumn: 'span 2',
                      padding: '0.5rem',
                      fontSize: '0.875rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px'
                    }}
                  />
                )}
              </div>
            </div>
          ) : fieldName === 'deadline' || fieldName === 'decision_date' ? (
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                {fieldLabels[fieldName]} <span style={{ color: '#dc3545' }}>*</span>
              </label>
              <div style={{ marginBottom: '0.75rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                  <input
                    type="radio"
                    checked={(fieldName === 'deadline' ? deadline : decisionDate).type === 'specific'}
                    onChange={() => fieldName === 'deadline' ? setDeadline({...deadline, type: 'specific'}) : setDecisionDate({...decisionDate, type: 'specific'})}
                  />
                  <span>Specific Date</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem' }}>
                  <input
                    type="radio"
                    checked={(fieldName === 'deadline' ? deadline : decisionDate).type === 'rolling'}
                    onChange={() => fieldName === 'deadline' ? setDeadline({...deadline, type: 'rolling'}) : setDecisionDate({...decisionDate, type: 'rolling'})}
                  />
                  <span>Rolling / Ongoing</span>
                </label>
              </div>
              {(fieldName === 'deadline' ? deadline : decisionDate).type === 'specific' ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <input
                    type="date"
                    value={(fieldName === 'deadline' ? deadline : decisionDate).date}
                    onChange={(e) => fieldName === 'deadline' ? setDeadline({...deadline, date: e.target.value}) : setDecisionDate({...decisionDate, date: e.target.value})}
                    style={{
                      padding: '0.5rem',
                      fontSize: '0.875rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px'
                    }}
                  />
                  <input
                    type="text"
                    value={(fieldName === 'deadline' ? deadline : decisionDate).text}
                    onChange={(e) => fieldName === 'deadline' ? setDeadline({...deadline, text: e.target.value}) : setDecisionDate({...decisionDate, text: e.target.value})}
                    placeholder="Or enter as text (e.g., March 15, 2025)"
                    style={{
                      padding: '0.5rem',
                      fontSize: '0.875rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px'
                    }}
                  />
                </div>
              ) : (
                <input
                  type="text"
                  value={(fieldName === 'deadline' ? deadline : decisionDate).text}
                  onChange={(e) => fieldName === 'deadline' ? setDeadline({...deadline, text: e.target.value}) : setDecisionDate({...decisionDate, text: e.target.value})}
                  placeholder="e.g., Rolling, Ongoing, Open year-round"
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    fontSize: '0.875rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px'
                  }}
                />
              )}
            </div>
          ) : fieldName === 'acceptance_rate' ? (
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                Acceptance Rate <span style={{ color: '#dc3545' }}>*</span>
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                    Percentage
                  </label>
                  <input
                    type="text"
                    value={acceptanceRate.percentage}
                    onChange={(e) => setAcceptanceRate({...acceptanceRate, percentage: e.target.value})}
                    placeholder="e.g., 15"
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      fontSize: '0.875rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px'
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                    Year (optional)
                  </label>
                  <input
                    type="text"
                    value={acceptanceRate.year}
                    onChange={(e) => setAcceptanceRate({...acceptanceRate, year: e.target.value})}
                    placeholder="e.g., 2024"
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      fontSize: '0.875rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px'
                    }}
                  />
                </div>
              </div>
              <div style={{ fontSize: '0.75rem', color: '#6c757d', marginBottom: '0.5rem' }}>Or provide raw numbers:</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                    Applications Received
                  </label>
                  <input
                    type="text"
                    value={acceptanceRate.applications_received}
                    onChange={(e) => setAcceptanceRate({...acceptanceRate, applications_received: e.target.value})}
                    placeholder="e.g., 500"
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      fontSize: '0.875rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px'
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', fontWeight: '500' }}>
                    Awards Made
                  </label>
                  <input
                    type="text"
                    value={acceptanceRate.awards_made}
                    onChange={(e) => setAcceptanceRate({...acceptanceRate, awards_made: e.target.value})}
                    placeholder="e.g., 25"
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      fontSize: '0.875rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px'
                    }}
                  />
                </div>
              </div>
            </div>
          ) : fieldName === 'preferred_applicants' || fieldName === 'application_requirements' ? (
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                {fieldLabels[fieldName]} <span style={{ color: '#dc3545' }}>*</span>
              </label>
              <div style={{ fontSize: '0.75rem', color: '#6c757d', marginBottom: '0.75rem', padding: '0.5rem', backgroundColor: '#f0f9ff', borderRadius: '4px' }}>
                <strong>Format:</strong> Add each item separately. They will be stored as a structured list.
              </div>
              {listItems.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
                  <input
                    type="text"
                    value={item}
                    onChange={(e) => updateListItem(idx, e.target.value)}
                    placeholder={`Item ${idx + 1}`}
                    style={{
                      flex: 1,
                      padding: '0.5rem',
                      fontSize: '0.875rem',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px'
                    }}
                  />
                  {listItems.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeListItem(idx)}
                      style={{
                        padding: '0.5rem',
                        background: 'none',
                        border: 'none',
                        color: '#dc2626',
                        cursor: 'pointer',
                        fontSize: '0.875rem'
                      }}
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={addListItem}
                style={{
                  padding: '0.5rem 1rem',
                  fontSize: '0.875rem',
                  backgroundColor: '#f3f4f6',
                  border: '1px solid #d1d5db',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  color: '#374151',
                  fontWeight: '500'
                }}
              >
                + Add Another Item
              </button>
            </div>
          ) : fieldName === 'award_structure' ? (
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                Award Structure <span style={{ color: '#dc3545' }}>*</span>
              </label>
              <select
                value={awardStructure}
                onChange={(e) => setAwardStructure(e.target.value)}
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
                <option value="">Select award structure...</option>
                <option value="One-time payment">One-time payment</option>
                <option value="Milestone-based">Milestone-based</option>
                <option value="Installments">Installments</option>
                <option value="Reimbursement">Reimbursement</option>
                <option value="Matching funds">Matching funds</option>
                <option value="Other">Other</option>
              </select>
              {awardStructure === 'Other' && (
                <input
                  type="text"
                  value={fieldValue}
                  onChange={(e) => setFieldValue(e.target.value)}
                  placeholder="Describe the award structure..."
                  style={{
                    width: '100%',
                    marginTop: '0.5rem',
                    padding: '0.5rem',
                    fontSize: '0.875rem',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px'
                  }}
                />
              )}
            </div>
          ) : (
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
          )}

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
