import { useEffect, useState } from 'react'
import { useChatStore } from '../store/chatStore'
import { Scene } from './Scene'

type AssetDropdownProps = {
  label: string
  value: string
  options: string[]
  fallbackLabel: string
  getOptionValue: (option: string) => string
  getOptionLabel?: (option: string) => string
  onChange: (value: string) => void
}

function AssetDropdown({
  label,
  value,
  options,
  fallbackLabel,
  getOptionValue,
  getOptionLabel = (option) => option,
  onChange,
}: AssetDropdownProps) {
  const [open, setOpen] = useState(false)
  const selectedOption = options.find((option) => getOptionValue(option) === value)
  const displayLabel = selectedOption ? getOptionLabel(selectedOption) : fallbackLabel
  const listId = `${label.toLowerCase().replace(/\s+/g, '-')}-asset-list`

  return (
    <div style={s.controlRow}>
      <span style={s.label}>{label}</span>
      <div style={s.dropdown}>
        <button
          type="button"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((current) => !current)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          style={s.dropdownButton}
        >
          <span style={s.dropdownText}>{displayLabel}</span>
          <span aria-hidden="true" style={s.chevron}>⌄</span>
        </button>
        {open && (
          <div id={listId} role="listbox" style={s.dropdownMenu}>
            {(options.length > 0 ? options : [fallbackLabel]).map((option) => {
              const optionValue = options.length > 0 ? getOptionValue(option) : value
              const optionLabel = options.length > 0 ? getOptionLabel(option) : fallbackLabel
              const selected = optionValue === value

              return (
                <button
                  key={optionValue}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    onChange(optionValue)
                    setOpen(false)
                  }}
                  style={{
                    ...s.dropdownOption,
                    ...(selected ? s.dropdownOptionSelected : null),
                  }}
                >
                  {optionLabel}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export function RightSidebar() {
  const { currentModel, currentVoice, setCurrentModel, setCurrentVoice } = useChatStore()
  const [models, setModels] = useState<string[]>([])
  const [voices, setVoices] = useState<string[]>([])

  useEffect(() => {
    // Fetch models
    fetch('/api/models')
      .then((res) => res.json())
      .then((data) => {
        if (data.models && data.models.length > 0) {
          setModels(data.models)
        }
      })
      .catch((err) => console.error('Failed to fetch models', err))

    // Fetch voices
    fetch('/api/voices')
      .then((res) => res.json())
      .then((data) => {
        if (data.voices && data.voices.length > 0) {
          setVoices(data.voices)
        }
      })
      .catch((err) => console.error('Failed to fetch voices', err))
  }, [])

  return (
    <div style={s.sidebar}>
      {/* Settings Panel */}
      <div style={s.settingsPanel}>
        <div style={s.header}>
          <span style={s.title}>Avatar & Voice Options</span>
        </div>
        
        <div style={s.divider} />
        
        <AssetDropdown
          label="3D Model"
          value={currentModel}
          options={models}
          fallbackLabel={currentModel.split('/').pop() ?? currentModel}
          getOptionValue={(model) => `/models/${model}`}
          onChange={setCurrentModel}
        />
        
        <AssetDropdown
          label="Voice"
          value={currentVoice}
          options={voices}
          fallbackLabel={currentVoice}
          getOptionValue={(voice) => voice}
          getOptionLabel={(voice) => voice.replace(/\.wav$/i, '')}
          onChange={setCurrentVoice}
        />
        <div style={s.divider} />
      </div>

      {/* 3D Scene Container */}
      <div style={s.sceneContainer}>
        <Scene />
      </div>
    </div>
  )
}

const s: Record<string, React.CSSProperties> = {
  sidebar: {
    width: 320,
    minWidth: 320,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    background: '#151521',
    borderLeft: '1px solid rgba(255,255,255,0.07)',
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
  },
  settingsPanel: {
    padding: '16px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  title: {
    fontSize: 14,
    fontWeight: 600,
    color: '#e2e8f0',
    letterSpacing: '0.02em',
  },
  divider: {
    height: 1,
    background: 'rgba(255,255,255,0.06)',
  },
  controlRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  label: {
    fontSize: 11,
    fontWeight: 600,
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  dropdown: {
    position: 'relative',
  },
  dropdownButton: {
    width: '100%',
    height: 36,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    background: 'rgba(255,255,255,0.05)',
    color: '#e2e8f0',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 6,
    padding: '0 8px 0 14px',
    fontSize: 12,
    cursor: 'pointer',
    outline: 'none',
    fontFamily: 'inherit',
  },
  dropdownText: {
    minWidth: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    fontWeight: 600,
    textAlign: 'left',
  },
  chevron: {
    flex: '0 0 auto',
    color: '#cbd5e1',
    fontSize: 18,
    lineHeight: 1,
    paddingLeft: 8,
  },
  dropdownMenu: {
    position: 'absolute',
    top: 'calc(100% + 4px)',
    left: 0,
    right: 0,
    zIndex: 40,
    maxHeight: 168,
    overflowY: 'auto',
    padding: 4,
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    background: '#20202c',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 6,
    boxShadow: '0 14px 32px rgba(0,0,0,0.38)',
  },
  dropdownOption: {
    width: '100%',
    minHeight: 32,
    border: 0,
    borderRadius: 4,
    padding: '7px 10px',
    background: 'transparent',
    color: '#dbeafe',
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 12,
    fontWeight: 600,
    textAlign: 'left',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  dropdownOptionSelected: {
    background: 'rgba(96,165,250,0.2)',
    color: '#ffffff',
  },
  sceneContainer: {
    flex: 1,
    position: 'relative',
    background: 'linear-gradient(180deg, #0d1117 0%, #161b27 100%)',
    overflow: 'hidden',
  },
}
