// Global variables
let currentUser = null
let goalsData = []
let hideCompleted = false // used to hide/show old goals sections (Completed + Missed)
function applyOldGoalsVisibility() {
  const comp = document.getElementById('completed-goals')
  const miss = document.getElementById('missed-goals')
  if (comp) {
    const isEmpty = comp.getAttribute('data-empty') === '1'
    comp.style.display = (hideCompleted || isEmpty) ? 'none' : ''
  }
  if (miss) {
    const isEmpty = miss.getAttribute('data-empty') === '1'
    miss.style.display = (hideCompleted || isEmpty) ? 'none' : ''
  }
}

async function fetchGoals(){
  try {
    const res = await fetch('/api/goals')
    if (res.status === 401) return { __error: 'unauthorized', items: [] }
    const data = await res.json()
    if (data.error) {
      console.error('Goals API error:', data.error)
      return { __error: data.error, items: [] }
    }
    // Sort newest first by created_at/id
    try {
      data.sort((a,b) => {
        const at = a.created_at || ''
        const bt = b.created_at || ''
        if (at && bt) return bt.localeCompare(at)
        return (b.id||0) - (a.id||0)
      })
    } catch {}
    return { items: data }
  } catch (error) {
    console.error('Failed to fetch goals:', error)
    return { __error: String(error), items: [] }
  }
}

function renderCard(g){
  const status = g.status || {}
  const taskType = status.task_type || 'increment'
  const current = status.progress || 0
  const target = g.target
  const start = (typeof status.start === 'number') ? status.start : 0
  const percent = typeof status.percent === 'number'
    ? status.percent
    : (target ? Math.min(100, Math.max(0, (Number(current) / Number(target)) * 100)) : 0)

  // Determine status label using normalized expected percent vs actual percent
  let label = 'Pending'
  if (percent >= 100) {
    label = '🏁 Completed'
  } else if (typeof status.expected !== 'undefined' && status.expected !== null) {
    // Normalize expected to percent using start baseline for non-percentage
    let expectedPct = null
    if (taskType === 'percentage') {
      expectedPct = Math.max(0, Math.min(100, Number(status.expected) || 0))
    } else {
      const s0 = (typeof status.start === 'number') ? Number(status.start) : 0
      const t0 = (target != null) ? Number(target) : NaN
      const expVal = Number(status.expected)
      if (!isNaN(s0) && !isNaN(t0) && !isNaN(expVal)) {
        const denom = Math.abs(t0 - s0)
        expectedPct = denom > 0 ? Math.max(0, Math.min(100, (Math.abs(expVal - s0) / denom) * 100)) : 100
      }
    }
    if (expectedPct === null || typeof expectedPct === 'undefined') {
      label = percent > 0 ? '⏳ In Progress' : 'Pending'
    } else if (expectedPct === 0) {
      // Day 1 or zero expected distance yet
      label = percent > 0 ? '🚀 Ahead' : '✅ On Track'
    } else {
      const ratio = (percent || 0) / expectedPct
      if (ratio >= 1.3) label = '🚀 Ahead'
      else if (ratio <= 0.7) label = '⚠️ Behind'
      else label = '✅ On Track'
    }
  } else {
    label = percent > 0 ? '⏳ In Progress' : 'Pending'
  }

  // First row right: tiny reset/delete
  const firstRowRight = `
    <div class="card-menu">
      ${taskType !== 'percentage' ? `<button class="btn tiny update-target" data-id="${g.id}" title="Edit target">✏️</button>` : ''}
      <button class="btn tiny reset-task" data-id="${g.id}" title="Reset progress">🔄</button>
      <button class="btn tiny delete-task" data-id="${g.id}" title="Delete task">🗑️</button>
    </div>`

  // Big line value display
  let currentTargetBig = ''
  if (taskType === 'percentage') {
    currentTargetBig = `${Math.round(current)}%`
  } else if (target != null && target !== '') {
    if (start && start !== 0) {
      currentTargetBig = `
        <span class="goal-bound start-val">${start}</span>
        <span class="sep">/</span>
        <span class="goal-current current-val">${current}</span>
        <span class="sep">/</span>
        <span class="goal-bound end-val">${target}</span>`
    } else {
      currentTargetBig = `${current} / ${target}`
    }
  } else {
    currentTargetBig = `${current}`
  }

  // Fourth row: original progress controls
  let progressControl = ''
  if (taskType === 'percentage') {
    progressControl = `
      <div class="percentage-slider wide">
        <input type="range" min="0" max="100" value="${Math.floor(current)}" class="slider" data-id="${g.id}" id="slider-${g.id}">
        <label for="slider-${g.id}">${Math.floor(current)}%</label>
      </div>`
  } else {
    // Action buttons with step 1 and 5
    if (taskType === 'increment') {
      progressControl = `
        <div class="stepper">
          <button class="btn increment" data-id="${g.id}" data-action="increment" data-value="1">+1</button>
          <button class="btn increment" data-id="${g.id}" data-action="increment" data-value="5">+5</button>
          <span class="inline-percent">${(percent||0).toFixed(1)}%</span>
        </div>`
    } else if (taskType === 'decrement') {
      progressControl = `
        <div class="stepper">
          <button class="btn decrement" data-id="${g.id}" data-action="decrement" data-value="1">-1</button>
          <button class="btn decrement" data-id="${g.id}" data-action="decrement" data-value="5">-5</button>
          <span class="inline-percent">${(percent||0).toFixed(1)}%</span>
        </div>`
    } else {
      // Fallback to increment controls
      progressControl = `
        <div class="stepper">
          <button class="btn increment" data-id="${g.id}" data-action="increment" data-value="1">+1</button>
          <button class="btn increment" data-id="${g.id}" data-action="increment" data-value="5">+5</button>
          <span class="inline-percent">${(percent||0).toFixed(1)}%</span>
        </div>`
    }
  }

  return `
    <div class="card" data-id="${g.id}">
      <div class="card-row first-row">
        <div class="goal-name">${g.text}</div>
        ${firstRowRight}
      </div>
      <div class="card-row second-row">
        <div class="goal-ct-big">${currentTargetBig}</div>
        <div class="goal-status">${label}</div>
      </div>
      <div class="card-row third-row">
        <div class="progress-bar-container">
          <div class="progress-track">
            <div class="progress-fill" style="width:${(percent||0).toFixed(1)}%;"></div>
          </div>
        </div>
      </div>
      <div class="card-row fourth-row actions">
        ${progressControl}
        <button class="btn small view-logs" data-id="${g.id}" title="Logs">📜</button>
      </div>
    </div>`
}

function showLogsForGoal(goalId) {
  currentLogsGoalId = goalId // Store for later use in rollback
  document.getElementById('logs-title').textContent = `Logs for Goal ${goalId}`

  fetch(`/api/goals/${goalId}/logs`)
    .then(response => response.json())
    .then(logs => {
      const logsTableBody = document.querySelector('#logs-table tbody')
      logsTableBody.innerHTML = ''

      if (!Array.isArray(logs) || logs.length === 0) {
        const row = logsTableBody.insertRow()
        row.innerHTML = `<td colspan="3" style="text-align: center; color: #666;">No logs found for this goal</td>`
        document.getElementById('logs-modal').style.display = 'block'
        return
      }

      // Sort logs by timestamp (newest first)
      logs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))

      logs.forEach((log, index) => {
        const row = logsTableBody.insertRow()
        const date = new Date(log.timestamp)
        const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})

        // Only show rollback button for the most recent entry (index 0)
        const rollbackButton = index === 0 ? `<button class="log-btn rollback-btn" onclick="rollbackLog(${log.id})">Rollback</button>` : ''

        row.innerHTML = `
          <td>${formattedDate}</td>
          <td class="log-value">${log.value}</td>
          <td>${rollbackButton}</td>
        `
      })

      document.getElementById('logs-modal').style.display = 'block'
    })
}

