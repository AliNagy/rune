#!/usr/bin/env node

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
const TASK_COLUMNS = [
  'id',
  'milestone',
  'title',
  'status',
  'blocked_by',
  'worktree',
  'attempts',
  'failures',
  'latest_finding',
  'blocker',
  'resume_at',
]

const STATUSES = new Set([
  'diagnosing',
  'pending',
  'in_progress',
  'verifying',
  'landing',
  'done',
  'drifted',
  'awaiting',
  'blocked',
])

const PENDING_RESUME = /^(fresh|step:[1-9]\d*|evidence:(red_then_green|green_baseline|characterization)|publish)$/
const FINDING = /^\.agent\/[A-Za-z0-9._/#-]+$/
const ATTEMPTS = /^d(\d+)\/e(\d+)\/v(\d+)\/l(\d+)$/

function cells(line) {
  const trimmed = line.trim()
  if (!trimmed.startsWith('|') || !trimmed.endsWith('|')) return null
  return trimmed.slice(1, -1).split('|').map((cell) => cell.trim())
}

function isSeparator(row) {
  return row && row.every((cell) => /^:?-{3,}:?$/.test(cell))
}

function fail(errors, line, message) {
  errors.push(`line ${line}: ${message}`)
}

export function validateLedger(source) {
  const errors = []
  const lines = source.split(/\r?\n/)
  const schemas = lines
    .map((line, index) => ({ line: index + 1, value: line.match(/^schema:\s*(\S+)\s*$/)?.[1] }))
    .filter(({ value }) => value !== undefined)

  if (schemas.length !== 1) {
    errors.push(`expected exactly one schema marker, found ${schemas.length}`)
  } else if (schemas[0].value !== '1') {
    fail(errors, schemas[0].line, `unsupported ledger schema ${schemas[0].value}`)
  }

  const topValue = (name) => {
    const matches = lines
      .map((line, index) => ({ line: index + 1, value: line.match(new RegExp(`^${name}:\\s*(.*?)\\s*$`))?.[1] }))
      .filter(({ value }) => value !== undefined)
    if (matches.length !== 1) {
      errors.push(`expected exactly one ${name} field, found ${matches.length}`)
      return null
    }
    return matches[0]
  }

  const vision = topValue('vision')
  const milestone = topValue('current_milestone')
  const oracle = topValue('oracle')
  const main = topValue('main')
  if (vision && !/^(absent|drafting|complete)$/.test(vision.value)) fail(errors, vision.line, `invalid vision ${vision.value}`)
  if (milestone && !/^(—|M-\d{2})$/.test(milestone.value)) fail(errors, milestone.line, `invalid current_milestone ${milestone.value}`)
  if (oracle && oracle.value === '') fail(errors, oracle.line, 'oracle must be a command or none')
  if (main && !/^(green|red)$/.test(main.value)) fail(errors, main.line, `invalid main ${main.value}`)

  const headerIndexes = []
  for (let index = 0; index < lines.length; index++) {
    const row = cells(lines[index])
    if (row?.join('\0') === TASK_COLUMNS.join('\0')) headerIndexes.push(index)
  }

  if (headerIndexes.length !== 1) {
    errors.push(`expected exactly one canonical Tasks table, found ${headerIndexes.length}`)
    return errors
  }

  const headerIndex = headerIndexes[0]
  let sectionIndex = headerIndex - 1
  while (sectionIndex >= 0 && lines[sectionIndex].trim() === '') sectionIndex--
  if (!/^## Tasks\s*$/.test(lines[sectionIndex] ?? '')) {
    fail(errors, headerIndex + 1, 'canonical task table must be the first content under `## Tasks`')
  }

  if (!isSeparator(cells(lines[headerIndex + 1] ?? ''))) {
    fail(errors, headerIndex + 2, 'task table separator must contain one cell per canonical field')
    return errors
  }

  const tasks = []
  for (let index = headerIndex + 2; index < lines.length; index++) {
    const row = cells(lines[index])
    if (!row) break
    if (row.length !== TASK_COLUMNS.length) {
      fail(errors, index + 1, `expected ${TASK_COLUMNS.length} task fields, found ${row.length}`)
      continue
    }
    tasks.push({ line: index + 1, value: Object.fromEntries(TASK_COLUMNS.map((key, i) => [key, row[i]])) })
  }

  const ids = new Set(tasks.map(({ value }) => value.id))
  const seen = new Set()

  for (const task of tasks) {
    const { line, value } = task
    const {
      id, milestone, title, status, blocked_by: blockedBy, worktree, attempts,
      failures: rawFailures, latest_finding: finding, blocker, resume_at: resume,
    } = value

    if (!/^T-\d{3}$/.test(id)) fail(errors, line, `invalid task id ${id || '(empty)'}`)
    if (seen.has(id)) fail(errors, line, `duplicate task id ${id}`)
    seen.add(id)
    if (!/^M-\d{2}$/.test(milestone)) fail(errors, line, `invalid milestone ${milestone || '(empty)'}`)
    if (!title || title === '—') fail(errors, line, 'title must be nonempty')
    if (!STATUSES.has(status)) fail(errors, line, `invalid status ${status || '(empty)'}`)

    const dependencies = blockedBy === '—' ? [] : blockedBy.split(',').map((item) => item.trim())
    for (const dependency of dependencies) {
      if (!/^T-\d{3}$/.test(dependency)) fail(errors, line, `invalid dependency ${dependency || '(empty)'}`)
      else if (dependency === id) fail(errors, line, 'task cannot depend on itself')
      else if (!ids.has(dependency)) fail(errors, line, `dependency ${dependency} has no task row`)
    }

    const attemptMatch = attempts.match(ATTEMPTS)
    if (!attemptMatch) {
      fail(errors, line, `attempts must be dN/eN/vN/lN, got ${attempts || '(empty)'}`)
      continue
    }

    const [, d, e, v, l] = attemptMatch.map(Number)
    const failures = Number(rawFailures)
    if (!/^\d+$/.test(rawFailures)) fail(errors, line, `failures must be a non-negative integer, got ${rawFailures || '(empty)'}`)
    else if (failures > v) fail(errors, line, `failures ${failures} cannot exceed verifier attempts ${v}`)

    const absoluteWorktree = worktree.startsWith('/')
    if (!(worktree === '—' || worktree === 'discarded' || worktree === 'merged' || absoluteWorktree)) {
      fail(errors, line, `worktree must be —, discarded, merged, or an absolute path`)
    }
    if (!(finding === '—' || FINDING.test(finding))) {
      fail(errors, line, `latest_finding must be — or a coordination-relative .agent/ pointer`)
    }
    if (failures > 0 && finding === '—') fail(errors, line, 'a task with verifier failures requires latest_finding')

    const external = /^external:[a-z0-9][a-z0-9-]*$/.test(blocker)
    const decision = /^decision:DEC-\d{3}$/.test(blocker)
    const drift = /^drift:DRF-\d{3}$/.test(blocker)
    const knownBlocker = blocker === '—' || blocker === 'main:red' || external || decision || drift
    if (!knownBlocker) fail(errors, line, `invalid blocker ${blocker || '(empty)'}`)
    if (external && finding === '—') fail(errors, line, 'external blocker requires a finding pointer with reason and unblock condition')

    if (status === 'diagnosing') {
      if (!absoluteWorktree) fail(errors, line, 'diagnosing requires an absolute worktree')
      if (d < 1 || e !== 0 || v !== 0 || l !== 0) fail(errors, line, 'diagnosing requires d>=1 and e0/v0/l0')
      if (!(resume === 'diagnose' || /^plan:M-\d{2}\/R-\d{3}$/.test(resume))) fail(errors, line, 'diagnosing resume_at must be diagnose or plan:M-nn/R-nnn')
      if (!(blocker === '—' || external)) fail(errors, line, 'diagnosing blocker must be — or external:*')
    }

    if (status === 'pending') {
      if (blocker !== '—') fail(errors, line, 'pending requires blocker —')
      if (!PENDING_RESUME.test(resume)) fail(errors, line, 'pending has invalid resume_at')
      if (!absoluteWorktree && resume !== 'fresh') fail(errors, line, 'pending without a live worktree must resume fresh')
      if (/^(step:|evidence:)/.test(resume) && finding === '—') fail(errors, line, 'pending partial resume requires a finding pointer')
    }

    if (status === 'in_progress') {
      if (!absoluteWorktree || e < 1 || blocker !== '—' || resume !== 'recover') {
        fail(errors, line, 'in_progress requires an absolute worktree, e>=1, blocker —, and resume_at recover')
      }
    }

    if (status === 'verifying') {
      if (!absoluteWorktree || e < 1 || v < 1 || blocker !== '—' || resume !== 'verify') {
        fail(errors, line, 'verifying requires an absolute worktree, e>=1, v>=1, blocker —, and resume_at verify')
      }
    }

    if (status === 'landing') {
      if (!absoluteWorktree || v < 1 || l < 1 || blocker !== '—' || resume !== 'land') {
        fail(errors, line, 'landing requires an absolute worktree, v>=1, l>=1, blocker —, and resume_at land')
      }
    }

    if (status === 'done') {
      if (!(worktree === 'merged' || absoluteWorktree) || blocker !== '—' || resume !== '—') {
        fail(errors, line, 'done requires merged or cleanup-pending absolute worktree, blocker —, and resume_at —')
      }
    }

    if (status === 'drifted' && (!drift || resume !== 'replan' || finding === '—')) {
      fail(errors, line, 'drifted requires drift blocker, finding pointer, and resume_at replan')
    }

    if (status === 'awaiting') {
      if (!absoluteWorktree || !decision || !PENDING_RESUME.test(resume) || finding === '—') {
        fail(errors, line, 'awaiting requires an absolute worktree, decision blocker, finding pointer, and pending resume token')
      }
    }

    if (status === 'blocked') {
      if (!(external || drift || blocker === 'main:red')) fail(errors, line, 'blocked requires external, drift, or main:red blocker')
      if (finding === '—') fail(errors, line, 'blocked requires a finding pointer')
      if (drift && resume !== 'replan') fail(errors, line, 'drift-blocked task must resume at replan')
      if (blocker === 'main:red' && resume !== 'land') fail(errors, line, 'main:red task must resume at land')
      if (external && !(PENDING_RESUME.test(resume) || resume === 'diagnose' || resume === 'verify' || resume === 'land')) {
        fail(errors, line, 'externally blocked task has invalid resume_at')
      }
      if (external && !absoluteWorktree && resume !== 'fresh') {
        fail(errors, line, 'externally blocked task without a live worktree must resume fresh')
      }
    }
  }

  return errors
}

function checkFile(path) {
  return validateLedger(readFileSync(path, 'utf8')).map((error) => `${path}: ${error}`)
}

if (resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2)
  if (args.length === 0) {
    console.error('usage: node scripts/validate-ledger.mjs <ledger.md> [...]')
    process.exitCode = 2
  } else {
    const failures = args.flatMap((path) => checkFile(resolve(path)))
    if (failures.length) {
      console.error(failures.join('\n'))
      process.exitCode = 1
    } else {
      for (const path of args) console.log(`valid ledger: ${path}`)
    }
  }
}
