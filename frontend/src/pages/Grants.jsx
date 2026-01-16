import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import '../App.css'

function Grants() {
  const [showForm, setShowForm] = useState(false)
  const [grantUrl, setGrantUrl] = useState('')
  const [keywordFilter, setKeywordFilter] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [extractionError, setExtractionError] = useState('')
  const [showSuccess, setShowSuccess] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')

  const queryClient = useQueryClient()

  const { data: grants, isLoading } = useQuery({
    queryKey: ['grants'],
    queryFn: async () => {
      const response = await api.get('/api/v1/grants/')
      return response.data
    },
    refetchInterval: 10000, // Auto-refresh every 10 seconds (polls for new approvals)
    refetchOnWindowFocus: true, // Refetch when user returns to tab
    staleTime: 5000, // Consider data stale after 5 seconds
  })

  // Get display title (canonical if available, fallback to name)
  const getDisplayTitle = (grant) => {
    // Use canonical_title if normalization exists and is approved
    if (grant.normalization?.canonical_title) {
      return grant.normalization.canonical_title
    }
    // Fallback to raw name
    return grant.name || 'Untitled Grant'
  }

  // Generate neutral summary from canonical or raw fields
  const getSummary = (grant) => {
    // Use canonical_summary if normalization exists and is approved
    if (grant.normalization?.canonical_summary) {
      return grant.normalization.canonical_summary
    }
    // Fallback to raw description/mission
    if (grant.description) {
      return grant.description
    }
    if (grant.mission) {
      return grant.mission
    }
    return null
  }

  // Get timeline info (canonical status if available, fallback to raw deadline)
  const getTimeline = (grant) => {
    // Use timeline_status from normalization if available
    if (grant.normalization?.timeline_status) {
      const status = grant.normalization.timeline_status
      const statusLabels = {
        'active': '🟢 Active',
        'closed': '🔴 Closed',
        'rolling': '🔄 Rolling',
        'unknown': '⚪ Unknown'
      }
      return statusLabels[status] || status
    }
    
    // Fallback to raw deadline/decision_date
    const parts = []
    if (grant.deadline) {
      parts.push(`Deadline: ${grant.deadline}`)
    }
    if (grant.decision_date) {
      parts.push(`Decision: ${grant.decision_date}`)
    }
    return parts.length > 0 ? parts.join(' | ') : null
  }

  // Get timeline status badge (for display)
  const getTimelineBadge = (grant) => {
    if (!grant.normalization?.timeline_status) {
      return null
    }
    const status = grant.normalization.timeline_status
    const badges = {
      'active': { emoji: '🟢', label: 'Active', color: '#10b981' },
      'closed': { emoji: '🔴', label: 'Closed', color: '#ef4444' },
      'rolling': { emoji: '🔄', label: 'Rolling', color: '#3b82f6' },
      'unknown': { emoji: '⚪', label: 'Unknown', color: '#6b7280' }
    }
    return badges[status] || null
  }

  // Filter grants by keyword (searches both canonical and raw fields)
  const filteredGrants = useMemo(() => {
    if (!grants) return []
    if (!keywordFilter.trim()) return grants
    
    const keyword = keywordFilter.toLowerCase()
    return grants.filter(grant => {
      const title = getDisplayTitle(grant).toLowerCase()
      const summary = getSummary(grant)?.toLowerCase() || ''
      const name = grant.name?.toLowerCase() || ''
      const description = grant.description?.toLowerCase() || ''
      const url = grant.source_url?.toLowerCase() || ''
      
      return title.includes(keyword) ||
        summary.includes(keyword) ||
        name.includes(keyword) ||
        description.includes(keyword) ||
        url.includes(keyword)
    })
  }, [grants, keywordFilter])

  // Check if user is admin (this would come from user context - simplified for now)
  const { data: userProfile } = useQuery({
    queryKey: ['userProfile'],
    queryFn: async () => {
      try {
        const response = await api.get('/api/v1/users/me')
        return response.data
      } catch {
        return null
      }
    },
  })

  const isAdmin = userProfile?.is_superuser || false

  // Fetch pending grants if admin
  const { data: pendingGrants } = useQuery({
    queryKey: ['pendingGrants'],
    queryFn: async () => {
      const response = await api.get('/api/v1/grants/pending')
      return response.data
    },
    enabled: isAdmin,
  })

  const extractFromUrlMutation = useMutation({
    mutationFn: async (url) => {
      const response = await api.post('/api/v1/grants/from-url', {
        source_url: url,
        name: null,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['grants'])
      queryClient.invalidateQueries(['pendingGrants'])
      setGrantUrl('')
      setShowForm(false)
      setExtractionError('')
      setSuccessMessage('Grant submitted successfully! It will be reviewed by an admin before being visible to all users.')
      setShowSuccess(true)
      // Auto-hide after 8 seconds
      setTimeout(() => {
        setShowSuccess(false)
      }, 8000)
    },
    onError: (err) => {
      setExtractionError(err.response?.data?.detail || 'Failed to extract grant from URL')
    },
  })

  const approveGrantMutation = useMutation({
    mutationFn: async ({ grantId, status, reason }) => {
      const response = await api.post(`/api/v1/grants/${grantId}/approve`, {
        approval_status: status,
        rejection_reason: reason || null,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['grants'])
      queryClient.invalidateQueries(['pendingGrants'])
    },
  })

  const handleExtractFromUrl = async (e) => {
    e.preventDefault()
    if (!grantUrl.trim()) {
      setExtractionError('Please enter a grant URL')
      return
    }
    setExtracting(true)
    setExtractionError('')
    extractFromUrlMutation.mutate(grantUrl)
    setExtracting(false)
  }

  if (isLoading) {
    return <div className="container">Loading...</div>
  }

  return (
    <div className="container" style={{ maxWidth: '900px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: '500' }}>Grant Index</h1>
          <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.875rem', color: '#6b7280' }}>
            Reference memory of grants encountered
          </p>
        </div>
        <button 
          onClick={() => setShowForm(!showForm)} 
          className="btn btn-secondary"
          style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
        >
          {showForm ? 'Cancel' : 'Add Grant'}
        </button>
      </div>

      {/* Success Message */}
      {showSuccess && (
        <div style={{
          marginBottom: '1.5rem',
          padding: '1rem 1.25rem',
          backgroundColor: '#d1fae5',
          border: '1px solid #10b981',
          borderLeft: '4px solid #10b981',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'start',
          gap: '0.75rem',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
        }}>
          <div style={{ fontSize: '1.25rem', lineHeight: '1' }}>✓</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: '500', color: '#065f46', marginBottom: '0.25rem' }}>
              Grant Submitted
            </div>
            <div style={{ fontSize: '0.875rem', color: '#047857' }}>
              {successMessage}
            </div>
          </div>
          <button
            onClick={() => setShowSuccess(false)}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.25rem',
              color: '#065f46',
              cursor: 'pointer',
              padding: '0',
              lineHeight: '1'
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* Add Grant Form - Minimal */}
      {showForm && (
        <div className="card" style={{ marginBottom: '2rem' }}>
          <h3 style={{ marginTop: 0, fontSize: '1rem', fontWeight: '500' }}>Add Grant from URL</h3>
          <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '1rem' }}>
            Paste a grant URL. Information will be extracted and stored for reference.
          </p>
          <form onSubmit={handleExtractFromUrl} style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="url"
              className="landing-input"
              placeholder="https://example.com/grant-opportunity"
              value={grantUrl}
              onChange={(e) => setGrantUrl(e.target.value)}
              style={{ flex: 1, padding: '0.625rem 0.875rem', fontSize: '0.875rem' }}
              disabled={extracting || extractFromUrlMutation.isLoading}
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={extracting || extractFromUrlMutation.isLoading || !grantUrl.trim()}
              style={{ whiteSpace: 'nowrap', padding: '0.625rem 1rem', fontSize: '0.875rem' }}
            >
              {extracting || extractFromUrlMutation.isLoading ? 'Extracting...' : 'Add'}
            </button>
          </form>
          {extractionError && (
            <div style={{ 
              padding: '0.75rem', 
              marginTop: '0.75rem',
              backgroundColor: '#fee2e2', 
              color: '#dc2626',
              borderRadius: '4px',
              fontSize: '0.875rem'
            }}>
              {extractionError}
            </div>
          )}
        </div>
      )}

      {/* Admin: Pending Grants Section */}
      {isAdmin && pendingGrants && pendingGrants.length > 0 && (
        <div style={{ marginBottom: '2rem', padding: '1rem', backgroundColor: '#fff3cd', borderRadius: '6px', border: '1px solid #ffc107' }}>
          <h3 style={{ marginTop: 0, fontSize: '1rem', fontWeight: '500', marginBottom: '1rem' }}>Pending Approval ({pendingGrants.length})</h3>
          <div style={{ border: '1px solid #e5e7eb', borderRadius: '4px', overflow: 'hidden', marginBottom: '1rem' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280' }}>ID</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280' }}>Name</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280' }}>URL</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pendingGrants.map((grant) => (
                  <tr key={grant.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '0.75rem', fontFamily: 'monospace', fontSize: '0.8125rem' }}>{grant.id}</td>
                    <td style={{ padding: '0.75rem', fontWeight: '500' }}>{grant.name}</td>
                    <td style={{ padding: '0.75rem' }}>
                      <a href={grant.source_url} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', fontSize: '0.8125rem' }}>
                        {grant.source_url}
                      </a>
                    </td>
                    <td style={{ padding: '0.75rem' }}>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button
                          onClick={() => {
                            if (window.confirm(`Approve grant: ${grant.name}?`)) {
                              approveGrantMutation.mutate({ grantId: grant.id, status: 'approved' })
                            }
                          }}
                          className="btn"
                          style={{ 
                            fontSize: '0.75rem', 
                            padding: '0.375rem 0.75rem',
                            backgroundColor: '#28a745',
                            color: 'white',
                            border: 'none'
                          }}
                          disabled={approveGrantMutation.isLoading}
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => {
                            const reason = window.prompt('Rejection reason (optional):')
                            if (reason !== null) {
                              approveGrantMutation.mutate({ grantId: grant.id, status: 'rejected', reason })
                            }
                          }}
                          className="btn"
                          style={{ 
                            fontSize: '0.75rem', 
                            padding: '0.375rem 0.75rem',
                            backgroundColor: '#dc3545',
                            color: 'white',
                            border: 'none'
                          }}
                          disabled={approveGrantMutation.isLoading}
                        >
                          Reject
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Filter */}
      {grants && grants.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <input
            type="text"
            placeholder="Filter by keyword..."
            value={keywordFilter}
            onChange={(e) => setKeywordFilter(e.target.value)}
            style={{
              width: '100%',
              padding: '0.625rem 0.875rem',
              fontSize: '0.875rem',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              maxWidth: '400px'
            }}
          />
        </div>
      )}

      {/* Grant List - Table Format */}
      <div>
        {filteredGrants && filteredGrants.length > 0 ? (
          <div style={{ border: '1px solid #e5e7eb', borderRadius: '6px', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>ID</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Name</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Summary</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Timeline</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>URL</th>
                </tr>
              </thead>
              <tbody>
                {filteredGrants.map((grant, idx) => {
                  const displayTitle = getDisplayTitle(grant)
                  const summary = getSummary(grant)
                  const timeline = getTimeline(grant)
                  const timelineBadge = getTimelineBadge(grant)
                  return (
                    <tr 
                      key={grant.id} 
                      style={{ 
                        borderBottom: idx < filteredGrants.length - 1 ? '1px solid #f3f4f6' : 'none',
                        backgroundColor: idx % 2 === 0 ? '#ffffff' : '#fafafa'
                      }}
                    >
                      <td style={{ padding: '0.75rem', color: '#9ca3af', fontFamily: 'monospace', fontSize: '0.8125rem' }}>
                        {grant.id}
                      </td>
                      <td style={{ padding: '0.75rem', fontWeight: '500', color: '#111827' }}>
                        <div>
                          {displayTitle}
                          {grant.normalization && (
                            <span style={{ 
                              marginLeft: '0.5rem', 
                              fontSize: '0.625rem', 
                              color: '#6b7280',
                              backgroundColor: '#f3f4f6',
                              padding: '0.125rem 0.375rem',
                              borderRadius: '3px'
                            }}>
                              Curated
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '0.75rem', color: '#4b5563', lineHeight: '1.5', maxWidth: '300px' }}>
                        {summary ? (
                          <div style={{ 
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical'
                          }}>
                            {summary}
                          </div>
                        ) : (
                          <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>No summary</span>
                        )}
                      </td>
                      <td style={{ padding: '0.75rem', fontSize: '0.8125rem' }}>
                        {timelineBadge ? (
                          <span style={{ 
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            padding: '0.25rem 0.5rem',
                            backgroundColor: timelineBadge.color + '15',
                            color: timelineBadge.color,
                            borderRadius: '4px',
                            fontWeight: '500',
                            fontSize: '0.75rem'
                          }}>
                            <span>{timelineBadge.emoji}</span>
                            <span>{timelineBadge.label}</span>
                          </span>
                        ) : timeline ? (
                          <span style={{ color: '#6b7280', whiteSpace: 'nowrap' }}>{timeline}</span>
                        ) : (
                          <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>Not specified</span>
                        )}
                      </td>
                      <td style={{ padding: '0.75rem' }}>
                        {grant.source_url ? (
                          <a 
                            href={grant.source_url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            style={{ 
                              color: '#2563eb',
                              textDecoration: 'none',
                              fontSize: '0.8125rem',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              display: 'block',
                              maxWidth: '200px',
                              whiteSpace: 'nowrap'
                            }}
                            title={grant.source_url}
                          >
                            {grant.source_url}
                          </a>
                        ) : (
                          <span style={{ color: '#9ca3af', fontStyle: 'italic', fontSize: '0.8125rem' }}>No URL</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : grants && grants.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
            <p style={{ margin: 0, color: '#6b7280' }}>No grants in index. Add a grant URL to begin.</p>
          </div>
        ) : keywordFilter.trim() && filteredGrants.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
            <p style={{ margin: 0, color: '#6b7280' }}>No grants match "{keywordFilter}"</p>
          </div>
        ) : null}
      </div>

      {grants && grants.length > 0 && (
        <div style={{ marginTop: '1rem', fontSize: '0.75rem', color: '#9ca3af', textAlign: 'right' }}>
          {filteredGrants.length} of {grants.length} grants
        </div>
      )}
    </div>
  )
}

export default Grants