async function deleteLog(logId) {
  if (!confirm('Are you sure you want to delete this log entry?')) return
  
  try {
    const response = await fetch(`/api/logs/${logId}`, { method: 'DELETE' })
    
    if (response.ok) {
      alert('Log deleted successfully')
      await loadAndRender()
      // Refresh the logs modal if it's open
      const modal = document.getElementById('logs-modal')
      if (modal.style.display === 'block' && currentLogsGoalId) {
        await showLogsForGoal(currentLogsGoalId)
      }
    } else {
      alert('Failed to delete log')
    }
  } catch (error) {
    console.error('Error deleting log:', error)
    alert('Error deleting log')
  }
}

async function rollbackLog(logId) {
  if (!confirm(`Rollback this operation?\nThis will create a reverse operation to undo this change.`)) return
  
  try {
    const response = await fetch(`/api/logs/${logId}/rollback`, { method: 'POST' })
    
    if (response.ok) {
      alert('Operation rolled back successfully')
      
      // First refresh the main dashboard
      await loadAndRender()
      
      // Then refresh the logs modal if it's open and we have a stored goal ID
      const modal = document.getElementById('logs-modal')
      if (modal.style.display === 'block' && currentLogsGoalId) {
        await showLogsForGoal(currentLogsGoalId)
      }
    } else {
      alert('Failed to rollback operation')
    }
  } catch (error) {
    console.error('Error rolling back log:', error)
    alert('Error rolling back operation')
  }
}

async function loadAndRender(){
  const res = await fetchGoals()
  const goals = res.items || []
  goalsData = goals // Store globally for dashboard modal
  const cards = document.getElementById('cards')
  const empty = document.getElementById('empty-state')
  // Compute missed: end date in the past AND percent < 100
  const now = new Date()
  const isMissed = (g) => {
    const sd = g.end_date
    if (!sd) return false
    const end = new Date(sd)
    return end < now && g.status && g.status.percent < 100
  }
  // Exclude completed and missed from active cards
  let list = goals.filter(g => !(g.status && g.status.percent >= 100) && !isMissed(g))
  if (!hideCompleted) {
    // still keep completed out of card block (as requested)
    list = list
  }
  cards.innerHTML = list.map(renderCard).join('\n')
  if (empty) {
    // Show empty state when there are no goals at all OR no active cards to display
    const noGoals = !goals || goals.length === 0
    const noActive = !list || list.length === 0
    const apiError = !!res.__error
    const shouldShow = apiError || noGoals || noActive
    const currentlyHidden = empty.style.display === 'none' || !empty.style.display
    empty.style.display = shouldShow ? 'flex' : 'none'
    if (shouldShow && currentlyHidden) {
      try { empty.scrollIntoView({ behavior: 'smooth', block: 'center' }) } catch {}
    }
  }
  await loadCompleted()
  await loadMissed(goals.filter(isMissed))
}

document.addEventListener('click', async (e) => {
  if (e.target.matches('.btn.increment') || e.target.matches('.btn.decrement')) {
    const id = e.target.dataset.id
    const action = e.target.dataset.action
    const value = parseInt(e.target.dataset.value || '1', 10)
    
    try {
      const response = await fetch(`/api/goals/${id}`, { 
        method: 'PUT', 
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ action, value })
      })
      
      if (response.ok) {
        await loadAndRender()
      } else {
        const error = await response.json()
        console.error('Update failed:', error)
        alert('Failed to update goal: ' + (error.error || 'Unknown error'))
      }
    } catch (error) {
      console.error('Network error:', error)
      alert('Network error occurred')
    }
  }
  if (e.target.id === 'add-goal') {
    // Open the original modal so quick date buttons and Start field are available
    showGoalModal()
  }
  // Inline name edit on clicking goal name
  const nameEl = e.target.closest && e.target.closest('.goal-name')
  if (nameEl) {
    const card = nameEl.closest('.card')
    const id = card && card.getAttribute('data-id')
    if (id) {
      const currentName = nameEl.textContent || ''
      const newName = prompt('Edit goal name:', currentName.trim())
      if (newName != null) {
        const txt = newName.trim()
        if (txt.length === 0) { alert('Name cannot be empty'); }
        else {
          try {
            const res = await fetch(`/api/goals/${id}/name`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ text: txt }) })
            if (!res.ok) {
              const er = await res.json().catch(()=>({}))
              alert('Failed to update name' + (er.error?`: ${er.error}`:''))
            } else {
              await loadAndRender()
            }
          } catch (err) {
            console.error(err)
            alert('Network error updating name')
          }
        }
      }
    }
  }
  if (e.target.id === 'summary-table') {
    showSummaryTable()
  }
  if (e.target.matches('.btn.small.view-logs')) {
    const id = e.target.dataset.id
    showLogsForGoal(id)
  }
  if (e.target.id === 'cancel-goal') {
    hideGoalModal()
  }
  if (e.target.matches('.quick-date-btn')) {
    const days = parseInt(e.target.dataset.days)
    const startDate = document.getElementById('goal-start').value || new Date().toISOString().split('T')[0]
    
    // Calculate end date
    const start = new Date(startDate)
    const end = new Date(start)
    end.setDate(start.getDate() + days)
    
    // Set end date
    document.getElementById('goal-end').value = end.toISOString().split('T')[0]
    
    // Update button states
    document.querySelectorAll('.quick-date-btn').forEach(btn => btn.classList.remove('active'))
    e.target.classList.add('active')
  }
  if (e.target.id === 'close-logs') {
    document.getElementById('logs-modal').style.display = 'none'
  }
  if (e.target.matches('.btn.tiny.reset-task')) {
    const id = e.target.dataset.id
    if (confirm('Reset all progress for this task? This will delete all logs.')) {
      await resetTask(id)
      await loadAndRender()
    }
  }
  if (e.target.matches('.btn.tiny.delete-task')) {
    const id = e.target.dataset.id
    if (confirm('Delete this task completely? This cannot be undone.')) {
      await deleteTask(id)
      await loadAndRender()
    }
  }
  if (e.target.matches('.delete-completed')) {
    const id = e.target.dataset.id
    if (confirm('Delete this completed goal?')) {
      try {
        await fetch(`/api/completed-goals/${id}`, { method:'DELETE' })
        await loadCompleted()
      } catch (err) { console.error(err) }
    }
  }
  const updateBtn = e.target.closest('.update-target')
  if (updateBtn) {
    const id = updateBtn.dataset.id
    const val = prompt('Enter new target value (blank to 100):')
    if (val === null) return
    const payloadTarget = (val.trim() === '') ? 100 : val
    try {
      const res = await fetch(`/api/goals/${id}/target`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ target: payloadTarget }) })
      if (!res.ok) {
        const er = await res.json().catch(()=>({}))
        alert('Failed to update target' + (er.error?`: ${er.error}`:''))
      }
      await loadAndRender()
    } catch (err) {
      console.error(err)
      alert('Network error')
    }
  }
  if (e.target.matches('.btn.small.update-progress')) {
    const id = e.target.dataset.id
    // For increment/decrement, prompt a delta; for percentage, prompt absolute percent
    const mode = (goalsData.find(x=>String(x.id)===String(id))?.status?.task_type) || 'increment'
    if (mode === 'percentage') {
      const val = prompt('Set progress to percent (0-100):')
      if (val===null) return
      const num = Number(val)
      if (isNaN(num)) return alert('Invalid number')
      await fetch(`/api/goals/${id}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ action:'update', value: num }) })
      await loadAndRender()
    } else {
      const val = prompt('Enter amount to add (use negative to subtract):', '1')
      if (val===null) return
      const num = Number(val)
      if (isNaN(num) || num===0) return alert('Invalid number')
      const action = num>0 ? (mode==='increment'?'increment':'decrement') : (mode==='increment'?'decrement':'increment')
      await fetch(`/api/goals/${id}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ action, value: Math.abs(num) }) })
      await loadAndRender()
    }
  }
})

