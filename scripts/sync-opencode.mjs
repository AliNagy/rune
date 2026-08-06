#!/usr/bin/env node
// Generates an OpenCode variant of Rune from the canonical Claude Code source.
//
//   node scripts/sync-opencode.mjs [--target <dir>] [--dry-run]
//
// Claude Code namespaces plugin skills as /rune:<name>. OpenCode has no plugin
// namespace, so every skill is emitted with a literal rune- prefix instead, and
// cross-references in skill bodies are rewritten to match.

import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { homedir } from 'node:os'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

const argv = process.argv.slice(2)
const arg = (n, d) => { const i = argv.indexOf(`--${n}`); return i === -1 ? d : argv[i + 1] }
const DRY = argv.includes('--dry-run')
const TARGET = arg('target', join(homedir(), '.config', 'opencode'))

const AI_SKILLS = [
  'taskfmt', 'serena', 'oracle', 'survey', 'decompose', 'report', 'recover',
  'bug', 'feature', 'refactor', 'investigate', 'research', 'drift', 'verify',
  'ledger', 'execute', 'triage',
]

// Claude Code's /rune:init becomes OpenCode's /rune-init; bare ai-* skill
// references pick up the prefix they lose without a plugin namespace.
//
// There is nothing else to translate. Rune defines no agents, so no tool lists,
// model tiers, or agent names need mapping onto this harness's spelling of them.
function rewriteBody(text) {
  return text
    .replace(/\/rune:/g, '/rune-')
    .replace(/rune:/g, 'rune-')
    .replace(new RegExp(`\\bai-(${AI_SKILLS.join('|')})\\b`, 'g'), 'rune-ai-$1')
}

function splitFrontmatter(raw) {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!m) throw new Error('no frontmatter')
  const fields = {}
  for (const line of m[1].split(/\r?\n/)) {
    const f = line.match(/^([a-zA-Z-]+):\s*(.*)$/)
    if (f) fields[f[1]] = f[2]
  }
  return { fields, body: m[2] }
}

const write = (path, content) => {
  if (DRY) return
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, content, 'utf8')
}

let skillCount = 0
const skillsOut = join(TARGET, 'skills')

for (const name of readdirSync(join(ROOT, 'skills'))) {
  const src = join(ROOT, 'skills', name, 'SKILL.md')
  if (!existsSync(src)) continue

  const { fields, body } = splitFrontmatter(readFileSync(src, 'utf8'))
  const outName = `rune-${name}`

  // user-invocable is a Claude Code field. OpenCode ignores unknown frontmatter,
  // so it is preserved rather than dropped: harmless now, correct if support lands.
  const fm = [
    '---',
    `name: ${outName}`,
    ...(fields['user-invocable'] ? [`user-invocable: ${fields['user-invocable']}`] : []),
    `description: ${rewriteBody(fields.description)}`,
    '---',
  ].join('\n')

  write(join(skillsOut, outName, 'SKILL.md'), `${fm}\n${rewriteBody(body)}`)
  skillCount++
}

console.log(`${DRY ? '[dry run] ' : ''}rune -> opencode`)
console.log(`  skills   ${skillCount}  -> ${skillsOut}`)
console.log('  agents   none — Rune defines no agents')
if (!DRY) console.log('\nRestart OpenCode, then run /rune-init')
