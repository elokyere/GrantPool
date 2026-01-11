/**
 * PrivacySecurityNotice Component
 * Displays industry-grade privacy and security information to build user trust
 */

function PrivacySecurityNotice({ compact = false }) {
  if (compact) {
    return (
      <div style={{
        padding: '0.75rem 1rem',
        backgroundColor: '#f0f9ff',
        border: '1px solid #0ea5e9',
        borderRadius: '6px',
        fontSize: '0.875rem',
        color: '#0c4a6e',
        marginTop: '0.5rem'
      }}>
        <span>
          <strong>Your data is secure:</strong> Encrypted (AES-256), private to you, and stored on SOC 2 compliant infrastructure.
        </span>
      </div>
    )
  }

  return (
    <div style={{
      padding: '1.25rem',
      backgroundColor: '#f8fafc',
      border: '1px solid #e2e8f0',
      borderRadius: '8px',
      marginTop: '1rem',
      marginBottom: '1rem'
    }}>
      <div style={{
        marginBottom: '1rem'
      }}>
        <h3 style={{
          margin: 0,
          fontSize: '1.1rem',
          color: '#1e293b',
          fontWeight: 600
        }}>
          Industry-Grade Data Privacy & Security
        </h3>
      </div>
      
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '1rem',
        marginBottom: '1rem'
      }}>
        <div>
          <strong style={{ color: '#334155', display: 'block', marginBottom: '0.25rem' }}>
            End-to-End Encryption
          </strong>
          <span style={{ color: '#64748b', fontSize: '0.9rem' }}>
            All data encrypted in transit (TLS) and at rest (AES-256)
          </span>
        </div>
        
        <div>
          <strong style={{ color: '#334155', display: 'block', marginBottom: '0.25rem' }}>
            Private to You
          </strong>
          <span style={{ color: '#64748b', fontSize: '0.9rem' }}>
            Your projects are private and only accessible by you
          </span>
        </div>
        
        <div>
          <strong style={{ color: '#334155', display: 'block', marginBottom: '0.25rem' }}>
            SOC 2 Compliant
          </strong>
          <span style={{ color: '#64748b', fontSize: '0.9rem' }}>
            Infrastructure meets industry security standards
          </span>
        </div>
      </div>
      
      <div style={{
        padding: '0.75rem',
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: '6px',
        fontSize: '0.875rem',
        color: '#475569'
      }}>
        <strong style={{ color: '#1e293b' }}>Data Protection Details:</strong>
        <ul style={{
          margin: '0.5rem 0 0 0',
          paddingLeft: '1.25rem',
          lineHeight: '1.6'
        }}>
          <li>Your project data is stored on Neon PostgreSQL (SOC 2 Type II certified)</li>
          <li>All database connections use TLS encryption</li>
          <li>Data is isolated per-user with application-level access controls</li>
          <li>No sensitive data is shared between users</li>
          <li>Regular security audits and monitoring</li>
        </ul>
      </div>
    </div>
  )
}

export default PrivacySecurityNotice