async function loadCompleted(){
  try {
    const res = await fetch('/api/completed-goals')
    const tbody = document.querySelector('#completed-table tbody')
    const section = document.getElementById('completed-goals')
    if (!tbody) return
    if (!res.ok) { tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Unable to load</td></tr>'; return }
    const items = await res.json()
    if (!items.length) {
      if (tbody) tbody.innerHTML = ''
      if (section) section.setAttribute('data-empty', '1')
      applyOldGoalsVisibility()
      return
    }
    if (section) section.removeAttribute('data-empty')
    tbody.innerHTML = items.map(it => {
      const name = it.text || 'Unnamed'
      const startT = it.start_date || '-'
      const endT = it.end_date || (it.completed_at ? it.completed_at.split(' ')[0] : '-')
      const startV = (it.start_value != null) ? it.start_value : 0
      const endV = (it.completed_value != null) ? it.completed_value : ((it.target != null) ? it.target : '-')
      const delta = (typeof startV === 'number' && typeof endV === 'number') ? (Math.abs(endV - startV)) : '-'
      return `<tr>
        <td>${name}</td>
        <td>${startT}</td>
        <td>${endT}</td>
        <td>${startV}</td>
        <td>${endV}</td>
        <td>${delta}</td>
        <td><button class="btn small delete-completed" data-id="${it.id}">Delete</button></td>`
    }).join('')
    applyOldGoalsVisibility()
  } catch(e) { console.error(e) }
}

async function loadMissed(items){
  try {
    const tbody = document.querySelector('#missed-table tbody')
    const section = document.getElementById('missed-goals')
    if (!tbody) return
    if (!items || !items.length) {
      if (tbody) tbody.innerHTML = ''
      if (section) section.setAttribute('data-empty', '1')
      applyOldGoalsVisibility()
      return
    }
    if (section) section.removeAttribute('data-empty')
    tbody.innerHTML = items.map(it => {
      const name = it.text || 'Unnamed'
      const startT = it.start_date || '-'
      const endT = it.end_date || '-'
      const startV = (it.start_value != null) ? it.start_value : 0
      const curr = (it.status && it.status.progress != null) ? it.status.progress : '-'
      const tgt = (it.target != null) ? it.target : '-'
      return `<tr>
        <td>${name}</td>
        <td>${startT}</td>
        <td>${endT}</td>
        <td>${startV}</td>
        <td>${curr}</td>
        <td>${tgt}</td>
        <td><button class="btn small delete-task" data-id="${it.id}">Delete</button></td>
      </tr>`
    }).join('')
    applyOldGoalsVisibility()
  } catch(e) { console.error(e) }
}

// Adjust end date when start date changes (keep 30-day default window)
document.getElementById('goal-start').addEventListener('change', (e) => {
  const startDate = e.target.value
  if (!startDate) return
  const start = new Date(startDate)
  const end = new Date(start)
  end.setDate(start.getDate() + 30)
  document.getElementById('goal-end').value = end.toISOString().split('T')[0]
  // reflect default quick button
  document.querySelectorAll('.quick-date-btn').forEach(btn => btn.classList.remove('active'))
  const thirtyBtn = document.querySelector('.quick-date-btn[data-days="30"]')
  if (thirtyBtn) thirtyBtn.classList.add('active')
})

// Keep Start field visible for all types; set target to 100 for percentage and hide target field
document.getElementById('goal-type').addEventListener('change', (e) => {
  const type = e.target.value
  const targetEl = document.getElementById('goal-target')
  const startField = document.getElementById('start-field')
  const targetField = document.getElementById('target-field')
  if (type === 'percentage') {
    targetEl.value = '100'
    targetEl.placeholder = '100'
    if (targetField) targetField.style.display = 'none'
  } else {
    if (targetEl.value === '100') targetEl.value = ''
    targetEl.placeholder = 'e.g., 100'
    if (targetField) targetField.style.display = ''
  }
  if (startField) startField.style.display = ''
})

function showGoalModal() {
  document.getElementById('goal-modal').style.display = 'flex'
  document.getElementById('goal-text').focus()
  document.getElementById('goal-target').required = true
  
  // Set default start date to current date
  const today = new Date().toISOString().split('T')[0]
  document.getElementById('goal-start').value = today
  
  // Default end date to +30 days from start
  const start = new Date(today)
  const end = new Date(start)
  end.setDate(start.getDate() + 30)
  document.getElementById('goal-end').value = end.toISOString().split('T')[0]
  
  // Mark the 30 days quick button active (visual default)
  document.querySelectorAll('.quick-date-btn').forEach(btn => btn.classList.remove('active'))
  const thirtyBtn = document.querySelector('.quick-date-btn[data-days="30"]')
  if (thirtyBtn) thirtyBtn.classList.add('active')
  
  // Default target for percentage goals is 100
  const typeEl = document.getElementById('goal-type')
  const targetEl = document.getElementById('goal-target')
  const targetField = document.getElementById('target-field')
  const startField = document.getElementById('start-field')
  const startValueEl = document.getElementById('goal-start-value')
  if (typeEl && typeEl.value === 'percentage') {
    targetEl.value = '100'
    targetEl.placeholder = '100'
    if (startField) startField.style.display = ''
    if (targetField) targetField.style.display = 'none'
  } else {
    targetEl.placeholder = 'e.g., 100'
    // Always show Start regardless of type (increment/decrement)
    if (startField) startField.style.display = ''
    if (targetField) targetField.style.display = ''
  }
  
  // Clear any previous quick date button selections
  document.querySelectorAll('.quick-date-btn').forEach(btn => btn.classList.remove('active'))
}

function hideGoalModal() {
  document.getElementById('goal-modal').style.display = 'none'
  document.getElementById('goal-form').reset()
  // Clear any validation messages
  document.getElementById('goal-target').required = false
}

document.getElementById('goal-form').addEventListener('submit', async (e) => {
  e.preventDefault()
  const text = document.getElementById('goal-text').value
  const target = document.getElementById('goal-target').value
  const startValueRaw = document.getElementById('goal-start-value').value
  const taskType = document.getElementById('goal-type').value
  const startDate = document.getElementById('goal-start').value
  const endDate = document.getElementById('goal-end').value
  
  const goalData = { text, task_type: taskType }
  if (target) goalData.target = parseFloat(target)
  if (startDate) goalData.start_date = startDate
  if (endDate) goalData.end_date = endDate
  if (startValueRaw !== '' && !isNaN(Number(startValueRaw))) goalData.start_value = parseFloat(startValueRaw)
  
  await fetch('/api/goals', { 
    method: 'POST', 
    headers: {'Content-Type': 'application/json'}, 
    body: JSON.stringify(goalData) 
  })
  .then(r => r.json())
  .then(async (res) => {
    // If user provided a non-zero start value, create an initial log entry
    const startVal = Number(startValueRaw)
    if (res && res.id && !isNaN(startVal)) {
      try {
        let action, value
        if (taskType === 'percentage') {
          action = 'update'
          value = startVal
        } else if (taskType === 'increment') {
          if (startVal === 0) {
            action = null
          } else {
            action = 'increment'
            value = Math.abs(startVal)
          }
        } else if (taskType === 'decrement') {
          // Set absolute current to Start for decrement
          action = 'update'
          value = startVal
        }
        if (action) {
          await fetch(`/api/goals/${res.id}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ action, value }) })
        }
      } catch (e) { console.error('Failed to set start value', e) }
    }
  })
  
  hideGoalModal()
  await loadAndRender()
})

// Handle slider changes for percentage tasks
document.addEventListener('input', async (e) => {
  if (e.target.matches('.slider')) {
    const id = e.target.dataset.id
    const value = parseFloat(e.target.value)
    
    // Update the label immediately
    const label = e.target.nextElementSibling
    if (label) {
      label.textContent = `${Math.floor(value)}%`
    }
  }
})

// Handle slider change (when user releases the slider)
document.addEventListener('change', async (e) => {
  if (e.target.matches('.slider')) {
    const id = e.target.dataset.id
    const value = parseFloat(e.target.value)
    
    // Send update to server
    try {
      const response = await fetch(`/api/goals/${id}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ action: 'update', value })
      })
      
      if (response.ok) {
        await loadAndRender()
      } else {
        const error = await response.json()
        console.error('Slider update failed:', error)
      }
    } catch (error) {
      console.error('Slider network error:', error)
    }
    
    // Reload to get updated progress
    await loadAndRender()
  }
})

// Close modals when clicking outside
document.getElementById('goal-modal').addEventListener('click', (e) => {
  if (e.target.id === 'goal-modal') {
    hideGoalModal()
  }
})

document.getElementById('logs-modal').addEventListener('click', (e) => {
  if (e.target.id === 'logs-modal') {
    document.getElementById('logs-modal').style.display = 'none'
  }
})

async function resetTask(goalId) {
  // Delete all logs for this goal
  const allLogs = await fetch('/api/logs').then(r => r.json())
  const goalLogs = allLogs.filter(l => l.goal_id == goalId)
  
  for (const log of goalLogs) {
    await fetch(`/api/logs/${log.id}`, { method: 'DELETE' })
  }

  // After clearing logs, set current back to start value for all types
  try {
    const g = (goalsData || []).find(x => String(x.id) === String(goalId))
    const startVal = (g && (g.start_value != null)) ? Number(g.start_value) : 0
    const ttype = (g && (g.status && g.status.task_type)) ? g.status.task_type : (g && g.task_type) ? g.task_type : 'increment'
    if (!isNaN(startVal)) {
      if (ttype === 'percentage') {
        await fetch(`/api/goals/${goalId}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ action:'update', value: startVal }) })
      } else if (ttype === 'decrement') {
        await fetch(`/api/goals/${goalId}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ action:'update', value: startVal }) })
      } else {
        // increment: set by adding startVal if non-zero
        if (startVal !== 0) {
          await fetch(`/api/goals/${goalId}`, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ action:'increment', value: Math.abs(startVal) }) })
        }
      }
    }
  } catch (e) {
    console.error('Failed to reset to start value', e)
  }
}

