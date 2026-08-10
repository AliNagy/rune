#!/usr/bin/env node
// Verifies that every executor outcome has a parent mapping and that blocked tasks keep
// the same required interface across execution, ledger storage, dispatch, and recovery.
//
//   node scripts/check-executor-lifecycle.mjs

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const read = path => readFileSync(join(root, path), 'utf8')
const files = {
  taskfmt: read('skills/ai-taskfmt/SKILL.md'),
  execute: read('skills/ai-execute/SKILL.md'),
  ledger: read('skills/ai-ledger/SKILL.md'),
  work: read('skills/work/SKILL.md'),
  resume: read('skills/continue/SKILL.md'),
}

const expectedStatuses = ['done', 'drifted', 'budget', 'blocked', 'question']
const returnSection = files.execute.slice(files.execute.lastIndexOf('## Return'))
const enumMatch = returnSection.match(/status: ([a-z |]+)/)
if (!enumMatch) throw new Error('ai-execute has no status enumeration')

const actualStatuses = enumMatch[1].split('|').map(value => value.trim())
if (actualStatuses.join(',') !== expectedStatuses.join(',')) {
  throw new Error(`ai-execute statuses changed: ${actualStatuses.join(', ')}`)
}

for (const status of expectedStatuses) {
  if (!files.work.includes(`| \`${status}\` |`)) {
    throw new Error(`work has no executor mapping for status: ${status}`)
  }
}

const blockedReturnFields = ['blocker:', 'resume_at:', 'detail:']
for (const field of blockedReturnFields) {
  for (const [name, body] of Object.entries({ taskfmt: files.taskfmt, execute: files.execute })) {
    if (!body.includes(field)) throw new Error(`${name} omits blocked return field ${field}`)
  }
}

const blockedHandoffFields = ['blocker:', 'blocker_reason:', 'unblocks_when:']
for (const field of blockedHandoffFields) {
  for (const [name, body] of Object.entries({ taskfmt: files.taskfmt, execute: files.execute })) {
    if (!body.includes(field)) throw new Error(`${name} omits blocked handoff field ${field}`)
  }
}

const lifecycleChecks = [
  ['ledger transition', files.ledger, '├─blocked──────────> blocked'],
  ['ledger unblock transition', files.ledger, 'external block ─unblocks_when observed'],
  ['ledger blocker storage', files.ledger, 'external:<slug>'],
  ['ledger finding pointer', files.ledger, '`latest_finding`'],
  ['blocked worktree policy', files.execute, 'Return `worktree: discarded` only when no task source state exists'],
  ['dispatcher fail-closed rule', files.work, 'without constructing an invalid schema-1 blocked row'],
  ['recovery blocked mapping', files.resume, 'treat the handoff as unusable'],
]

for (const [name, body, required] of lifecycleChecks) {
  if (!body.includes(required)) throw new Error(`${name} is missing: ${required}`)
}

console.log('executor lifecycle contract: ok')
