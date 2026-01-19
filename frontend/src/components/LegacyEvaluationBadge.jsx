/**
 * Legacy Evaluation Badge Component
 * 
 * Displays a badge indicating this is a legacy evaluation with a link to create a new assessment.
 */

function LegacyEvaluationBadge({ evaluation, onCreateNew }) {
  return (
    <div style={{
      padding: '1rem',
      backgroundColor: '#fff3cd',
      borderLeft: '4px solid #ffc107',
      marginBottom: '1rem',
      borderRadius: '4px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      flexWrap: 'wrap',
      gap: '1rem'
    }}>
      <div>
        <strong>Legacy Evaluation</strong>
        <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: '#856404' }}>
          This assessment was created with the previous scoring system. 
          Scoring logic has evolved to provide more accurate and transparent evaluations.
        </p>
      </div>
      {onCreateNew && (
        <button
          onClick={onCreateNew}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
        >
          Create New Assessment
        </button>
      )}
    </div>
  )
}

export default LegacyEvaluationBadge