async function deleteTask(goalId) {
  // First delete all logs for this goal
  await resetTask(goalId)
  
  // Then delete the goal itself
  await fetch(`/api/goals/${goalId}`, { method: 'DELETE' })
}

// Global variable to track current logs modal goal ID
let currentLogsGoalId = null

// Authentication functions
async function checkAuthStatus() {
  try {
    const response = await fetch('/api/current-user')
    if (response.ok) {
      const data = await response.json()
      currentUser = data.user
      showMainApp()
      return true
    } else {
      currentUser = null
      showAuthScreen()
      return false
    }
  } catch (error) {
    console.error('Auth check failed:', error)
    currentUser = null
    showAuthScreen()
    return false
  }
}

function showAuthScreen() {
  const authHtml = `
    <div class="auth-container">
      <h2>Welcome to Year Plan</h2>
      <p>Track your annual goals with progress monitoring and smart insights</p>
      <div class="auth-buttons">
        <button id="show-login" class="btn primary">Login</button>
        <button id="show-register" class="btn secondary">Sign Up</button>
      </div>
    </div>
  `
  const authEl = document.getElementById('auth-screen')
  if (authEl) {
    authEl.innerHTML = authHtml
    authEl.style.display = 'flex'
  }
  const appEl = document.getElementById('main-app')
  if (appEl) appEl.style.display = 'none'
  const bottomBar = document.querySelector('.bottom-bar')
  if (bottomBar) bottomBar.style.display = 'none'
  // Re-bind auth buttons each time we rebuild the auth screen
  const loginBtn = document.getElementById('show-login')
  if (loginBtn) loginBtn.addEventListener('click', showLoginModal)
  const registerBtn = document.getElementById('show-register')
  if (registerBtn) registerBtn.addEventListener('click', showRegisterModal)
}

function showMainApp() {
  document.getElementById('auth-screen').style.display = 'none'
  document.getElementById('main-app').style.display = 'block'
  document.getElementById('user-name').textContent = currentUser?.name || 'User'
  const bottomBar = document.querySelector('.bottom-bar')
  if (bottomBar) bottomBar.style.display = 'flex'
  loadAndRender()
}

function showLoginModal() {
  document.getElementById('login-modal').style.display = 'flex'
}

function hideLoginModal() {
  document.getElementById('login-modal').style.display = 'none'
  document.getElementById('login-form').reset()
}

function showRegisterModal() {
  document.getElementById('register-modal').style.display = 'flex'
}

function hideRegisterModal() {
  document.getElementById('register-modal').style.display = 'none'
  document.getElementById('register-form').reset()
}

async function handleLogin(event) {
  event.preventDefault()
  
  const email = document.getElementById('login-email').value
  const password = document.getElementById('login-password').value
  
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    })
    
    const data = await response.json()
    
    if (response.ok) {
      currentUser = data.user
      hideLoginModal()
      showMainApp()
    } else {
      if (data.verification_required) {
        // Show verification prompt with resend option
        showVerificationRequired(email, data.error)
      } else {
        alert(data.error || 'Login failed')
      }
    }
  } catch (error) {
    console.error('Login error:', error)
    alert('Login failed. Please try again.')
  }
}

