import { useState } from 'react'

/**
 * Contact Funder Template Component
 * 
 * Provides an email template for users to contact funders about missing grant information.
 */

function ContactFunderTemplate({ grantName, missingData, onClose }) {
  const [copied, setCopied] = useState(false)

  // Build email template
  const buildEmailTemplate = () => {
    const subject = `Award Range Inquiry - ${grantName || 'Grant Opportunity'}`
    
    const questions = []
    if (missingData.includes('award_amount')) {
      questions.push('1. What is the typical award range for this grant?')
    }
    if (missingData.includes('acceptance_rate') || missingData.includes('past_recipients')) {
      questions.push('2. Approximately how many applications do you receive vs. awards made?')
    }
    if (missingData.includes('past_recipients')) {
      questions.push('3. Are there examples of previously funded projects I could review?')
    }
    
    // If no specific missing data, use generic questions
    if (questions.length === 0) {
      questions.push('1. What is the typical award range for this grant?')
      questions.push('2. Approximately how many applications do you receive vs. awards made?')
      questions.push('3. Are there examples of previously funded projects I could review?')
    }

    const body = `Dear Grant Program Officer,

I'm interested in applying for ${grantName || 'this grant opportunity'} and would like to confirm some details before investing time in the application:

${questions.join('\n')}

Understanding these details will help me determine if this opportunity aligns with my project needs and whether it's worth the application effort.

Thank you for your time and consideration.

Best regards,
[Your Name]`

    return { subject, body }
  }

  const { subject, body } = buildEmailTemplate()

  const handleCopy = () => {
    const fullEmail = `Subject: ${subject}\n\n${body}`
    navigator.clipboard.writeText(fullEmail).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleOpenGmail = () => {
    const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    window.open(gmailUrl, '_blank')
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
      <div className="card" style={{ 
        maxWidth: '600px', 
        width: '100%', 
        maxHeight: '90vh',
        overflowY: 'auto'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: 0 }}>Contact Funder Template</h2>
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

        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
            Subject:
          </label>
          <div style={{
            padding: '0.75rem',
            backgroundColor: '#f8f9fa',
            borderRadius: '4px',
            border: '1px solid #dee2e6',
            fontSize: '0.9rem',
            fontFamily: 'monospace'
          }}>
            {subject}
          </div>
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
            Email Body:
          </label>
          <textarea
            readOnly
            value={body}
            style={{
              width: '100%',
              minHeight: '300px',
              padding: '0.75rem',
              border: '1px solid #dee2e6',
              borderRadius: '4px',
              fontSize: '0.9rem',
              fontFamily: 'monospace',
              resize: 'vertical'
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
          <strong>Tip:</strong> Edit the template before sending. Replace [Your Name] with your actual name and customize the questions based on what you need to know.
        </div>

        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <button
            onClick={handleCopy}
            className="btn btn-primary"
            style={{ flex: 1, minWidth: '120px' }}
          >
            {copied ? 'Copied!' : 'Copy Template'}
          </button>
          <button
            onClick={handleOpenGmail}
            className="btn"
            style={{ 
              flex: 1, 
              minWidth: '120px',
              backgroundColor: '#ea4335',
              color: 'white',
              border: 'none'
            }}
          >
            Open in Gmail
          </button>
          <button
            onClick={onClose}
            className="btn btn-secondary"
            style={{ flex: 1, minWidth: '120px' }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default ContactFunderTemplate
