import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ContactFunderTemplate from './ContactFunderTemplate'
import ContributeDataForm from './ContributeDataForm'

/**
 * Free Assessment Display Component
 * 
 * Displays grant quality assessment (free tier).
 * Shows: clarity, access barrier, timeline, award structure, competition level.
 * Does NOT show: mission alignment, profile match (requires project data).
 */

function FreeAssessmentDisplay({ evaluation, grantData }) {
  const navigate = useNavigate()
  const [showContactTemplate, setShowContactTemplate] = useState(false)
  const [showContributeForm, setShowContributeForm] = useState(false)
  const grantQuality = evaluation.reasoning?._grant_quality || {}
  const isLegacy = evaluation.is_legacy || false

  // Extract grant data - prefer grant_snapshot_json (in-memory grants), fallback to grantData prop (indexed grants)
  const grantSnapshot = evaluation.grant_snapshot_json || grantData || {}
  const awardAmount = grantSnapshot.award_amount || null
  const deadline = grantSnapshot.deadline || null
  const decisionDate = grantSnapshot.decision_date || null
  const eligibility = grantSnapshot.eligibility || grantData?.eligibility || null
  const recipientPatterns = grantSnapshot.recipient_patterns || grantData?.recipient_patterns || {}
  const recipients = recipientPatterns?.recipients || []

  // Extract grant quality data
  const clarityScore = grantQuality.clarity_score ?? evaluation.composite_score
  const clarityRating = grantQuality.clarity_rating || 'Unknown'
  const accessBarrier = grantQuality.access_barrier || 'UNKNOWN'
  const accessHours = grantQuality.access_barrier_hours || 'N/A'
  const timelineStatus = grantQuality.timeline_status || 'UNKNOWN'
  const timelineWeeks = grantQuality.timeline_weeks || null
  const awardScore = grantQuality.award_structure_score ?? evaluation.award_structure
  const awardTransparency = grantQuality.award_structure_transparency || 'Unclear'
  const competitionLevel = grantQuality.competition_level || 'UNKNOWN'
  const competitionRate = grantQuality.competition_acceptance_rate || null
  const competitionSource = grantQuality.competition_source || 'unknown'
  const competitionConfidence = grantQuality.competition_confidence || 'unknown'

  // Get good_fit_if and poor_fit_if from reasoning
  const goodFitIf = evaluation.reasoning?.good_fit_if || []
  const poorFitIf = evaluation.reasoning?.poor_fit_if || []

  // Get readiness score from backend if available, otherwise calculate in frontend
  const backendReadiness = evaluation.reasoning?._readiness
  const readinessScore = backendReadiness?.score ?? (() => {
    // Fallback frontend calculation
    let score = 0
    const missing = []

    // CRITICAL DATA (6 points total)
    if (awardAmount) {
      const amountStr = String(awardAmount).trim().toLowerCase()
      if (amountStr && !['varies', 'contact us', 'not disclosed', 'n/a', 'tbd'].includes(amountStr)) {
        const numbers = amountStr.match(/[\d,]+/g)
        if (numbers && numbers.length > 0) {
          score += 3
        } else {
          missing.push('award_amount')
        }
      } else {
        missing.push('award_amount')
      }
    } else {
      missing.push('award_amount')
    }

    if (deadline && deadline.toLowerCase() !== 'rolling') {
      score += 1
    }

    if (eligibility && eligibility.length > 50) {
      score += 2
    } else {
      missing.push('eligibility_criteria')
    }

    // STRATEGIC DATA (4 points total)
    if (recipients && recipients.length >= 5) {
      score += 2
    } else {
      missing.push('past_recipients')
    }

    if (competitionRate && competitionLevel !== 'UNKNOWN') {
      score += 1
    } else {
      missing.push('acceptance_rate')
    }

    if (grantSnapshot.preferred_applicants && grantSnapshot.preferred_applicants.length > 50) {
      score += 1
    }

    return { score, missing }
  })()

  const missingData = backendReadiness?.missing_data || (typeof readinessScore === 'object' ? readinessScore.missing : [])
  const actualReadinessScore = typeof readinessScore === 'object' ? readinessScore.score : readinessScore

  // Determine quality tier (use backend tier if available)
  const getQualityTier = (score, backendTier) => {
    if (backendTier) {
      const tierMap = {
        'HIGH': { tier: 'HIGH', label: 'EXCELLENT', color: '#28a745' },
        'MEDIUM': { tier: 'MEDIUM', label: 'PARTIAL', color: '#ffc107' },
        'LOW': { tier: 'LOW', label: 'POOR', color: '#dc3545' }
      }
      return tierMap[backendTier] || getQualityTierByScore(score)
    }
    return getQualityTierByScore(score)
  }

  const getQualityTierByScore = (score) => {
    if (score >= 8) return { tier: 'HIGH', label: 'EXCELLENT', color: '#28a745' }
    if (score >= 5) return { tier: 'MEDIUM', label: 'PARTIAL', color: '#ffc107' }
    return { tier: 'LOW', label: 'POOR', color: '#dc3545' }
  }

  const qualityTier = getQualityTier(actualReadinessScore, backendReadiness?.tier)

  // Determine what analysis is possible
  const analysisCapabilities = {
    can_assess_funding_fit: !!awardAmount,
    can_assess_competition: competitionLevel !== 'UNKNOWN' || (recipients && recipients.length >= 5),
    can_estimate_probability: !!competitionRate && recipients && recipients.length >= 10,
    can_provide_positioning: recipients && recipients.length >= 5
  }

  // Paid upgrade recommendation logic
  const getPaidUpgradeRecommendation = () => {
    if (actualReadinessScore >= 8) {
      return {
        show: true,
        recommended: true,
        message: 'RECOMMENDED',
        reasoning: 'This grant has excellent data. Strategic analysis will significantly improve your odds.',
        canProvide: ['Funding fit', 'Competitive positioning', 'Success probability', 'Strategic recommendations']
      }
    }
    if (actualReadinessScore >= 5) {
      return {
        show: true,
        recommended: false,
        message: 'PARTIAL VALUE',
        reasoning: 'We can analyze what\'s available, but missing data limits probability estimates.',
        canProvide: analysisCapabilities.can_assess_funding_fit ? ['Funding fit', 'Mission alignment'] : ['Mission alignment'],
        cannotProvide: missingData.filter(d => ['award_amount', 'past_recipients', 'acceptance_rate'].includes(d))
      }
    }
    return {
      show: true,
      recommended: false,
      message: 'NOT RECOMMENDED',
      reasoning: 'Missing critical data means limited analysis. Better to use credits on well-documented grants.',
      canProvide: ['Mission alignment only'],
      cannotProvide: missingData
    }
  }

  const upgradeRecommendation = getPaidUpgradeRecommendation()

  // Status colors
  const getStatusColor = (status) => {
    switch (status) {
      case 'GREEN': return '#28a745'
      case 'YELLOW': return '#ffc107'
      case 'RED': return '#dc3545'
      case 'LOW': return '#28a745'
      case 'MEDIUM': return '#ffc107'
      case 'HIGH': return '#dc3545'
      default: return '#6c757d'
    }
  }

  const getStatusBgColor = (status) => {
    switch (status) {
      case 'GREEN': return '#d4edda'
      case 'YELLOW': return '#fff3cd'
      case 'RED': return '#f8d7da'
      case 'LOW': return '#d4edda'
      case 'MEDIUM': return '#fff3cd'
      case 'HIGH': return '#f8d7da'
      default: return '#e9ecef'
    }
  }

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }}>
      {isLegacy && (
        <div style={{
          padding: '0.5rem',
          backgroundColor: '#fff3cd',
          borderLeft: '4px solid #ffc107',
          marginBottom: '1rem',
          borderRadius: '4px'
        }}>
          <strong>Legacy Evaluation</strong> - This assessment was created with the previous scoring system.
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1rem' }}>
        <div>
          <h3>{evaluation.grant_name || `Grant ID: ${evaluation.grant_id}`}</h3>
          <p style={{ color: '#6c757d', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            {actualReadinessScore < 5 && 'INCOMPLETE DATA'}
            {actualReadinessScore >= 5 && actualReadinessScore < 8 && 'PARTIAL DATA'}
            {actualReadinessScore >= 8 && 'COMPLETE DATA'}
            {deadline && ` • ${deadline}`}
          </p>
        </div>
        <span
          style={{
            padding: '0.5rem 1rem',
            borderRadius: '4px',
            backgroundColor: evaluation.recommendation === 'PASS' ? '#dc3545' : '#ffc107',
            color: 'white',
            fontWeight: 'bold',
          }}
        >
          {evaluation.recommendation}
        </span>
      </div>

      {/* Data Quality Score */}
      <div style={{ 
        marginBottom: '1.5rem', 
        padding: '1rem', 
        backgroundColor: qualityTier.tier === 'HIGH' ? '#d4edda' : qualityTier.tier === 'MEDIUM' ? '#fff3cd' : '#f8d7da',
        borderRadius: '6px',
        borderLeft: `4px solid ${qualityTier.color}`
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <strong style={{ color: qualityTier.tier === 'HIGH' ? '#155724' : qualityTier.tier === 'MEDIUM' ? '#856404' : '#721c24' }}>
            Data Quality: {actualReadinessScore}/10 ({qualityTier.label})
          </strong>
          <span style={{ 
            fontSize: '1.2rem', 
            fontWeight: 'bold', 
            color: qualityTier.color 
          }}>
            {actualReadinessScore}/10
          </span>
        </div>
        {missingData.length > 0 && (
          <div style={{ fontSize: '0.85rem', color: qualityTier.tier === 'HIGH' ? '#155724' : qualityTier.tier === 'MEDIUM' ? '#856404' : '#721c24', marginTop: '0.5rem' }}>
            Missing: {missingData.map(d => d.replace(/_/g, ' ')).join(', ')}
          </div>
        )}
      </div>

      {/* Quick Decision Factors - Priority-focused display */}
      <div style={{ 
        marginBottom: '2rem', 
        padding: '1.5rem', 
        backgroundColor: '#f8f9fa', 
        borderRadius: '8px', 
        border: '1px solid #dee2e6'
      }}>
        <h4 style={{ marginTop: 0, marginBottom: '1.5rem' }}>Quick Decision Factors</h4>
        
        {/* Funding */}
        <div style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid #dee2e6' }}>
          <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.5rem', fontWeight: '500' }}>
            FUNDING
          </div>
          {awardAmount ? (
            <>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#004085', marginBottom: '0.25rem' }}>
                {awardAmount}
              </div>
              <div style={{ fontSize: '0.85rem', color: '#28a745' }}>Amount disclosed</div>
            </>
          ) : (
            <>
              <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#dc3545', marginBottom: '0.25rem' }}>
                NOT DISCLOSED
              </div>
              <div style={{ fontSize: '0.85rem', color: '#721c24' }}>
                Cannot assess if this meets your funding needs
              </div>
            </>
          )}
        </div>

        {/* Timing */}
        <div style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid #dee2e6' }}>
          <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.5rem', fontWeight: '500' }}>
            TIMING
          </div>
          {deadline ? (
            <>
              <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#004085', marginBottom: '0.25rem' }}>
                {deadline}
              </div>
              {timelineWeeks && (
                <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>
                  {timelineWeeks} weeks remaining
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: '0.9rem', color: '#6c757d' }}>Deadline not specified</div>
          )}
          {accessHours !== 'N/A' && (
            <div style={{ fontSize: '0.85rem', color: '#28a745', marginTop: '0.5rem' }}>
              Prep time: ~{accessHours} hours
            </div>
          )}
        </div>

        {/* Eligibility */}
        {eligibility && (
          <div style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid #dee2e6' }}>
            <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.5rem', fontWeight: '500' }}>
              ELIGIBILITY
            </div>
            <div style={{ fontSize: '0.9rem', color: '#495057', lineHeight: '1.5', whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
              {eligibility}
            </div>
          </div>
        )}

        {/* Your Odds */}
        <div>
          <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '0.5rem', fontWeight: '500' }}>
            YOUR ODDS
          </div>
          {competitionRate ? (
            <>
              <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#004085', marginBottom: '0.25rem' }}>
                {competitionRate} acceptance rate
              </div>
              {competitionSource !== 'unknown' && (
                <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>
                  {competitionSource === 'official' ? 'Official data' : 'Estimated'}
                </div>
              )}
            </>
          ) : (
            <>
              <div style={{ fontSize: '1rem', fontWeight: 'bold', color: '#dc3545', marginBottom: '0.25rem' }}>
                UNKNOWN
              </div>
              <div style={{ fontSize: '0.85rem', color: '#721c24' }}>
                Cannot estimate competitiveness
              </div>
            </>
          )}
        </div>
      </div>

      {/* Grant Quality Scores */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h4 style={{ marginBottom: '1rem' }}>Grant Quality Indicators</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
          {/* Clarity Score */}
          <div style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <strong>Clarity</strong>
              <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{clarityScore}/10</span>
            </div>
            <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>{clarityRating}</div>
            <div style={{ marginTop: '0.5rem', height: '8px', backgroundColor: '#e9ecef', borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ width: `${(clarityScore / 10) * 100}%`, height: '100%', backgroundColor: '#007bff' }}></div>
            </div>
          </div>

          {/* Access Barrier */}
          <div style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <strong>Access Barrier</strong>
              <span style={{
                padding: '0.25rem 0.5rem',
                borderRadius: '4px',
                backgroundColor: getStatusBgColor(accessBarrier),
                color: getStatusColor(accessBarrier),
                fontSize: '0.85rem',
                fontWeight: 'bold'
              }}>
                {accessBarrier}
              </span>
            </div>
            <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>Est. {accessHours} hours</div>
          </div>

          {/* Timeline */}
          <div style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <strong>Timeline</strong>
              <span style={{
                padding: '0.25rem 0.5rem',
                borderRadius: '4px',
                backgroundColor: getStatusBgColor(timelineStatus),
                color: getStatusColor(timelineStatus),
                fontSize: '0.85rem',
                fontWeight: 'bold'
              }}>
                {timelineStatus}
              </span>
            </div>
            {timelineWeeks && (
              <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>{timelineWeeks} weeks remaining</div>
            )}
          </div>

          {/* Award Structure */}
          <div style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <strong>Award Structure</strong>
              <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{awardScore}/10</span>
            </div>
            <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>{awardTransparency}</div>
          </div>
        </div>
      </div>

      {/* Competition Level */}
      {competitionLevel !== 'UNKNOWN' && (
        <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <strong>Competition Level</strong>
            <span style={{ fontSize: '0.9rem', fontWeight: 'bold' }}>{competitionLevel}</span>
          </div>
          {competitionRate && (
            <div style={{ fontSize: '0.85rem', color: '#6c757d' }}>
              Acceptance rate: {competitionRate}
              {competitionSource !== 'unknown' && (
                <span style={{ marginLeft: '0.5rem', padding: '0.15rem 0.4rem', backgroundColor: '#e9ecef', borderRadius: '3px', fontSize: '0.75rem' }}>
                  {competitionSource === 'official' ? 'Official' : 'Estimated'}
                </span>
              )}
            </div>
          )}
          {competitionConfidence === 'low' && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#dc3545' }}>
              Warning: Low confidence - limited data available
            </div>
          )}
        </div>
      )}

      {/* Good Fit If / Poor Fit If */}
      {(goodFitIf.length > 0 || poorFitIf.length > 0) && (
        <div style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem' }}>
            {goodFitIf.length > 0 && (
              <div style={{ padding: '1rem', backgroundColor: '#d4edda', borderRadius: '4px' }}>
                <h5 style={{ color: '#155724', marginBottom: '0.5rem' }}>Good fit if:</h5>
                <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
                  {goodFitIf.map((item, idx) => (
                    <li key={idx} style={{ color: '#155724', marginBottom: '0.25rem' }}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {poorFitIf.length > 0 && (
              <div style={{ padding: '1rem', backgroundColor: '#f8d7da', borderRadius: '4px' }}>
                <h5 style={{ color: '#721c24', marginBottom: '0.5rem' }}>Poor fit if:</h5>
                <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
                  {poorFitIf.map((item, idx) => (
                    <li key={idx} style={{ color: '#721c24', marginBottom: '0.25rem' }}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Red Flags */}
      {evaluation.red_flags && evaluation.red_flags.length > 0 && (
        <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#f8d7da', borderRadius: '4px' }}>
          <h5 style={{ color: '#721c24', marginBottom: '0.5rem' }}>Red Flags</h5>
          <ul style={{ margin: 0, paddingLeft: '1.5rem' }}>
            {evaluation.red_flags.map((flag, idx) => (
              <li key={idx} style={{ color: '#721c24', marginBottom: '0.25rem' }}>{flag}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Key Insights */}
      {evaluation.key_insights && evaluation.key_insights.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <h5>Key Insights</h5>
          <div>
            {evaluation.key_insights.map((insight, idx) => (
              <p key={idx} style={{ marginBottom: '0.5rem', marginTop: 0 }}>{insight}</p>
            ))}
          </div>
        </div>
      )}

      {/* Should You Apply? Section */}
      {actualReadinessScore < 8 && (
        <div style={{ marginTop: '1.5rem', padding: '1.5rem', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
          <h4 style={{ marginTop: 0, marginBottom: '1rem' }}>Should You Apply?</h4>
          
          {actualReadinessScore < 5 ? (
            <>
              <div style={{ 
                padding: '1rem', 
                backgroundColor: '#fff3cd', 
                borderRadius: '4px',
                borderLeft: '4px solid #ffc107',
                marginBottom: '1rem'
              }}>
                <strong style={{ color: '#856404' }}>Recommendation: Get More Info First</strong>
                <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: '#856404' }}>
                  This grant might be great, but we can't tell without critical information. Contact the funder to ask about typical award amounts, past recipient profiles, and application success rates.
                </p>
              </div>
              
              <div style={{ marginBottom: '1rem' }}>
                <strong style={{ fontSize: '0.9rem' }}>Worth pursuing IF:</strong>
                <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.5rem', fontSize: '0.9rem' }}>
                  <li>You contact funder and award amount fits your needs</li>
                  <li>You meet all eligibility requirements</li>
                  <li>~{accessHours} hours of effort is acceptable risk</li>
                </ul>
              </div>
            </>
          ) : (
            <>
              <div style={{ marginBottom: '1rem' }}>
                <strong style={{ fontSize: '0.9rem' }}>Worth exploring if:</strong>
                <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.5rem', fontSize: '0.9rem' }}>
                  {awardAmount && <li>You meet the eligibility requirements</li>}
                  {deadline && <li>Deadline fits your timeline</li>}
                  <li>~{accessHours} hours of effort is acceptable</li>
          </ul>
              </div>
              
              {missingData.length > 0 && (
                <div style={{ 
                  marginTop: '1rem', 
                  padding: '0.75rem', 
                  backgroundColor: '#fff3cd', 
                  borderRadius: '4px',
                  fontSize: '0.85rem',
                  color: '#856404'
                }}>
                  <strong>Get more info:</strong> Contact funder about {missingData.slice(0, 2).map(d => d.replace(/_/g, ' ')).join(' and ')} to make a better decision.
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Confidence Notes */}
      {evaluation.confidence_notes && (
        <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#fff3cd', borderRadius: '4px', borderLeft: '4px solid #ffc107' }}>
          <strong>Note:</strong> {evaluation.confidence_notes}
        </div>
      )}

      {/* Actionable Next Step */}
      {evaluation.reasoning?.actionable_next_step && (
        <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: '#d1ecf1', borderRadius: '4px' }}>
          <strong>Next Step:</strong> {evaluation.reasoning.actionable_next_step}
        </div>
      )}

      {/* Paid Assessment Recommendation */}
      {upgradeRecommendation.show && (
        <div style={{ 
          marginTop: '1.5rem', 
          padding: '1.5rem', 
          backgroundColor: upgradeRecommendation.recommended ? '#e7f3ff' : '#f8f9fa',
          borderRadius: '8px', 
          border: `2px solid ${upgradeRecommendation.recommended ? '#007bff' : '#dee2e6'}`
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1rem' }}>
            <h4 style={{ margin: 0, color: upgradeRecommendation.recommended ? '#004085' : '#6c757d' }}>
              Paid Assessment: {upgradeRecommendation.message}
            </h4>
            {!upgradeRecommendation.recommended && (
              <span style={{
                padding: '0.25rem 0.75rem',
                backgroundColor: '#dc3545',
                color: 'white',
                borderRadius: '4px',
                fontSize: '0.75rem',
                fontWeight: 'bold'
              }}>
                NOT RECOMMENDED
              </span>
            )}
          </div>

          <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: upgradeRecommendation.recommended ? '#004085' : '#495057' }}>
            {upgradeRecommendation.reasoning}
          </p>

          {upgradeRecommendation.canProvide && upgradeRecommendation.canProvide.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <strong style={{ fontSize: '0.85rem', color: upgradeRecommendation.recommended ? '#004085' : '#495057' }}>
                We CAN analyze:
              </strong>
              <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.5rem', fontSize: '0.85rem', color: upgradeRecommendation.recommended ? '#004085' : '#495057' }}>
                {upgradeRecommendation.canProvide.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {upgradeRecommendation.cannotProvide && upgradeRecommendation.cannotProvide.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <strong style={{ fontSize: '0.85rem', color: '#dc3545' }}>
                We CANNOT analyze (data missing):
              </strong>
              <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.5rem', fontSize: '0.85rem', color: '#721c24' }}>
                {upgradeRecommendation.cannotProvide.map((item, idx) => (
                  <li key={idx}>{item.replace(/_/g, ' ')}</li>
                ))}
              </ul>
            </div>
          )}

              {!upgradeRecommendation.recommended && (
            <div style={{ 
              marginTop: '1rem', 
              padding: '1rem', 
              backgroundColor: '#fff3cd', 
              borderRadius: '4px',
              borderLeft: '4px solid #ffc107'
            }}>
              <strong style={{ color: '#856404' }}>Better investment:</strong>
              <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem', color: '#856404' }}>
                Use paid assessments on well-documented grants where we can provide comprehensive probability analysis and competitive positioning.
        </p>
      </div>
          )}

          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            {missingData.length > 0 && (
              <>
                <button
                  onClick={() => setShowContactTemplate(true)}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
                >
                  Contact Funder Template
                </button>
                <button
                  onClick={() => setShowContributeForm(true)}
                  className="btn btn-primary"
                  style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
                >
                  Contribute Data
                </button>
              </>
            )}
            <button
              onClick={() => {
                // Navigate to grants page
                navigate('/dashboard/grants')
              }}
              className="btn btn-secondary"
              style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
            >
              Find Better Grants
            </button>
          </div>
        </div>
      )}

      {showContactTemplate && (
        <ContactFunderTemplate
          grantName={evaluation.grant_name}
          missingData={missingData}
          onClose={() => setShowContactTemplate(false)}
        />
      )}

      {showContributeForm && (
        <ContributeDataForm
          grantId={grantData?.id || null}
          evaluationId={evaluation.id}
          grantName={evaluation.grant_name}
          grantUrl={evaluation.grant_url || grantData?.source_url || null}
          missingFields={missingData}
          onClose={() => setShowContributeForm(false)}
          onSuccess={() => {
            // Optionally refresh data or show success message
            setShowContributeForm(false)
          }}
        />
      )}
    </div>
  )
}

export default FreeAssessmentDisplay
