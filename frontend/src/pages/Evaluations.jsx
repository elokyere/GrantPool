import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import FreeAssessmentDisplay from '../components/FreeAssessmentDisplay'
import PaidAssessmentDisplay from '../components/PaidAssessmentDisplay'
import LegacyEvaluationBadge from '../components/LegacyEvaluationBadge'
import '../App.css'

function Evaluations() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [showForm, setShowForm] = useState(false)
  const [showPaywall, setShowPaywall] = useState(false)
  const [formData, setFormData] = useState({
    grant_id: '',
    project_id: '',
    use_llm: true,
  })

  const queryClient = useQueryClient()

  // Get single evaluation if ID provided
  const { data: singleEvaluation, isLoading: singleLoading } = useQuery({
    queryKey: ['evaluation', id],
    queryFn: async () => {
      const response = await api.get(`/api/v1/evaluations/${id}`)
      return response.data
    },
    enabled: !!id,
  })

  const { data: evaluations, isLoading } = useQuery({
    queryKey: ['evaluations'],
    queryFn: async () => {
      const response = await api.get('/api/v1/evaluations/')
      return response.data
    },
    enabled: !id, // Only fetch list if not viewing single evaluation
    refetchOnWindowFocus: true, // Refetch when user returns to tab
    staleTime: 0, // Always consider data stale, refetch immediately when invalidated
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

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await api.get('/api/v1/projects/')
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

  const evaluateMutation = useMutation({
    mutationFn: async (data) => {
      const response = await api.post('/api/v1/evaluations/', data)
      return response.data
    },
    onSuccess: (data) => {
      // Force immediate refetch of evaluations
      queryClient.refetchQueries({ queryKey: ['evaluations'] })
      queryClient.invalidateQueries(['creditStatus'])
      setShowForm(false)
      setShowPaywall(false)
      setFormData({
        grant_id: '',
        project_id: '',
        use_llm: true,
      })
      // Navigate to the new evaluation
      navigate(`/dashboard/evaluations/${data.id}`)
    },
    onError: (error) => {
      // If payment required, show paywall
      if (error.response?.status === 402) {
        setShowPaywall(true)
        setShowForm(false)
      }
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    
    // Check if free assessment available (first assessment with defaults)
    if (creditStatus?.free_available) {
      evaluateMutation.mutate({
        grant_id: parseInt(formData.grant_id),
        project_id: formData.project_id ? parseInt(formData.project_id) : null,
        use_llm: formData.use_llm,
      })
    } else if (creditStatus?.bundle_credits > 0) {
      // User has bundle credits - use them directly
      evaluateMutation.mutate({
        grant_id: parseInt(formData.grant_id),
        project_id: formData.project_id ? parseInt(formData.project_id) : null,
        use_llm: formData.use_llm,
        // No payment_reference needed - bundle credits will be used automatically
      })
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

  // Check for pending assessment after payment return
  useEffect(() => {
    // Get payment reference from URL parameters (preferred) or sessionStorage (fallback)
    const urlParams = new URLSearchParams(window.location.search)
    const refFromUrl = urlParams.get('reference') || urlParams.get('ref') || urlParams.get('trxref')
    
    const pendingEvalData = sessionStorage.getItem('pending_evaluation')
    const pendingRef = refFromUrl || sessionStorage.getItem('pending_payment_reference')
    
    if (pendingEvalData && pendingRef) {
      const evalData = JSON.parse(pendingEvalData)
      const checkPaymentAndEvaluate = async () => {
        try {
          const paymentCheck = await api.get('/api/v1/payments/history')
          const payment = paymentCheck.data.find(p => 
            (p.paystack_reference === pendingRef || p.reference === pendingRef) && 
            p.status === 'succeeded' &&
            p.payment_type === 'standard'
          )
          
          if (payment) {
            try {
              const evalResponse = await api.post('/api/v1/evaluations/', {
                grant_id: parseInt(evalData.grant_id),
                project_id: evalData.project_id ? parseInt(evalData.project_id) : null,
                use_llm: evalData.use_llm,
                payment_reference: pendingRef,
              })
              
              sessionStorage.removeItem('pending_evaluation')
              sessionStorage.removeItem('pending_payment_reference')
              
              // Clean up URL parameters
              urlParams.delete('reference')
              urlParams.delete('ref')
              urlParams.delete('trxref')
              window.history.replaceState({}, '', `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`)
              
              queryClient.invalidateQueries(['evaluations'])
              queryClient.invalidateQueries(['creditStatus'])
              navigate(`/dashboard/evaluations/${evalResponse.data.id}`)
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
  }, [queryClient, navigate])

  // If viewing single evaluation
  if (id) {
    if (singleLoading) {
      return (
        <div className="container" style={{ textAlign: 'center', padding: '3rem' }}>
          <div style={{ fontSize: '1.125rem', color: '#6b7280', marginBottom: '1rem' }}>Loading evaluation...</div>
          <div style={{ fontSize: '0.875rem', color: '#9ca3af' }}>Please wait while we fetch the evaluation from the database.</div>
        </div>
      )
    }

    if (!singleEvaluation) {
      return <div className="container">Evaluation not found</div>
    }

    const evaluation = singleEvaluation
    const assessmentType = evaluation.assessment_type || (evaluation.is_legacy ? null : 'free')
    
    return (
      <div className="container">
        <button onClick={() => navigate('/dashboard/evaluations')} className="btn btn-secondary" style={{ marginBottom: '1rem' }}>
          ← Back to Evaluations
        </button>
        
        {evaluation.is_legacy && (
          <LegacyEvaluationBadge 
            evaluation={evaluation}
            onCreateNew={() => {
              navigate('/dashboard/evaluations')
              setShowForm(true)
            }}
          />
        )}

        {assessmentType === 'free' ? (
          <FreeAssessmentDisplay evaluation={evaluation} />
        ) : assessmentType === 'paid' ? (
          <PaidAssessmentDisplay evaluation={evaluation} />
        ) : (
          // Legacy evaluation - show basic display
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1rem' }}>
              <div>
                <h2>Evaluation #{evaluation.id}</h2>
                <p>Grant ID: {evaluation.grant_id} | Project ID: {evaluation.project_id}</p>
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
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <strong>Timeline:</strong> {evaluation.timeline_viability}/10
              </div>
              <div>
                <strong>Mission:</strong> {evaluation.mission_alignment ?? 'N/A'}/10
              </div>
              <div>
                <strong>Winner Match:</strong> {evaluation.winner_pattern_match ?? 'N/A'}/10
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
                  .filter(([key]) => !key.startsWith('_'))
                  .map(([key, value]) => (
                    <div key={key} style={{ marginBottom: '0.5rem' }}>
                      <strong>{key}:</strong> {typeof value === 'string' ? value : JSON.stringify(value)}
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
                <div>
                  {evaluation.key_insights.map((insight, idx) => (
                    <p key={idx} style={{ marginBottom: '0.5rem', marginTop: 0 }}>{insight}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  if (isLoading) {
    return <div className="container">Loading...</div>
  }

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1>Evaluations</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn btn-primary">
          {showForm ? 'Cancel' : 'New Evaluation'}
        </button>
      </div>

      {showPaywall && (
        <div className="card" style={{ textAlign: 'center', maxWidth: '600px', margin: '0 auto' }}>
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
              backgroundColor: '#ffffff', 
              borderRadius: '4px',
              border: '1px solid #e5e7eb',
              boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
            }}>
              <p style={{ margin: 0, fontWeight: '600', color: '#374151' }}>
                You have {creditStatus.bundle_credits} bundle credit{creditStatus.bundle_credits > 1 ? 's' : ''} available
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
        <div className="card">
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
              <label>Grant *</label>
              <select
                value={formData.grant_id}
                onChange={(e) => setFormData({ ...formData, grant_id: e.target.value })}
                required
              >
                <option value="">Select grant</option>
                {grants?.map((grant) => (
                  <option key={grant.id} value={grant.id}>
                    {grant.name}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ marginTop: '1rem', marginBottom: '0.5rem' }}>
              <p style={{ margin: 0, fontSize: '0.9rem', color: '#6b7280', fontWeight: '500' }}>
                LLM Evaluator
              </p>
            </div>
            <button type="submit" className="btn btn-primary" disabled={evaluateMutation.isLoading}>
              {evaluateMutation.isLoading ? 'Evaluating...' : 'Evaluate'}
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

      <div>
        {evaluations && evaluations.length > 0 ? (
          evaluations.map((evaluation) => {
            const assessmentType = evaluation.assessment_type || (evaluation.is_legacy ? null : 'free')
            
            return (
              <div key={evaluation.id}>
                {assessmentType === 'free' ? (
                  <FreeAssessmentDisplay evaluation={evaluation} />
                ) : assessmentType === 'paid' ? (
                  <PaidAssessmentDisplay evaluation={evaluation} />
                ) : (
                  // Legacy evaluation - show basic card
                  <div className="card">
                    <LegacyEvaluationBadge 
                      evaluation={evaluation}
                      onCreateNew={() => setShowForm(true)}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1rem' }}>
                      <div>
                        <h3>Evaluation #{evaluation.id}</h3>
                        <p>Grant ID: {evaluation.grant_id} | Project ID: {evaluation.project_id}</p>
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
                        <strong>Mission:</strong> {evaluation.mission_alignment ?? 'N/A'}/10
                      </div>
                      <div>
                        <strong>Winner Match:</strong> {evaluation.winner_pattern_match ?? 'N/A'}/10
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
                )}
              </div>
            )
          })
        ) : !isLoading ? (
          <div className="card">
            <p>No evaluations yet. Create an evaluation to see grant recommendations.</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default Evaluations

