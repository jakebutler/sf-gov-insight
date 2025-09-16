import React from 'react'

type Source = {
  meetingId?: string
  url?: string
  date?: string
  source_type?: string
  chunkIndex?: number
}

const badgeColor = (t?: string) => {
  switch ((t || '').toLowerCase()) {
    case 'transcript':
      return 'bg-purple-100 text-purple-800 border-purple-200'
    case 'minutes':
      return 'bg-green-100 text-green-800 border-green-200'
    case 'agenda':
      return 'bg-blue-100 text-blue-800 border-blue-200'
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200'
  }
}

const SourcesCard = ({ sources }: { sources: Source[] }) => {
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-md p-4">
      <h3 className="text-lg font-semibold mb-3">Sources</h3>
      {(!sources || sources.length === 0) && (
        <p className="text-sm text-gray-500">No sources available.</p>
      )}
      <ul className="space-y-3">
        {sources?.slice(0, 12).map((s, idx) => (
          <li key={`${s.meetingId || idx}-${s.chunkIndex || 0}`} className="text-sm">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded-full border text-xs ${badgeColor(s.source_type)}`}>
                    {s.source_type || 'source'}
                  </span>
                  <span className="text-gray-700 font-medium truncate max-w-[10rem]" title={s.date || ''}>
                    {s.date || 'Unknown date'}
                  </span>
                </div>
                <div className="text-gray-500 truncate max-w-[16rem]" title={s.url || ''}>
                  {s.url}
                  {typeof s.chunkIndex === 'number' ? `#chunk-${s.chunkIndex}` : ''}
                </div>
              </div>
              {s.url && (
                <a
                  href={`${s.url}${typeof s.chunkIndex === 'number' ? `#chunk-${s.chunkIndex}` : ''}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 hover:text-blue-700 whitespace-nowrap"
                >
                  View
                </a>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default SourcesCard
