import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import ContributeDataForm from '../components/ContributeDataForm'
import '../App.css'

function Grants() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [showForm, setShowForm] = useState(false)
  const [grantUrl, setGrantUrl] = useState('')
  const [keywordFilter, setKeywordFilter] = useState('')
  const [readinessFilter, setReadinessFilter] = useState(searchParams.get('readiness') || '') // 'Ready for Evaluation', 'Partial — Missing Signals', 'Low Confidence Grant', or ''
  const [expandedGrantId, setExpandedGrantId] = useState(null) // Track which grant row is expanded
  const [contributingGrantId, setContributingGrantId] = useState(null) // Track which grant is being contributed to
  
  // Update URL when readiness filter changes
  useEffect(() => {
    if (readinessFilter) {
      searchParams.set('readiness', readinessFilter)
    } else {
      searchParams.delete('readiness')
    }
    setSearchParams(searchParams, { replace: true })
  }, [readinessFilter, searchParams, setSearchParams])
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
        'active': 'Active',
        'closed': 'Closed',
        'rolling': 'Rolling',
        'unknown': 'Unknown'
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
      'active': { label: 'Active', color: '#10b981' },
      'closed': { label: 'Closed', color: '#ef4444' },
      'rolling': { label: 'Rolling', color: '#3b82f6' },
      'unknown': { label: 'Unknown', color: '#6b7280' }
    }
    return badges[status] || null
  }

  // Get bucket state icon (🟢🟡🔴)
  const getBucketIcon = (state) => {
    if (state === 'known') return '🟢'
    if (state === 'partial') return '🟡'
    if (state === 'unknown') return '🔴'
    return '⚪' // Default for null/undefined
  }

  // Get bucket tooltip text
  const getBucketTooltip = (bucketName, state, grant) => {
    if (!state) return `${bucketName}: Not evaluated`
    
    const explanations = {
      timeline_clarity: {
        known: grant.deadline ? `Timeline: ${grant.deadline}` : 'Timeline: Deadline and decision cycle known',
        partial: 'Timeline: Rolling or vague timing',
        unknown: 'Timeline: No timing information found'
      },
      winner_signal: {
        known: grant.recipient_patterns?.past_recipients 
          ? `Winner Signal: Past recipients found\n\n${grant.recipient_patterns.past_recipients.substring(0, 200)}${grant.recipient_patterns.past_recipients.length > 200 ? '...' : ''}`
          : 'Winner Signal: Past recipients found',
        partial: grant.recipient_patterns?.acceptance_rate
          ? `Winner Signal: Aggregate stats only\n\nAcceptance Rate: ${grant.recipient_patterns.acceptance_rate}`
          : 'Winner Signal: Aggregate stats only',
        unknown: 'Winner Signal: No public recipient data found'
      },
      mission_specificity: {
        known: 'Mission: Narrow domain with explicit priorities',
        partial: 'Mission: Broad mission with some specificity',
        unknown: 'Mission: Generic language without specific focus'
      },
      application_burden: {
        known: 'Application: Length and steps disclosed',
        partial: 'Application: Partial information available',
        unknown: 'Application: No application detail found'
      },
      award_structure_clarity: {
        known: 'Award: Amount and terms clear',
        partial: 'Award: Range or conditional amounts',
        unknown: 'Award: No award information found'
      }
    }
    
    return explanations[bucketName]?.[state] || `${bucketName}: ${state}`
  }

  // Filter grants by keyword and readiness score
  const filteredGrants = useMemo(() => {
    if (!grants) return []
    
    let filtered = grants
    
    // Filter by keyword
    if (keywordFilter.trim()) {
      const keyword = keywordFilter.toLowerCase()
      filtered = filtered.filter(grant => {
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
    }
    
    // Filter by decision readiness (new system)
    if (readinessFilter) {
      filtered = filtered.filter(grant => {
        // Use new decision_readiness field if available, otherwise fall back to old score
        if (grant.decision_readiness) {
          return grant.decision_readiness === readinessFilter
        }
        // Fallback for grants not yet migrated
        return false
      })
    }
    
    return filtered
  }, [grants, keywordFilter, readinessFilter])

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
    return (
      <div className="container" style={{ maxWidth: '900px', textAlign: 'center', padding: '3rem' }}>
        <div style={{ fontSize: '1.125rem', color: '#6b7280', marginBottom: '1rem' }}>Loading grants...</div>
        <div style={{ fontSize: '0.875rem', color: '#9ca3af' }}>Please wait while we fetch grant data from the database.</div>
      </div>
    )
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

      {/* Filters */}
      {grants && grants.length > 0 && (
        <div style={{ marginBottom: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Filter by keyword..."
            value={keywordFilter}
            onChange={(e) => setKeywordFilter(e.target.value)}
            style={{
              padding: '0.625rem 0.875rem',
              fontSize: '0.875rem',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              minWidth: '200px',
              flex: '1 1 200px'
            }}
          />
          <select
            value={readinessFilter}
            onChange={(e) => setReadinessFilter(e.target.value)}
            style={{
              padding: '0.625rem 0.875rem',
              fontSize: '0.875rem',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              backgroundColor: 'white',
              cursor: 'pointer'
            }}
          >
            <option value="">All Decision Readiness</option>
            <option value="Ready for Evaluation">Ready for Evaluation</option>
            <option value="Partial — Missing Signals">Partial — Missing Signals</option>
            <option value="Low Confidence Grant">Low Confidence Grant</option>
          </select>
          {readinessFilter && (
            <button
              onClick={() => setReadinessFilter('')}
              className="btn btn-secondary"
              style={{ fontSize: '0.75rem', padding: '0.5rem 0.75rem' }}
            >
              Clear Filter
            </button>
          )}
        </div>
      )}

      {/* Grant List - Table Format */}
      <div>
        {filteredGrants && filteredGrants.length > 0 ? (
          <div style={{ border: '1px solid #e5e7eb', borderRadius: '6px', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase', width: '40px' }}></th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Grant Name</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Decision Readiness</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Indicators</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Scope</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Timeline</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '500', fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>URL</th>
                </tr>
              </thead>
              <tbody>
                {filteredGrants.map((grant, idx) => {
                  const displayTitle = getDisplayTitle(grant)
                  const timeline = getTimeline(grant)
                  const timelineBadge = getTimelineBadge(grant)
                  const isExpanded = expandedGrantId === grant.id
                  
                  // Get decision readiness label
                  const decisionReadiness = grant.decision_readiness || (grant.evaluation_complete === false ? 'Evaluating...' : null)
                  
                  // Get bucket states
                  const buckets = {
                    timeline_clarity: grant.timeline_clarity,
                    winner_signal: grant.winner_signal,
                    mission_specificity: grant.mission_specificity,
                    application_burden: grant.application_burden,
                    award_structure_clarity: grant.award_structure_clarity
                  }
                  
                  return (
                    <>
                      <tr 
                        key={grant.id} 
                        style={{ 
                          borderBottom: '1px solid #f3f4f6',
                          backgroundColor: idx % 2 === 0 ? '#ffffff' : '#fafafa'
                        }}
                      >
                        <td 
                          style={{ padding: '0.75rem', textAlign: 'center', width: '40px', cursor: 'pointer' }}
                          onClick={(e) => {
                            e.stopPropagation()
                            if (isExpanded) {
                              setExpandedGrantId(null)
                            } else {
                              setExpandedGrantId(grant.id)
                            }
                          }}
                        >
                          <span style={{ 
                            display: 'inline-block',
                            transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s',
                            fontSize: '0.75rem',
                            color: '#6b7280'
                          }}>
                            ▶
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem', fontWeight: '500', color: '#111827' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span>{displayTitle}</span>
                            {grant.source_verified && (
                              <span style={{ 
                                fontSize: '0.625rem', 
                                color: '#059669',
                                backgroundColor: '#d1fae5',
                                padding: '0.125rem 0.375rem',
                                borderRadius: '3px',
                                fontWeight: '500'
                              }}>
                                Source Verified
                              </span>
                            )}
                            {!grant.evaluation_complete && (
                              <span style={{ 
                                fontSize: '0.625rem', 
                                color: '#6b7280',
                                backgroundColor: '#f3f4f6',
                                padding: '0.125rem 0.375rem',
                                borderRadius: '3px',
                                fontStyle: 'italic'
                              }}>
                                Evaluating...
                              </span>
                            )}
                          </div>
                        </td>
                        <td style={{ padding: '0.75rem', fontSize: '0.8125rem' }}>
                          {decisionReadiness ? (
                            <span style={{
                              fontSize: '0.75rem',
                              padding: '0.25rem 0.5rem',
                              borderRadius: '4px',
                              fontWeight: '500',
                              backgroundColor: decisionReadiness === 'Ready for Evaluation' ? '#d1fae5' : 
                                            decisionReadiness === 'Partial — Missing Signals' ? '#fef3c7' : '#fee2e2',
                              color: decisionReadiness === 'Ready for Evaluation' ? '#065f46' : 
                                     decisionReadiness === 'Partial — Missing Signals' ? '#92400e' : '#991b1b'
                            }}>
                              {decisionReadiness}
                            </span>
                          ) : (
                            <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>Not evaluated</span>
                          )}
                        </td>
                        <td style={{ padding: '0.75rem' }}>
                          <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                            {Object.entries(buckets).map(([bucketName, state]) => (
                              <span
                                key={bucketName}
                                title={getBucketTooltip(bucketName, state, grant)}
                                style={{
                                  fontSize: '0.875rem',
                                  cursor: 'help',
                                  display: 'inline-block',
                                  lineHeight: '1'
                                }}
                              >
                                {getBucketIcon(state)}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td style={{ padding: '0.75rem', fontSize: '0.8125rem' }}>
                          {grant.scope ? (
                            <span style={{ color: '#6b7280' }}>{grant.scope}</span>
                          ) : (
                            <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>Unclear</span>
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
                              onClick={(e) => e.stopPropagation()}
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
                      {/* Expanded row content */}
                      {isExpanded && (
                        <tr key={`${grant.id}-expanded`} style={{ backgroundColor: '#fafafa', borderBottom: '1px solid #f3f4f6' }}>
                          <td colSpan="7" style={{ padding: '1rem', borderTop: '1px solid #e5e7eb' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                              {/* Left column: Summary and Grant Data */}
                              <div>
                                <h4 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '0.875rem', fontWeight: '600', color: '#374151' }}>Summary</h4>
                                <p style={{ margin: 0, fontSize: '0.8125rem', color: '#6b7280', lineHeight: '1.6' }}>
                                  {getSummary(grant) || <span style={{ fontStyle: 'italic', color: '#9ca3af' }}>No summary available</span>}
                                </p>
                                
                                {grant.status_of_knowledge && (
                                  <div style={{ marginTop: '1rem' }}>
                                    <h4 style={{ marginTop: 0, marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: '600', color: '#374151' }}>Status of Knowledge</h4>
                                    <span style={{
                                      fontSize: '0.75rem',
                                      padding: '0.25rem 0.5rem',
                                      borderRadius: '4px',
                                      fontWeight: '500',
                                      backgroundColor: grant.status_of_knowledge === 'Well-Specified' ? '#dbeafe' : 
                                                      grant.status_of_knowledge === 'Partially Opaque' ? '#fef3c7' : '#fee2e2',
                                      color: grant.status_of_knowledge === 'Well-Specified' ? '#1e40af' : 
                                             grant.status_of_knowledge === 'Partially Opaque' ? '#92400e' : '#991b1b'
                                    }}>
                                      {grant.status_of_knowledge}
                                    </span>
                                  </div>
                                )}

                                {/* Grant Data Details */}
                                <div style={{ marginTop: '1.5rem' }}>
                                  <h4 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '0.875rem', fontWeight: '600', color: '#374151' }}>Grant Details</h4>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                    {/* Mission Statement */}
                                    {grant.mission && (
                                      <div style={{ 
                                        padding: '0.75rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '4px',
                                        border: '1px solid #e5e7eb',
                                        fontSize: '0.8125rem'
                                      }}>
                                        <strong style={{ color: '#374151', display: 'block', marginBottom: '0.5rem' }}>Mission:</strong>
                                        <div style={{ color: '#6b7280', lineHeight: '1.5' }}>{grant.mission}</div>
                                      </div>
                                    )}

                                    {/* Award Details */}
                                    {(grant.award_amount || grant.award_structure) && (
                                      <div style={{ 
                                        padding: '0.75rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '4px',
                                        border: '1px solid #e5e7eb',
                                        fontSize: '0.8125rem'
                                      }}>
                                        <strong style={{ color: '#374151', display: 'block', marginBottom: '0.5rem' }}>Award:</strong>
                                        <div style={{ color: '#6b7280', lineHeight: '1.5' }}>
                                          {grant.award_amount && <div style={{ marginBottom: '0.25rem' }}><strong>Amount:</strong> {grant.award_amount}</div>}
                                          {grant.award_structure && <div><strong>Structure:</strong> {grant.award_structure}</div>}
                                        </div>
                                      </div>
                                    )}

                                    {/* Application Requirements */}
                                    {grant.application_requirements && (
                                      <div style={{ 
                                        padding: '0.75rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '4px',
                                        border: '1px solid #e5e7eb',
                                        fontSize: '0.8125rem'
                                      }}>
                                        <strong style={{ color: '#374151', display: 'block', marginBottom: '0.5rem' }}>Application Requirements:</strong>
                                        <div style={{ color: '#6b7280', lineHeight: '1.5' }}>
                                          {Array.isArray(grant.application_requirements) ? (
                                            <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                                              {grant.application_requirements.map((req, idx) => (
                                                <li key={idx} style={{ marginBottom: '0.25rem' }}>{req}</li>
                                              ))}
                                            </ul>
                                          ) : (
                                            <div>{grant.application_requirements}</div>
                                          )}
                                        </div>
                                      </div>
                                    )}

                                    {/* Past Recipients */}
                                    {grant.recipient_patterns?.past_recipients && (
                                      <div style={{ 
                                        padding: '0.75rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '4px',
                                        border: '1px solid #e5e7eb',
                                        fontSize: '0.8125rem'
                                      }}>
                                        <strong style={{ color: '#374151', display: 'block', marginBottom: '0.5rem' }}>Past Recipients:</strong>
                                        <div style={{ color: '#6b7280', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
                                          {grant.recipient_patterns.past_recipients}
                                        </div>
                                      </div>
                                    )}

                                    {/* Acceptance Rate */}
                                    {grant.recipient_patterns?.acceptance_rate && (
                                      <div style={{ 
                                        padding: '0.75rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '4px',
                                        border: '1px solid #e5e7eb',
                                        fontSize: '0.8125rem'
                                      }}>
                                        <strong style={{ color: '#374151', display: 'block', marginBottom: '0.5rem' }}>Acceptance Rate:</strong>
                                        <div style={{ color: '#6b7280', lineHeight: '1.5' }}>
                                          {grant.recipient_patterns.acceptance_rate}
                                        </div>
                                      </div>
                                    )}

                                    {/* Eligibility */}
                                    {grant.eligibility && (
                                      <div style={{ 
                                        padding: '0.75rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '4px',
                                        border: '1px solid #e5e7eb',
                                        fontSize: '0.8125rem'
                                      }}>
                                        <strong style={{ color: '#374151', display: 'block', marginBottom: '0.5rem' }}>Eligibility:</strong>
                                        <div style={{ color: '#6b7280', lineHeight: '1.5' }}>{grant.eligibility}</div>
                                      </div>
                                    )}

                                    {/* Preferred Applicants */}
                                    {grant.preferred_applicants && (
                                      <div style={{ 
                                        padding: '0.75rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '4px',
                                        border: '1px solid #e5e7eb',
                                        fontSize: '0.8125rem'
                                      }}>
                                        <strong style={{ color: '#374151', display: 'block', marginBottom: '0.5rem' }}>Preferred Applicants:</strong>
                                        <div style={{ color: '#6b7280', lineHeight: '1.5' }}>{grant.preferred_applicants}</div>
                                      </div>
                                    )}
                                  </div>
                                  
                                  {/* Contribute Data Button */}
                                  <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #e5e7eb' }}>
                                    <button
                                      onClick={() => setContributingGrantId(grant.id)}
                                      className="btn"
                                      style={{
                                        fontSize: '0.875rem',
                                        padding: '0.5rem 1rem',
                                        backgroundColor: '#4b5563',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        fontWeight: '500'
                                      }}
                                    >
                                      Contribute Grant Data
                                    </button>
                                    <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.75rem', color: '#6b7280' }}>
                                      Help improve this grant's information by contributing missing data
                                    </p>
                                  </div>
                                </div>
                              </div>
                              
                              {/* Right column: Bucket Details */}
                              <div>
                                <h4 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '0.875rem', fontWeight: '600', color: '#374151' }}>Decision Readiness Details</h4>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                  {Object.entries(buckets).map(([bucketName, state]) => {
                                    const bucketLabels = {
                                      timeline_clarity: 'Timeline',
                                      winner_signal: 'Winner Signal',
                                      mission_specificity: 'Mission',
                                      application_burden: 'Application',
                                      award_structure_clarity: 'Award'
                                    }
                                    const label = bucketLabels[bucketName] || bucketName
                                    const explanation = getBucketTooltip(bucketName, state, grant)
                                    
                                    // Show actual data for winner_signal when available
                                    const showActualData = bucketName === 'winner_signal' && state === 'known' && grant.recipient_patterns?.past_recipients
                                    const showAcceptanceRate = bucketName === 'winner_signal' && state === 'partial' && grant.recipient_patterns?.acceptance_rate
                                    
                                    return (
                                      <div key={bucketName} style={{ 
                                        padding: '0.5rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '4px',
                                        border: '1px solid #e5e7eb',
                                        fontSize: '0.8125rem'
                                      }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                                          <span style={{ fontSize: '0.875rem' }}>{getBucketIcon(state)}</span>
                                          <strong style={{ color: '#374151' }}>{label}:</strong>
                                        </div>
                                        <div style={{ color: '#6b7280', fontSize: '0.75rem', lineHeight: '1.5', paddingLeft: '1.5rem' }}>
                                          {showActualData ? (
                                            <div>
                                              <div style={{ marginBottom: '0.5rem', fontWeight: '500' }}>Past Recipients Found:</div>
                                              <div style={{ whiteSpace: 'pre-wrap', backgroundColor: '#f9fafb', padding: '0.5rem', borderRadius: '4px', fontSize: '0.8125rem' }}>
                                                {grant.recipient_patterns.past_recipients}
                                              </div>
                                            </div>
                                          ) : showAcceptanceRate ? (
                                            <div>
                                              <div style={{ marginBottom: '0.5rem', fontWeight: '500' }}>Acceptance Rate:</div>
                                              <div style={{ backgroundColor: '#f9fafb', padding: '0.5rem', borderRadius: '4px', fontSize: '0.8125rem' }}>
                                                {grant.recipient_patterns.acceptance_rate}
                                              </div>
                                            </div>
                                          ) : (
                                            explanation
                                          )}
                                        </div>
                                      </div>
                                    )
                                  })}
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : !isLoading && grants && grants.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
            <p style={{ margin: 0, color: '#6b7280' }}>No grants in index. Add a grant URL to begin.</p>
          </div>
        ) : !isLoading && keywordFilter.trim() && filteredGrants.length === 0 ? (
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

      {/* Contribute Data Form Modal */}
      {contributingGrantId && grants && (() => {
        const grant = grants.find(g => g.id === contributingGrantId)
        if (!grant) return null
        
        // Determine missing fields
        const missingFields = []
        if (!grant.award_amount && !grant.award_structure) missingFields.push('award_amount')
        if (!grant.deadline && !grant.decision_date) missingFields.push('deadline')
        if (!grant.mission) missingFields.push('mission')
        if (!grant.eligibility) missingFields.push('eligibility')
        if (!grant.preferred_applicants) missingFields.push('preferred_applicants')
        if (!grant.application_requirements || (Array.isArray(grant.application_requirements) && grant.application_requirements.length === 0)) {
          missingFields.push('application_requirements')
        }
        if (!grant.recipient_patterns?.past_recipients) missingFields.push('past_recipients')
        if (!grant.recipient_patterns?.acceptance_rate) missingFields.push('acceptance_rate')
        
        return (
          <ContributeDataForm
            key={grant.id}
            grantId={grant.id}
            grantName={grant.name || getDisplayTitle(grant)}
            grantUrl={grant.source_url}
            missingFields={missingFields.length > 0 ? missingFields : undefined}
            onClose={() => {
              setContributingGrantId(null)
              queryClient.invalidateQueries(['grants'])
            }}
            onSuccess={() => {
              setContributingGrantId(null)
              queryClient.invalidateQueries(['grants'])
            }}
          />
        )
      })()}
    </div>
  )
}

export default Grants