async function handleRegister(event) {
  event.preventDefault()
  
  const name = document.getElementById('register-name').value
  const email = document.getElementById('register-email').value
  const password = document.getElementById('register-password').value
  const confirm = document.getElementById('register-confirm').value
  
  if (password !== confirm) {
    alert('Passwords do not match')
    return
  }
  
  try {
    const response = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password })
    })
    
    const data = await response.json()
    
    if (response.ok) {
      // Show verification message
      hideRegisterModal()
      showVerificationMessage(data.email, data.message)
    } else {
      alert(data.error || 'Registration failed')
    }
  } catch (error) {
    console.error('Registration error:', error)
    alert('Registration failed. Please try again.')
  }
}

async function handleLogout() {
  try {
    await fetch('/api/logout', { method: 'POST' })
    currentUser = null
    showAuthScreen()
  } catch (error) {
    console.error('Logout error:', error)
  }
}

// Add event listener for custom end date changes
// User dropdown functionality
function toggleUserDropdown() {
  const dropdown = document.getElementById('user-dropdown-menu')
  const btn = document.querySelector('.user-dropdown')
  
  if (dropdown.style.display === 'none' || !dropdown.style.display) {
    dropdown.style.display = 'block'
    btn.classList.add('open')
  } else {
    dropdown.style.display = 'none'
    btn.classList.remove('open')
  }
}

function hideUserDropdown() {
  const dropdown = document.getElementById('user-dropdown-menu')
  const btn = document.querySelector('.user-dropdown')
  dropdown.style.display = 'none'
  btn.classList.remove('open')
}

// User management modal functions
function showChangePasswordModal() {
  hideUserDropdown()
  document.getElementById('change-password-modal').style.display = 'block'
  document.getElementById('current-password').focus()
}

function hideChangePasswordModal() {
  document.getElementById('change-password-modal').style.display = 'none'
  document.getElementById('change-password-form').reset()
}

function showChangeEmailModal() {
  hideUserDropdown()
  // Get current user info and populate current email
  fetch('/api/current-user')
    .then(res => res.json())
    .then(data => {
      if (data.user) {
        document.getElementById('current-email').value = data.user.email
      }
    })
  document.getElementById('change-email-modal').style.display = 'block'
  document.getElementById('new-email').focus()
}

function hideChangeEmailModal() {
  document.getElementById('change-email-modal').style.display = 'none'
  document.getElementById('change-email-form').reset()
}

function showDeleteAccountModal() {
  hideUserDropdown()
  document.getElementById('delete-account-modal').style.display = 'block'
  document.getElementById('delete-password').focus()
}

function hideDeleteAccountModal() {
  document.getElementById('delete-account-modal').style.display = 'none'
  document.getElementById('delete-account-form').reset()
}

// User management API handlers
async function handleChangePassword(e) {
  e.preventDefault()
  const currentPassword = document.getElementById('current-password').value
  const newPassword = document.getElementById('new-password').value
  const confirmPassword = document.getElementById('confirm-password').value
  
  if (newPassword !== confirmPassword) {
    alert('New passwords do not match')
    return
  }
  
  try {
    const res = await fetch('/api/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword
      })
    })
    
    const data = await res.json()
    if (res.ok) {
      alert('Password changed successfully!')
      hideChangePasswordModal()
    } else {
      alert(data.error || 'Failed to change password')
    }
  } catch (error) {
    console.error('Change password error:', error)
    alert('An error occurred while changing password')
  }
}

async function handleChangeEmail(e) {
  e.preventDefault()
  const newEmail = document.getElementById('new-email').value
  const password = document.getElementById('email-password').value
  
  try {
    const res = await fetch('/api/change-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_email: newEmail,
        password: password
      })
    })
    
    const data = await res.json()
    if (res.ok) {
      alert('Email changed successfully!')
      hideChangeEmailModal()
      // Update the username display
      checkAuthStatus()
    } else {
      alert(data.error || 'Failed to change email')
    }
  } catch (error) {
    console.error('Change email error:', error)
    alert('An error occurred while changing email')
  }
}

async function handleDeleteAccount(e) {
  e.preventDefault()
  const password = document.getElementById('delete-password').value
  const confirmed = document.getElementById('delete-confirm').checked
  
  if (!confirmed) {
    alert('Please confirm that you understand this action is permanent')
    return
  }
  
  if (!confirm('Are you absolutely sure you want to delete your account? This cannot be undone.')) {
    return
  }
  
  try {
    const res = await fetch('/api/delete-account', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: password })
    })
    
    const data = await res.json()
    if (res.ok) {
      alert('Account deleted successfully')
      hideDeleteAccountModal()
      showAuthScreen()
    } else {
      alert(data.error || 'Failed to delete account')
    }
  } catch (error) {
    console.error('Delete account error:', error)
    alert('An error occurred while deleting account')
  }
}

// Reminder Settings Functions
function showReminderSettingsModal() {
  hideUserDropdown()
  
  // Load current preferences
  loadReminderPreferences()
  
  document.getElementById('reminder-settings-modal').style.display = 'block'
}

function hideReminderSettingsModal() {
  document.getElementById('reminder-settings-modal').style.display = 'none'
  document.getElementById('reminder-settings-form').reset()
}

async function loadReminderPreferences() {
  try {
    const res = await fetch('/api/reminder-preferences')
    const data = await res.json()
    
    if (res.ok) {
      const preferences = data.preferences
      document.getElementById('reminder-frequency').value = preferences.frequency || 'weekly'
      document.getElementById('reminder-enabled').checked = preferences.enabled !== false
    }
  } catch (error) {
    console.error('Error loading reminder preferences:', error)
  }
}

async function handleReminderSettings(e) {
  e.preventDefault()
  
  const frequency = document.getElementById('reminder-frequency').value
  const enabled = document.getElementById('reminder-enabled').checked
  
  try {
    const res = await fetch('/api/reminder-preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        frequency: frequency,
        enabled: enabled
      })
    })
    
    const data = await res.json()
    if (res.ok) {
      alert('Reminder settings updated successfully!')
      hideReminderSettingsModal()
    } else {
      alert(data.error || 'Failed to update reminder settings')
    }
  } catch (error) {
    console.error('Update reminder settings error:', error)
    alert('An error occurred while updating reminder settings')
  }
}

async function sendManualReminder() {
  hideUserDropdown()
  
  if (!confirm('Send a test reminder email to yourself now?')) {
    return
  }
  
  try {
    const res = await fetch('/api/send-reminder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    
    const data = await res.json()
    if (res.ok) {
      alert('✅ Test reminder email sent! Check your inbox.')
    } else {
      alert('❌ ' + (data.error || 'Failed to send reminder email'))
    }
  } catch (error) {
    console.error('Send reminder error:', error)
    alert('❌ An error occurred while sending reminder email')
  }
}

// Email verification functions
function showVerificationMessage(email, message) {
  const verificationHtml = `
    <div class="verification-message">
      <h3>✉️ Check Your Email</h3>
      <p>${message}</p>
      <p><strong>Email:</strong> ${email}</p>
      <div class="verification-actions">
        <button id="resend-verification" class="btn secondary">Resend Verification Email</button>
        <button id="back-to-login" class="btn primary">Back to Login</button>
      </div>
    </div>
  `
  
  document.getElementById('auth-screen').innerHTML = verificationHtml
  document.getElementById('auth-screen').style.display = 'flex'
  
  // Add event listeners
  document.getElementById('resend-verification').addEventListener('click', () => resendVerification(email))
  document.getElementById('back-to-login').addEventListener('click', showAuthScreen)
}

function showVerificationRequired(email, message) {
  const verificationHtml = `
    <div class="verification-message">
      <h3>⚠️ Email Verification Required</h3>
      <p>${message}</p>
      <p><strong>Email:</strong> ${email}</p>
      <div class="verification-actions">
        <button id="resend-verification" class="btn secondary">Resend Verification Email</button>
        <button id="back-to-login" class="btn primary">Back to Login</button>
      </div>
    </div>
  `
  
  document.getElementById('auth-screen').innerHTML = verificationHtml
  document.getElementById('auth-screen').style.display = 'flex'
  
  // Add event listeners
  document.getElementById('resend-verification').addEventListener('click', () => resendVerification(email))
  document.getElementById('back-to-login').addEventListener('click', showAuthScreen)
}

async function resendVerification(email) {
  try {
    const response = await fetch('/api/resend-verification', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    })
    
    const data = await response.json()
    
    if (response.ok) {
      alert('Verification email sent successfully! Please check your email.')
    } else {
      alert(data.error || 'Failed to send verification email')
    }
  } catch (error) {
    console.error('Resend verification error:', error)
    alert('Failed to send verification email. Please try again.')
  }
}

