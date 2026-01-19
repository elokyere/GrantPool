/**
 * Credit Conversion Notification Component
 * 
 * Displays a one-time notification when user has converted refinement payments to credits.
 * Can be dismissed and stores dismissal state in localStorage.
 */

import { useState, useEffect } from 'react'

function CreditConversionNotification({ hasConvertedRefinement, onDismiss }) {
  const [isVisible, setIsVisible] = useState(false)
  const [isDismissed, setIsDismissed] = useState(false)

  useEffect(() => {
    if (hasConvertedRefinement) {
      // Check if user has already dismissed this notification
      const dismissed = localStorage.getItem('credit_conversion_notification_dismissed')
      if (!dismissed) {
        setIsVisible(true)
      } else {
        setIsDismissed(true)
      }
    }
  }, [hasConvertedRefinement])

  const handleDismiss = () => {
    // Store dismissal in localStorage
    localStorage.setItem('credit_conversion_notification_dismissed', 'true')
    setIsVisible(false)
    setIsDismissed(true)
    if (onDismiss) {
      onDismiss()
    }
  }

  if (!isVisible || isDismissed) {
    return null
  }

  return (
    <div style={{
      marginBottom: '1.5rem',
      padding: '1rem 1.5rem',
      backgroundColor: '#ffffff',
      borderRadius: '4px',
      border: '1px solid #a7f3d0', // muted emerald-200 border
      borderLeft: '4px solid #059669', // muted emerald-600 accent
      boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '1rem'
    }}>
      <div style={{ flex: 1, minWidth: '250px' }}>
        <p style={{ margin: 0, fontWeight: '600', color: '#059669', fontSize: '1rem' }}>
          Credit Conversion Complete
        </p>
        <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: '#6b7280' }}>
          Your $3 refinement payment has been automatically converted to 1 bundle credit. 
          You can now use this credit to create a paid assessment.
        </p>
      </div>
      <button
        onClick={handleDismiss}
        style={{
          padding: '0.5rem 1rem',
          backgroundColor: '#4b5563',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontWeight: '500',
          fontSize: '0.9rem'
        }}
      >
        Got it
      </button>
    </div>
  )
}

export default CreditConversionNotification
