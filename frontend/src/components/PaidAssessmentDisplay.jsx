import { useState } from 'react'
import ContributeDataForm from './ContributeDataForm'

/**
 * Paid Assessment Display Component
 * 
 * Displays personalized fit assessment (paid tier).
 * Shows: mission alignment, profile match, funding fit, effort-reward, success probability,
 * decision gates, strategic recommendations.
 */

function PaidAssessmentDisplay({ evaluation, projectData, grantData }) {
  const [showContributeForm, setShowContributeForm] = useState(false)
  const paidTier = evaluation.reasoning?._paid_tier || {}
  const isLegacy = evaluation.is_legacy || false
  
  // Extract grant data - prefer grant_snapshot_json (in-memory grants), fallback to grantData prop (indexed grants)
  const grantSnapshot = evaluation.grant_snapshot_json || grantData || {}
  
  // Get missing grant data from readiness score
  const readinessData = evaluation.reasoning?._readiness || {}
  const missingGrantData = readinessData.missing_data || []

  // Extract paid tier data
  const missionDetails = paidTier.mission_alignment_details || {}
  const profileDetails = paidTier.profile_match_details || {}
  const fundingFit = paidTier.funding_fit || {}
  const effortReward = paidTier.effort_reward || {}
  const successProb = paidTier.success_probability || {}

  // Helper function to create a summary from long text (first sentence or first 120 chars)
  // Always ends at word boundary with "..." to look professional
  const summarizeText = (text) => {
    if (!text || typeof text !== 'string') return text || ''
    
    // Try to find first sentence (ending with period, exclamation, or question mark)
    const sentenceMatch = text.match(/^[^.!?]+[.!?]/)
    if (sentenceMatch && sentenceMatch[0].length <= 150) {
      return sentenceMatch[0].trim()
    }
    
    // If first sentence is too long or no sentence found, truncate at word boundary
    const maxLength = 120
    if (text.length <= maxLength) {
      return text
    }
    
    // Truncate to maxLength, then find last space before that point
    let truncated = text.substring(0, maxLength)
    const lastSpace = truncated.lastIndexOf(' ')
    
    // If we found a space, cut there; otherwise cut at maxLength
    if (lastSpace > maxLength * 0.7) {
      // Only use space if it's not too early (at least 70% of maxLength)
      truncated = truncated.substring(0, lastSpace)
    }
    
    // Ensure it ends with "..." and doesn't have trailing punctuation that looks odd
    truncated = truncated.trim()
    // Remove trailing punctuation that might look odd before "..."
    truncated = truncated.replace(/[,;:]\s*$/, '')
    
    return truncated + '...'
  }

  // Scores
  const missionScore = evaluation.mission_alignment ?? 0
  const profileScore = profileDetails.score
  const compositeScore = evaluation.composite_score

  // Format funding need amount
  const formatFundingNeed = () => {
    if (!projectData) return null
    if (projectData.funding_need_amount && projectData.funding_need_currency) {
      const amount = projectData.funding_need_amount / 100 // Convert from cents
      return `${amount.toLocaleString()} ${projectData.funding_need_currency}`
    }
    return projectData.funding_need || null
  }

  // Recommendation colors - muted psychology-based palette
  const getRecommendationColor = (rec) => {
    switch (rec) {
      case 'APPLY': return '#059669' // muted emerald-600
      case 'CONDITIONAL': return '#d97706' // muted amber-600
      case 'PASS': return '#dc2626' // muted red-600
      default: return '#6b7280' // muted gray-500
    }
  }

  // Confidence badge (without source indicator) - muted colors
  const ConfidenceBadge = ({ confidence }) => {
    if (!confidence || confidence === 'unknown') return null
    
    const colors = {
      high: { bg: '#d1fae5', text: '#059669', icon: '' }, // muted emerald
      medium: { bg: '#fef3c7', text: '#d97706', icon: '' }, // muted amber
      low: { bg: '#fee2e2', text: '#dc2626', icon: '' } // muted red
    }
    
    const color = colors[confidence] || colors.medium
    
    return (
      <span style={{
        marginLeft: '0.5rem',
        padding: '0.15rem 0.4rem',
        backgroundColor: color.bg,
        color: color.text,
        borderRadius: '3px',
        fontSize: '0.75rem',
        fontWeight: 'bold'
      }}>
        {confidence.toUpperCase()}
      </span>
    )
  }

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }}>
      {isLegacy && (
        <div style={{
          padding: '0.5rem',
          backgroundColor: '#fef3c7', // muted amber-100
          borderLeft: '4px solid #d97706', // muted amber-600
          marginBottom: '1rem',
          borderRadius: '4px',
          color: '#92400e' // muted amber-800
        }}>
          <strong>Legacy Evaluation</strong> - This assessment was created with the previous scoring system.
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1.5rem' }}>
        <div>
          <h3>Personalized Fit Assessment</h3>
          <p style={{ color: '#6c757d', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Evaluation #{evaluation.id} • {new Date(evaluation.created_at).toLocaleDateString()}
          </p>
        </div>
        <span
          style={{
            padding: '0.5rem 1rem',
            borderRadius: '4px',
            backgroundColor: getRecommendationColor(evaluation.recommendation),
            color: 'white',
            fontWeight: 'bold',
          }}
        >
          {evaluation.recommendation}
        </span>
      </div>

      {/* Grant Evaluated - Prominently Displayed */}
      <div style={{ 
        marginBottom: '2rem', 
        padding: '1.5rem', 
        backgroundColor: '#f0f9ff', 
        borderRadius: '4px', 
        border: '1px solid #bae6fd',
        boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)'
      }}>
        <h4 style={{ marginTop: 0, marginBottom: '1rem', color: '#111827', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.25rem' }}>📋</span>
          Grant Evaluated
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
          {(evaluation.grant_name || grantSnapshot.name) && (
            <div style={{ gridColumn: 'span 2' }}>
              <div style={{ fontSize: '0.85rem', color: '#0369a1', marginBottom: '0.25rem', fontWeight: '600' }}>Grant Name</div>
              <div style={{ fontSize: '1.1rem', fontWeight: '600', color: '#111827' }}>{evaluation.grant_name || grantSnapshot.name}</div>
            </div>
          )}
          {grantSnapshot.description && (
            <div style={{ gridColumn: 'span 2' }}>
              <div style={{ fontSize: '0.85rem', color: '#0369a1', marginBottom: '0.25rem', fontWeight: '600' }}>Description</div>
              <div style={{ fontSize: '0.95rem', color: '#374151', lineHeight: '1.5' }}>{grantSnapshot.description}</div>
            </div>
          )}
          {grantSnapshot.mission && (
            <div style={{ gridColumn: 'span 2' }}>
              <div style={{ fontSize: '0.85rem', color: '#0369a1', marginBottom: '0.25rem', fontWeight: '600' }}>Mission</div>
              <div style={{ fontSize: '0.95rem', color: '#374151', lineHeight: '1.5', padding: '0.75rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb' }}>
                {grantSnapshot.mission}
              </div>
            </div>
          )}
          {grantSnapshot.deadline && (
            <div>
              <div style={{ fontSize: '0.85rem', color: '#0369a1', marginBottom: '0.25rem', fontWeight: '600' }}>Deadline</div>
              <div style={{ fontSize: '0.95rem', fontWeight: '500', color: '#374151' }}>{grantSnapshot.deadline}</div>
            </div>
          )}
          {grantSnapshot.award_amount && (
            <div>
              <div style={{ fontSize: '0.85rem', color: '#0369a1', marginBottom: '0.25rem', fontWeight: '600' }}>Award Amount</div>
              <div style={{ fontSize: '0.95rem', fontWeight: '500', color: '#374151' }}>{grantSnapshot.award_amount}</div>
            </div>
          )}
          {evaluation.grant_url && (
            <div style={{ gridColumn: 'span 2' }}>
              <div style={{ fontSize: '0.85rem', color: '#0369a1', marginBottom: '0.25rem', fontWeight: '600' }}>Source URL</div>
              <a 
                href={evaluation.grant_url} 
                target="_blank" 
                rel="noopener noreferrer"
                style={{ fontSize: '0.85rem', color: '#3b82f6', textDecoration: 'underline', wordBreak: 'break-all' }}
              >
                {evaluation.grant_url}
              </a>
            </div>
          )}
        </div>
        <div style={{ 
          marginTop: '1rem', 
          padding: '0.75rem', 
          backgroundColor: '#ffffff', 
          borderRadius: '4px',
          border: '1px solid #bae6fd',
          fontSize: '0.85rem',
          color: '#0369a1'
        }}>
          <strong>✓ Verified:</strong> This evaluation was performed using the grant information shown above. The system compared your project against this grant's mission, requirements, and priorities.
        </div>
      </div>

      {/* Your Project Context - Prominently Displayed */}
      {projectData && (
        <div style={{ 
          marginBottom: '2rem', 
          padding: '1.5rem', 
          backgroundColor: '#ffffff', 
          borderRadius: '4px', 
          border: '1px solid #e5e7eb',
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)'
        }}>
          <h4 style={{ marginTop: 0, marginBottom: '1rem', color: '#111827', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.25rem' }}>🎯</span>
            Your Project
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
            {projectData.name && (
              <div>
                <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.25rem', fontWeight: '500' }}>Project Name</div>
                <div style={{ fontSize: '1.1rem', fontWeight: '600', color: '#111827' }}>{projectData.name}</div>
              </div>
            )}
            {projectData.description && (
              <div style={{ gridColumn: 'span 2' }}>
                <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.25rem', fontWeight: '500' }}>Description</div>
                <div style={{ fontSize: '0.95rem', color: '#495057', lineHeight: '1.5' }}>{projectData.description}</div>
              </div>
            )}
            {projectData.stage && (
              <div>
                <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.25rem', fontWeight: '500' }}>Stage</div>
                <div style={{ fontSize: '0.95rem', fontWeight: '500', color: '#374151' }}>{projectData.stage}</div>
              </div>
            )}
            {projectData.urgency && (
              <div>
                <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.25rem', fontWeight: '500' }}>Urgency</div>
                <div style={{ 
                  fontSize: '0.95rem', 
                  fontWeight: '500', 
                  color: projectData.urgency === 'critical' ? '#dc2626' : projectData.urgency === 'high' ? '#d97706' : '#059669',
                  textTransform: 'capitalize'
                }}>
                  {projectData.urgency}
                </div>
              </div>
            )}
            {formatFundingNeed() && (
              <div>
                <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.25rem', fontWeight: '500' }}>Funding Need</div>
                <div style={{ fontSize: '1rem', fontWeight: '600', color: '#111827' }}>{formatFundingNeed()}</div>
              </div>
            )}
            {projectData.organization_country && (
              <div>
                <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.25rem', fontWeight: '500' }}>Country</div>
                <div style={{ fontSize: '0.95rem', color: '#495057' }}>{projectData.organization_country}</div>
              </div>
            )}
            {projectData.organization_type && (
              <div>
                <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.25rem', fontWeight: '500' }}>Organization Type</div>
                <div style={{ fontSize: '0.95rem', color: '#495057' }}>{projectData.organization_type}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Strategic Fit Scores */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h4 style={{ marginBottom: '1rem' }}>Strategic Fit</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
          {/* Mission Alignment */}
          <div style={{ padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <div>
              <strong>Mission Alignment</strong>
                <div style={{ fontSize: '0.75rem', color: '#6c757d', marginTop: '0.25rem' }}>
                  How well your project matches the grant's mission
                </div>
              </div>
              <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{missionScore}/10</span>
            </div>
            <ConfidenceBadge confidence={missionScore === 0 ? 'low' : missionDetails.confidence} />
            <div style={{ marginTop: '0.5rem', height: '8px', backgroundColor: '#e5e7eb', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ width: `${(missionScore / 10) * 100}%`, height: '100%', backgroundColor: missionScore >= 7 ? '#059669' : missionScore >= 4 ? '#3b82f6' : '#d97706' }}></div>
            </div>
            {/* Why this score - show gaps or strong matches */}
            {missionScore === 0 && (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#fee2e2', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid #fecaca' }}>
                <strong style={{ color: '#dc2626' }}>Why 0/10:</strong>
                <div style={{ marginTop: '0.25rem', color: '#991b1b', wordWrap: 'break-word', overflowWrap: 'break-word', whiteSpace: 'normal' }}>
                  {missionDetails.gaps && missionDetails.gaps.length > 0 ? (
                    <div>
                      No alignment found due to: {missionDetails.gaps[0] ? summarizeText(missionDetails.gaps[0]) : 'Unknown alignment issue'}
                      {missionDetails.gaps.length > 1 && ` (+${missionDetails.gaps.length - 1} more)`}
                    </div>
                  ) : (
                    <div style={{ marginTop: '0.25rem' }}>No alignment found between your project and the grant's mission priorities.</div>
                  )}
                </div>
              </div>
            )}
            {missionScore > 0 && missionScore < 4 && missionDetails.gaps && missionDetails.gaps.length > 0 && (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#f9fafb', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid #e5e7eb' }}>
                <strong style={{ color: '#374151' }}>Why {missionScore}/10:</strong>
                <div style={{ marginTop: '0.25rem', color: '#6b7280', wordWrap: 'break-word', overflowWrap: 'break-word', whiteSpace: 'normal' }}>
                  Weak alignment due to: {missionDetails.gaps[0] ? summarizeText(missionDetails.gaps[0]) : 'Unknown alignment issue'}
                  {missionDetails.gaps.length > 1 && ` (+${missionDetails.gaps.length - 1} more)`}
                </div>
              </div>
            )}
            {missionScore >= 4 && missionDetails.strong_matches && missionDetails.strong_matches.length > 0 && (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#f9fafb', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid #e5e7eb' }}>
                <strong style={{ color: '#374151' }}>Why {missionScore}/10:</strong>
                <div style={{ marginTop: '0.25rem', color: '#6b7280', wordWrap: 'break-word', overflowWrap: 'break-word', whiteSpace: 'normal' }}>
                  {missionDetails.strong_matches[0]}
                  {missionDetails.strong_matches.length > 1 && ` (+${missionDetails.strong_matches.length - 1} more match${missionDetails.strong_matches.length - 1 > 1 ? 'es' : ''})`}
                </div>
              </div>
            )}
          </div>

          {/* Profile Match */}
          <div style={{ padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <strong>Profile Match</strong>
              {profileScore !== null ? (
                <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{profileScore}/10</span>
              ) : (
                <span style={{ fontSize: '0.9rem', color: '#6c757d' }}>Insufficient Data</span>
              )}
            </div>
              {profileDetails.reason === 'INSUFFICIENT_DATA' && (
              <div style={{ fontSize: '0.85rem', color: '#d97706', marginBottom: '0.5rem', padding: '0.5rem', backgroundColor: '#fef3c7', borderRadius: '4px' }}>
                Warning: Only {profileDetails.recipient_count || 0} recipients available (need 5+)
              </div>
            )}
            {profileScore !== null && (
              <>
                <ConfidenceBadge confidence={profileDetails.confidence} />
                <div style={{ marginTop: '0.5rem', height: '8px', backgroundColor: '#e5e7eb', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{ width: `${(profileScore / 10) * 100}%`, height: '100%', backgroundColor: profileScore >= 7 ? '#059669' : profileScore >= 4 ? '#3b82f6' : '#d97706' }}></div>
                </div>
              </>
            )}
            {/* Show insights even with limited data */}
            {profileDetails.reason === 'INSUFFICIENT_DATA' && profileDetails.recipient_count > 0 && (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#f9fafb', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid #e5e7eb' }}>
                <strong style={{ color: '#374151' }}>What {profileDetails.recipient_count} recipient{profileDetails.recipient_count > 1 ? 's' : ''} tell us:</strong>
                {profileDetails.similarities && profileDetails.similarities.length > 0 && (
                  <div style={{ marginTop: '0.25rem', color: '#6b7280' }}>
                    {profileDetails.similarities[0]}
                    {profileDetails.similarities.length > 1 && ` (+${profileDetails.similarities.length - 1} more)`}
                  </div>
                )}
                {profileDetails.differences && profileDetails.differences.length > 0 && (
                  <div style={{ marginTop: '0.25rem', color: '#6b7280' }}>
                    Note: {profileDetails.differences[0]}
                    {profileDetails.differences.length > 1 && ` (+${profileDetails.differences.length - 1} more)`}
                  </div>
                )}
                {(!profileDetails.similarities || profileDetails.similarities.length === 0) && (!profileDetails.differences || profileDetails.differences.length === 0) && (
                  <div style={{ marginTop: '0.25rem', color: '#6c757d', fontStyle: 'italic' }}>
                    Limited data available - assessment confidence reduced
                  </div>
                )}
              </div>
            )}
            {/* Show score explanation when score exists */}
            {profileScore !== null && (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#f9fafb', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid #e5e7eb' }}>
                <strong style={{ color: '#374151' }}>Why {profileScore}/10:</strong>
                {profileDetails.similarities && profileDetails.similarities.length > 0 && (
                  <div style={{ marginTop: '0.25rem', color: '#6b7280' }}>
                    Matches: {profileDetails.similarities[0]}
                    {profileDetails.similarities.length > 1 && ` (+${profileDetails.similarities.length - 1} more)`}
                  </div>
                )}
                {profileDetails.differences && profileDetails.differences.length > 0 && (
                  <div style={{ marginTop: '0.25rem', color: '#6b7280' }}>
                    Differences: {profileDetails.differences[0]}
                    {profileDetails.differences.length > 1 && ` (+${profileDetails.differences.length - 1} more)`}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Funding Fit */}
          <div style={{ padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <strong>Funding Fit</strong>
              <span style={{
                padding: '0.25rem 0.5rem',
                borderRadius: '4px',
                backgroundColor: '#f3f4f6',
                color: '#374151',
                fontSize: '0.85rem',
                fontWeight: 'bold'
              }}>
                {fundingFit.fit || 'UNCERTAIN'}
              </span>
            </div>
            {fundingFit.severity && (
              <div style={{ 
                fontSize: '0.85rem', 
                color: fundingFit.severity === 'CRITICAL' ? '#dc2626' : fundingFit.severity === 'HIGH' ? '#dc2626' : '#d97706', 
                marginBottom: '0.25rem',
                padding: '0.375rem 0.5rem',
                backgroundColor: fundingFit.severity === 'CRITICAL' ? '#fee2e2' : fundingFit.severity === 'HIGH' ? '#fee2e2' : '#fef3c7',
                borderRadius: '4px',
                display: 'inline-block'
              }}>
                {fundingFit.severity === 'CRITICAL' && 'CRITICAL: '}
                Severity: {fundingFit.severity}
              </div>
            )}
            {/* Explain why it's UNCERTAIN and MODERATE */}
            {fundingFit.fit === 'UNCERTAIN' && fundingFit.severity && (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#f9fafb', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid #e5e7eb' }}>
                <strong style={{ color: '#374151' }}>Why UNCERTAIN + {fundingFit.severity}:</strong>
                {fundingFit.reasoning && (
                  <div style={{ marginTop: '0.25rem', color: '#6b7280' }}>
                    {fundingFit.reasoning.length > 150 ? `${fundingFit.reasoning.substring(0, 150)}...` : fundingFit.reasoning}
                  </div>
                )}
                {!fundingFit.reasoning && (
                  <div style={{ marginTop: '0.25rem', color: '#6c757d', fontStyle: 'italic' }}>
                    Fit status is uncertain due to insufficient data, but severity is {fundingFit.severity.toLowerCase()} based on available information.
                  </div>
                )}
              </div>
            )}
            {/* Explain other fit statuses */}
            {fundingFit.fit !== 'UNCERTAIN' && fundingFit.reasoning && (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#f9fafb', borderRadius: '4px', fontSize: '0.8rem', border: '1px solid #e5e7eb' }}>
                <strong style={{ color: '#374151' }}>Why {fundingFit.fit}:</strong>
                <div style={{ marginTop: '0.25rem', color: '#6b7280' }}>
                  {fundingFit.reasoning.length > 150 ? `${fundingFit.reasoning.substring(0, 150)}...` : fundingFit.reasoning}
                </div>
                {fundingFit.severity && (
                  <div style={{ 
                    marginTop: '0.25rem', 
                    fontSize: '0.75rem', 
                    color: fundingFit.severity === 'CRITICAL' ? '#dc2626' : '#d97706',
                    padding: '0.25rem 0.5rem',
                    backgroundColor: fundingFit.severity === 'CRITICAL' ? '#fee2e2' : '#fef3c7',
                    borderRadius: '4px',
                    display: 'inline-block'
                  }}>
                    Severity: {fundingFit.severity}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Composite Score */}
          <div style={{ padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <div>
              <strong>Composite Score</strong>
                <div style={{ fontSize: '0.75rem', color: '#6c757d', marginTop: '0.25rem' }}>
                  Overall fit assessment combining all factors
                </div>
              </div>
              <span style={{ 
                fontSize: '1.5rem', 
                fontWeight: 'bold', 
                color: compositeScore >= 7 ? '#059669' : compositeScore >= 4 ? '#3b82f6' : '#d97706'
              }}>
                {compositeScore}/10
              </span>
            </div>
            
            {/* Score Breakdown */}
            <div style={{ 
              marginTop: '0.75rem', 
              padding: '0.75rem', 
              backgroundColor: '#f9fafb', 
              borderRadius: '4px',
              fontSize: '0.85rem',
              border: '1px solid #e5e7eb'
            }}>
              <strong style={{ color: '#374151', marginBottom: '0.5rem', display: 'block' }}>How This Score Is Calculated:</strong>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <div>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>Mission Alignment</div>
                  <div style={{ fontWeight: '600', color: '#374151' }}>{missionScore}/10 <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>(30% weight)</span></div>
                </div>
                <div>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>Profile Match</div>
                  <div style={{ fontWeight: '600', color: '#374151' }}>
                    {profileScore !== null ? `${profileScore}/10` : 'N/A'} <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>(25% weight)</span>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>Funding Fit</div>
                  <div style={{ fontWeight: '600', color: '#374151' }}>
                    {fundingFit.fit === 'ALIGNED' ? '10/10' : fundingFit.fit === 'PARTIAL' ? '6/10' : fundingFit.fit === 'INSUFFICIENT' ? '2/10' : '2/10'} <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>(25% weight)</span>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>Effort-Reward</div>
                  <div style={{ fontWeight: '600', color: '#374151' }}>
                    {effortReward.assessment === 'WORTH_IT' ? '10/10' : effortReward.assessment === 'MAYBE' ? '6/10' : '2/10'} <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>(20% weight)</span>
                  </div>
                </div>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid #e5e7eb' }}>
                <strong style={{ color: '#374151' }}>Formula:</strong> (Mission × 30%) + (Profile × 25%) + (Funding × 25%) + (Effort-Reward × 20%) = Composite Score
              </div>
            </div>
            
            {/* Recommendation Explanation */}
            <div style={{ 
              marginTop: '0.75rem', 
              padding: '0.75rem', 
              backgroundColor: evaluation.recommendation === 'APPLY' ? '#d1fae5' : evaluation.recommendation === 'CONDITIONAL' ? '#fef3c7' : '#fee2e2', 
              borderRadius: '4px',
              fontSize: '0.85rem',
              border: `1px solid ${evaluation.recommendation === 'APPLY' ? '#a7f3d0' : evaluation.recommendation === 'CONDITIONAL' ? '#fde68a' : '#fecaca'}`
            }}>
              <strong style={{ color: evaluation.recommendation === 'APPLY' ? '#059669' : evaluation.recommendation === 'CONDITIONAL' ? '#d97706' : '#dc2626', marginBottom: '0.5rem', display: 'block' }}>
                Why {evaluation.recommendation}:
              </strong>
              <div style={{ color: '#374151', lineHeight: '1.5', wordWrap: 'break-word', overflowWrap: 'break-word', whiteSpace: 'normal' }}>
                {compositeScore >= 8.0 ? (
                  <>Your composite score of {compositeScore}/10 indicates a <strong>strong fit</strong> across all dimensions. This grant aligns well with your project and is worth the investment of time and effort to apply.</>
                ) : compositeScore >= 6.5 ? (
                  <>Your composite score of {compositeScore}/10 indicates a <strong>potential fit</strong> with some conditions. This grant may be worth pursuing if you can address the specific gaps identified in the assessment.</>
                ) : (
                  <>Your composite score of {compositeScore}/10 is <strong>below the 6.5 threshold</strong> required for a CONDITIONAL recommendation. This indicates significant misalignment across multiple dimensions, making this grant not worth pursuing given your project context and constraints. The low score reflects: {missionScore === 0 ? 'no mission alignment (0/10), ' : missionScore < 3 ? `very low mission alignment (${missionScore}/10), ` : ''}{fundingFit.fit === 'INSUFFICIENT' || fundingFit.fit === 'UNCERTAIN' ? `funding fit issues, ` : ''}{effortReward.assessment === 'SKIP' ? 'poor effort-reward ratio, ' : ''}and other factors that collectively indicate this is not a good match.</>
                )}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid rgba(0,0,0,0.1)' }}>
                <strong>Score Range:</strong> 0-10 | <strong>Thresholds:</strong> APPLY (8.0+), CONDITIONAL (6.5-7.9), PASS (&lt;6.5)
              </div>
            </div>
            
            <div style={{ marginTop: '0.5rem', height: '10px', backgroundColor: '#e5e7eb', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ 
                width: `${(compositeScore / 10) * 100}%`, 
                height: '100%', 
                backgroundColor: compositeScore >= 7 ? '#059669' : compositeScore >= 4 ? '#3b82f6' : '#d97706'
              }}></div>
            </div>
          </div>
        </div>
      </div>

      {/* Mission Alignment Details - Enhanced with Project and Grant Comparison */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h4 style={{ marginBottom: '1rem' }}>Mission Alignment Analysis</h4>
        <p style={{ fontSize: '0.9rem', color: '#6c757d', marginBottom: '1rem' }}>
          This analysis compares your project's mission and goals with the grant's stated priorities to assess how well you line up with what this grant historically funds.
        </p>

        {/* Project vs Grant Comparison - Enhanced with clear labels */}
        {projectData && grantSnapshot && (
          <div style={{ marginBottom: '1.5rem', padding: '1.5rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '2px solid #e5e7eb', boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)' }}>
            <h5 style={{ marginTop: 0, marginBottom: '1rem', color: '#374151', fontWeight: '600', fontSize: '1.1rem' }}>
              🔍 What Was Compared
            </h5>
            <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1rem', lineHeight: '1.5' }}>
              The system evaluated your project against this grant. Below is the exact information used for the comparison:
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
              {projectData.description && (
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: '600', color: '#059669', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Your Project Focus
                  </div>
                  <div style={{ fontSize: '0.95rem', color: '#374151', padding: '1rem', backgroundColor: '#f0fdf4', borderRadius: '4px', border: '1px solid #bbf7d0', lineHeight: '1.6' }}>
                    {projectData.description}
                  </div>
                  {projectData.name && (
                    <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.5rem', fontStyle: 'italic' }}>
                      Project: {projectData.name}
                    </div>
                  )}
                </div>
              )}
              {grantSnapshot.mission && (
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: '600', color: '#0369a1', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Grant Mission & Priorities
                  </div>
                  <div style={{ fontSize: '0.95rem', color: '#374151', padding: '1rem', backgroundColor: '#f0f9ff', borderRadius: '4px', border: '1px solid #bae6fd', lineHeight: '1.6' }}>
                    {grantSnapshot.mission}
                  </div>
                  {(evaluation.grant_name || grantSnapshot.name) && (
                    <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.5rem', fontStyle: 'italic' }}>
                      Grant: {evaluation.grant_name || grantSnapshot.name}
                    </div>
                  )}
                </div>
              )}
            </div>
            {(!projectData.description || !grantSnapshot.mission) && (
              <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: '#fef3c7', borderRadius: '4px', border: '1px solid #fde68a', fontSize: '0.85rem', color: '#92400e' }}>
                <strong>Note:</strong> Some comparison data is missing. The evaluation was performed with the available information.
              </div>
            )}
          </div>
        )}

        {/* Strong Matches */}
      {missionDetails.strong_matches && missionDetails.strong_matches.length > 0 && (
          <div style={{ 
            marginBottom: '1rem', 
            padding: '1rem', 
            backgroundColor: '#d1fae5', // muted emerald-100
            borderRadius: '4px',
            border: '1px solid #a7f3d0', // muted emerald-200
            boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
          }}>
            <h5 style={{ color: '#059669', marginBottom: '0.75rem', fontWeight: '600' }}>
              Where Your Project Aligns (Strengthens Your Position)
            </h5>
            <div>
            {missionDetails.strong_matches.map((match, idx) => (
                <p key={idx} style={{ color: '#6b7280', marginBottom: '0.5rem', marginTop: 0, lineHeight: '1.5' }}>{match}</p>
            ))}
            </div>
        </div>
      )}

        {/* Score Explanation - Always show why score is what it is */}
        <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '4px', fontSize: '0.85rem', color: '#374151', border: '1px solid #e5e7eb' }}>
          <strong>Why {missionScore}/10:</strong>
          {missionScore === 0 && missionDetails.gaps && missionDetails.gaps.length > 0 ? (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ fontWeight: '500', marginBottom: '0.25rem' }}>No alignment found due to:</div>
              {missionDetails.gaps.map((gap, idx) => (
                <div key={idx} style={{ marginLeft: '1rem', marginTop: '0.25rem', wordWrap: 'break-word', overflowWrap: 'break-word', whiteSpace: 'normal' }}>{gap}</div>
              ))}
            </div>
          ) : missionScore > 0 && missionScore < 4 && missionDetails.gaps && missionDetails.gaps.length > 0 ? (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ fontWeight: '500', marginBottom: '0.5rem' }}>Weak alignment due to:</div>
              {missionDetails.gaps.map((gap, idx) => (
                <div key={idx} style={{ marginLeft: '1rem', marginTop: '0.5rem', wordWrap: 'break-word', overflowWrap: 'break-word', whiteSpace: 'normal', lineHeight: '1.6' }}>{gap}</div>
              ))}
            </div>
          ) : missionScore >= 4 && missionDetails.strong_matches && missionDetails.strong_matches.length > 0 ? (
            <div style={{ marginTop: '0.5rem' }}>
              <div style={{ wordWrap: 'break-word', overflowWrap: 'break-word', whiteSpace: 'normal' }}>Alignment found in: {missionDetails.strong_matches.slice(0, 2).join(', ')}</div>
              {missionDetails.strong_matches.length > 2 && <div style={{ marginTop: '0.25rem' }}>+ {missionDetails.strong_matches.length - 2} more match{missionDetails.strong_matches.length - 2 > 1 ? 'es' : ''}</div>}
            </div>
          ) : (
            <div style={{ marginTop: '0.5rem' }}>
              {missionScore >= 7 ? 'Strong alignment suggests you are well-positioned for this grant.' : missionScore >= 4 ? 'Moderate alignment - consider how to strengthen weak areas.' : 'Weak alignment may reduce your competitiveness unless you can address the gaps.'}
            </div>
          )}
        </div>
      </div>

      {/* Profile Match Details - Always show when there's any data */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h4 style={{ marginBottom: '1rem' }}>Profile Match Analysis</h4>
        {projectData && projectData.name && (
          <p style={{ fontSize: '0.9rem', color: '#6c757d', marginBottom: '1rem' }}>
            This analysis compares your project profile with past grant recipients to assess how well you align with typical winners.
          </p>
        )}
        
        {/* Show recipient details when available - always show if data exists, even with only 1 recipient */}
        {profileDetails.recipient_details && profileDetails.recipient_details.length > 0 && (
          <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
            <h5 style={{ marginTop: 0, marginBottom: '0.75rem', color: '#374151', fontWeight: '600' }}>
              Past Recipients Found ({profileDetails.recipient_count})
            </h5>
            <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.75rem' }}>
              {profileDetails.recipient_count === 1 
                ? "The following recipient data was found and analyzed (limited data - more recipients would improve assessment confidence):"
                : "The following recipient data was collected and analyzed to understand historical recipient patterns:"}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '0.75rem' }}>
              {profileDetails.recipient_details.map((recipient, idx) => {
                // Check if recipient has any data to display
                const hasData = recipient.career_stage || recipient.organization_type || recipient.country || recipient.education_level || recipient.year || recipient.organization_name || recipient.project_title;
                const hasProjectData = recipient.project_title || recipient.project_summary || recipient.project_theme;
                return (
                  <div key={idx} style={{ padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb', fontSize: '0.85rem' }}>
                    <div style={{ fontWeight: '500', marginBottom: '0.5rem', color: '#374151' }}>Recipient {idx + 1}:</div>
                    {recipient.organization_name && (
                      <div style={{ marginBottom: '0.25rem', fontWeight: '600', color: '#111827' }}><strong>Organization:</strong> {recipient.organization_name}</div>
                    )}
                    {recipient.organization_type && (
                      <div style={{ marginBottom: '0.25rem' }}><strong>Type:</strong> {recipient.organization_type}</div>
                    )}
                    {recipient.career_stage && (
                      <div style={{ marginBottom: '0.25rem' }}><strong>Career Stage:</strong> {recipient.career_stage}</div>
                    )}
                    {recipient.country && (
                      <div style={{ marginBottom: '0.25rem' }}><strong>Country:</strong> {recipient.country}</div>
                    )}
                    {recipient.education_level && (
                      <div style={{ marginBottom: '0.25rem' }}><strong>Education:</strong> {recipient.education_level}</div>
                    )}
                    {recipient.year && (
                      <div style={{ marginBottom: '0.5rem', color: '#6c757d' }}><strong>Year:</strong> {recipient.year}</div>
                    )}
                    {hasProjectData && (
                      <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid #e5e7eb' }}>
                        <div style={{ fontSize: '0.8rem', fontWeight: '600', color: '#374151', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Funded Project</div>
                        {recipient.project_title && (
                          <div style={{ marginBottom: '0.5rem', fontWeight: '600', color: '#111827' }}>{recipient.project_title}</div>
                        )}
                        {recipient.project_summary && (
                          <div style={{ marginBottom: '0.5rem', color: '#6b7280', lineHeight: '1.5', fontSize: '0.8125rem' }}>{recipient.project_summary}</div>
                        )}
                        {recipient.project_theme && Array.isArray(recipient.project_theme) && recipient.project_theme.length > 0 && (
                          <div style={{ marginTop: '0.5rem' }}>
                            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>Themes:</div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                              {recipient.project_theme.map((theme, themeIdx) => (
                                <span key={themeIdx} style={{ 
                                  padding: '0.125rem 0.375rem', 
                                  backgroundColor: '#e5e7eb', 
                                  borderRadius: '3px', 
                                  fontSize: '0.75rem',
                                  color: '#374151'
                                }}>
                                  {theme}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {!hasData && (
                      <div style={{ marginBottom: '0.25rem', color: '#6c757d', fontStyle: 'italic' }}>Limited details available for this recipient</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
        
        {/* Strategic Alignment Analysis */}
        {(profileDetails.similarities && profileDetails.similarities.length > 0) || (profileDetails.differences && profileDetails.differences.length > 0) ? (
          <div style={{ marginBottom: '1rem' }}>
            <h5 style={{ marginBottom: '0.75rem', color: '#495057' }}>Strategic Alignment with Grant Position</h5>
            
            {profileDetails.similarities && profileDetails.similarities.length > 0 && (
              <div style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#d1fae5', borderRadius: '4px', border: '1px solid #a7f3d0', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
                <strong style={{ color: '#059669', fontWeight: '600' }}>Where Your Profile Aligns (Increases Your Chances):</strong>
                <div style={{ marginTop: '0.5rem' }}>
                  {profileDetails.similarities.map((item, idx) => (
                    <p key={idx} style={{ color: '#6b7280', marginBottom: '0.5rem', marginTop: 0, lineHeight: '1.5' }}>{item}</p>
                  ))}
                </div>
                <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#ffffff', borderRadius: '4px', fontSize: '0.85rem', color: '#6b7280', border: '1px solid #e5e7eb' }}>
                  <strong>What this means:</strong> These alignments suggest your profile matches patterns seen in past recipients, which may increase your competitiveness for this grant.
                </div>
        </div>
      )}
            
            {profileDetails.differences && profileDetails.differences.length > 0 && (
              <div style={{ padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
                <strong style={{ color: '#374151', fontWeight: '600' }}>Where Your Profile Differs (May Reduce Your Chances):</strong>
                <div style={{ marginTop: '0.5rem' }}>
                  {profileDetails.differences.map((item, idx) => (
                    <p key={idx} style={{ color: '#6b7280', marginBottom: '0.5rem', marginTop: 0, lineHeight: '1.5' }}>{item}</p>
                  ))}
                </div>
                <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#ffffff', borderRadius: '4px', fontSize: '0.85rem', color: '#6b7280', border: '1px solid #e5e7eb' }}>
                  <strong>What this means:</strong> These differences don't necessarily disqualify you, but they suggest you may need to emphasize other strengths or address these gaps in your application to stand out.
                </div>
              </div>
            )}
          </div>
        ) : profileDetails.reason === 'INSUFFICIENT_DATA' && (!profileDetails.similarities || profileDetails.similarities.length === 0) && (!profileDetails.differences || profileDetails.differences.length === 0) ? (
          <div style={{ padding: '1rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb' }}>
            <p style={{ margin: 0, color: '#6b7280', fontSize: '0.9rem', lineHeight: '1.5' }}>
              <strong>Assessment Note:</strong> With only {profileDetails.recipient_count} recipient{profileDetails.recipient_count > 1 ? 's' : ''} found, we cannot provide a statistical pattern alignment score. {profileDetails.recipient_details && profileDetails.recipient_details.length > 0 ? 'However, you can review the recipient details shown above to manually assess how your profile compares. ' : ''}More recipient data would improve the accuracy and confidence of this assessment.
            </p>
            {profileDetails.recipient_details && profileDetails.recipient_details.length > 0 && (
                <div style={{ marginTop: '0.75rem', padding: '0.75rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #d1d5db', fontSize: '0.85rem' }}>
                <strong style={{ color: '#374151' }}>How to use this pattern data:</strong>
                <ul style={{ marginTop: '0.5rem', marginBottom: 0, paddingLeft: '1.25rem', color: '#6b7280' }}>
                  <li>Compare your career stage, organization type, and location with the recipient shown above.</li>
                  <li>Look for similarities that might indicate alignment with historical recipient patterns.</li>
                  <li>Note any differences that you may need to thoughtfully address in your application.</li>
                  <li>Remember: one recipient doesn't represent all winners, but it provides a useful directional signal.</li>
                </ul>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* Funding Fit Details */}
      {fundingFit.reasoning && (
        <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
          <h5 style={{ color: '#374151', marginBottom: '0.5rem', fontWeight: '600' }}>
            Funding Fit Analysis
          </h5>
          <p style={{ margin: 0, color: '#6b7280' }}>
            {fundingFit.reasoning}
          </p>
          {fundingFit.recommendation && (
            <p style={{ marginTop: '0.5rem', fontWeight: 'bold' }}>{fundingFit.recommendation}</p>
          )}
        </div>
      )}

      {/* Historical Acceptance (Grant-Level) */}
      {successProb.range && successProb.range !== 'UNKNOWN' && (
        <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <strong style={{ color: '#374151' }}>Historical Acceptance (Grant-Level)</strong>
            <span style={{ fontSize: '1.2rem', fontWeight: '600', color: '#111827' }}>{successProb.range}</span>
          </div>
          {successProb.base_rate && (
            <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>
              Base acceptance rate across all applicants: {successProb.base_rate}
              <ConfidenceBadge confidence={successProb.confidence} />
            </div>
          )}
          {successProb.explanation && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>{successProb.explanation}</div>
          )}
        </div>
      )}

      {/* Decision Gates */}
      {evaluation.decision_gates && evaluation.decision_gates.length > 0 && (
        <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', borderLeft: '3px solid #9ca3af', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
          <h5 style={{ marginBottom: '0.5rem' }}>Decision Gates</h5>
          <p style={{ fontSize: '0.9rem', marginBottom: '0.5rem', color: '#d97706', padding: '0.5rem', backgroundColor: '#fef3c7', borderRadius: '4px' }}>
            Before proceeding, ensure these conditions are met:
          </p>
          <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
            {evaluation.decision_gates.map((gate, idx) => (
              <li key={idx} style={{ marginBottom: '0.5rem' }}>{gate}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Strategic Recommendations */}
      {paidTier.strategic_recommendations && (
        <div style={{ marginBottom: '1.5rem' }}>
          <h4>Strategic Recommendations</h4>
          
          {paidTier.strategic_recommendations.competitive_advantages && paidTier.strategic_recommendations.competitive_advantages.length > 0 && (
            <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
              <h5 style={{ color: '#374151', marginBottom: '0.5rem', fontWeight: '600' }}>Your Competitive Advantages</h5>
              <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
                {paidTier.strategic_recommendations.competitive_advantages.map((item, idx) => (
                  <li key={idx} style={{ color: '#6b7280', marginBottom: '0.25rem' }}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {paidTier.strategic_recommendations.areas_to_strengthen && paidTier.strategic_recommendations.areas_to_strengthen.length > 0 && (
            <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
              <h5 style={{ color: '#374151', marginBottom: '0.5rem', fontWeight: '600' }}>Areas to Strengthen</h5>
              <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
                {paidTier.strategic_recommendations.areas_to_strengthen.map((item, idx) => (
                  <li key={idx} style={{ color: '#6b7280', marginBottom: '0.25rem' }}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {paidTier.strategic_recommendations.application_strategy && (
            <div style={{ padding: '1rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
              <h5 style={{ marginBottom: '0.5rem' }}>Application Strategy</h5>
              <p style={{ margin: 0 }}>{paidTier.strategic_recommendations.application_strategy}</p>
            </div>
          )}
        </div>
      )}

      {/* Effort-Reward Analysis */}
      {effortReward.assessment && (
        <div style={{ marginBottom: '1.5rem', padding: '1.5rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h5 style={{ margin: 0, color: '#374151', fontWeight: '600' }}>Effort-Reward Analysis</h5>
            <span style={{
              padding: '0.375rem 0.75rem',
              borderRadius: '4px',
              backgroundColor: '#f3f4f6',
              color: '#374151',
              fontSize: '0.875rem',
              fontWeight: 'bold'
            }}>
              {effortReward.assessment}
            </span>
          </div>

          {/* What's Required from You */}
          <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb' }}>
            <strong style={{ fontSize: '0.9rem', color: '#374151', marginBottom: '0.5rem', display: 'block' }}>
              What's Required from You:
            </strong>
          {effortReward.estimated_hours && (
              <div style={{ marginBottom: '0.75rem' }}>
                <div style={{ fontSize: '0.9rem', fontWeight: '500', color: '#212529', marginBottom: '0.25rem' }}>
                  Time Investment: ~{effortReward.estimated_hours} hours
                </div>
                <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>
                  This includes time for research, writing, gathering documents, and completing the application.
                </div>
              </div>
            )}
            {grantSnapshot.application_requirements && Array.isArray(grantSnapshot.application_requirements) && grantSnapshot.application_requirements.length > 0 && (
              <div style={{ marginBottom: '0.75rem' }}>
                <div style={{ fontSize: '0.9rem', fontWeight: '500', color: '#212529', marginBottom: '0.5rem' }}>
                  Application Requirements:
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.5rem', fontSize: '0.85rem', color: '#495057' }}>
                  {grantSnapshot.application_requirements.slice(0, 5).map((req, idx) => (
                    <li key={idx} style={{ marginBottom: '0.25rem' }}>{req}</li>
                  ))}
                  {grantSnapshot.application_requirements.length > 5 && (
                    <li style={{ color: '#6c757d', fontStyle: 'italic' }}>
                      + {grantSnapshot.application_requirements.length - 5} more requirement{grantSnapshot.application_requirements.length - 5 > 1 ? 's' : ''}
                    </li>
                  )}
                </ul>
              </div>
            )}
            {effortReward.opportunity_cost && (
              <div style={{ marginTop: '0.75rem', padding: '0.75rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: '500', color: '#374151' }}>
                  Opportunity Cost: {effortReward.opportunity_cost}
                </div>
                <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '0.25rem' }}>
                  {effortReward.opportunity_cost === 'HIGH' && 'Significant time commitment that may impact other priorities.'}
                  {effortReward.opportunity_cost === 'MODERATE' && 'Moderate time commitment, plan accordingly.'}
                  {effortReward.opportunity_cost === 'LOW' && 'Low time commitment, minimal impact on other activities.'}
                </div>
              </div>
            )}
          </div>

          {/* Why This Assessment */}
          {effortReward.reasoning && (
            <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb', borderLeft: '3px solid #9ca3af' }}>
              <strong style={{ fontSize: '0.9rem', color: '#374151', marginBottom: '0.5rem', display: 'block' }}>
                Why {effortReward.assessment}:
              </strong>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#6b7280', lineHeight: '1.5' }}>
                {effortReward.reasoning}
              </p>
            </div>
          )}

          {/* Value Breakdown */}
          {(effortReward.potential_value > 0 || effortReward.value_per_hour > 0) && (
            <div style={{ padding: '1rem', backgroundColor: '#f9fafb', borderRadius: '4px', border: '1px solid #e5e7eb' }}>
              <strong style={{ fontSize: '0.9rem', color: '#374151', marginBottom: '0.5rem', display: 'block' }}>
                Value Breakdown:
              </strong>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', fontSize: '0.85rem' }}>
                {effortReward.potential_value > 0 && (
                  <div>
                    <div style={{ color: '#6b7280', marginBottom: '0.25rem' }}>Potential Value</div>
                    <div style={{ fontWeight: 'bold', color: '#059669' }}>
                      ${(effortReward.potential_value / 100).toLocaleString()}
                    </div>
                  </div>
                )}
                {effortReward.value_per_hour > 0 && (
                  <div>
                    <div style={{ color: '#6b7280', marginBottom: '0.25rem' }}>Value per Hour</div>
                    <div style={{ fontWeight: 'bold', color: '#3b82f6' }}>
                      ${(effortReward.value_per_hour / 100).toLocaleString()}/hr
                    </div>
                  </div>
                )}
                {effortReward.confidence && (
                  <div>
                    <div style={{ color: '#6c757d', marginBottom: '0.25rem' }}>Confidence</div>
                    <div style={{ fontWeight: 'bold', color: '#6c757d', textTransform: 'capitalize' }}>
                      {effortReward.confidence}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Red Flags */}
      {evaluation.red_flags && evaluation.red_flags.length > 0 && (
        <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
          <h5 style={{ color: '#374151', marginBottom: '0.5rem', fontWeight: '600' }}>Red Flags</h5>
          <div>
            {evaluation.red_flags.map((flag, idx) => (
              <p key={idx} style={{ color: '#6b7280', marginBottom: '0.5rem', marginTop: 0, lineHeight: '1.5' }}>{flag}</p>
            ))}
          </div>
        </div>
      )}

      {/* Key Insights */}
      {evaluation.key_insights && evaluation.key_insights.length > 0 && (
        <div style={{ 
          marginBottom: '1.5rem', 
          padding: '1.5rem', 
          backgroundColor: '#ffffff', 
          borderRadius: '4px', 
          border: '1px solid #e5e7eb',
          borderLeft: '3px solid #3b82f6', // muted blue accent
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)'
        }}>
          <h5 style={{ marginTop: 0, marginBottom: '1rem', color: '#374151', fontWeight: '600' }}>Key Insights</h5>
          <div>
            {evaluation.key_insights.map((insight, idx) => (
              <p key={idx} style={{ 
                marginBottom: '0.75rem', 
                marginTop: 0, 
                color: '#6b7280',
                lineHeight: '1.6',
                paddingLeft: '1rem',
                borderLeft: '2px solid #dbeafe' // subtle blue accent
              }}>
                {insight}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Confidence Notes */}
      {evaluation.confidence_notes && (
        <div style={{ 
          marginTop: '1.5rem', 
          padding: '1rem', 
          backgroundColor: '#ffffff', 
          borderRadius: '4px', 
          border: '1px solid #e5e7eb',
          borderLeft: '3px solid #9ca3af',
          boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
        }}>
          <strong style={{ color: '#374151' }}>Confidence Assessment:</strong> 
          <span style={{ color: '#6b7280', marginLeft: '0.5rem' }}>{evaluation.confidence_notes}</span>
        </div>
      )}

      {/* Pattern Knowledge */}
      {evaluation.pattern_knowledge && (
        <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '4px', border: '1px solid #e5e7eb', borderLeft: '3px solid #9ca3af', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
          <strong>Pattern Knowledge:</strong>
          <p style={{ margin: '0.5rem 0 0 0' }}>{evaluation.pattern_knowledge}</p>
        </div>
      )}

      {/* Opportunity Cost */}
      {evaluation.opportunity_cost && (
        <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
          <strong>Opportunity Cost:</strong> {evaluation.opportunity_cost}
        </div>
      )}

      {/* Improve Assessment Quality - Contribute Missing Grant Data */}
      {missingGrantData.length > 0 && (
        <div style={{ 
          marginTop: '2rem', 
          padding: '1.5rem', 
          backgroundColor: '#ffffff', 
          borderRadius: '4px', 
          border: '1px solid #e5e7eb',
          borderLeft: '3px solid #9ca3af',
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)'
        }}>
          <h4 style={{ marginTop: 0, marginBottom: '0.75rem', color: '#111827', fontWeight: '600' }}>
            Improve This Assessment
          </h4>
          <p style={{ marginBottom: '1rem', color: '#6b7280', fontSize: '0.95rem' }}>
            This assessment is limited by missing grant information. If you have access to this data, 
            you can contribute it to improve the evaluation quality and get more accurate recommendations.
          </p>
          
          <div style={{ marginBottom: '1rem' }}>
            <strong style={{ fontSize: '0.9rem', color: '#374151' }}>Missing Information:</strong>
            <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.5rem', fontSize: '0.9rem', color: '#6b7280' }}>
              {missingGrantData.map((field, idx) => (
                <li key={idx} style={{ marginBottom: '0.25rem' }}>
                  {field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </li>
              ))}
            </ul>
          </div>

          <div style={{ 
            padding: '1rem', 
            backgroundColor: '#f9fafb', 
            borderRadius: '4px',
            marginBottom: '1rem',
            fontSize: '0.85rem',
            color: '#6b7280',
            border: '1px solid #e5e7eb'
          }}>
            <strong>What happens when you contribute:</strong>
            <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.5rem' }}>
              <li>Your contribution is reviewed by our team</li>
              <li>Once approved, the grant data is updated</li>
              <li>You can request a new assessment with improved data quality</li>
              <li>Future evaluations for this grant will be more accurate</li>
            </ul>
          </div>

          <button
            onClick={() => setShowContributeForm(true)}
            className="btn"
            style={{ 
              fontSize: '0.95rem', 
              padding: '0.75rem 1.5rem',
              fontWeight: '500',
              backgroundColor: '#4b5563',
              color: 'white',
              borderColor: '#4b5563'
            }}
          >
            Contribute Grant Data
          </button>
        </div>
      )}

      {/* Contribute Data Form Modal */}
      {showContributeForm && (
        <ContributeDataForm
          grantId={evaluation.grant_id || null}
          evaluationId={evaluation.id}
          grantName={evaluation.grant_name}
          grantUrl={evaluation.grant_url || grantData?.source_url || null}
          missingFields={missingGrantData}
          onClose={() => setShowContributeForm(false)}
          onSuccess={() => {
            setShowContributeForm(false)
            // Optionally show success message or refresh data
          }}
        />
      )}
    </div>
  )
}

export default PaidAssessmentDisplay