// (Duplicate showAuthScreen removed; unified above)







function isGoalOnTrack(goal) {
  if (goal.status?.completed) return true
  if (!goal.start_date || !goal.end_date || !goal.status?.target) return null
  
  const now = new Date()
  const start = new Date(goal.start_date)
  const end = new Date(goal.end_date)
  
  if (now < start || now > end) return null
  
  const totalTime = end - start
  const elapsedTime = now - start
  const timeProgress = elapsedTime / totalTime
  const progress = goal.status?.progress || 0
  const target = goal.status?.target || 0
  const expectedProgress = timeProgress * target
  
  return progress >= expectedProgress * 0.8 // 80% of expected progress
}



function formatDate(dateStr) {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function showSummaryTable() {
  // Ensure we have fresh data
  if (!goalsData || goalsData.length === 0) {
    alert('No goals found. Add some goals first!')
    return
  }
  
  let tableHTML = `
    <div class="summary-modal" id="summary-modal" style="display: flex;">
      <div class="modal-content summary-content">
        <div class="modal-header">
          <h3>📊 Project Summary Table</h3>
          <button class="close-btn" onclick="closeSummaryTable()">✕</button>
        </div>
        <div class="summary-table-container">
          <table class="summary-table">
            <thead>
              <tr>
                <th class="project-header">Project Name</th>
                <th class="progress-header">Progress</th>
                <th class="percentage-header">Complete</th>
                <th class="status-header">Status</th>
              </tr>
            </thead>
            <tbody>
  `
  
  goalsData.forEach(goal => {
    const name = escapeHtml(goal.text || 'Unnamed')
    const taskType = (goal.status && goal.status.task_type) || goal.task_type || 'increment'
    const target = goal.target
    const start = (goal.status && typeof goal.status.start === 'number') ? goal.status.start : (goal.start_value ?? 0)
    const current = (goal.status && goal.status.progress != null) ? goal.status.progress : (goal.current_value ?? 0)
    // Distance-based percent
    let percent = 0
    if (taskType === 'percentage') {
      percent = Math.max(0, Math.min(100, Number(current) || 0))
    } else if (target != null && !isNaN(Number(target))) {
      const denom = Math.abs(Number(target) - Number(start))
      percent = denom > 0 ? Math.max(0, Math.min(100, (Math.abs(Number(current) - Number(start)) / denom) * 100)) : 100
    } else {
      percent = 0
    }
    // Expected percent: prefer time-based inclusive days, else backend expected normalized
    let expectedPct = null
    let expectedTimePct = null
    if (goal.start_date && goal.end_date) {
      const s = parseLocalDate(goal.start_date)
      const e = parseLocalDate(goal.end_date)
      const today = startOfLocalDay(new Date())
      if (s && e) {
        const ms = 24*60*60*1000
        const totalDays = Math.max(1, Math.floor((e - s)/ms) + 1)
        let elapsed = 0
        if (today < s) elapsed = 0
        else if (today > e) elapsed = totalDays
        else elapsed = Math.floor((today - s)/ms) + 1
        elapsed = Math.min(Math.max(elapsed, 1), totalDays) // inclusive clamp
        expectedTimePct = (elapsed / totalDays) * 100
      }
    }
    if (expectedTimePct != null) expectedPct = expectedTimePct
    else if (goal.status && goal.status.expected != null) {
      const expectedVal = Number(goal.status.expected)
      if (taskType === 'percentage') expectedPct = Math.max(0, Math.min(100, expectedVal))
      else if (target != null && !isNaN(Number(target))) {
        const denom = Math.abs(Number(target) - Number(start))
        expectedPct = denom > 0 ? Math.max(0, Math.min(100, (Math.abs(expectedVal - Number(start)) / denom) * 100)) : 100
      }
    }
    // Status based on percent vs expectedPct
    let status = 'Pending'
    if (percent >= 100) status = '🏁 Completed'
    else if (expectedPct != null && expectedPct > 0) {
      const ratio = percent / expectedPct
      if (ratio >= 1.3) status = '🚀 Ahead'
      else if (ratio <= 0.7) status = '🔴 Behind'
      else status = '✅ On Track'
    } else {
      status = percent > 0 ? '⏳ In Progress' : 'Pending'
    }
    const progressBarClass = (status === '🔴 Behind') ? 'progress-red' : 'progress-green'
    const progressBarColor = (status === '🔴 Behind') ? '#ff4444' : '#4CAF50'
    tableHTML += `
      <tr class="task-row ${progressBarClass}">
        <td class="project-cell">
          <div class="project-name">${name}</div>
          <div class="project-details">${current} of ${target ?? '-'} completed</div>
        </td>
        <td class="progress-cell">
          <div class="progress-bar-container">
            <div class="progress-track">
              <div class="progress-fill" style="width: ${Math.min(percent, 100).toFixed(1)}%; background-color: ${progressBarColor};"></div>
            </div>
          </div>
        </td>
        <td class="percentage-cell">
          <span class="percentage-value">${percent.toFixed(1)}%</span>
        </td>
        <td class="status-cell">
          <span class="status-badge ${progressBarClass}">${status}</span>
        </td>
      </tr>
    `
  })
  
  tableHTML += `
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `
  
  // Remove existing modal if it exists
  const existingModal = document.getElementById('summary-modal')
  if (existingModal) {
    existingModal.remove()
  }
  
  document.body.insertAdjacentHTML('beforeend', tableHTML)
}

function closeSummaryTable() {
  const modal = document.getElementById('summary-modal')
  if (modal) {
    modal.remove()
  }
}

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// Reusable: show All Logs modal and populate table
async function showAllLogsModal() {
  try {
    const res = await fetch('/api/logs')
    if (!res.ok) throw new Error('Failed to fetch logs')
    const logs = await res.json()

    // build goals map
    const goalsMap = {}
    for (const g of (goalsData || [])) goalsMap[g.id] = g.text

    const tbody = document.querySelector('#all-logs-table tbody')
    tbody.innerHTML = ''
    if (!logs || logs.length === 0) {
      const tr = document.createElement('tr')
      tr.innerHTML = `<td colspan="4" style="text-align:center;color:#666;">No logs found</td>`
      tbody.appendChild(tr)
    } else {
      // newest first
      logs.sort((a,b) => new Date(b.timestamp) - new Date(a.timestamp))
      for (const log of logs) {
        const date = new Date(log.timestamp)
        const formatted = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'})
        const tr = document.createElement('tr')
        tr.innerHTML = `
          <td>${formatted}</td>
          <td>${goalsMap[log.goal_id] || ('Goal ' + log.goal_id)}</td>
          <td class="log-value">${log.value}</td>
          <td>
            <button class="log-btn edit" data-log-id="${log.id}">Edit</button>
            <button class="log-btn delete" data-log-id="${log.id}">Delete</button>
          </td>
        `
        tbody.appendChild(tr)
      }
    }
    document.getElementById('all-logs-modal').style.display = 'block'
  } catch (e) {
    console.error(e)
    alert('Error loading logs')
  }
}

document.addEventListener('DOMContentLoaded', function() {
  const goalEndInput = document.getElementById('goal-end')
  if (goalEndInput) {
    goalEndInput.addEventListener('change', function() {
      // Clear quick date button selections when user manually changes end date
      document.querySelectorAll('.quick-date-btn').forEach(btn => btn.classList.remove('active'))
    })
  }
  
  // Set up auth event listeners
  document.getElementById('show-login').addEventListener('click', showLoginModal)
  document.getElementById('show-register').addEventListener('click', showRegisterModal)
  document.getElementById('cancel-login').addEventListener('click', hideLoginModal)
  document.getElementById('cancel-register').addEventListener('click', hideRegisterModal)
  document.getElementById('logout-btn').addEventListener('click', handleLogout)
  document.getElementById('login-form').addEventListener('submit', handleLogin)
  document.getElementById('register-form').addEventListener('submit', handleRegister)
  
  // Set up user dropdown event listeners
  document.getElementById('user-dropdown-btn').addEventListener('click', toggleUserDropdown)
  document.getElementById('change-password').addEventListener('click', showChangePasswordModal)
  document.getElementById('change-email').addEventListener('click', showChangeEmailModal)
  document.getElementById('reminder-settings').addEventListener('click', showReminderSettingsModal)
  const toggleCompleted = document.getElementById('toggle-completed')
  if (toggleCompleted) {
    toggleCompleted.addEventListener('click', async () => {
      hideCompleted = !hideCompleted
      // persist preference
      try { localStorage.setItem('hideOldGoals', hideCompleted ? '1' : '0') } catch {}
      toggleCompleted.textContent = hideCompleted ? '👀 Show Old Goals' : '🙈 Hide Old Goals'
      applyOldGoalsVisibility()
    })
  }
  document.getElementById('send-manual-reminder').addEventListener('click', sendManualReminder)
  document.getElementById('delete-account').addEventListener('click', showDeleteAccountModal)
  const firstBtn = document.getElementById('create-first-goal')
  if (firstBtn) firstBtn.addEventListener('click', showGoalModal)
  
  // Set up user management modal event listeners
  document.getElementById('cancel-password-change').addEventListener('click', hideChangePasswordModal)
  document.getElementById('cancel-email-change').addEventListener('click', hideChangeEmailModal)
  document.getElementById('cancel-reminder-settings').addEventListener('click', hideReminderSettingsModal)
  document.getElementById('cancel-delete-account').addEventListener('click', hideDeleteAccountModal)
  document.getElementById('change-password-form').addEventListener('submit', handleChangePassword)
  document.getElementById('change-email-form').addEventListener('submit', handleChangeEmail)
  document.getElementById('reminder-settings-form').addEventListener('submit', handleReminderSettings)
  document.getElementById('delete-account-form').addEventListener('submit', handleDeleteAccount)
  
  // FAB: Goals Summary (statistics icon)
  const viewLogsBtn = document.getElementById('view-logs-btn')
  if (viewLogsBtn) {
    viewLogsBtn.addEventListener('click', showGoalsTable)
    viewLogsBtn.title = 'Goals Statistics'
    viewLogsBtn.setAttribute('aria-label', 'Goals Statistics')
  }

  const closeAllLogsBtn = document.getElementById('close-all-logs')
  if (closeAllLogsBtn) {
    closeAllLogsBtn.addEventListener('click', () => {
      document.getElementById('all-logs-modal').style.display = 'none'
    })
  }

  // Delegate edit/delete actions inside All Logs table
  const allLogsTable = document.getElementById('all-logs-table')
  if (allLogsTable) {
    allLogsTable.addEventListener('click', async (e) => {
      const editBtn = e.target.closest('.log-btn.edit')
      const deleteBtn = e.target.closest('.log-btn.delete')
      if (editBtn) {
        const logId = editBtn.getAttribute('data-log-id')
        const row = editBtn.closest('tr')
        const currentValueText = row?.querySelector('.log-value')?.textContent || '0'
        const currentValue = parseFloat(currentValueText)
        await editLog(logId, isNaN(currentValue) ? 0 : currentValue)
        await showAllLogsModal()
      } else if (deleteBtn) {
        const logId = deleteBtn.getAttribute('data-log-id')
        await deleteLog(logId)
        await showAllLogsModal()
      }
    })
  }

  // Close All Logs when clicking outside content
  const allLogsModal = document.getElementById('all-logs-modal')
  if (allLogsModal) {
    allLogsModal.addEventListener('click', (e) => {
      if (e.target === allLogsModal) {
        allLogsModal.style.display = 'none'
      }
    })
  }

  // Close dropdown when clicking outside
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.user-dropdown')) {
      hideUserDropdown()
    }
  })
  
  // Close modals when clicking outside
  const modals = ['change-password-modal', 'change-email-modal', 'reminder-settings-modal', 'delete-account-modal']
  modals.forEach(modalId => {
    const el = document.getElementById(modalId)
    if (!el) return
    el.addEventListener('click', (e) => {
      if (e.target === e.currentTarget) {
        if (modalId === 'change-password-modal') hideChangePasswordModal()
        else if (modalId === 'change-email-modal') hideChangeEmailModal()
        else if (modalId === 'reminder-settings-modal') hideReminderSettingsModal()
        else if (modalId === 'delete-account-modal') hideDeleteAccountModal()
      }
    })
  })

  // Close Goals Summary when clicking close button
  const closeGoalsTableBtn = document.getElementById('close-goals-table')
  if (closeGoalsTableBtn) {
    closeGoalsTableBtn.addEventListener('click', () => {
      const m = document.getElementById('goals-table-modal')
      if (m) m.style.display = 'none'
    })
  }

  // Check authentication status on page load
  checkAuthStatus()

  // Initialize old goals visibility from persisted preference
  try {
    const saved = localStorage.getItem('hideOldGoals')
    if (saved === '1') hideCompleted = true
  } catch {}
  const toggleBtn = document.getElementById('toggle-completed')
  if (toggleBtn) toggleBtn.textContent = hideCompleted ? '👀 Show Old Goals' : '🙈 Hide Old Goals'
  applyOldGoalsVisibility()
})

