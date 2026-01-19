import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

/**
 * Contributions History Component
 * 
 * Displays user's contribution history with status, badges, and statistics.
 */

function ContributionsHistory() {
  const { data: contributions, isLoading } = useQuery({
    queryKey: ['my-contributions'],
    queryFn: async () => {
      const response = await api.get('/api/v1/contributions/my-contributions')
      return response.data
    }
  })

  // Calculate statistics
  const stats = contributions ? {
    total: contributions.length,
    approved: contributions.filter(c => c.status === 'approved').length,
    pending: contributions.filter(c => c.status === 'pending').length,
    rejected: contributions.filter(c => c.status === 'rejected').length,
    merged: contributions.filter(c => c.status === 'merged').length
  } : { total: 0, approved: 0, pending: 0, rejected: 0, merged: 0 }

  // Determine badge level
  const getBadgeLevel = () => {
    if (stats.approved >= 20) return { level: 'Expert Contributor', color: '#9c27b0', description: '20+ approved contributions' }
    if (stats.approved >= 10) return { level: 'Advanced Contributor', color: '#2196f3', description: '10+ approved contributions' }
    if (stats.approved >= 5) return { level: 'Active Contributor', color: '#4caf50', description: '5+ approved contributions' }
    if (stats.approved >= 1) return { level: 'Contributor', color: '#ff9800', description: '1+ approved contribution' }
    return { level: 'New Contributor', color: '#9e9e9e', description: 'Start contributing to earn badges' }
  }

  const badge = getBadgeLevel()

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

  const statusColors = {
    pending: { bg: '#fff3cd', text: '#856404', border: '#ffc107' },
    approved: { bg: '#d4edda', text: '#155724', border: '#28a745' },
    rejected: { bg: '#f8d7da', text: '#721c24', border: '#dc3545' },
    merged: { bg: '#d1ecf1', text: '#0c5460', border: '#17a2b8' }
  }

  if (isLoading) {
    return (
      <div className="card" style={{ padding: '2rem', textAlign: 'center' }}>
        <p>Loading your contributions...</p>
      </div>
    )
  }

  return (
    <div>
      {/* Statistics and Badge */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <h3 style={{ marginTop: 0, marginBottom: '1.5rem' }}>Your Contributions</h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
          <div style={{ textAlign: 'center', padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#333' }}>{stats.total}</div>
            <div style={{ fontSize: '0.85rem', color: '#666', marginTop: '0.25rem' }}>Total</div>
          </div>
          <div style={{ textAlign: 'center', padding: '1rem', backgroundColor: '#d4edda', borderRadius: '8px' }}>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#155724' }}>{stats.approved}</div>
            <div style={{ fontSize: '0.85rem', color: '#155724', marginTop: '0.25rem' }}>Approved</div>
          </div>
          <div style={{ textAlign: 'center', padding: '1rem', backgroundColor: '#fff3cd', borderRadius: '8px' }}>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#856404' }}>{stats.pending}</div>
            <div style={{ fontSize: '0.85rem', color: '#856404', marginTop: '0.25rem' }}>Pending</div>
          </div>
          <div style={{ textAlign: 'center', padding: '1rem', backgroundColor: '#f8d7da', borderRadius: '8px' }}>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#721c24' }}>{stats.rejected}</div>
            <div style={{ fontSize: '0.85rem', color: '#721c24', marginTop: '0.25rem' }}>Rejected</div>
          </div>
        </div>

        {/* Badge Display */}
        <div style={{
          padding: '1.5rem',
          backgroundColor: badge.color + '15',
          border: `2px solid ${badge.color}`,
          borderRadius: '8px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: badge.color, marginBottom: '0.5rem' }}>
            {badge.level}
          </div>
          <div style={{ fontSize: '0.9rem', color: '#666' }}>
            {badge.description}
          </div>
        </div>
      </div>

      {/* Contributions List */}
      {contributions && contributions.length > 0 ? (
        <div className="card">
          <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>Contribution History</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {contributions.map((contribution) => {
              const statusColor = statusColors[contribution.status] || statusColors.pending
              const fieldLabel = fieldLabels[contribution.field_name] || contribution.field_name.replace('_', ' ').title()
              
              return (
                <div
                  key={contribution.id}
                  style={{
                    padding: '1rem',
                    border: `1px solid ${statusColor.border}`,
                    borderRadius: '6px',
                    backgroundColor: statusColor.bg
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 'bold', color: '#333', marginBottom: '0.25rem' }}>
                        {contribution.grant_name || 'Unknown Grant'}
                      </div>
                      <div style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
                        <strong>Field:</strong> {fieldLabel}
                      </div>
                      <div style={{ fontSize: '0.85rem', color: '#666', marginBottom: '0.5rem' }}>
                        <strong>Value:</strong> {contribution.field_value.length > 150 
                          ? contribution.field_value.substring(0, 150) + '...' 
                          : contribution.field_value}
                      </div>
                      {contribution.source_url && (
                        <div style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>
                          <a 
                            href={contribution.source_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            style={{ color: '#2563eb', textDecoration: 'none' }}
                          >
                            View Source
                          </a>
                        </div>
                      )}
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{
                        display: 'inline-block',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        fontWeight: 'bold',
                        backgroundColor: statusColor.bg,
                        color: statusColor.text,
                        border: `1px solid ${statusColor.border}`
                      }}>
                        {contribution.status.toUpperCase()}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#666', marginTop: '0.5rem' }}>
                        {new Date(contribution.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                  {contribution.admin_notes && (
                    <div style={{
                      marginTop: '0.75rem',
                      padding: '0.75rem',
                      backgroundColor: 'white',
                      borderRadius: '4px',
                      fontSize: '0.85rem',
                      color: '#666',
                      borderLeft: `3px solid ${statusColor.border}`
                    }}>
                      <strong>Admin Note:</strong> {contribution.admin_notes}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ color: '#666', marginBottom: '1rem' }}>
            You haven't made any contributions yet.
          </p>
          <p style={{ color: '#666', fontSize: '0.9rem' }}>
            Start contributing by submitting missing grant information when you view assessments!
          </p>
        </div>
      )}
    </div>
  )
}

export default ContributionsHistory
