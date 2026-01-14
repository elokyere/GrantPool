import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import ReportIssue from '../components/ReportIssue'
import PrivacySecurityNotice from '../components/PrivacySecurityNotice'
import '../App.css'

function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams()
  const evaluationId = searchParams.get('evaluation')
  const [showForm, setShowForm] = useState(false)
  const [showPaywall, setShowPaywall] = useState(false)
  const [showReportIssue, setShowReportIssue] = useState(false)
  const [reportIssueContext, setReportIssueContext] = useState({})
  const [formData, setFormData] = useState({
    grant_id: '',
    grant_url: '',  // For Option A: in-memory grants
    project_id: '',
    use_llm: true,
    // Optional grant context fields (for supplementing extracted data)
    grant_name: '',
    grant_description: '',
    grant_deadline: '',
    grant_decision_date: '',
    grant_award_amount: '',
    grant_award_structure: '',
    grant_eligibility: '',
    grant_preferred_applicants: '',
    grant_application_requirements: '',
    grant_reporting_requirements: '',
    grant_restrictions: '',
    grant_mission: '',
  })
  const [useUrlInput, setUseUrlInput] = useState(true)  // Default to URL input (Option A)
  const [extractedGrantData, setExtractedGrantData] = useState(null)  // Store extracted data
  const [showReviewForm, setShowReviewForm] = useState(false)  // Show review/edit form
  const [extractingGrant, setExtractingGrant] = useState(false)  // Extraction in progress
  const [showAllEvaluations, setShowAllEvaluations] = useState(false)  // Toggle for showing all evaluations

  const queryClient = useQueryClient()

  const { data: projects, isLoading: projectsLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await api.get('/api/v1/projects/')
      // Ensure we always return an array, even if API returns unexpected format
      return Array.isArray(response.data) ? response.data : []
    },
  })

  const { data: evaluations, isLoading: evaluationsLoading } = useQuery({
    queryKey: ['evaluations'],
    queryFn: async () => {
      const response = await api.get('/api/v1/evaluations/')
      return response.data
    },
  })

  // Get single evaluation if ID provided
  const { data: singleEvaluation, isLoading: singleLoading } = useQuery({
    queryKey: ['evaluation', evaluationId],
    queryFn: async () => {
      const response = await api.get(`/api/v1/evaluations/${evaluationId}`)
      return response.data
    },
    enabled: !!evaluationId,
  })

  // Get credit status to check if paywall needed
  const { data: creditStatus } = useQuery({
    queryKey: ['creditStatus'],
    queryFn: async () => {
      const response = await api.get('/api/v1/payments/status')
      return response.data
    },
  })

  // Get pricing information (for display)
  const { data: pricing } = useQuery({
    queryKey: ['pricing'],
    queryFn: async () => {
      const response = await api.get('/api/v1/payments/pricing')
      return response.data
    },
  })

  const { data: grants } = useQuery({
    queryKey: ['grants'],
    queryFn: async () => {
      const response = await api.get('/api/v1/grants/')
      return response.data
    },
  })

  // Mutation to extract grant data from URL (for review/edit before evaluation)
  // This does NOT create a grant in the DB - only extracts data for user review
  const extractGrantMutation = useMutation({
    mutationFn: async (url) => {
      // Use extract endpoint - no DB grant creation, just returns extracted data
      const response = await api.post('/api/v1/grants/extract', {
        source_url: url,
        name: null,
      })
      return response.data
    },
    onSuccess: (grantData) => {
      // Populate form with extracted data
      setExtractedGrantData(grantData)
      setFormData(prev => ({
        ...prev,
        grant_name: grantData.name || '',
        grant_description: grantData.description || '',
        grant_deadline: grantData.deadline || '',
        grant_decision_date: grantData.decision_date || '',
        grant_award_amount: grantData.award_amount || '',
        grant_award_structure: grantData.award_structure || '',
        grant_eligibility: grantData.eligibility || '',
        grant_preferred_applicants: grantData.preferred_applicants || '',
        grant_application_requirements: Array.isArray(grantData.application_requirements) 
          ? grantData.application_requirements.join('\n') 
          : (grantData.application_requirements || ''),
        grant_reporting_requirements: grantData.reporting_requirements || '',
        grant_restrictions: Array.isArray(grantData.restrictions)
          ? grantData.restrictions.join('\n')
          : (grantData.restrictions || ''),
        grant_mission: grantData.mission || '',
      }))
      setShowReviewForm(true)  // Show review/edit form
      setExtractingGrant(false)
    },
    onError: (error) => {
      setExtractingGrant(false)
      
      // Extract error message from response
      let errorMessage = 'Failed to extract grant information from URL'
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail
      } else if (error.response?.data?.message) {
        errorMessage = error.response.data.message
      } else if (error.message) {
        errorMessage = error.message
      }
      
      // Log full error for debugging
      console.error('Grant extraction error:', {
        message: errorMessage,
        status: error.response?.status,
        data: error.response?.data,
        fullError: error
      })
      
      // Show user-friendly error message
      if (errorMessage.includes('ANTHROPIC_API_KEY') || errorMessage.includes('API key') || errorMessage.includes('authentication')) {
        alert('Grant extraction is temporarily unavailable. Please contact support or try again later.')
      } else if (errorMessage.includes('timeout') || errorMessage.includes('timed out')) {
        alert('The grant page took too long to load. Please try again or check if the URL is correct.')
      } else if (errorMessage.includes('connection') || errorMessage.includes('fetch')) {
        alert('Unable to reach the grant page. Please check your internet connection and the URL.')
      } else if (errorMessage.includes('404') || errorMessage.includes('not found')) {
        alert('Grant page not found. Please check the URL and try again.')
      } else if (errorMessage.includes('403') || errorMessage.includes('Access denied')) {
        alert('Access denied. The grant page may block automated access. Please try a different URL.')
      } else if (errorMessage.includes('500') || errorMessage.includes('Server error')) {
        alert('The grant website is temporarily unavailable. Please try again later.')
      } else {
        // Show the actual error message from backend
        alert(`Error: ${errorMessage}`)
      }
    },
  })

  const evaluateMutation = useMutation({
    mutationFn: async (data) => {
      const response = await api.post('/api/v1/evaluations/', data)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries(['evaluations'])
      queryClient.invalidateQueries(['creditStatus'])
      setShowForm(false)
      setShowPaywall(false)
      setFormData({
        grant_id: '',
        grant_url: '',
        project_id: '',
        use_llm: true,
        grant_name: '',
        grant_description: '',
        grant_deadline: '',
        grant_decision_date: '',
        grant_award_amount: '',
        grant_award_structure: '',
        grant_eligibility: '',
        grant_preferred_applicants: '',
        grant_application_requirements: '',
        grant_reporting_requirements: '',
        grant_restrictions: '',
        grant_mission: '',
      })
      setUseUrlInput(true)  // Reset to URL input (Option A)
      setShowReviewForm(false)
      setExtractedGrantData(null)
      // Navigate to the new evaluation on dashboard
      setSearchParams({ evaluation: data.id.toString() })
    },
    onError: (error) => {
      // If payment required, show paywall
      if (error.response?.status === 402) {
        setShowPaywall(true)
        setShowForm(false)
      }
    },
  })

  const handleExtractGrant = async () => {
    if (!formData.grant_url.trim()) {
      alert('Please enter a grant URL')
      return
    }
    setExtractingGrant(true)
    extractGrantMutation.mutate(formData.grant_url.trim())
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    
    // If review form is showing but user hasn't extracted yet, extract first
    if (useUrlInput && !showReviewForm && formData.grant_url.trim()) {
      handleExtractGrant()
      return
    }
    
    // Prepare evaluation data - either grant_id (indexed) or grant_url (in-memory)
    const evaluationData = {
        project_id: formData.project_id ? parseInt(formData.project_id) : null,
        use_llm: formData.use_llm,
    }
    
    if (useUrlInput) {
      // Option A: In-memory grant (no DB grant)
      if (!formData.grant_url.trim()) {
        alert('Please enter a grant URL')
        return
      }
      evaluationData.grant_url = formData.grant_url.trim()
      
      // Include user-provided grant context (if any fields were filled)
      if (formData.grant_name) evaluationData.grant_name = formData.grant_name
      if (formData.grant_description) evaluationData.grant_description = formData.grant_description
      if (formData.grant_deadline) evaluationData.grant_deadline = formData.grant_deadline
      if (formData.grant_decision_date) evaluationData.grant_decision_date = formData.grant_decision_date
      if (formData.grant_award_amount) evaluationData.grant_award_amount = formData.grant_award_amount
      if (formData.grant_award_structure) evaluationData.grant_award_structure = formData.grant_award_structure
      if (formData.grant_eligibility) evaluationData.grant_eligibility = formData.grant_eligibility
      if (formData.grant_preferred_applicants) evaluationData.grant_preferred_applicants = formData.grant_preferred_applicants
      if (formData.grant_application_requirements) {
        // Convert newline-separated string to array
        evaluationData.grant_application_requirements = formData.grant_application_requirements
          .split('\n')
          .map(line => line.trim())
          .filter(line => line.length > 0)
      }
      if (formData.grant_reporting_requirements) evaluationData.grant_reporting_requirements = formData.grant_reporting_requirements
      if (formData.grant_restrictions) {
        // Convert newline-separated string to array
        evaluationData.grant_restrictions = formData.grant_restrictions
          .split('\n')
          .map(line => line.trim())
          .filter(line => line.length > 0)
      }
      if (formData.grant_mission) evaluationData.grant_mission = formData.grant_mission
    } else {
      // Option B: Indexed grant (from DB)
      if (!formData.grant_id) {
        alert('Please select a grant from the list')
        return
      }
      evaluationData.grant_id = parseInt(formData.grant_id)
    }
    
    // Check if free assessment available (first assessment with defaults)
    if (creditStatus?.free_available) {
      evaluateMutation.mutate(evaluationData)
    } else if (creditStatus?.bundle_credits > 0) {
      // User has bundle credits - use them directly
      evaluateMutation.mutate(evaluationData)
        // No payment_reference needed - bundle credits will be used automatically
    } else {
      // No free assessment or bundle credits - show paywall for full context assessment
      setShowPaywall(true)
      setShowForm(false)
    }
  }

  const handleInitializePayment = async (paymentType = 'standard') => {
    try {
      const response = await api.post('/api/v1/payments/initialize', {
        country_code: null,
        payment_type: paymentType,
      })
      // Store form data in sessionStorage (better than localStorage for payment data)
      sessionStorage.setItem('pending_evaluation', JSON.stringify({
        grant_id: formData.grant_id,
        project_id: formData.project_id,
        use_llm: formData.use_llm,
      }))
      // Redirect to Paystack - reference will be in URL when user returns
      window.location.href = response.data.authorization_url
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to initialize payment')
    }
  }

  const handleRefineEvaluation = async (evaluationId) => {
    try {
      // Initialize refinement payment
      const paymentResponse = await api.post('/api/v1/payments/initialize', {
        country_code: null,
        payment_type: 'refinement',
      })
      // Store evaluation ID in sessionStorage
      sessionStorage.setItem('pending_refinement_evaluation_id', evaluationId.toString())
      // Redirect to Paystack - reference will be in URL when user returns
      window.location.href = paymentResponse.data.authorization_url
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to initialize refinement payment')
    }
  }

  // Check for pending assessment or refinement after payment return
  useEffect(() => {
    // Get payment reference from URL parameters (preferred) or sessionStorage (fallback)
    const urlParams = new URLSearchParams(window.location.search)
    const refFromUrl = urlParams.get('reference') || urlParams.get('ref') || urlParams.get('trxref')
    
    // Check for pending standard assessment
    const pendingEvalData = sessionStorage.getItem('pending_evaluation')
    const pendingRef = refFromUrl || sessionStorage.getItem('pending_payment_reference')
    
    if (pendingEvalData && pendingRef) {
      const evalData = JSON.parse(pendingEvalData)
      // Check if payment was successful
      const checkPaymentAndEvaluate = async () => {
        try {
          const paymentCheck = await api.get('/api/v1/payments/history')
          const payment = paymentCheck.data.find(p => 
            (p.paystack_reference === pendingRef || p.reference === pendingRef) && 
            p.status === 'succeeded' &&
            p.payment_type === 'standard'
          )
          
          if (payment) {
            // Payment succeeded, now create evaluation
            try {
              const evalResponse = await api.post('/api/v1/evaluations/', {
                grant_id: parseInt(evalData.grant_id),
                project_id: evalData.project_id ? parseInt(evalData.project_id) : null,
                use_llm: evalData.use_llm,
                payment_reference: pendingRef,
              })
              
              // Clear pending state
              sessionStorage.removeItem('pending_evaluation')
              sessionStorage.removeItem('pending_payment_reference')
              
              // Clean up URL parameters
              urlParams.delete('reference')
              urlParams.delete('ref')
              urlParams.delete('trxref')
              window.history.replaceState({}, '', `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`)
              
              // Refresh evaluations and navigate to result
              queryClient.invalidateQueries(['evaluations'])
              queryClient.invalidateQueries(['creditStatus'])
              setSearchParams({ evaluation: evalResponse.data.id.toString() })
            } catch (evalError) {
              console.error('Evaluation failed:', evalError)
              alert(evalError.response?.data?.detail || 'Failed to create evaluation')
            }
          }
        } catch (error) {
          console.error('Payment check failed:', error)
        }
      }
      
      checkPaymentAndEvaluate()
    }
    
    // Check for pending refinement
    const pendingEvalId = sessionStorage.getItem('pending_refinement_evaluation_id')
    const pendingRefineRef = refFromUrl || sessionStorage.getItem('pending_refinement_reference')
    
    if (pendingEvalId && pendingRefineRef) {
      // Check if payment was successful by verifying the reference
      const checkPaymentAndRefine = async () => {
        try {
          // Verify payment succeeded
          const paymentCheck = await api.get('/api/v1/payments/history')
          const payment = paymentCheck.data.find(p => 
            (p.paystack_reference === pendingRefineRef || p.reference === pendingRefineRef) && 
            p.status === 'succeeded' &&
            p.payment_type === 'refinement'
          )
          
          if (payment) {
            // Payment succeeded, now refine
            try {
              const refineResponse = await api.post('/api/v1/evaluations/refine', {
                evaluation_id: parseInt(pendingEvalId),
                payment_reference: pendingRefineRef,
              })
              
              // Clear pending state
              sessionStorage.removeItem('pending_refinement_evaluation_id')
              sessionStorage.removeItem('pending_refinement_reference')
              
              // Clean up URL parameters
              urlParams.delete('reference')
              urlParams.delete('ref')
              urlParams.delete('trxref')
              window.history.replaceState({}, '', `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`)
              
              // Refresh evaluations and navigate to refined result
              queryClient.invalidateQueries(['evaluations'])
              setSearchParams({ evaluation: refineResponse.data.id.toString() })
            } catch (refineError) {
              console.error('Refinement failed:', refineError)
              alert(refineError.response?.data?.detail || 'Failed to refine evaluation')
            }
          }
        } catch (error) {
          console.error('Payment check failed:', error)
        }
      }
      
      checkPaymentAndRefine()
    }
  }, [queryClient, setSearchParams])

  if (projectsLoading || evaluationsLoading) {
    return <div className="container">Loading...</div>
  }

  // Ensure evaluations is an array before filtering
  const evaluationsArray = Array.isArray(evaluations) ? evaluations : []
  const applyCount = evaluationsArray.filter(e => e.recommendation === 'APPLY').length || 0
  const passCount = evaluationsArray.filter(e => e.recommendation === 'PASS').length || 0
  const conditionalCount = evaluationsArray.filter(e => e.recommendation === 'CONDITIONAL').length || 0

  // If viewing single evaluation
  if (evaluationId) {
    const evaluationsArray = Array.isArray(evaluations) ? evaluations : []
    const evaluation = singleEvaluation || evaluationsArray.find(e => e.id === parseInt(evaluationId))
    
    if (singleLoading) {
      return <div className="container">Loading...</div>
    }

    if (!evaluation) {
      return <div className="container">Evaluation not found</div>
    }

    return (
      <div className="container">
        <button onClick={() => setSearchParams({})} className="btn btn-secondary" style={{ marginBottom: '1rem' }}>
          ← Back to Dashboard
        </button>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1rem' }}>
            <div>
              <h2>Evaluation #{evaluation.id}</h2>
              <p>Grant ID: {evaluation.grant_id} | Project ID: {evaluation.project_id}</p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                onClick={() => {
                  setReportIssueContext({ evaluation_id: evaluation.id, issue_type: 'technical_error' })
                  setShowReportIssue(true)
                }}
                className="btn btn-secondary"
                style={{ fontSize: '0.875rem' }}
              >
                Report Issue
              </button>
              <span
              style={{
                padding: '0.5rem 1rem',
                borderRadius: '4px',
                backgroundColor:
                  evaluation.recommendation === 'APPLY'
                    ? '#28a745'
                    : evaluation.recommendation === 'PASS'
                    ? '#dc3545'
                    : '#ffc107',
                color: 'white',
                fontWeight: 'bold',
              }}
            >
              {evaluation.recommendation}
            </span>
            </div>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <strong>Timeline:</strong> {evaluation.timeline_viability}/10
            </div>
            <div>
              <strong>Mission:</strong> {evaluation.mission_alignment}/10
            </div>
            <div>
              <strong>Winner Match:</strong> {evaluation.winner_pattern_match}/10
            </div>
            <div>
              <strong>Burden:</strong> {evaluation.application_burden}/10
            </div>
            <div>
              <strong>Structure:</strong> {evaluation.award_structure}/10
            </div>
            <div>
              <strong>Composite:</strong> {evaluation.composite_score}/10
            </div>
          </div>

          {evaluation.reasoning && (
            <div style={{ marginTop: '1rem' }}>
              <h4>Reasoning</h4>
              {Object.entries(evaluation.reasoning)
                .filter(([key]) => key !== '_paid_tier' && key !== '_free_tier_note')
                .map(([key, value]) => (
                  <div key={key} style={{ marginBottom: '0.5rem' }}>
                    <strong>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:</strong> {value}
                  </div>
                ))}
            </div>
          )}

          {evaluation.red_flags && evaluation.red_flags.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <h4 style={{ color: '#dc3545' }}>Red Flags</h4>
              <ul>
                {evaluation.red_flags.map((flag, idx) => (
                  <li key={idx}>{flag}</li>
                ))}
              </ul>
            </div>
          )}

          {evaluation.key_insights && evaluation.key_insights.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <h4>Key Insights</h4>
              <ul>
                {evaluation.key_insights.map((insight, idx) => (
                  <li key={idx}>{insight}</li>
                ))}
              </ul>
            </div>
          )}

          {evaluation.confidence_notes && evaluation.evaluation_tier === 'free' && (
            <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: '#f8f9fa', borderRadius: '4px', fontSize: '0.9rem', color: '#6b7280' }}>
              <strong>Note:</strong> {evaluation.confidence_notes}
            </div>
          )}
          
          {evaluation.confidence_notes && evaluation.evaluation_tier !== 'free' && (
            <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: '#f8f9fa', borderRadius: '4px', fontSize: '0.9rem', color: '#495057' }}>
              <strong>Confidence:</strong> {evaluation.confidence_notes}
            </div>
          )}

          {/* Paid Tier Enhancements - Only show for paid assessments (standard or refined) */}
          {/* Only show if explicitly 'standard' or 'refined' - not just "not free" */}
          {(evaluation.evaluation_tier === 'standard' || evaluation.evaluation_tier === 'refined') && (
            <div style={{ marginTop: '1.5rem', padding: '1.5rem', backgroundColor: '#e7f3ff', borderRadius: '8px', border: '2px solid #007bff' }}>
              <div style={{ marginBottom: '1.5rem' }}>
                <h3 style={{ marginTop: 0, color: '#004085', marginBottom: '0.5rem' }}>
                  ✨ Paid Assessment Insights
                </h3>
                <p style={{ margin: 0, color: '#004085', fontSize: '0.95rem', lineHeight: '1.5' }}>
                  <strong>Decision authority transferred.</strong> These insights remove ambiguity and save you hours of research. 
                  You're getting pattern knowledge, probability estimates, and strategic framing .
                </p>
              </div>
              
              {evaluation.success_probability_range && (
                <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #b3d9ff' }}>
                  <h4 style={{ color: '#004085', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    Success Probability Range
                  </h4>
                  <p style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#004085', margin: '0.5rem 0' }}>
                    {evaluation.success_probability_range}
                  </p>
                  <p style={{ margin: 0, fontSize: '0.85rem', color: '#495057', fontStyle: 'italic' }}>
                    Based on your project context, competition level, and past winner patterns. Use this to prioritize which grants deserve your time.
                  </p>
                </div>
              )}
              
              {evaluation.decision_gates && evaluation.decision_gates.length > 0 && (
                <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #b3d9ff' }}>
                  <h4 style={{ color: '#004085', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span>🚪</span> Decision Gates
                  </h4>
                  <p style={{ marginBottom: '0.75rem', color: '#004085', fontWeight: 'bold', fontSize: '0.95rem' }}>
                    {evaluation.recommendation === 'APPLY' || evaluation.recommendation === 'CONDITIONAL' 
                      ? 'Apply only if all conditions are met:'
                      : 'Would apply only if these conditions are met:'}
                  </p>
                  <ul style={{ margin: 0, paddingLeft: '1.5rem', color: '#004085' }}>
                    {evaluation.decision_gates.map((gate, idx) => (
                      <li key={idx} style={{ marginBottom: '0.5rem', lineHeight: '1.5' }}>{gate}</li>
                    ))}
                  </ul>
                  <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.85rem', color: '#495057', fontStyle: 'italic' }}>
                    These concrete conditions turn analysis into action. No guessing—just clear decision logic.
                  </p>
                </div>
              )}
              
              {evaluation.pattern_knowledge && (
                <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #b3d9ff' }}>
                  <h4 style={{ color: '#004085', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    Pattern Knowledge
                  </h4>
                  <p style={{ margin: 0, color: '#004085', fontStyle: 'italic', lineHeight: '1.6' }}>
                    {evaluation.pattern_knowledge}
                  </p>
                  <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.85rem', color: '#495057' }}>
                    <strong>Why this matters:</strong> Non-obvious insights from analyzing grant patterns. This is the kind of strategic knowledge that separates successful applicants from those wasting time.
                  </p>
                </div>
              )}
              
              {evaluation.opportunity_cost && (
                <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #b3d9ff' }}>
                  <h4 style={{ color: '#004085', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span>⚖️</span> Opportunity Cost Analysis
                  </h4>
                  <p style={{ margin: 0, color: '#004085', lineHeight: '1.6' }}>
                    {evaluation.opportunity_cost}
                  </p>
                  <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.85rem', color: '#495057', fontStyle: 'italic' }}>
                    Time is your most valuable resource. This analysis helps you allocate it where it yields the highest return.
                  </p>
                </div>
              )}
              
              {evaluation.confidence_index !== null && evaluation.confidence_index !== undefined && (
                <div style={{ padding: '1rem', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #b3d9ff' }}>
                  <h4 style={{ color: '#004085', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    Assessment Confidence
                  </h4>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
                    <div style={{ flex: 1, backgroundColor: '#cfe2ff', borderRadius: '4px', height: '24px', position: 'relative', overflow: 'hidden' }}>
                      <div 
                        style={{ 
                          width: `${(evaluation.confidence_index * 100).toFixed(0)}%`,
                          backgroundColor: evaluation.confidence_index >= 0.7 ? '#28a745' : evaluation.confidence_index >= 0.5 ? '#ffc107' : '#dc3545',
                          height: '100%',
                          transition: 'width 0.3s ease'
                        }}
                      />
                    </div>
                    <span style={{ fontWeight: 'bold', color: '#004085', minWidth: '50px', fontSize: '1.1rem' }}>
                      {(evaluation.confidence_index * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.85rem', color: '#495057', fontStyle: 'italic' }}>
                    Based on data completeness and verification. Higher confidence = more reliable recommendation.
                  </p>
                </div>
              )}
              
              {/* Value Summary Footer */}
              <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#004085', borderRadius: '6px', color: '#ffffff' }}>
                <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: '1.6', textAlign: 'center' }}>
                  <strong>You've unlocked the full value:</strong> Decisive recommendations, pattern insights, and time-saving analysis 
                  that free assessments can't provide. This is what you paid for—clarity, authority, and strategic advantage.
                </p>
              </div>
            </div>
          )}

          {/* Free Tier - Show Premium Features as Locked/Upgrade Prompts */}
          {evaluation.evaluation_tier === 'free' && !evaluation.is_refinement && (() => {
            // Get project name for personalization
            const project = projects?.find(p => p.id === evaluation.project_id)
            const projectName = project?.name || 'your project'
            const grantName = evaluation.grant_name || 'this grant'
            
            return (
              <div style={{ marginTop: '1.5rem' }}>
                <div style={{ 
                  padding: '1rem', 
                  backgroundColor: '#fff3cd', 
                  borderRadius: '6px', 
                  borderLeft: '4px solid #ffc107',
                  marginBottom: '1.5rem'
                }}>
                  <p style={{ margin: 0, fontSize: '0.9rem', color: '#856404' }}>
                    <strong>Free assessment.</strong> Unlock premium insights below with a paid assessment.
                  </p>
                </div>

                {/* Premium Features Preview - Locked */}
                <div style={{ 
                  padding: '1.5rem', 
                  backgroundColor: '#f8f9fa', 
                  borderRadius: '8px', 
                  border: '2px dashed #dee2e6',
                  position: 'relative',
                  opacity: 0.7
                }}>
                  <div style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    backgroundColor: '#ffc107',
                    color: '#856404',
                    padding: '0.25rem 0.75rem',
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    fontWeight: 'bold'
                  }}>
                    UPGRADE TO UNLOCK
                  </div>
                  
                  <div style={{ marginBottom: '1.5rem' }}>
                    <p style={{ margin: 0, color: '#495057', fontSize: '1.1rem', lineHeight: '1.6', marginBottom: '0.75rem', fontWeight: '600' }}>
                      Stop wasting 20+ hours on low-probability applications.
                    </p>
                    <p style={{ margin: 0, color: '#6c757d', fontSize: '0.95rem', lineHeight: '1.6' }}>
                      Your Free Match score is ready. Now, let's see if it's worth the effort.
                    </p>
                  </div>
                  
                  <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #dee2e6' }}>
                    <h4 style={{ color: '#6c757d', marginBottom: '0.5rem', fontWeight: '600' }}>
                      Success Probability Estimate
                    </h4>
                    <p style={{ margin: 0, color: '#6c757d', fontStyle: 'italic' }}>
                      Get your specific Success Probability Range for <strong>{projectName}</strong>. Get a precise % range based on past winner patterns for this specific funder.
                    </p>
                  </div>
                  
                  <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #dee2e6' }}>
                    <h4 style={{ color: '#6c757d', marginBottom: '0.5rem', fontWeight: '600' }}>
                      Hard APPLY/PASS Gates
                    </h4>
                    <p style={{ margin: 0, color: '#6c757d', fontStyle: 'italic' }}>
                      We give you a definitive verdict so you don't waste days on a 'No-Go' project. If you can't meet the grants specific criteria in 30 minutes, we'll tell you to pass—saving you days of wasted effort.
                    </p>
                  </div>
                  
                  <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: '#ffffff', borderRadius: '6px', border: '1px solid #dee2e6' }}>
                    <h4 style={{ color: '#6c757d', marginBottom: '0.5rem', fontWeight: '600' }}>
                      Opportunity Cost Analysis
                    </h4>
                    <p style={{ margin: 0, color: '#6c757d', fontStyle: 'italic' }}>
                      Is <strong>{grantName}</strong> your best option right now? See if your 10+ hours would yield a higher ROI on 3 smaller, faster grants.
                    </p>
                  </div>
                </div>
                
                {/* Unlock Button - Prominent CTA */}
                <div style={{ 
                  marginTop: '2rem', 
                  padding: '1.5rem', 
                  backgroundColor: '#ffffff', 
                  borderRadius: '12px', 
                  border: '3px solid #007bff',
                  boxShadow: '0 4px 12px rgba(0, 123, 255, 0.15)',
                  textAlign: 'center' 
                }}>
                  <h3 style={{ marginTop: 0, marginBottom: '1rem', color: '#004085' }}>
                    Ready to Unlock Full Insights?
                  </h3>
                  <p style={{ marginBottom: '1.5rem', color: '#495057', fontSize: '0.95rem' }}>
                    Don't leave your application to chance. Get the strategy you need before writing the first word.
                  </p>
                  <button
                    onClick={() => handleRefineEvaluation(evaluation.id)}
                    className="btn btn-primary"
                    style={{
                      padding: '1.25rem 3rem',
                      fontSize: '1.2rem',
                      fontWeight: 'bold',
                      backgroundColor: '#007bff',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      boxShadow: '0 4px 12px rgba(0, 123, 255, 0.4)',
                      transition: 'all 0.2s ease',
                      minWidth: '280px'
                    }}
                    onMouseOver={(e) => {
                      e.target.style.backgroundColor = '#0056b3'
                      e.target.style.transform = 'translateY(-2px)'
                      e.target.style.boxShadow = '0 6px 16px rgba(0, 123, 255, 0.5)'
                    }}
                    onMouseOut={(e) => {
                      e.target.style.backgroundColor = '#007bff'
                      e.target.style.transform = 'translateY(0)'
                      e.target.style.boxShadow = '0 4px 12px rgba(0, 123, 255, 0.4)'
                    }}
                  >
                    🔓 Unlock My Full Assessment
                  </button>
                  <p style={{ marginTop: '1rem', fontSize: '0.9rem', color: '#6b7280', marginBottom: 0 }}>
                    Price shown in USD. Paystack will automatically convert to your local currency when you pay.
                  </p>
                </div>
              </div>
            )
          })()}

          {/* Refined Assessment Badge */}
          {evaluation.evaluation_tier === 'refined' && (
            <div style={{ 
              marginTop: '1.5rem', 
              padding: '1rem', 
              backgroundColor: '#d4edda', 
              borderRadius: '8px', 
              border: '2px solid #28a745',
              borderLeft: '6px solid #28a745'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <strong style={{ color: '#155724' }}>Refined Assessment</strong>
                <span style={{ color: '#155724', marginLeft: 'auto' }}>
                  Full project context included
                </span>
              </div>
            </div>
          )}

          {/* Standard Assessment Badge */}
          {evaluation.evaluation_tier === 'standard' && (
            <div style={{ 
              marginTop: '1.5rem', 
              padding: '0.75rem', 
              backgroundColor: '#e7f3ff', 
              borderRadius: '4px', 
              borderLeft: '4px solid #007bff'
            }}>
              <span style={{ color: '#004085', fontSize: '0.9rem' }}>
                ✓ Standard Assessment
              </span>
            </div>
          )}
        </div>
        {showReportIssue && (
          <ReportIssue 
            onClose={() => {
              setShowReportIssue(false)
              setReportIssueContext({})
            }}
            initialData={reportIssueContext}
          />
        )}
      </div>
    )
  }

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1>Dashboard</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn btn-primary">
          {showForm ? 'Cancel' : 'New Evaluation'}
        </button>
      </div>

      {showPaywall && (
        <div className="card" style={{ textAlign: 'center', maxWidth: '600px', margin: '0 auto 2rem' }}>
          <h2>Get Full Context Assessment</h2>
          <p style={{ marginBottom: '1.5rem' }}>
            You've used your free assessment with defaults. Get detailed, personalized grant evaluations with full project context.
          </p>
          <p style={{ marginBottom: '1rem', fontSize: '0.9rem', color: '#6b7280' }}>
            Charged in local currency. Final amount shown at checkout.
          </p>
          
          {/* Show bundle credits if available */}
          {creditStatus?.bundle_credits > 0 && (
            <div style={{ 
              marginBottom: '1.5rem', 
              padding: '1rem', 
              backgroundColor: '#e7f3ff', 
              borderRadius: '8px',
              border: '2px solid #007bff'
            }}>
              <p style={{ margin: 0, fontWeight: 'bold', color: '#004085' }}>
                You have {creditStatus.bundle_credits} bundle credit{creditStatus.bundle_credits > 1 ? 's' : ''} available!
              </p>
              <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: '#004085' }}>
                You can create {creditStatus.bundle_credits} more assessment{creditStatus.bundle_credits > 1 ? 's' : ''} without additional payment.
              </p>
            </div>
          )}
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div style={{ 
              padding: '1.5rem', 
              border: '2px solid #007bff', 
              borderRadius: '8px',
              backgroundColor: '#f8f9fa'
            }}>
              <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Single Assessment</h3>
              <p style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#007bff', margin: '0.5rem 0' }}>
                {pricing?.standard?.usd_equivalent ? `$${pricing.standard.usd_equivalent.toFixed(0)}` : '$7'}
              </p>
              <p style={{ fontSize: '0.85rem', color: '#6b7280', margin: '0.5rem 0' }}>
                One full context assessment
              </p>
              <button 
                onClick={() => handleInitializePayment('standard')} 
                className="btn btn-primary" 
                style={{ width: '100%', marginTop: '0.5rem' }}
              >
                {pricing?.standard?.usd_equivalent ? `Pay $${pricing.standard.usd_equivalent.toFixed(0)}` : 'Pay $7'}
              </button>
            </div>
            
            <div style={{ 
              padding: '1.5rem', 
              border: '2px solid #28a745', 
              borderRadius: '8px',
              backgroundColor: '#f8f9fa',
              position: 'relative'
            }}>
              <div style={{
                position: 'absolute',
                top: '-10px',
                right: '10px',
                backgroundColor: '#28a745',
                color: 'white',
                padding: '0.25rem 0.75rem',
                borderRadius: '12px',
                fontSize: '0.75rem',
                fontWeight: 'bold'
              }}>
                BEST VALUE
              </div>
              <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Bundle</h3>
              <p style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#28a745', margin: '0.5rem 0' }}>
                {pricing?.bundle?.usd_equivalent ? `$${pricing.bundle.usd_equivalent.toFixed(0)}` : '$18'}
              </p>
              <p style={{ fontSize: '0.85rem', color: '#6b7280', margin: '0.5rem 0' }}>
                3 full context assessments
              </p>
              <p style={{ fontSize: '0.75rem', color: '#155724', margin: '0.5rem 0', fontWeight: 'bold' }}>
                Save $1 per assessment
              </p>
              <button 
                onClick={() => handleInitializePayment('bundle')} 
                className="btn" 
                style={{ 
                  width: '100%', 
                  marginTop: '0.5rem',
                  backgroundColor: '#28a745',
                  color: 'white',
                  borderColor: '#28a745'
                }}
              >
                {pricing?.bundle?.usd_equivalent ? `Pay $${pricing.bundle.usd_equivalent.toFixed(0)}` : 'Pay $18'}
              </button>
            </div>
          </div>
          
          <button 
            onClick={() => {
              setShowPaywall(false)
              setShowForm(true)
            }} 
            className="btn btn-secondary" 
            style={{ width: '100%' }}
          >
            Cancel
          </button>
        </div>
      )}

      {showForm && !showPaywall && (
        <div className="card" style={{ marginBottom: '2rem' }}>
          <h2>Evaluate Grant</h2>
          <form onSubmit={handleSubmit}>
            {projects && projects.length > 0 && (
              <div className="form-group">
                <label>Project (optional - leave blank for default)</label>
                <select
                  value={formData.project_id}
                  onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
                >
                  <option value="">Use default project</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="form-group">
              <label>Grant URL *</label>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setUseUrlInput(!useUrlInput)}
                  className="btn btn-secondary"
                  style={{ 
                    fontSize: '0.875rem', 
                    padding: '0.5rem 1rem',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {useUrlInput ? '← Select from index' : '+ Enter URL'}
                </button>
              </div>
              {useUrlInput ? (
                <div>
                  {!showReviewForm ? (
                    // Step 1: URL input and extraction
                    <>
                      <input
                        type="url"
                        value={formData.grant_url}
                        onChange={(e) => setFormData({ ...formData, grant_url: e.target.value })}
                        placeholder="https://example.com/grant-opportunity"
                        className="landing-input"
                        style={{ width: '100%', padding: '0.625rem 0.875rem', fontSize: '0.875rem' }}
                        disabled={extractingGrant || extractGrantMutation.isLoading}
                        required
                      />
                      <button
                        type="button"
                        onClick={handleExtractGrant}
                        className="btn btn-primary"
                        disabled={!formData.grant_url.trim() || extractingGrant || extractGrantMutation.isLoading}
                        style={{ 
                          marginTop: '0.5rem',
                          fontSize: '0.875rem',
                          padding: '0.5rem 1rem'
                        }}
                      >
                        {extractingGrant || extractGrantMutation.isLoading ? 'Extracting...' : 'Extract Grant Information'}
                      </button>
                      <div style={{ 
                        marginTop: '0.5rem', 
                        padding: '0.75rem', 
                        backgroundColor: '#f0f9ff', 
                        borderRadius: '6px',
                        border: '1px solid #bae6fd',
                        fontSize: '0.85rem',
                        color: '#0369a1'
                      }}>
                        <strong>Private Evaluation:</strong> This grant URL will only be used for your evaluation. 
                        It will not be added to the public grant index.
                      </div>
                    </>
                  ) : (
                    // Step 2: Review/edit extracted grant data
                    <div style={{ 
                      padding: '1rem', 
                      backgroundColor: '#f8f9fa', 
                      borderRadius: '8px',
                      border: '1px solid #dee2e6',
                      maxHeight: '600px',
                      overflowY: 'auto'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: '600' }}>Review & Edit Grant Information</h4>
                        <button
                          type="button"
                          onClick={() => {
                            setShowReviewForm(false)
                            setExtractedGrantData(null)
                          }}
                          className="btn btn-secondary"
                          style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                        >
                          Change URL
                        </button>
                      </div>
                      <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '1rem' }}>
                        Review the extracted information and add any missing details that the AI couldn't find.
                      </p>
                      
                      <div style={{ display: 'grid', gap: '0.75rem' }}>
                        <div>
                          <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Grant Name *</label>
                          <input
                            type="text"
                            value={formData.grant_name}
                            onChange={(e) => setFormData({ ...formData, grant_name: e.target.value })}
                            className="landing-input"
                            style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem' }}
                            required
                          />
                        </div>
                        
                        <div>
                          <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Description</label>
                          <textarea
                            value={formData.grant_description}
                            onChange={(e) => setFormData({ ...formData, grant_description: e.target.value })}
                            className="landing-input"
                            style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem', minHeight: '80px', resize: 'vertical' }}
                            placeholder="Grant description or overview"
                          />
                        </div>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                          <div>
                            <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Deadline</label>
                            <input
                              type="text"
                              value={formData.grant_deadline}
                              onChange={(e) => setFormData({ ...formData, grant_deadline: e.target.value })}
                              className="landing-input"
                              style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem' }}
                              placeholder="e.g., March 15, 2024"
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Decision Date</label>
                            <input
                              type="text"
                              value={formData.grant_decision_date}
                              onChange={(e) => setFormData({ ...formData, grant_decision_date: e.target.value })}
                              className="landing-input"
                              style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem' }}
                              placeholder="e.g., June 2024"
                            />
                          </div>
                        </div>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                          <div>
                            <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Award Amount</label>
                            <input
                              type="text"
                              value={formData.grant_award_amount}
                              onChange={(e) => setFormData({ ...formData, grant_award_amount: e.target.value })}
                              className="landing-input"
                              style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem' }}
                              placeholder="e.g., $50,000 - $100,000"
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Award Structure</label>
                            <input
                              type="text"
                              value={formData.grant_award_structure}
                              onChange={(e) => setFormData({ ...formData, grant_award_structure: e.target.value })}
                              className="landing-input"
                              style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem' }}
                              placeholder="e.g., One-time payment"
                            />
                          </div>
                        </div>
                        
                        <div>
                          <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Eligibility</label>
                          <textarea
                            value={formData.grant_eligibility}
                            onChange={(e) => setFormData({ ...formData, grant_eligibility: e.target.value })}
                            className="landing-input"
                            style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem', minHeight: '60px', resize: 'vertical' }}
                            placeholder="Who is eligible to apply?"
                          />
                        </div>
                        
                        <div>
                          <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Preferred Applicants</label>
                          <input
                            type="text"
                            value={formData.grant_preferred_applicants}
                            onChange={(e) => setFormData({ ...formData, grant_preferred_applicants: e.target.value })}
                            className="landing-input"
                            style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem' }}
                            placeholder="e.g., Early-stage startups, Non-profits"
                          />
                        </div>
                        
                        <div>
                          <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Application Requirements (one per line)</label>
                          <textarea
                            value={formData.grant_application_requirements}
                            onChange={(e) => setFormData({ ...formData, grant_application_requirements: e.target.value })}
                            className="landing-input"
                            style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem', minHeight: '80px', resize: 'vertical' }}
                            placeholder="Project proposal&#10;Budget breakdown&#10;Team bios"
                          />
                        </div>
                        
                        <div>
                          <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Reporting Requirements</label>
                          <textarea
                            value={formData.grant_reporting_requirements}
                            onChange={(e) => setFormData({ ...formData, grant_reporting_requirements: e.target.value })}
                            className="landing-input"
                            style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem', minHeight: '60px', resize: 'vertical' }}
                            placeholder="What reporting is required if awarded?"
                          />
                        </div>
                        
                        <div>
                          <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Restrictions (one per line)</label>
                          <textarea
                            value={formData.grant_restrictions}
                            onChange={(e) => setFormData({ ...formData, grant_restrictions: e.target.value })}
                            className="landing-input"
                            style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem', minHeight: '60px', resize: 'vertical' }}
                            placeholder="No overhead costs&#10;Must be used within 12 months"
                          />
                        </div>
                        
                        <div>
                          <label style={{ fontSize: '0.85rem', fontWeight: '500', display: 'block', marginBottom: '0.25rem' }}>Mission</label>
                          <textarea
                            value={formData.grant_mission}
                            onChange={(e) => setFormData({ ...formData, grant_mission: e.target.value })}
                            className="landing-input"
                            style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.875rem', minHeight: '60px', resize: 'vertical' }}
                            placeholder="Grant mission or focus area"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
              <select
                value={formData.grant_id}
                onChange={(e) => setFormData({ ...formData, grant_id: e.target.value })}
                required
              >
                  <option value="">Select grant from index</option>
                {grants?.map((grant) => (
                  <option key={grant.id} value={grant.id}>
                    {grant.name}
                  </option>
                ))}
              </select>
              )}
            </div>
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem' }}>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#6b7280', fontWeight: '500' }}>
                LLM Evaluator
              </p>
            </div>
            
            <PrivacySecurityNotice compact={true} />
            
            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={
                evaluateMutation.isLoading || 
                extractingGrant || 
                extractGrantMutation.isLoading ||
                (useUrlInput && !showReviewForm && formData.grant_url.trim())
              }
              title={
                useUrlInput && !showReviewForm && formData.grant_url.trim() 
                  ? "Please extract grant information first" 
                  : ""
              }
            >
              {evaluateMutation.isLoading 
                ? 'Assessing...' 
                : (useUrlInput && !showReviewForm && formData.grant_url.trim())
                  ? 'Extract Grant Information First'
                  : 'Assess Grant'
              }
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="btn btn-secondary"
              style={{ marginLeft: '0.5rem' }}
            >
              Cancel
            </button>
          </form>
        </div>
      )}
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="card">
          <h3>Projects</h3>
          <p style={{ fontSize: '2rem', fontWeight: 'bold' }}>{projects?.length || 0}</p>
        </div>
        <div className="card">
          <h3>Evaluations</h3>
          <p style={{ fontSize: '2rem', fontWeight: 'bold' }}>{evaluations?.length || 0}</p>
        </div>
        <div className="card">
          <h3>Apply</h3>
          <p style={{ fontSize: '2rem', fontWeight: 'bold', color: '#28a745' }}>{applyCount}</p>
        </div>
        <div className="card">
          <h3>Pass</h3>
          <p style={{ fontSize: '2rem', fontWeight: 'bold', color: '#dc3545' }}>{passCount}</p>
        </div>
        <div className="card">
          <h3>Conditional</h3>
          <p style={{ fontSize: '2rem', fontWeight: 'bold', color: '#ffc107' }}>{conditionalCount}</p>
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0 }}>
            All Evaluations
            {evaluations && evaluations.length > 0 && (
              <span style={{
                marginLeft: '0.5rem',
                fontSize: '1rem',
                fontWeight: 'normal',
                color: '#6b7280'
              }}>
                ({evaluations.length} total)
              </span>
            )}
          </h2>
          {evaluations && evaluations.length > 5 && (
            <button
              onClick={() => setShowAllEvaluations(!showAllEvaluations)}
              className="btn btn-secondary"
              style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
            >
              {showAllEvaluations ? 'Show Less' : 'Show All'}
            </button>
            )
          })()}
        </div>
        {evaluations && evaluations.length > 0 ? (
          <div>
            {(showAllEvaluations || evaluations.length <= 5 
              ? evaluations 
              : evaluations.slice(0, 5)
            ).map((evaluation) => (
              <div 
                key={evaluation.id} 
                className="card" 
                style={{ 
                  marginBottom: '1rem', 
                  cursor: 'pointer',
                  transition: 'transform 0.2s',
                }}
                onClick={() => setSearchParams({ evaluation: evaluation.id.toString() })}
                onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1rem' }}>
                  <div>
                    <h3>Evaluation #{evaluation.id}</h3>
                    <p>Grant ID: {evaluation.grant_id} | Project ID: {evaluation.project_id}</p>
                    {/* Tier Badge */}
                    {evaluation.evaluation_tier === 'free' && (
                      <span style={{ 
                        display: 'inline-block',
                        marginTop: '0.5rem',
                        padding: '0.25rem 0.75rem',
                        backgroundColor: '#fff3cd',
                        color: '#856404',
                        borderRadius: '4px',
                        fontSize: '0.85rem',
                        fontWeight: 'bold'
                      }}>
                        Free Tier
                      </span>
                    )}
                    {evaluation.evaluation_tier === 'refined' && (
                      <span style={{ 
                        display: 'inline-block',
                        marginTop: '0.5rem',
                        padding: '0.25rem 0.75rem',
                        backgroundColor: '#d4edda',
                        color: '#155724',
                        borderRadius: '4px',
                        fontSize: '0.85rem',
                        fontWeight: 'bold'
                      }}>
                        ✓ Refined
                      </span>
                    )}
                    {evaluation.evaluation_tier === 'standard' && (
                      <span style={{ 
                        display: 'inline-block',
                        marginTop: '0.5rem',
                        padding: '0.25rem 0.75rem',
                        backgroundColor: '#e7f3ff',
                        color: '#004085',
                        borderRadius: '4px',
                        fontSize: '0.85rem'
                      }}>
                        Standard
                      </span>
                    )}
                  </div>
                  <span
                    style={{
                      padding: '0.5rem 1rem',
                      borderRadius: '4px',
                      backgroundColor:
                        evaluation.recommendation === 'APPLY'
                          ? '#28a745'
                          : evaluation.recommendation === 'PASS'
                          ? '#dc3545'
                          : '#ffc107',
                      color: 'white',
                      fontWeight: 'bold',
                    }}
                  >
                    {evaluation.recommendation}
                  </span>
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
                  <div>
                    <strong>Timeline:</strong> {evaluation.timeline_viability}/10
                  </div>
                  <div>
                    <strong>Mission:</strong> {evaluation.mission_alignment}/10
                  </div>
                  <div>
                    <strong>Winner Match:</strong> {evaluation.winner_pattern_match}/10
                  </div>
                  <div>
                    <strong>Burden:</strong> {evaluation.application_burden}/10
                  </div>
                  <div>
                    <strong>Structure:</strong> {evaluation.award_structure}/10
                  </div>
                  <div>
                    <strong>Composite:</strong> {evaluation.composite_score}/10
                  </div>
                </div>
              </div>
              ))}
            </div>
          ) : (
            <p>No evaluations yet. Create an evaluation to see grant recommendations.</p>
          )
        })()}
      </div>
      {showReportIssue && (
        <ReportIssue 
          onClose={() => {
            setShowReportIssue(false)
            setReportIssueContext({})
          }}
          initialData={reportIssueContext}
        />
      )}
    </div>
  )
}

export default Dashboard