// Don't load goals immediately - wait for auth check
// loadAndRender() - removed, now called from showMainApp()

// Goals Summary helpers
// Parse YYYY-MM-DD as a local date (midnight local) to avoid UTC offset issues
function parseLocalDate(isoDateStr) {
  if (!isoDateStr || typeof isoDateStr !== 'string') return null
  // Try YYYY-MM-DD (and tolerate trailing time like 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DDTHH:MM:SSZ')
  const m = isoDateStr.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (m) {
    const y = Number(m[1])
    const mo = Number(m[2])
    const d = Number(m[3])
    if (y && mo && d) return new Date(y, mo - 1, d)
  }
  // Fallback: let Date parse it, then coerce to local start of day
  const parsed = new Date(isoDateStr)
  if (!isNaN(parsed.getTime())) return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate())
  // Last resort: try MM/DD/YYYY
  const us = isoDateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/)
  if (us) {
    const mo = Number(us[1])
    const d = Number(us[2])
    const y = Number(us[3])
    if (y && mo && d) return new Date(y, mo - 1, d)
  }
  return null
}

function startOfLocalDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}
async function showGoalsTable() {
  const modal = document.getElementById('goals-table-modal')
  if (!modal) return
  await populateGoalsTable()
  modal.style.display = 'block'
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none'
  })
}

