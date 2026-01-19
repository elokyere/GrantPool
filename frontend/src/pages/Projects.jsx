import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import PrivacySecurityNotice from '../components/PrivacySecurityNotice'
import '../App.css'

function Projects() {
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    stage: '',
    funding_need: '',
    urgency: 'moderate',
    founder_type: '',
    timeline_constraints: '',
  })

  const queryClient = useQueryClient()

  // Helper function to count words
  const countWords = (text) => {
    return text.trim() === '' ? 0 : text.trim().split(/\s+/).length
  }

  // Helper function to limit text to 100 words
  const limitToWords = (text, maxWords) => {
    const words = text.trim().split(/\s+/)
    if (words.length <= maxWords) return text
    return words.slice(0, maxWords).join(' ')
  }

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      try {
        const response = await api.get('/api/v1/projects/')
        const data = response?.data
        // Check if response is HTML (API routing issue)
        if (typeof data === 'string' && data.trim().startsWith('<!')) {
          console.error('API returned HTML instead of JSON. Check VITE_API_URL configuration.')
          return []
        }
        // Ensure we always return an array
        if (Array.isArray(data)) {
          return data
        }
        if (data) {
          console.warn('Projects API returned non-array data:', data)
        }
        return []
      } catch (error) {
        console.error('Error fetching projects:', error)
        return []
      }
    },
    // Remove placeholderData and initialData to prevent showing empty state during loading
    select: (data) => Array.isArray(data) ? data : [],
  })

  const createMutation = useMutation({
    mutationFn: async (data) => {
      const response = await api.post('/api/v1/projects/', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['projects'])
      setShowForm(false)
      setError('')
      setFormData({
        name: '',
        description: '',
        stage: '',
        funding_need: '',
        urgency: 'moderate',
        founder_type: '',
        timeline_constraints: '',
      })
    },
    onError: (err) => {
      const errorMessage = err.response?.data?.detail || 'Failed to create project'
      setError(errorMessage)
      console.error('Project creation error:', err)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (projectId) => {
      const response = await api.delete(`/api/v1/projects/${projectId}`)
      return response
    },
    onMutate: async (projectId) => {
      // Cancel any outgoing refetches (so they don't overwrite our optimistic update)
      await queryClient.cancelQueries(['projects'])

      // Snapshot the previous value
      const previousProjects = queryClient.getQueryData(['projects'])

      // Optimistically update to the new value - remove project immediately
      queryClient.setQueryData(['projects'], (old) => {
        return Array.isArray(old) ? old.filter((project) => project.id !== projectId) : []
      })

      // Return a context object with the snapshotted value
      return { previousProjects }
    },
    onError: (err, projectId, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousProjects) {
        queryClient.setQueryData(['projects'], context.previousProjects)
      }
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to delete project'
      alert(`Error: ${errorMessage}`)
      console.error('Project deletion error:', err)
      console.error('Error details:', err.response?.data)
    },
    onSuccess: () => {
      // Invalidate to ensure we have the latest data
      queryClient.invalidateQueries(['projects'])
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const handleDelete = (projectId, projectName) => {
    if (window.confirm(`Are you sure you want to delete "${projectName}"? This action cannot be undone.`)) {
      deleteMutation.mutate(projectId)
    }
  }

  if (isLoading) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '3rem' }}>
        <div style={{ fontSize: '1.125rem', color: '#6b7280', marginBottom: '1rem' }}>Loading projects...</div>
        <div style={{ fontSize: '0.875rem', color: '#9ca3af' }}>Please wait while we fetch your projects from the database.</div>
      </div>
    )
  }

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1>Projects</h1>
        <button 
          onClick={() => {
            setShowForm(!showForm)
            setError('')
          }} 
          className="btn btn-primary"
        >
          {showForm ? 'Cancel' : 'New Project'}
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h2>Create New Project</h2>
          {error && (
            <div style={{ 
              padding: '1rem', 
              marginBottom: '1rem', 
              backgroundColor: '#fee', 
              border: '1px solid #fcc',
              borderRadius: '4px',
              color: '#c33'
            }}>
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Project Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>
                Description *
                <span style={{ fontSize: '0.85rem', color: '#6c757d', fontWeight: 'normal', marginLeft: '0.5rem' }}>
                  ({countWords(formData.description)} / 100 words)
                </span>
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => {
                  const newValue = e.target.value
                  const wordCount = countWords(newValue)
                  // Limit to 100 words
                  if (wordCount <= 100) {
                    setFormData({ ...formData, description: newValue })
                  } else {
                    // If over limit, truncate to 100 words
                    const limited = limitToWords(newValue, 100)
                    setFormData({ ...formData, description: limited })
                  }
                }}
                placeholder="Describe your project in detail. Include: what problem you're solving, your approach, target beneficiaries, expected impact, and why this project matters. More detail helps us provide better grant assessments."
                required
                rows={6}
                style={{ 
                  minHeight: '120px',
                  resize: 'vertical'
                }}
              />
              <div style={{ 
                marginTop: '0.5rem', 
                padding: '0.75rem', 
                backgroundColor: '#f8f9fa', 
                borderRadius: '4px', 
                border: '1px solid #e9ecef',
                fontSize: '0.85rem',
                color: '#495057'
              }}>
                <strong style={{ display: 'block', marginBottom: '0.5rem', color: '#212529' }}>
                  What to include for best assessment quality:
                </strong>
                <ul style={{ margin: 0, paddingLeft: '1.25rem', lineHeight: '1.6' }}>
                  <li><strong>Problem statement:</strong> What specific problem are you addressing?</li>
                  <li><strong>Your solution:</strong> How does your project solve this problem?</li>
                  <li><strong>Target audience:</strong> Who will benefit from your project?</li>
                  <li><strong>Expected impact:</strong> What outcomes or changes do you expect?</li>
                  <li><strong>Unique value:</strong> What makes your approach different or important?</li>
                  <li><strong>Context:</strong> Any relevant background, location, or sector details</li>
                </ul>
                {countWords(formData.description) > 0 && countWords(formData.description) < 30 && (
                  <div style={{ 
                    marginTop: '0.75rem', 
                    padding: '0.5rem', 
                    backgroundColor: '#fff3cd', 
                    border: '1px solid #ffc107', 
                    borderRadius: '4px',
                    color: '#856404'
                  }}>
                    <strong>Note:</strong> Your description is quite short. Adding more detail (aim for 30-100 words) will help us provide more accurate and personalized grant assessments.
                  </div>
                )}
                {countWords(formData.description) >= 30 && countWords(formData.description) < 100 && (
                  <div style={{ 
                    marginTop: '0.75rem', 
                    padding: '0.5rem', 
                    backgroundColor: '#d1fae5', 
                    border: '1px solid #10b981', 
                    borderRadius: '4px',
                    color: '#065f46'
                  }}>
                    <strong>Good:</strong> Your description length is ideal for comprehensive assessments.
                  </div>
                )}
                {countWords(formData.description) >= 100 && (
                  <div style={{ 
                    marginTop: '0.75rem', 
                    padding: '0.5rem', 
                    backgroundColor: '#fee2e2', 
                    border: '1px solid #ef4444', 
                    borderRadius: '4px',
                    color: '#991b1b'
                  }}>
                    <strong>Limit reached:</strong> Maximum of 100 words. Your description has been truncated.
                  </div>
                )}
              </div>
            </div>
            <div className="form-group">
              <label>Stage</label>
              <select
                value={formData.stage}
                onChange={(e) => setFormData({ ...formData, stage: e.target.value })}
                required
              >
                <option value="">Select stage</option>
                <option value="Early prototype">Early prototype</option>
                <option value="MVP">MVP</option>
                <option value="Scaling">Scaling</option>
              </select>
            </div>
            <div className="form-group">
              <label>Funding Need</label>
              <input
                type="text"
                value={formData.funding_need}
                onChange={(e) => setFormData({ ...formData, funding_need: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Urgency</label>
              <select
                value={formData.urgency}
                onChange={(e) => setFormData({ ...formData, urgency: e.target.value })}
                required
              >
                <option value="critical">Critical</option>
                <option value="moderate">Moderate</option>
                <option value="flexible">Flexible</option>
              </select>
            </div>
            <div className="form-group">
              <label>Founder Type</label>
              <select
                value={formData.founder_type}
                onChange={(e) => setFormData({ ...formData, founder_type: e.target.value })}
              >
                <option value="">Select type</option>
                <option value="solo">Solo</option>
                <option value="startup">Startup</option>
                <option value="institution">Institution</option>
              </select>
            </div>
            <div className="form-group">
              <label>Timeline Constraints</label>
              <textarea
                value={formData.timeline_constraints}
                onChange={(e) => setFormData({ ...formData, timeline_constraints: e.target.value })}
              />
            </div>
            
            <PrivacySecurityNotice />
            
            <button 
              type="submit" 
              className="btn btn-primary" 
              disabled={createMutation.isLoading || countWords(formData.description) === 0}
            >
              {createMutation.isLoading ? 'Creating...' : 'Create Project'}
            </button>
            {countWords(formData.description) === 0 && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: '#dc2626' }}>
                Description is required (minimum 1 word)
              </div>
            )}
          </form>
        </div>
      )}

      <div>
        {Array.isArray(projects) && projects.length > 0 ? (
          projects.map((project) => (
            <div key={project.id} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '0.5rem' }}>
                <div style={{ flex: 1 }}>
                  <h3>{project.name}</h3>
                  <p>{project.description}</p>
                </div>
                <button
                  onClick={() => handleDelete(project.id, project.name)}
                  className="btn btn-secondary"
                  style={{ 
                    padding: '0.5rem 1rem',
                    fontSize: '0.9rem',
                    backgroundColor: '#dc3545',
                    color: 'white',
                    border: 'none',
                    marginLeft: '1rem'
                  }}
                  disabled={deleteMutation.isLoading}
                >
                  {deleteMutation.isLoading ? 'Deleting...' : 'Delete'}
                </button>
              </div>
              <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <span><strong>Stage:</strong> {project.stage}</span>
                <span><strong>Urgency:</strong> {project.urgency}</span>
                <span><strong>Funding Need:</strong> {project.funding_need}</span>
              </div>
            </div>
          ))
        ) : !isLoading ? (
          <div className="card">
            <p>No projects yet. Create your first project to get started.</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default Projects
