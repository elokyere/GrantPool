import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add token to requests dynamically via interceptor
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Handle 401 errors - redirect to login
// Also detect HTML responses (API routing issues)
api.interceptors.response.use(
  (response) => {
    // Check if response is HTML instead of JSON (API routing issue)
    const contentType = response.headers['content-type'] || ''
    const data = response.data
    
    if (contentType.includes('text/html') || (typeof data === 'string' && data.trim().startsWith('<!'))) {
      console.error('API returned HTML instead of JSON. Current API URL:', api.defaults.baseURL)
      console.error('This usually means VITE_API_URL is not set correctly or API routes are misconfigured.')
      // Return empty array to prevent crashes
      return { ...response, data: [] }
    }
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      // Clear invalid token
      localStorage.removeItem('token')
      // Redirect to login if not already there
      if (window.location.pathname !== '/login' && window.location.pathname !== '/') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api