async function populateGoalsTable() {
  try {
    const res = await fetch('/api/goals')
    const tbody = document.getElementById('goals-table-body')
    if (!tbody) return
    if (!res.ok) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:16px;">Unable to load goals</td></tr>'
      return
    }
  const goals = await res.json()
    tbody.innerHTML = ''
  const countEl = document.getElementById('goals-summary-count')
  if (countEl) countEl.textContent = `(${goals ? goals.length : 0})`
    if (!goals || goals.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:16px;">No goals found</td></tr>'
      return
    }
    goals.forEach(g => {
      const name = g.text || g.name || 'Unnamed'
      const target = g.target ?? ''
      const current = (g.status && g.status.progress != null) ? g.status.progress : (g.current_value ?? 0)
      let percent = 0
      if (g.status && typeof g.status.percent === 'number') percent = g.status.percent
      else if (target) {
        const t = Number(target) || 0
        const c = Number(current) || 0
        percent = t > 0 ? Math.max(0, Math.min(100, (c / t) * 100)) : 0
      }
  const gType = (g.status && g.status.task_type) || g.task_type || g.type || 'increment'
  const expectedRaw = (g.status && g.status.expected != null) ? Number(g.status.expected) : null
  let expectedPct = null // resolved percent used for status only (not displayed)
  let expectedTimePct = null // purely time-progress-based percentage (not displayed)
      // Compute elapsed days inclusive based on start/end dates
  let elapsedDays = ''
  let elapsedTitle = ''
      if (g.start_date && g.end_date) {
        try {
          const start = parseLocalDate(g.start_date)
          const end = parseLocalDate(g.end_date)
          const today = startOfLocalDay(new Date())
          if (!isNaN(start.getTime()) && !isNaN(end.getTime())) {
            const msPerDay = 24 * 60 * 60 * 1000
            const totalDaysInclusive = Math.max(1, Math.floor((end - start) / msPerDay) + 1)
            let elapsedInclusive = 0
            if (today < start) {
              elapsedInclusive = 0
            } else if (today > end) {
              elapsedInclusive = totalDaysInclusive
            } else {
              elapsedInclusive = Math.floor((today - start) / msPerDay) + 1
            }
            // Clamp to [1, totalDaysInclusive] as requested (Day 1 counts even before start)
            elapsedInclusive = Math.min(Math.max(elapsedInclusive, 1), totalDaysInclusive)
            elapsedDays = `${elapsedInclusive}/${totalDaysInclusive}`
            elapsedTitle = `Start: ${start.toLocaleDateString()} | Today: ${today.toLocaleDateString()} | End: ${end.toLocaleDateString()}`
            const timeProgress = totalDaysInclusive > 0 ? (elapsedInclusive / totalDaysInclusive) : 0
            expectedTimePct = Math.max(0, Math.min(100, timeProgress * 100))
          }
        } catch (e) {
          // leave elapsedDays blank on parse error
        }
      }
      // Resolve expectedPct with a preference for time-based percent when available
      // This avoids 0.0% on day 1 if backend expected is 0
      const tNum = Number(target)
      if (expectedTimePct != null) {
        expectedPct = expectedTimePct
      } else if (gType === 'percentage') {
        if (expectedRaw != null && !isNaN(expectedRaw)) expectedPct = Math.max(0, Math.min(100, expectedRaw))
      } else if (tNum > 0) {
        if (expectedRaw != null && !isNaN(expectedRaw)) {
          expectedPct = Math.max(0, Math.min(100, (expectedRaw / tNum) * 100))
        }
      } else if (expectedRaw != null && !isNaN(expectedRaw)) {
        expectedPct = 0
      }
      // Target % for non-percentage goals is always 100 when a target exists; for percentage goals also 100
      const targetPct = (Number(target) > 0 || gType === 'percentage') ? 100 : ''
      let statusTxt = 'Pending'
      let statusClass = 'progress-red'
      // Normalize expected to percent when available to compare apples-to-apples
      { // status computation (no longer display expected explicitly)
        // First, Completed takes precedence
        if (percent >= 100) {
          statusTxt = '🏁 Completed'
          statusClass = 'progress-green'
        } else {
          const expectedPctLocal = (expectedPct == null) ? 0 : expectedPct
          if (expectedPctLocal > 0) {
            const ratio = percent / expectedPctLocal
            if (ratio >= 1.3) {
              statusTxt = '🚀 Ahead'
              statusClass = 'progress-green'
            } else if (ratio <= 0.7) {
              statusTxt = '⚠️ Behind'
              statusClass = 'progress-orange'
            } else {
              statusTxt = '✅ On Track'
              statusClass = 'progress-green'
            }
          } else {
            // expected is zero or invalid; fall back to simple state
            if (percent === 0) { statusTxt = '✅ On Track'; statusClass = 'progress-green' }
            else if (percent > 0) { statusTxt = '⏳ In Progress'; statusClass = 'progress-green' }
            else { statusTxt = 'Pending'; statusClass = 'progress-red' }
          }
        }
      }
      const statusTitle = (() => {
        const exp = (expectedPct == null) ? 0 : expectedPct
        if (exp > 0) {
          const ratio = percent / exp
          return `Actual: ${percent.toFixed(1)}% | Expected: ${exp.toFixed(1)}% | Ratio: ${ratio.toFixed(2)}`
        }
        return `Actual: ${percent.toFixed(1)}% | Expected: n/a`
      })()
  const tr = document.createElement('tr')
  const barColor = (statusClass === 'progress-green') ? '#2ecc71' : (statusClass === 'progress-orange' ? '#FF9800' : '#e74c3c')
      tr.className = 'task-row'
      tr.innerHTML = `
        <td class="project-cell">
          <div class="project-name">${name}</div>
          <div class="project-details">Target: ${target}</div>
        </td>
        <td>${target}</td>
        <td>${current}</td>
        <td class="progress-cell">
          <div class="progress-bar-container">
            <div class="progress-track">
              <div class="progress-fill" style="width:${percent.toFixed(1)}%;background-color:${barColor}"></div>
            </div>
          </div>
          <div class="percentage-value">${percent.toFixed(1)}%</div>
        </td>
        <td class="status-cell"><span class="status-badge ${statusClass}" title="${statusTitle}">${statusTxt}</span></td>
      `
      tbody.appendChild(tr)
    })
  } catch (e) {
    const tbody = document.getElementById('goals-table-body')
    if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:16px;">Error loading goals</td></tr>'
  }
}
