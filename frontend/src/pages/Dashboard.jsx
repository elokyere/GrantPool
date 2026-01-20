import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import ReportIssue from '../components/ReportIssue'
import PrivacySecurityNotice from '../components/PrivacySecurityNotice'
import FreeAssessmentDisplay from '../components/FreeAssessmentDisplay'
import PaidAssessmentDisplay from '../components/PaidAssessmentDisplay'
import LegacyEvaluationBadge from '../components/LegacyEvaluationBadge'
import CreditConversionNotification from '../components/CreditConversionNotification'
import '../App.css'

function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams()
  const evaluationId = searchParams.get('evaluation')
  const showDataContribution = searchParams.get('show_data_contribution') === 'true'
  const [showForm, setShowForm] = useState(false)
  const [showPaywall, setShowPaywall] = useState(false)
  const [showReportIssue, setShowReportIssue] = useState(false)
  const [showPaymentConfirmation, setShowPaymentConfirmation] = useState(false)
  const [selectedPaymentType, setSelectedPaymentType] = useState('standard')
  const [reportIssueContext, setReportIssueContext] = useState({})
  const [showDataContributionModal, setShowDataContributionModal] = useState(false)
  const [pendingGrantUrl, setPendingGrantUrl] = useState(null)
  const [pendingGrantName, setPendingGrantName] = useState('')
  const [isDataContributionFlow, setIsDataContributionFlow] = useState(false) // Track if we're in data contribution flow
  const [showProjectFormInModal, setShowProjectFormInModal] = useState(false) // Show project form inside modal
  const [showGrantDataForm, setShowGrantDataForm] = useState(false) // Show grant data editing form
  const [extractedGrantDataForModal, setExtractedGrantDataForModal] = useState(null) // Store extracted grant data for editing in modal
  const [extractingGrantData, setExtractingGrantData] = useState(false) // Loading state for extraction
  const [grantDataForm, setGrantDataForm] = useState({
    name: '',
    description: '',
    deadline: '',
    decision_date: '',
    award_amount: '',
    award_structure: '',
    eligibility: '',
    preferred_applicants: '',
    application_requirements: '',
    reporting_requirements: '',
    restrictions: '',
    mission: '',
  })
  const [projectFormData, setProjectFormData] = useState({
    name: '',
    description: '',
    stage: '',
    funding_need: '',
    urgency: 'moderate',
    founder_type: '',
    timeline_constraints: '',
  })
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
  const [evaluationSort, setEvaluationSort] = useState('most_recent')  // Sort option: 'most_recent', 'oldest_first', 'by_score'
  const [showAllEvaluationsModal, setShowAllEvaluationsModal] = useState(false)  // Modal for viewing all evaluations
  const [isAssessing, setIsAssessing] = useState(false)  // Local state to track assessment in progress
  const [pendingEvaluationId, setPendingEvaluationId] = useState(null)  // Track newly created evaluation ID

  const queryClient = useQueryClient()

  // Helper function to count words
  const countWords = (text) => {
    return text.trim() === '' ? 0 : text.trim().split(/\s+/).length
  }

  // Helper function to limit text to 50 words
  const limitToWords = (text, maxWords) => {
    const words = text.trim().split(/\s+/)
    if (words.length <= maxWords) return text
    return words.slice(0, maxWords).join(' ')
  }

  const { data: projects, isLoading: projectsLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      try {
        const response = await api.get('/api/v1/projects/')
        // Ensure we always return an array, even if API returns unexpected format
        const data = response?.data
        if (Array.isArray(data)) {
          return data
        }
        // If data exists but isn't an array, log and return empty array
        if (data) {
          console.warn('Projects API returned non-array data:', data)
        }
        return []
      } catch (error) {
        console.error('Error fetching projects:', error)
        return []
      }
    },
    placeholderData: [], // Ensure React Query always has an array
    initialData: [], // Set initial data to empty array
    select: (data) => Array.isArray(data) ? data : [], // Normalize data even from cache
  })

  const { data: evaluations, isLoading: evaluationsLoading } = useQuery({
    queryKey: ['evaluations'],
    queryFn: async () => {
      try {
        const response = await api.get('/api/v1/evaluations/')
        // Ensure we always return an array, even if API returns unexpected format
        const data = response?.data
        // Check if response is HTML (API routing issue)
        if (typeof data === 'string' && data.trim().startsWith('<!')) {
          console.error('Evaluations API returned HTML instead of JSON. Check VITE_API_URL configuration.')
          return []
        }
        if (Array.isArray(data)) {
          return data
        }
        // If data exists but isn't an array, log and return empty array
        if (data) {
          console.warn('Evaluations API returned non-array data:', data)
        }
        return []
      } catch (error) {
        console.error('Error fetching evaluations:', error)
        return []
      }
    },
    placeholderData: [], // Ensure React Query always has an array
    initialData: [], // Set initial data to empty array
    select: (data) => Array.isArray(data) ? data : [], // Normalize data even from cache
    refetchOnWindowFocus: true, // Refetch when user returns to tab
    staleTime: 0, // Always consider data stale, refetch immediately when invalidated
  })

  // Get single evaluation if ID provided
  const { data: singleEvaluation, isLoading: singleLoading, refetch: refetchEvaluation } = useQuery({
    queryKey: ['evaluation', evaluationId],
    queryFn: async () => {
      const response = await api.get(`/api/v1/evaluations/${evaluationId}`)
      return response.data
    },
    enabled: !!evaluationId,
    refetchInterval: (query) => {
      // If evaluation is loading and we have an evaluationId, poll every 2 seconds
      // Stop polling once we have data with composite_score
      const data = query.state.data
      if (data && data.composite_score !== null && data.composite_score !== undefined) {
        return false // Stop polling
      }
      return evaluationId ? 2000 : false // Poll every 2 seconds if evaluationId exists
    },
    refetchOnWindowFocus: true,
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
      try {
        const response = await api.get('/api/v1/grants/')
        // Ensure we always return an array, even if API returns unexpected format
        const data = response?.data
        // Check if response is HTML (API routing issue)
        if (typeof data === 'string' && data.trim().startsWith('<!')) {
          console.error('Grants API returned HTML instead of JSON. Check VITE_API_URL configuration.')
          return []
        }
        if (Array.isArray(data)) {
          return data
        }
        // If data exists but isn't an array, log and return empty array
        if (data) {
          console.warn('Grants API returned non-array data:', data)
        }
        return []
      } catch (error) {
        console.error('Error fetching grants:', error)
        return []
      }
    },
    placeholderData: [], // Ensure React Query always has an array
    initialData: [], // Set initial data to empty array
    select: (data) => Array.isArray(data) ? data : [], // Normalize data even from cache
  })

  // Lightweight dashboard summary (counts) for faster initial load
  const {
    data: dashboardSummary,
    isLoading: dashboardLoadingRaw,
    isFetching: dashboardFetching,
  } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: async () => {
      const response = await api.get('/api/v1/users/me/dashboard')
      return response.data
    },
    staleTime: 15000, // reuse data for 15s
    refetchOnWindowFocus: true,
  })
  const dashboardLoading = (dashboardLoadingRaw || dashboardFetching) && !dashboardSummary

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

  // Mutation to create project
  const createProjectMutation = useMutation({
    mutationFn: async (data) => {
      const response = await api.post('/api/v1/projects/', data)
      return response.data
    },
    onSuccess: async (projectData) => {
      queryClient.invalidateQueries(['projects'])
      // After project is created, automatically create evaluation with pending grant
      // Include grant data if user edited it
      const grantUrlToUse = pendingGrantUrl || sessionStorage.getItem('pending_grant_url')
      if (grantUrlToUse) {
        // Pass grant data form if user edited grant data - filter out empty strings
        const grantDataToUse = showGrantDataForm ? (() => {
          const data = {}
          if (grantDataForm.name?.trim() || pendingGrantName?.trim()) {
            data.grant_name = (grantDataForm.name || pendingGrantName).trim()
          }
          if (grantDataForm.description?.trim()) {
            data.grant_description = grantDataForm.description.trim()
          }
          if (grantDataForm.deadline?.trim()) {
            data.grant_deadline = grantDataForm.deadline.trim()
          }
          if (grantDataForm.decision_date?.trim()) {
            data.grant_decision_date = grantDataForm.decision_date.trim()
          }
          if (grantDataForm.award_amount?.trim()) {
            data.grant_award_amount = grantDataForm.award_amount.trim()
          }
          if (grantDataForm.award_structure?.trim()) {
            data.grant_award_structure = grantDataForm.award_structure.trim()
          }
          if (grantDataForm.eligibility?.trim()) {
            data.grant_eligibility = grantDataForm.eligibility.trim()
          }
          if (grantDataForm.preferred_applicants?.trim()) {
            data.grant_preferred_applicants = grantDataForm.preferred_applicants.trim()
          }
          if (grantDataForm.application_requirements?.trim()) {
            const items = grantDataForm.application_requirements.split('\n').filter(l => l.trim())
            if (items.length > 0) {
              data.grant_application_requirements = items
            }
          }
          if (grantDataForm.reporting_requirements?.trim()) {
            data.grant_reporting_requirements = grantDataForm.reporting_requirements.trim()
          }
          if (grantDataForm.restrictions?.trim()) {
            const items = grantDataForm.restrictions.split('\n').filter(l => l.trim())
            if (items.length > 0) {
              data.grant_restrictions = items
            }
          }
          if (grantDataForm.mission?.trim()) {
            data.grant_mission = grantDataForm.mission.trim()
          }
          return Object.keys(data).length > 0 ? data : null
        })() : null
        await handleCreateEvaluationFromPending(projectData.id, grantDataToUse)
      }
      // Reset form
      setProjectFormData({
        name: '',
        description: '',
        stage: '',
        funding_need: '',
        urgency: 'moderate',
        founder_type: '',
        timeline_constraints: '',
      })
      setShowProjectFormInModal(false)
    },
    onError: (err) => {
      alert(err.response?.data?.detail || 'Failed to create project')
    },
  })

  const evaluateMutation = useMutation({
    mutationFn: async (data) => {
      const response = await api.post('/api/v1/evaluations/', data)
      return response.data
    },
    onSuccess: (data) => {
      // Store the new evaluation ID and keep loading state active
      setPendingEvaluationId(data.id.toString())
      
      // Immediately set the evaluation in the cache so it's available right away
      queryClient.setQueryData(['evaluation', data.id.toString()], data)
      
      // Also add it to the evaluations list cache
      queryClient.setQueryData(['evaluations'], (oldData) => {
        if (Array.isArray(oldData)) {
          // Check if evaluation already exists in the list
          const exists = oldData.some(e => e && e.id === data.id)
          if (!exists) {
            return [data, ...oldData]
          }
          return oldData
        }
        return [data]
      })
      
      // Force refetch to ensure we have the latest data
      queryClient.refetchQueries({ queryKey: ['evaluations'] })
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
      setIsAssessing(false)  // Clear loading state on error
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
    
    // Set loading state immediately
    setIsAssessing(true)
    
    // Check if free assessment available (first assessment with defaults)
    if (creditStatus?.free_available) {
      evaluateMutation.mutate(evaluationData)
    } else if (creditStatus?.bundle_credits > 0) {
      // User has bundle credits - use them directly
      evaluateMutation.mutate(evaluationData)
        // No payment_reference needed - bundle credits will be used automatically
    } else {
      // No free assessment or bundle credits - show paywall for full context assessment
      setIsAssessing(false)  // Clear loading state
      setShowPaywall(true)
      setShowForm(false)
    }
  }

  const handleInitializePayment = async (paymentType = 'standard') => {
    // Show confirmation dialog first
    setSelectedPaymentType(paymentType)
    setShowPaymentConfirmation(true)
  }

  const confirmPayment = async () => {
    try {
      setShowPaymentConfirmation(false)
      const response = await api.post('/api/v1/payments/initialize', {
        country_code: null,
        payment_type: selectedPaymentType,
      })
      // Store form data in sessionStorage (better than localStorage for payment data)
      // Include all grant data, not just grant_id
      sessionStorage.setItem('pending_evaluation', JSON.stringify({
        grant_id: formData.grant_id,
        grant_url: formData.grant_url,
        project_id: formData.project_id,
        use_llm: formData.use_llm,
        // Include all grant context fields
        grant_name: formData.grant_name,
        grant_description: formData.grant_description,
        grant_deadline: formData.grant_deadline,
        grant_decision_date: formData.grant_decision_date,
        grant_award_amount: formData.grant_award_amount,
        grant_award_structure: formData.grant_award_structure,
        grant_eligibility: formData.grant_eligibility,
        grant_preferred_applicants: formData.grant_preferred_applicants,
        grant_application_requirements: formData.grant_application_requirements,
        grant_reporting_requirements: formData.grant_reporting_requirements,
        grant_restrictions: formData.grant_restrictions,
        grant_mission: formData.grant_mission,
      }))
      // Redirect to Paystack - callback will redirect back to dashboard
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
    const paymentStatus = urlParams.get('payment') // 'success', 'failed', or 'error'
    const refFromUrl = urlParams.get('reference') || urlParams.get('ref') || urlParams.get('trxref')
    
    // Show payment status message
    if (paymentStatus === 'success') {
      // Payment successful - will be handled below
    } else if (paymentStatus === 'failed') {
      alert('Payment failed. Please try again or contact support.')
      // Clean up URL
      urlParams.delete('payment')
      urlParams.delete('reference')
      window.history.replaceState({}, '', `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`)
    } else if (paymentStatus === 'error') {
      const errorMsg = urlParams.get('message') || 'An error occurred during payment'
      alert(`Payment error: ${errorMsg}`)
      // Clean up URL
      urlParams.delete('payment')
      urlParams.delete('reference')
      urlParams.delete('message')
      window.history.replaceState({}, '', `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`)
    }
    
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
              // Prepare evaluation data with all grant information
              const evaluationData = {
                project_id: evalData.project_id ? parseInt(evalData.project_id) : null,
                use_llm: evalData.use_llm,
                payment_reference: pendingRef,
              }
              
              // Include grant_id if available, otherwise use grant_url and other fields
              if (evalData.grant_id) {
                evaluationData.grant_id = parseInt(evalData.grant_id)
              } else if (evalData.grant_url) {
                evaluationData.grant_url = evalData.grant_url
                // Include any additional grant context fields
                if (evalData.grant_name) evaluationData.grant_name = evalData.grant_name
                if (evalData.grant_description) evaluationData.grant_description = evalData.grant_description
                if (evalData.grant_deadline) evaluationData.grant_deadline = evalData.grant_deadline
                if (evalData.grant_decision_date) evaluationData.grant_decision_date = evalData.grant_decision_date
                if (evalData.grant_award_amount) evaluationData.grant_award_amount = evalData.grant_award_amount
                if (evalData.grant_award_structure) evaluationData.grant_award_structure = evalData.grant_award_structure
                if (evalData.grant_eligibility) evaluationData.grant_eligibility = evalData.grant_eligibility
                if (evalData.grant_preferred_applicants) evaluationData.grant_preferred_applicants = evalData.grant_preferred_applicants
                if (evalData.grant_application_requirements) {
                  evaluationData.grant_application_requirements = Array.isArray(evalData.grant_application_requirements)
                    ? evalData.grant_application_requirements
                    : evalData.grant_application_requirements.split('\n').filter(l => l.trim())
                }
                if (evalData.grant_reporting_requirements) evaluationData.grant_reporting_requirements = evalData.grant_reporting_requirements
                if (evalData.grant_restrictions) {
                  evaluationData.grant_restrictions = Array.isArray(evalData.grant_restrictions)
                    ? evalData.grant_restrictions
                    : evalData.grant_restrictions.split('\n').filter(l => l.trim())
                }
                if (evalData.grant_mission) evaluationData.grant_mission = evalData.grant_mission
              }
              
              const evalResponse = await api.post('/api/v1/evaluations/', evaluationData)
              
              // Clear pending state
              sessionStorage.removeItem('pending_evaluation')
              sessionStorage.removeItem('pending_payment_reference')
              
              // Clean up URL parameters
              urlParams.delete('reference')
              urlParams.delete('ref')
              urlParams.delete('trxref')
              window.history.replaceState({}, '', `${window.location.pathname}${urlParams.toString() ? '?' + urlParams.toString() : ''}`)
              
              // Refresh evaluations and navigate to result
              queryClient.refetchQueries({ queryKey: ['evaluations'] })
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
              queryClient.refetchQueries({ queryKey: ['evaluations'] })
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

  // Handle data contribution modal for first-time users from landing page
  // Check both query param AND sessionStorage (in case redirect dropped the param)
  useEffect(() => {
    // Only check if modal isn't already shown and we don't have a pending evaluation
    if (showDataContributionModal || pendingEvaluationId) {
      return
    }

    const grantUrl = sessionStorage.getItem('pending_grant_url')
    const grantName = sessionStorage.getItem('pending_grant_name') || ''
    
    // Show modal if query param is present OR if sessionStorage has pending grant
    // AND we don't already have the grant URL in state
    if ((showDataContribution || grantUrl) && grantUrl && !pendingGrantUrl) {
      console.log('Showing data contribution modal for grant:', grantUrl)
      setPendingGrantUrl(grantUrl)
      setPendingGrantName(grantName)
      setShowDataContributionModal(true)
      // Remove the query parameter if present
      if (showDataContribution) {
        setSearchParams({})
      }
      // Don't clear sessionStorage yet - wait until evaluation is created
    }
  }, [showDataContribution, setSearchParams, showDataContributionModal, pendingGrantUrl, pendingEvaluationId])

  // Also check on initial mount in case sessionStorage was set before component mounted
  useEffect(() => {
    if (!showDataContributionModal && !pendingEvaluationId && !pendingGrantUrl) {
      const grantUrl = sessionStorage.getItem('pending_grant_url')
      const grantName = sessionStorage.getItem('pending_grant_name') || ''
      
      if (grantUrl) {
        console.log('Found pending grant URL on mount:', grantUrl)
        setPendingGrantUrl(grantUrl)
        setPendingGrantName(grantName)
        setShowDataContributionModal(true)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount

  // Extract grant data first (for user to review/edit)
  const handleExtractGrantData = async () => {
    const grantUrlToUse = pendingGrantUrl || sessionStorage.getItem('pending_grant_url')
    if (!grantUrlToUse) {
      alert('No grant URL found')
      return
    }

    setExtractingGrantData(true)
    try {
      const response = await api.post('/api/v1/grants/extract', {
        source_url: grantUrlToUse,
        name: null,
      })
      
      const extracted = response.data
      setExtractedGrantData(extracted)
      
      // Populate grant data form with extracted data
      setGrantDataForm({
        name: extracted.name || '',
        description: extracted.description || '',
        deadline: extracted.deadline || '',
        decision_date: extracted.decision_date || '',
        award_amount: extracted.award_amount || '',
        award_structure: extracted.award_structure || '',
        eligibility: extracted.eligibility || '',
        preferred_applicants: Array.isArray(extracted.preferred_applicants) 
          ? extracted.preferred_applicants.join('\n') 
          : (extracted.preferred_applicants || ''),
        application_requirements: Array.isArray(extracted.application_requirements)
          ? extracted.application_requirements.join('\n')
          : (extracted.application_requirements || ''),
        reporting_requirements: extracted.reporting_requirements || '',
        restrictions: Array.isArray(extracted.restrictions)
          ? extracted.restrictions.join('\n')
          : (extracted.restrictions || ''),
        mission: extracted.mission || '',
      })
      
      setShowGrantDataForm(true)
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to extract grant data')
    } finally {
      setExtractingGrantData(false)
    }
  }

  // Handler to create evaluation with project and grant data
  const handleCreateEvaluationFromPending = async (projectId = null, grantDataOverride = null) => {
    // Get grant URL from state or sessionStorage (in case state was lost)
    const grantUrlToUse = pendingGrantUrl || sessionStorage.getItem('pending_grant_url')
    const grantNameToUse = pendingGrantName || sessionStorage.getItem('pending_grant_name') || ''
    
    if (!grantUrlToUse) {
      console.error('No pending grant URL found')
      return
    }

    setIsAssessing(true)
    setShowDataContributionModal(false)
    setShowGrantDataForm(false)

    try {
      // Prepare grant context from form data (if user edited it)
      // Only include fields that have actual values (not empty strings)
      const buildGrantContext = (formData) => {
        const context = {}
        if (formData.name?.trim()) context.grant_name = formData.name.trim()
        if (formData.description?.trim()) context.grant_description = formData.description.trim()
        if (formData.deadline?.trim()) context.grant_deadline = formData.deadline.trim()
        if (formData.decision_date?.trim()) context.grant_decision_date = formData.decision_date.trim()
        if (formData.award_amount?.trim()) context.grant_award_amount = formData.award_amount.trim()
        if (formData.award_structure?.trim()) context.grant_award_structure = formData.award_structure.trim()
        if (formData.eligibility?.trim()) context.grant_eligibility = formData.eligibility.trim()
        if (formData.reporting_requirements?.trim()) context.grant_reporting_requirements = formData.reporting_requirements.trim()
        if (formData.mission?.trim()) context.grant_mission = formData.mission.trim()
        
        // Handle list fields - convert to array if there's content
        // NOTE: grant_preferred_applicants should be a STRING, not an array (backend expects str)
        if (formData.preferred_applicants?.trim()) {
          context.grant_preferred_applicants = formData.preferred_applicants.trim()
        }
        // grant_application_requirements and grant_restrictions should be arrays
        if (formData.application_requirements?.trim()) {
          const items = formData.application_requirements.split('\n').filter(l => l.trim())
          if (items.length > 0) context.grant_application_requirements = items
        }
        if (formData.restrictions?.trim()) {
          const items = formData.restrictions.split('\n').filter(l => l.trim())
          if (items.length > 0) context.grant_restrictions = items
        }
        
        return Object.keys(context).length > 0 ? context : null
      }

      const grantContext = grantDataOverride || (showGrantDataForm ? buildGrantContext(grantDataForm) : null)

      // Create evaluation with grant_url (in-memory) and optional grant context
      // Build the request object carefully - only include fields that should be sent
      const evaluationData = {
        grant_url: grantUrlToUse.trim(), // Ensure it's a string, not null/undefined
        use_llm: true,
      }
      
      // Add project_id only if provided (don't send null/undefined)
      if (projectId !== null && projectId !== undefined) {
        evaluationData.project_id = projectId
      }
      
      // Add grant context fields if available - filter out empty/null values
      if (grantContext && typeof grantContext === 'object') {
        Object.keys(grantContext).forEach(key => {
          const value = grantContext[key]
          // Only include if value is not null, undefined, or empty string
          if (value !== null && value !== undefined && value !== '') {
            // For arrays, only include if not empty
            if (Array.isArray(value)) {
              if (value.length > 0) {
                evaluationData[key] = value
              }
            } else if (typeof value === 'string' && value.trim() !== '') {
              evaluationData[key] = value.trim()
            } else {
              evaluationData[key] = value
            }
          }
        })
      }
      
      // Add grant_name if we have it from pendingGrantName but no grant context
      if (!grantContext && grantNameToUse?.trim()) {
        evaluationData.grant_name = grantNameToUse.trim()
      }

      // Debug: Log the request data
      console.log('Creating evaluation with data:', JSON.stringify(evaluationData, null, 2))
      
      // Validate required fields before sending
      if (!evaluationData.grant_url || evaluationData.grant_url.trim() === '') {
        alert('Error: Grant URL is missing or empty')
        setIsAssessing(false)
        return
      }

      const evaluationResponse = await api.post('/api/v1/evaluations/', evaluationData)

      // Clear sessionStorage now that evaluation is created
      sessionStorage.removeItem('pending_grant_url')
      sessionStorage.removeItem('pending_grant_name')

      // Navigate to the evaluation
      setPendingEvaluationId(evaluationResponse.data.id.toString())
      setSearchParams({ evaluation: evaluationResponse.data.id.toString() })
      setPendingGrantUrl(null)
      setPendingGrantName('')
      setShowGrantDataForm(false)
      setExtractedGrantDataForModal(null)
    } catch (err) {
      // Show detailed error message for 422 validation errors
      let errorMessage = 'Failed to create evaluation'
      if (err.response?.status === 422) {
        // Validation error - show the detail
        const detail = err.response?.data?.detail
        if (Array.isArray(detail)) {
          // Pydantic validation errors are arrays
          errorMessage = `Validation error: ${detail.map(d => d.msg || d).join(', ')}`
        } else if (typeof detail === 'string') {
          errorMessage = `Validation error: ${detail}`
        } else {
          errorMessage = `Validation error: ${JSON.stringify(detail)}`
        }
        console.error('Validation error details:', detail)
        if (Array.isArray(detail)) {
          detail.forEach((err, idx) => {
            console.error(`Validation error ${idx + 1}:`, {
              field: err.loc ? err.loc.join('.') : 'unknown',
              message: err.msg || err,
              type: err.type || 'unknown',
              input: err.input
            })
          })
        }
        if (evaluationData) {
          console.error('Request data that failed:', JSON.stringify(evaluationData, null, 2))
        } else {
          console.error('Request data that failed: evaluationData was not initialized')
        }
      } else {
        errorMessage = err.response?.data?.detail || err.message || errorMessage
      }
      alert(errorMessage)
      setIsAssessing(false)
    }
  }

  // Don't show full-page loading - show skeleton loaders instead for better UX
  // This prevents the jarring "0" values from appearing

  // Ensure all data is arrays - defensive programming at component level
  // This is a safety net in case query functions somehow return non-arrays
  const evaluationsArray = Array.isArray(evaluations) ? evaluations : (evaluations ? [] : [])
  const projectsArray = Array.isArray(projects) ? projects : (projects ? [] : [])
  const grantsArray = Array.isArray(grants) ? grants : (grants ? [] : [])
  
  // Effect to clear loading state once evaluation is available
  useEffect(() => {
    if (pendingEvaluationId && isAssessing) {
      const evaluationIdNum = parseInt(pendingEvaluationId)
      // Check if evaluation is available (either from single query or in array)
      const evaluationFound = singleEvaluation?.id === evaluationIdNum || 
                             evaluationsArray.some(e => e && e.id === evaluationIdNum)
      
      // Also check if single query is no longer loading (even if evaluation not found yet, it means we tried)
      if (evaluationFound || (!singleLoading && evaluationId === pendingEvaluationId)) {
        // Small delay to ensure UI has updated
        setTimeout(() => {
          setIsAssessing(false)
          setPendingEvaluationId(null)
        }, 100)
      }
    }
  }, [pendingEvaluationId, isAssessing, singleEvaluation, evaluationsArray, singleLoading, evaluationId])
  
  // Safety timeout: clear loading state after 30 seconds if evaluation doesn't load
  useEffect(() => {
    if (pendingEvaluationId && isAssessing) {
      const timeout = setTimeout(() => {
        console.warn('Evaluation loading timeout - clearing loading state')
        setIsAssessing(false)
        setPendingEvaluationId(null)
      }, 30000) // 30 seconds
      
      return () => clearTimeout(timeout)
    }
  }, [pendingEvaluationId, isAssessing])
  
  // Clear pending state if user navigates away from the evaluation
  useEffect(() => {
    if (pendingEvaluationId && evaluationId && evaluationId !== pendingEvaluationId) {
      // User navigated to a different evaluation - clear pending state
      setPendingEvaluationId(null)
      setIsAssessing(false)
    }
  }, [evaluationId, pendingEvaluationId])
  
  // Sort evaluations based on selected option
  const sortedEvaluations = [...evaluationsArray].sort((a, b) => {
    if (evaluationSort === 'most_recent') {
      // Most recent first (newest to oldest)
      const dateA = a.created_at ? new Date(a.created_at) : new Date(0)
      const dateB = b.created_at ? new Date(b.created_at) : new Date(0)
      return dateB - dateA
    } else if (evaluationSort === 'oldest_first') {
      // Oldest first
      const dateA = a.created_at ? new Date(a.created_at) : new Date(0)
      const dateB = b.created_at ? new Date(b.created_at) : new Date(0)
      return dateA - dateB
    } else if (evaluationSort === 'by_score') {
      // By composite score (highest first)
      return (b.composite_score || 0) - (a.composite_score || 0)
    }
    return 0
  })
  
  // Default: show 5 most recent as compact cards
  const defaultDisplayCount = 5
  const displayedEvaluations = sortedEvaluations.slice(0, defaultDisplayCount)
  
  // Format date for display
  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown date'
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }
  
  // Get recommendation color - muted psychology-based palette
  const getRecommendationColor = (rec) => {
    switch (rec) {
      case 'APPLY': return '#059669' // muted emerald-600
      case 'CONDITIONAL': return '#d97706' // muted amber-600
      case 'PASS': return '#dc2626' // muted red-600
      default: return '#6b7280' // muted gray-500
    }
  }
  
  // Safe filtering with additional validation
  const applyCount = evaluationsArray.filter(e => e && e.recommendation === 'APPLY').length || 0
  const passCount = evaluationsArray.filter(e => e && e.recommendation === 'PASS').length || 0
  const conditionalCount = evaluationsArray.filter(e => e && e.recommendation === 'CONDITIONAL').length || 0

  // If viewing single evaluation
  if (evaluationId) {
    // Use the already-validated evaluationsArray from above
    const evaluation = singleEvaluation || evaluationsArray.find(e => e && e.id === parseInt(evaluationId))
    
    // Check if we're waiting for a pending evaluation (newly created)
    const isWaitingForPending = pendingEvaluationId && evaluationId === pendingEvaluationId && isAssessing
    
    // Only show "Loading..." if we're not already showing the spinner overlay
    // (i.e., if this is a manual navigation, not a newly created assessment)
    if (singleLoading && !isWaitingForPending) {
      return (
        <div className="container" style={{ textAlign: 'center', padding: '3rem' }}>
          <div style={{ 
            display: 'inline-block',
            width: '40px',
            height: '40px',
            border: '4px solid #f3f4f6',
            borderTop: '4px solid #4a77e8',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            marginBottom: '1rem'
          }}></div>
          <div style={{ fontSize: '1.125rem', color: '#6b7280', marginBottom: '0.5rem', fontWeight: '500' }}>
            {isWaitingForPending ? 'Generating your assessment...' : 'Loading evaluation...'}
          </div>
          <div style={{ fontSize: '0.875rem', color: '#9ca3af' }}>
            {isWaitingForPending 
              ? 'This may take a few moments. We\'re analyzing the grant and preparing your personalized assessment.'
              : 'Please wait while we fetch the evaluation from the database.'}
          </div>
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )
    }

    // Don't show "Evaluation not found" if we're waiting for a pending evaluation
    // The spinner overlay should be visible instead
    if (!evaluation && !isWaitingForPending && !singleLoading) {
      return <div className="container">Evaluation not found</div>
    }
    
    // If we're waiting for pending evaluation but it's not loaded yet, show loading state
    // (the spinner overlay will be shown instead, but we still need to render something)
    if (!evaluation && isWaitingForPending) {
      return (
        <div className="container" style={{ textAlign: 'center', padding: '3rem' }}>
          <div style={{ fontSize: '1.125rem', color: '#6b7280', marginBottom: '1rem' }}>Loading evaluation...</div>
          <div style={{ fontSize: '0.875rem', color: '#9ca3af' }}>Please wait while we fetch the evaluation from the database.</div>
        </div>
      )
    }

    // Safety check: ensure evaluation exists before accessing properties
    if (!evaluation) {
      return (
        <div className="container" style={{ textAlign: 'center', padding: '3rem' }}>
          <div style={{ fontSize: '1.125rem', color: '#6b7280', marginBottom: '1rem' }}>Evaluation not found</div>
          <button onClick={() => setSearchParams({})} className="btn btn-secondary" style={{ marginTop: '1rem' }}>
            ← Back to Dashboard
          </button>
        </div>
      )
    }

    // Determine assessment type
    // Check assessment_type field first, then fallback to checking if it has paid-tier data
    let assessmentType = evaluation.assessment_type
    if (!assessmentType && !evaluation.is_legacy) {
      // Fallback: Check multiple indicators of paid assessment
      // 1. mission_alignment or winner_pattern_match exists (NULL for free tier)
      if (evaluation.mission_alignment !== null && evaluation.mission_alignment !== undefined) {
        assessmentType = 'paid'
      } else if (evaluation.winner_pattern_match !== null && evaluation.winner_pattern_match !== undefined) {
        assessmentType = 'paid'
      } else if (evaluation.confidence_notes && evaluation.confidence_notes.includes('Profile incomplete')) {
        // 2. "Profile incomplete" message only appears in paid assessments
        assessmentType = 'paid'
      } else {
        assessmentType = 'free'
      }
    }
    
    // Find grant data if evaluation has grant_id (indexed grant)
    const grantData = evaluation.grant_id 
      ? grantsArray.find(g => g && g.id === evaluation.grant_id)
      : null
    
    // Find project data for paid assessments
    const projectData = evaluation.project_id 
      ? projectsArray.find(p => p && p.id === evaluation.project_id)
      : null

    return (
      <div className="container">
        <button onClick={() => setSearchParams({})} className="btn btn-secondary" style={{ marginBottom: '1rem' }}>
          ← Back to Dashboard
        </button>
        
        {/* Report Issue Button - Always visible */}
        <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
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
        </div>

        {/* Render appropriate component based on assessment type */}
        {assessmentType === 'free' ? (
          <FreeAssessmentDisplay evaluation={evaluation} grantData={grantData} projectData={projectData} />
        ) : assessmentType === 'paid' ? (
          <PaidAssessmentDisplay evaluation={evaluation} projectData={projectData} grantData={grantData} />
        ) : (
          // Legacy evaluation - show basic info
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
                    ? '#059669' // muted emerald-600
                    : evaluation.recommendation === 'PASS'
                    ? '#dc2626' // muted red-600
                    : '#d97706', // muted amber-600
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

          {evaluation.red_flags && Array.isArray(evaluation.red_flags) && evaluation.red_flags.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <h4 style={{ color: '#dc3545' }}>Red Flags</h4>
              <ul>
                {evaluation.red_flags.map((flag, idx) => (
                  <li key={idx}>{flag}</li>
                ))}
              </ul>
            </div>
          )}

          {evaluation.key_insights && Array.isArray(evaluation.key_insights) && evaluation.key_insights.length > 0 && (
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

  // Define spinner and skeleton styles for loading indicators
  const spinnerStyles = `
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    @keyframes pulse {
      0%, 100% { opacity: 0.4; transform: scale(1); }
      50% { opacity: 1; transform: scale(1.2); }
    }
    @keyframes shimmer {
      0% { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
    .skeleton-pill {
      margin-top: 0.25rem;
      height: 1.8rem;
      border-radius: 999px;
      background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
      background-size: 200% 100%;
      animation: shimmer 1.2s ease-in-out infinite;
    }
  `

  return (
    <div className="container">
      <style>{spinnerStyles}</style>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1>Dashboard</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn btn-primary">
          {showForm ? 'Cancel' : 'New Evaluation'}
        </button>
      </div>

      {/* Credit Conversion Notification */}
      {creditStatus?.has_converted_refinement && (
        <CreditConversionNotification 
          hasConvertedRefinement={creditStatus.has_converted_refinement}
        />
      )}

      {/* Bundle Credits Indicator - Always Visible */}
      {creditStatus?.bundle_credits > 0 && (
        <div style={{ 
          marginBottom: '1.5rem', 
          padding: '1.25rem 1.5rem', 
          backgroundColor: '#ffffff', 
          borderRadius: '4px',
          border: '1px solid #e5e7eb',
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div>
            <p style={{ margin: 0, fontWeight: '600', color: '#374151', fontSize: '1rem' }}>
              You have {creditStatus.bundle_credits} bundle credit{creditStatus.bundle_credits > 1 ? 's' : ''} available
            </p>
            <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.875rem', color: '#6b7280' }}>
              Create {creditStatus.bundle_credits} more assessment{creditStatus.bundle_credits > 1 ? 's' : ''} without additional payment
            </p>
          </div>
          <button 
            onClick={() => setShowForm(true)} 
            className="btn" 
            style={{ 
              backgroundColor: '#4b5563',
              color: 'white',
              borderColor: '#4b5563',
              marginLeft: '1rem',
              padding: '0.5rem 1rem',
              fontSize: '0.875rem'
            }}
          >
            Create Assessment
          </button>
        </div>
      )}

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
              backgroundColor: '#ffffff', 
              borderRadius: '4px',
              border: '1px solid #e5e7eb',
              boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
            }}>
              <p style={{ margin: 0, fontWeight: '600', color: '#374151' }}>
                You have {creditStatus.bundle_credits} bundle credit{creditStatus.bundle_credits > 1 ? 's' : ''} available
              </p>
              <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: '#6b7280' }}>
                You can create {creditStatus.bundle_credits} more assessment{creditStatus.bundle_credits > 1 ? 's' : ''} without additional payment.
              </p>
            </div>
          )}
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div style={{ 
              padding: '1.5rem', 
              border: '2px solid #3b82f6', // muted blue-500
              borderRadius: '8px',
              backgroundColor: '#ffffff',
              boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)'
            }}>
              <h3 style={{ marginTop: 0, marginBottom: '0.5rem', color: '#374151' }}>Single Assessment</h3>
              <p style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#3b82f6', margin: '0.5rem 0' }}>
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
              border: '2px solid #059669', // muted emerald-600
              borderRadius: '8px',
              backgroundColor: '#ffffff',
              position: 'relative',
              boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)'
            }}>
              <div style={{
                position: 'absolute',
                top: '-10px',
                right: '10px',
                backgroundColor: '#059669', // muted emerald-600
                color: 'white',
                padding: '0.25rem 0.75rem',
                borderRadius: '12px',
                fontSize: '0.75rem',
                fontWeight: 'bold'
              }}>
                BEST VALUE
              </div>
              <h3 style={{ marginTop: 0, marginBottom: '0.5rem', color: '#374151' }}>Bundle</h3>
              <p style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#059669', margin: '0.5rem 0' }}>
                {pricing?.bundle?.usd_equivalent ? `$${pricing.bundle.usd_equivalent.toFixed(0)}` : '$18'}
              </p>
              <p style={{ fontSize: '0.85rem', color: '#6b7280', margin: '0.5rem 0' }}>
                3 full context assessments
              </p>
              <p style={{ fontSize: '0.75rem', color: '#059669', margin: '0.5rem 0', fontWeight: 'bold', padding: '0.25rem 0.5rem', backgroundColor: '#d1fae5', borderRadius: '4px', display: 'inline-block' }}>
                Save $1 per assessment
              </p>
              <button 
                onClick={() => handleInitializePayment('bundle')} 
                className="btn" 
                style={{ 
                  width: '100%', 
                  marginTop: '0.5rem',
                  backgroundColor: '#059669', // muted emerald-600
                  color: 'white',
                  borderColor: '#059669'
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

      {/* Payment Confirmation Dialog */}
      {showPaymentConfirmation && (
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
          zIndex: 1000
        }}>
          <div className="card" style={{ maxWidth: '500px', width: '90%', margin: '0 auto' }}>
            <h2>Confirm Payment</h2>
            <div style={{ marginBottom: '1.5rem' }}>
              <p><strong>Assessment Type:</strong> {selectedPaymentType === 'standard' ? 'Single Assessment' : selectedPaymentType === 'bundle' ? 'Bundle (3 Assessments)' : 'Refinement'}</p>
              <p><strong>Price:</strong> {
                selectedPaymentType === 'standard' 
                  ? (pricing?.standard?.usd_equivalent ? `$${pricing.standard.usd_equivalent.toFixed(2)}` : '$7.00')
                  : selectedPaymentType === 'bundle'
                  ? (pricing?.bundle?.usd_equivalent ? `$${pricing.bundle.usd_equivalent.toFixed(2)}` : '$18.00')
                  : (pricing?.refinement?.usd_equivalent ? `$${pricing.refinement.usd_equivalent.toFixed(2)}` : '$3.00')
              }</p>
              {formData.grant_url && (
                <p><strong>Grant URL:</strong> {formData.grant_url}</p>
              )}
              {formData.grant_name && (
                <p><strong>Grant Name:</strong> {formData.grant_name}</p>
              )}
              {formData.project_id && (
                <p><strong>Project:</strong> {projectsArray.find(p => p.id === parseInt(formData.project_id))?.name || 'Selected project'}</p>
              )}
              <p style={{ marginTop: '1rem', fontSize: '0.9rem', color: '#6b7280' }}>
                You will be redirected to Paystack to complete payment. After successful payment, your assessment will be created automatically.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button 
                onClick={() => setShowPaymentConfirmation(false)} 
                className="btn btn-secondary" 
                style={{ flex: 1 }}
              >
                Cancel
              </button>
              <button 
                onClick={confirmPayment} 
                className="btn btn-primary" 
                style={{ flex: 1 }}
              >
                Confirm & Pay
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assessment Loading Overlay */}
      {(isAssessing || evaluateMutation.isLoading || evaluateMutation.isPending) && (
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
          zIndex: 2000,
          backdropFilter: 'blur(4px)'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '12px',
            padding: '2.5rem 3rem',
            maxWidth: '500px',
            width: '90%',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            textAlign: 'center'
          }}>
            {/* Spinner */}
            <div style={{
              width: '60px',
              height: '60px',
              margin: '0 auto 1.5rem',
              border: '4px solid #e5e7eb',
              borderTop: '4px solid #3b82f6',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite'
            }}></div>
            <style>{`
              @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
              }
            `}</style>
            
            <h3 style={{ 
              margin: '0 0 0.75rem 0', 
              color: '#374151', 
              fontSize: '1.5rem',
              fontWeight: '600'
            }}>
              Preparing Your Assessment
            </h3>
            <p style={{ 
              margin: '0 0 1rem 0', 
              color: '#6b7280', 
              fontSize: '1rem',
              lineHeight: '1.5'
            }}>
              Analyzing grant details, evaluating fit, and generating personalized recommendations...
            </p>
            <div style={{
              display: 'flex',
              gap: '0.5rem',
              justifyContent: 'center',
              marginTop: '1.5rem'
            }}>
              <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#3b82f6',
                animation: 'pulse 1.4s ease-in-out infinite'
              }}></div>
              <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#3b82f6',
                animation: 'pulse 1.4s ease-in-out infinite 0.2s'
              }}></div>
              <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#3b82f6',
                animation: 'pulse 1.4s ease-in-out infinite 0.4s'
              }}></div>
            </div>
            <style>{`
              @keyframes pulse {
                0%, 100% { opacity: 0.4; transform: scale(1); }
                50% { opacity: 1; transform: scale(1.2); }
              }
            `}</style>
            <p style={{ 
              margin: '1.5rem 0 0 0', 
              color: '#9ca3af', 
              fontSize: '0.875rem',
              fontStyle: 'italic'
            }}>
              This may take 30-60 seconds
            </p>
          </div>
        </div>
      )}

      {showForm && !showPaywall && (
        <div className="card" style={{ marginBottom: '2rem' }}>
          <h2>Evaluate Grant</h2>
          <form onSubmit={handleSubmit}>
            {projectsArray.length > 0 && (
              <div className="form-group">
                <label>Project (optional - leave blank for default)</label>
                <select
                  value={formData.project_id}
                  onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
                >
                  <option value="">Use default project</option>
                  {projectsArray.map((project) => (
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
                {grantsArray.map((grant) => (
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
          {dashboardLoading ? (
            <div className="skeleton-pill" />
          ) : (
            <p style={{ fontSize: '2rem', fontWeight: 'bold' }}>
              {dashboardSummary?.projects_count ?? projectsArray.length}
            </p>
          )}
        </div>
        <div className="card">
          <h3>Evaluations</h3>
          {dashboardLoading ? (
            <div className="skeleton-pill" />
          ) : (
            <p style={{ fontSize: '2rem', fontWeight: 'bold' }}>
              {dashboardSummary?.evaluations_count ?? evaluationsArray.length}
            </p>
          )}
        </div>
        <div className="card">
          <h3>Apply</h3>
          {dashboardLoading ? (
            <div className="skeleton-pill" />
          ) : (
            <p style={{ fontSize: '2rem', fontWeight: 'bold', color: '#059669' }}>
              {dashboardSummary?.apply_count ?? applyCount}
            </p>
          )}
        </div>
        <div className="card">
          <h3>Pass</h3>
          {dashboardLoading ? (
            <div className="skeleton-pill" />
          ) : (
            <p style={{ fontSize: '2rem', fontWeight: 'bold', color: '#dc2626' }}>
              {dashboardSummary?.pass_count ?? passCount}
            </p>
          )}
        </div>
        <div className="card">
          <h3>Conditional</h3>
          {dashboardLoading ? (
            <div className="skeleton-pill" />
          ) : (
            <p style={{ fontSize: '2rem', fontWeight: 'bold', color: '#d97706' }}>
              {dashboardSummary?.conditional_count ?? conditionalCount}
            </p>
          )}
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
          <h2 style={{ margin: 0 }}>
            All Evaluations
            {evaluationsArray.length > 0 && (
              <span style={{
                marginLeft: '0.5rem',
                fontSize: '1rem',
                fontWeight: 'normal',
                color: '#6b7280'
              }}>
                ({evaluationsArray.length} total)
              </span>
            )}
          </h2>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            {evaluationsArray.length > 0 && (
              <select
                value={evaluationSort}
                onChange={(e) => setEvaluationSort(e.target.value)}
                style={{
                  padding: '0.5rem 1rem',
                  fontSize: '0.875rem',
                  borderRadius: '4px',
                  border: '1px solid #d1d5db',
                  backgroundColor: 'white',
                  cursor: 'pointer'
                }}
              >
                <option value="most_recent">Most Recent</option>
                <option value="oldest_first">Oldest First</option>
                <option value="by_score">By Score</option>
              </select>
            )}
            {evaluationsArray.length > defaultDisplayCount && (
            <button
                onClick={() => setShowAllEvaluationsModal(true)}
              className="btn btn-secondary"
              style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
            >
                View All
            </button>
          )}
        </div>
        </div>
        {evaluationsLoading ? (
          <div style={{ textAlign: 'center', padding: '2rem' }}>
            <div style={{
              width: '40px',
              height: '40px',
              border: '3px solid #e5e7eb',
              borderTop: '3px solid #3b82f6',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              margin: '0 auto 1rem'
            }}></div>
            <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>Loading evaluations...</p>
          </div>
        ) : evaluationsArray.length > 0 ? (
          <div>
            {displayedEvaluations.map((evaluation) => {
              const assessmentType = evaluation.assessment_type || (evaluation.is_legacy ? null : 'free')
              const evalGrantData = evaluation.grant_id 
                ? grantsArray.find(g => g && g.id === evaluation.grant_id)
                : null
              const evalProjectData = evaluation.project_id 
                ? projectsArray.find(p => p && p.id === evaluation.project_id)
                : null
              
              return (
              <div 
                key={evaluation.id} 
                className="card" 
                style={{ 
                  marginBottom: '1rem', 
                  cursor: 'pointer',
                  transition: 'transform 0.2s',
                    padding: '1rem'
                }}
                onClick={() => setSearchParams({ evaluation: evaluation.id.toString() })}
                onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
              >
                  {/* Compact Card View */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '0.75rem' }}>
                    <div style={{ flex: 1 }}>
                      <h4 style={{ margin: 0, marginBottom: '0.25rem' }}>
                        {evaluation.grant_name || `Grant ID: ${evaluation.grant_id || 'N/A'}`}
                      </h4>
                      <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem', color: '#6b7280', flexWrap: 'wrap' }}>
                        <span>{formatDate(evaluation.created_at)}</span>
                        <span>Score: {evaluation.composite_score}/10</span>
                        {assessmentType && (
                          <span style={{ textTransform: 'capitalize' }}>{assessmentType} Assessment</span>
                        )}
                      </div>
                    </div>
                    <span
                      style={{
                        padding: '0.375rem 0.75rem',
                        borderRadius: '4px',
                        backgroundColor: getRecommendationColor(evaluation.recommendation),
                        color: 'white',
                        fontWeight: 'bold',
                        fontSize: '0.875rem',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {evaluation.recommendation}
                    </span>
                  </div>
                  {evaluation.key_insights && evaluation.key_insights.length > 0 && (
                    <div style={{ fontSize: '0.9rem', color: '#495057', fontStyle: 'italic' }}>
                      {evaluation.key_insights[0]}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : !evaluationsLoading && (
          <p>No evaluations yet. Create an evaluation to see grant recommendations.</p>
        )}
      </div>

      {/* View All Evaluations Modal */}
      {showAllEvaluationsModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '2rem'
        }} onClick={() => setShowAllEvaluationsModal(false)}>
          <div className="card" style={{
            maxWidth: '900px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            position: 'relative'
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ margin: 0 }}>
                All Evaluations ({sortedEvaluations.length})
              </h2>
              <button
                onClick={() => setShowAllEvaluationsModal(false)}
                className="btn btn-secondary"
                style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
              >
                Close
              </button>
            </div>
            <div>
              {sortedEvaluations.map((evaluation) => {
                  // Determine assessment type with fallback
                  let assessmentType = evaluation.assessment_type
                  if (!assessmentType && !evaluation.is_legacy) {
                    if (evaluation.mission_alignment !== null && evaluation.mission_alignment !== undefined) {
                      assessmentType = 'paid'
                    } else if (evaluation.winner_pattern_match !== null && evaluation.winner_pattern_match !== undefined) {
                      assessmentType = 'paid'
                    } else if (evaluation.confidence_notes && evaluation.confidence_notes.includes('Profile incomplete')) {
                      assessmentType = 'paid'
                  } else {
                      assessmentType = 'free'
                    }
                  }
                const evalGrantData = evaluation.grant_id 
                  ? grantsArray.find(g => g && g.id === evaluation.grant_id)
                  : null
                const evalProjectData = evaluation.project_id 
                  ? projectsArray.find(p => p && p.id === evaluation.project_id)
                  : null
                
                    return (
                  <div 
                    key={evaluation.id} 
                    className="card" 
                    style={{ 
                      marginBottom: '1rem', 
                      cursor: 'pointer',
                      transition: 'transform 0.2s',
                    }}
                    onClick={() => {
                      setShowAllEvaluationsModal(false)
                      setSearchParams({ evaluation: evaluation.id.toString() })
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                    onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                  >
                    {assessmentType === 'free' ? (
                      <FreeAssessmentDisplay evaluation={evaluation} grantData={evalGrantData} projectData={evalProjectData} />
                    ) : assessmentType === 'paid' ? (
                      <PaidAssessmentDisplay evaluation={evaluation} projectData={evalProjectData} grantData={evalGrantData} />
                    ) : (
                      <div>
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
                              backgroundColor: getRecommendationColor(evaluation.recommendation),
                              color: 'white',
                              fontWeight: 'bold',
                            }}
                          >
                            {evaluation.recommendation}
                          </span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
                          <div><strong>Timeline:</strong> {evaluation.timeline_viability}/10</div>
                          <div><strong>Mission:</strong> {evaluation.mission_alignment ?? 'N/A'}/10</div>
                          <div><strong>Winner Match:</strong> {evaluation.winner_pattern_match ?? 'N/A'}/10</div>
                          <div><strong>Burden:</strong> {evaluation.application_burden}/10</div>
                          <div><strong>Structure:</strong> {evaluation.award_structure}/10</div>
                          <div><strong>Composite:</strong> {evaluation.composite_score}/10</div>
                          </div>
                          </div>
                    )}
                      </div>
                    )
              })}
              </div>
          </div>
      </div>
      )}
      {showReportIssue && (
        <ReportIssue 
          onClose={() => {
            setShowReportIssue(false)
            setReportIssueContext({})
          }}
          initialData={reportIssueContext}
        />
      )}

      {/* Data Contribution Modal for First-Time Users */}
      {showDataContributionModal && pendingGrantUrl && (
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
          <div className="card" style={{ maxWidth: '700px', width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
            <h2>Make Your First Assessment Comprehensive</h2>
            <p style={{ color: '#6b7280', marginBottom: '1rem' }}>
              We'll extract grant information and let you add any missing details. You can also add your project details for a more personalized assessment.
            </p>
            
            {pendingGrantUrl && (
              <div style={{ 
                padding: '0.75rem', 
                backgroundColor: '#f0f9ff', 
                borderRadius: '8px', 
                marginBottom: '1.5rem',
                fontSize: '0.9rem'
              }}>
                <strong>Grant URL:</strong> 
                <div style={{ marginTop: '0.25rem', color: '#4a77e8', wordBreak: 'break-all' }}>
                  {pendingGrantUrl}
                </div>
              </div>
            )}

            {!showGrantDataForm && !showProjectFormInModal && !extractingGrantData && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1.5rem' }}>
                <button
                  onClick={handleExtractGrantData}
                  className="btn btn-primary"
                  disabled={extractingGrantData}
                >
                  {extractingGrantData ? 'Extracting...' : 'Extract & Review Grant Data'}
                </button>
                <button
                  onClick={() => handleCreateEvaluationFromPending(null)}
                  className="btn btn-secondary"
                  disabled={isAssessing}
                >
                  {isAssessing ? 'Creating...' : 'Skip & Use Defaults'}
                </button>
              </div>
            )}

            {extractingGrantData && (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>
                <div style={{ 
                  display: 'inline-block',
                  width: '40px',
                  height: '40px',
                  border: '4px solid #f3f4f6',
                  borderTop: '4px solid #4a77e8',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                  marginBottom: '1rem'
                }}></div>
                <p>Extracting grant information from URL...</p>
                <style>{`
                  @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                  }
                `}</style>
              </div>
            )}

            {showGrantDataForm && !showProjectFormInModal && (
              <div style={{ marginTop: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ margin: 0 }}>Review & Edit Grant Data</h3>
                  <button
                    onClick={() => {
                      setShowGrantDataForm(false)
                      setExtractedGrantData(null)
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#6b7280',
                      cursor: 'pointer',
                      fontSize: '0.9rem'
                    }}
                  >
                    Back
                  </button>
                </div>
                
                <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1rem' }}>
                  Review the extracted grant information and add any missing details. This will make your assessment more comprehensive.
                </p>

                <div style={{ maxHeight: '400px', overflowY: 'auto', marginBottom: '1rem' }}>
                  <div className="form-group">
                    <label>Grant Name</label>
                    <input
                      type="text"
                      value={grantDataForm.name}
                      onChange={(e) => setGrantDataForm({...grantDataForm, name: e.target.value})}
                      placeholder="Grant name"
                    />
                  </div>
                  
                  <div className="form-group">
                    <label>Description</label>
                    <textarea
                      value={grantDataForm.description}
                      onChange={(e) => setGrantDataForm({...grantDataForm, description: e.target.value})}
                      rows={3}
                      placeholder="Grant description"
                      style={{ fontFamily: 'inherit', resize: 'vertical' }}
                    />
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                    <div className="form-group">
                      <label>Deadline</label>
                      <input
                        type="text"
                        value={grantDataForm.deadline}
                        onChange={(e) => setGrantDataForm({...grantDataForm, deadline: e.target.value})}
                        placeholder="e.g., March 15, 2025"
                      />
                    </div>
                    <div className="form-group">
                      <label>Decision Date</label>
                      <input
                        type="text"
                        value={grantDataForm.decision_date}
                        onChange={(e) => setGrantDataForm({...grantDataForm, decision_date: e.target.value})}
                        placeholder="e.g., June 1, 2025"
                      />
                    </div>
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                    <div className="form-group">
                      <label>Award Amount</label>
                      <input
                        type="text"
                        value={grantDataForm.award_amount}
                        onChange={(e) => setGrantDataForm({...grantDataForm, award_amount: e.target.value})}
                        placeholder="e.g., $50,000"
                      />
                    </div>
                    <div className="form-group">
                      <label>Award Structure</label>
                      <input
                        type="text"
                        value={grantDataForm.award_structure}
                        onChange={(e) => setGrantDataForm({...grantDataForm, award_structure: e.target.value})}
                        placeholder="e.g., One-time payment"
                      />
                    </div>
                  </div>
                  
                  <div className="form-group">
                    <label>Eligibility</label>
                    <textarea
                      value={grantDataForm.eligibility}
                      onChange={(e) => setGrantDataForm({...grantDataForm, eligibility: e.target.value})}
                      rows={2}
                      placeholder="Eligibility criteria"
                      style={{ fontFamily: 'inherit', resize: 'vertical' }}
                    />
                  </div>
                  
                  <div className="form-group">
                    <label>Preferred Applicants</label>
                    <textarea
                      value={grantDataForm.preferred_applicants}
                      onChange={(e) => setGrantDataForm({...grantDataForm, preferred_applicants: e.target.value})}
                      rows={2}
                      placeholder="One per line"
                      style={{ fontFamily: 'inherit', resize: 'vertical' }}
                    />
                  </div>
                  
                  <div className="form-group">
                    <label>Application Requirements</label>
                    <textarea
                      value={grantDataForm.application_requirements}
                      onChange={(e) => setGrantDataForm({...grantDataForm, application_requirements: e.target.value})}
                      rows={2}
                      placeholder="One per line"
                      style={{ fontFamily: 'inherit', resize: 'vertical' }}
                    />
                  </div>
                  
                  <div className="form-group">
                    <label>Mission</label>
                    <textarea
                      value={grantDataForm.mission}
                      onChange={(e) => setGrantDataForm({...grantDataForm, mission: e.target.value})}
                      rows={2}
                      placeholder="Grant mission/focus"
                      style={{ fontFamily: 'inherit', resize: 'vertical' }}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
                  <button
                    onClick={() => setShowProjectFormInModal(true)}
                    className="btn btn-primary"
                    style={{ flex: 1 }}
                  >
                    Add Project Details & Assess
                  </button>
                  <button
                    onClick={() => {
                      // Include edited grant data if available - filter out empty strings
                      const grantDataToUse = showGrantDataForm ? (() => {
                        const data = {}
                        if (grantDataForm.name?.trim() || pendingGrantName?.trim()) {
                          data.grant_name = (grantDataForm.name || pendingGrantName).trim()
                        }
                        if (grantDataForm.description?.trim()) {
                          data.grant_description = grantDataForm.description.trim()
                        }
                        if (grantDataForm.deadline?.trim()) {
                          data.grant_deadline = grantDataForm.deadline.trim()
                        }
                        if (grantDataForm.decision_date?.trim()) {
                          data.grant_decision_date = grantDataForm.decision_date.trim()
                        }
                        if (grantDataForm.award_amount?.trim()) {
                          data.grant_award_amount = grantDataForm.award_amount.trim()
                        }
                        if (grantDataForm.award_structure?.trim()) {
                          data.grant_award_structure = grantDataForm.award_structure.trim()
                        }
                        if (grantDataForm.eligibility?.trim()) {
                          data.grant_eligibility = grantDataForm.eligibility.trim()
                        }
                        if (grantDataForm.preferred_applicants?.trim()) {
                          data.grant_preferred_applicants = grantDataForm.preferred_applicants.trim()
                        }
                        if (grantDataForm.application_requirements?.trim()) {
                          const items = grantDataForm.application_requirements.split('\n').filter(l => l.trim())
                          if (items.length > 0) {
                            data.grant_application_requirements = items
                          }
                        }
                        if (grantDataForm.reporting_requirements?.trim()) {
                          data.grant_reporting_requirements = grantDataForm.reporting_requirements.trim()
                        }
                        if (grantDataForm.restrictions?.trim()) {
                          const items = grantDataForm.restrictions.split('\n').filter(l => l.trim())
                          if (items.length > 0) {
                            data.grant_restrictions = items
                          }
                        }
                        if (grantDataForm.mission?.trim()) {
                          data.grant_mission = grantDataForm.mission.trim()
                        }
                        return Object.keys(data).length > 0 ? data : null
                      })() : null
                      handleCreateEvaluationFromPending(null, grantDataToUse)
                    }}
                    className="btn btn-secondary"
                    style={{ flex: 1 }}
                    disabled={isAssessing}
                  >
                    {isAssessing ? 'Creating...' : 'Assess with Grant Data Only'}
                  </button>
                </div>
              </div>
            )}

            {!showGrantDataForm && !showProjectFormInModal ? null : showProjectFormInModal ? (
              <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
                <button
                  onClick={() => setShowProjectFormInModal(true)}
                  className="btn btn-primary"
                  style={{ flex: 1 }}
                >
                  Add Project Details
                </button>
                <button
                  onClick={() => handleCreateEvaluationFromPending(null)}
                  className="btn btn-secondary"
                  style={{ flex: 1 }}
                  disabled={isAssessing}
                >
                  {isAssessing ? 'Creating...' : 'Skip & Use Defaults'}
                </button>
              </div>
            ) : (
              <div style={{ marginTop: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ margin: 0 }}>Project Details</h3>
                  <button
                    onClick={() => setShowProjectFormInModal(false)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#6b7280',
                      cursor: 'pointer',
                      fontSize: '0.9rem'
                    }}
                  >
                    Cancel
                  </button>
                </div>
                
                <form onSubmit={(e) => {
                  e.preventDefault()
                  createProjectMutation.mutate(projectFormData)
                }}>
                  <div className="form-group">
                    <label>Project Name *</label>
                    <input
                      type="text"
                      value={projectFormData.name}
                      onChange={(e) => setProjectFormData({...projectFormData, name: e.target.value})}
                      required
                    />
                  </div>
                  
                  <div className="form-group">
                    <label>
                      Description *
                      <span style={{ fontSize: '0.85rem', color: '#6c757d', fontWeight: 'normal', marginLeft: '0.5rem' }}>
                        ({countWords(projectFormData.description)} / 50 words)
                      </span>
                    </label>
                    <textarea
                      value={projectFormData.description}
                      onChange={(e) => {
                        const newValue = e.target.value
                        const wordCount = countWords(newValue)
                        // Limit to 50 words
                        if (wordCount <= 50) {
                          setProjectFormData({...projectFormData, description: newValue})
                        } else {
                          // If over limit, truncate to 50 words
                          const limited = limitToWords(newValue, 50)
                          setProjectFormData({...projectFormData, description: limited})
                        }
                      }}
                      required
                      rows={4}
                      placeholder="Describe your project, what problem it solves, and who it serves..."
                      style={{ fontFamily: 'inherit', resize: 'vertical' }}
                    />
                    {countWords(projectFormData.description) > 0 && countWords(projectFormData.description) < 30 && (
                      <div style={{ 
                        marginTop: '0.5rem', 
                        padding: '0.5rem', 
                        backgroundColor: '#fff3cd', 
                        border: '1px solid #ffc107', 
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        color: '#856404'
                      }}>
                        <strong>Note:</strong> Your description is quite short. Adding more detail (aim for 30-50 words) will help us provide more accurate grant assessments.
                      </div>
                    )}
                    {countWords(projectFormData.description) >= 50 && (
                      <div style={{ 
                        marginTop: '0.5rem', 
                        padding: '0.5rem', 
                        backgroundColor: '#fee2e2', 
                        border: '1px solid #ef4444', 
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        color: '#991b1b'
                      }}>
                        <strong>Limit reached:</strong> Maximum of 50 words. Your description has been truncated.
                      </div>
                    )}
                  </div>
                  
                  <div className="form-group">
                    <label>Stage *</label>
                    <select
                      value={projectFormData.stage}
                      onChange={(e) => setProjectFormData({...projectFormData, stage: e.target.value})}
                      required
                    >
                      <option value="">Select stage...</option>
                      <option value="Idea">Idea</option>
                      <option value="Early Development">Early Development</option>
                      <option value="Pilot">Pilot</option>
                      <option value="Established">Established</option>
                      <option value="Scaling">Scaling</option>
                    </select>
                  </div>
                  
                  <div className="form-group">
                    <label>Funding Need *</label>
                    <select
                      value={projectFormData.funding_need}
                      onChange={(e) => setProjectFormData({...projectFormData, funding_need: e.target.value})}
                      required
                    >
                      <option value="">Select funding need...</option>
                      <option value="Seed funding">Seed funding</option>
                      <option value="Growth capital">Growth capital</option>
                      <option value="Operational support">Operational support</option>
                      <option value="Research funding">Research funding</option>
                      <option value="Program expansion">Program expansion</option>
                    </select>
                  </div>
                  
                  <div className="form-group">
                    <label>Urgency</label>
                    <select
                      value={projectFormData.urgency}
                      onChange={(e) => setProjectFormData({...projectFormData, urgency: e.target.value})}
                    >
                      <option value="low">Low - Flexible timeline</option>
                      <option value="moderate">Moderate - Some time pressure</option>
                      <option value="high">High - Urgent need</option>
                    </select>
                  </div>
                  
                  <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
                    <button
                      type="submit"
                      className="btn btn-primary"
                      style={{ flex: 1 }}
                      disabled={createProjectMutation.isPending || isAssessing}
                    >
                      {createProjectMutation.isPending || isAssessing ? 'Creating...' : 'Create Project & Assess Grant'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowProjectFormInModal(false)
                        // Use grant data if it was edited - filter out empty strings
                        const grantDataToUse = showGrantDataForm ? (() => {
                          const data = {}
                          if (grantDataForm.name?.trim() || pendingGrantName?.trim()) {
                            data.grant_name = (grantDataForm.name || pendingGrantName).trim()
                          }
                          if (grantDataForm.description?.trim()) {
                            data.grant_description = grantDataForm.description.trim()
                          }
                          if (grantDataForm.deadline?.trim()) {
                            data.grant_deadline = grantDataForm.deadline.trim()
                          }
                          if (grantDataForm.decision_date?.trim()) {
                            data.grant_decision_date = grantDataForm.decision_date.trim()
                          }
                          if (grantDataForm.award_amount?.trim()) {
                            data.grant_award_amount = grantDataForm.award_amount.trim()
                          }
                          if (grantDataForm.award_structure?.trim()) {
                            data.grant_award_structure = grantDataForm.award_structure.trim()
                          }
                          if (grantDataForm.eligibility?.trim()) {
                            data.grant_eligibility = grantDataForm.eligibility.trim()
                          }
                          if (grantDataForm.preferred_applicants?.trim()) {
                            data.grant_preferred_applicants = grantDataForm.preferred_applicants.trim()
                          }
                          if (grantDataForm.application_requirements?.trim()) {
                            const items = grantDataForm.application_requirements.split('\n').filter(l => l.trim())
                            if (items.length > 0) {
                              data.grant_application_requirements = items
                            }
                          }
                          if (grantDataForm.reporting_requirements?.trim()) {
                            data.grant_reporting_requirements = grantDataForm.reporting_requirements.trim()
                          }
                          if (grantDataForm.restrictions?.trim()) {
                            const items = grantDataForm.restrictions.split('\n').filter(l => l.trim())
                            if (items.length > 0) {
                              data.grant_restrictions = items
                            }
                          }
                          if (grantDataForm.mission?.trim()) {
                            data.grant_mission = grantDataForm.mission.trim()
                          }
                          return Object.keys(data).length > 0 ? data : null
                        })() : null
                        handleCreateEvaluationFromPending(null, grantDataToUse)
                      }}
                      className="btn btn-secondary"
                      style={{ flex: 1 }}
                      disabled={createProjectMutation.isPending || isAssessing}
                    >
                      Skip Project & Assess
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard

