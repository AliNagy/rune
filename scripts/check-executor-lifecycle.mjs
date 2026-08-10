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
  if (!files.ledger.includes(`| \`${status}\` |`)) {
    throw new Error(`ledger has no executor mapping for status: ${status}`)
  }
}

const requiredBlockedFields = ['blocker:', 'unblock_when:', 'handoff:']
for (const field of requiredBlockedFields) {
  for (const [name, body] of Object.entries({ taskfmt: files.taskfmt, execute: files.execute })) {
    if (!body.includes(field)) throw new Error(`${name} omits blocked field ${field}`)
  }
}

const lifecycleChecks = [
  ['ledger transition', files.ledger, '├─blocked──────────> blocked'],
  ['ledger unblock transition', files.ledger, 'blocked ─unblock condition proven'],
  ['ledger blocker storage', files.ledger, '## Blockers'],
  ['dispatcher fail-closed rule', files.work, 'incomplete blocked return'],
  ['recovery blocked mapping', files.resume, 'incomplete blocked handoff'],
]

for (const [name, body, required] of lifecycleChecks) {
  if (!body.includes(required)) throw new Error(`${name} is missing: ${required}`)
}

console.log('executor lifecycle contract: ok')
