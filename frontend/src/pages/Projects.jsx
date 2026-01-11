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

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await api.get('/api/v1/projects/')
      return response.data
    },
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
        return old ? old.filter((project) => project.id !== projectId) : []
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
    return <div className="container">Loading...</div>
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
              <label>Description</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                required
              />
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
            
            <button type="submit" className="btn btn-primary" disabled={createMutation.isLoading}>
              {createMutation.isLoading ? 'Creating...' : 'Create Project'}
            </button>
          </form>
        </div>
      )}

      <div>
        {projects && projects.length > 0 ? (
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
        ) : (
          <div className="card">
            <p>No projects yet. Create your first project to get started.</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Projects
