import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

const skill = (name) => readFileSync(join(ROOT, 'skills', name, 'SKILL.md'), 'utf8')

const git = (cwd, ...args) => execFileSync('git', args, {
  cwd,
  encoding: 'utf8',
}).trim()

test('one immutable commit crosses the executor, verifier, and lander interfaces', () => {
  const execute = skill('ai-execute')
  const verify = skill('ai-verify')
  const work = skill('work')
  const land = skill('ai-land')
  const taskfmt = skill('ai-taskfmt')
  const resume = skill('continue')

  assert.match(execute, /base_commit:/)
  assert.match(execute, /artifact_commit:/)
  assert.match(execute, /git commit/)
  assert.match(execute, /status: done[\s\S]*artifact_commit:/)

  assert.match(verify, /base_commit:/)
  assert.match(verify, /artifact_commit:/)
  assert.match(verify, /verified_commit:/)
  assert.match(verify, /git diff <base_commit>\.\.<artifact_commit>/)

  assert.match(work, /verified_commit/)
  assert.match(work, /artifact_commit/)

  assert.match(land, /verified_commit/)
  assert.match(land, /git merge <verified_commit>/)
  assert.match(land, /branch HEAD[\s\S]*verified commit/)
  assert.match(land, /already an ancestor of main/)
  assert.match(land, /git worktree remove <worktree_path>/)

  assert.match(taskfmt, /executor publishes one immutable range/)
  assert.match(resume, /Valid complete publication present/)
  assert.match(resume, /empty diff, branch ahead/)
})

test('a worktree edit can be published, verified, landed, and cleaned up', () => {
  const repository = mkdtempSync(join(tmpdir(), 'rune-commit-handoff-'))
  const worktree = join(repository, 'task-worktree')

  try {
    git(repository, 'init', '-b', 'main')
    git(repository, 'config', 'user.name', 'Rune Test')
    git(repository, 'config', 'user.email', 'rune@example.test')

    writeFileSync(join(repository, 'base.txt'), 'base\n')
    git(repository, 'add', 'base.txt')
    git(repository, 'commit', '-m', 'base')
    const baseCommit = git(repository, 'rev-parse', 'HEAD')

    git(repository, 'worktree', 'add', '-b', 'task/T-001', worktree)
    writeFileSync(join(worktree, 'feature.txt'), 'published change\n')
    git(worktree, 'add', 'feature.txt')
    git(worktree, 'commit', '-m', 'T-001: publish the feature')
    const artifactCommit = git(worktree, 'rev-parse', 'HEAD')

    assert.equal(git(worktree, 'status', '--porcelain'), '')
    assert.equal(git(repository, 'diff', '--name-only', `${baseCommit}..${artifactCommit}`), 'feature.txt')

    const verifiedCommit = artifactCommit
    assert.equal(git(repository, 'rev-parse', 'task/T-001'), verifiedCommit)

    git(repository, 'merge', verifiedCommit)
    assert.equal(readFileSync(join(repository, 'feature.txt'), 'utf8'), 'published change\n')
    git(repository, 'merge-base', '--is-ancestor', verifiedCommit, 'HEAD')

    git(repository, 'worktree', 'remove', worktree)
    git(repository, 'branch', '-d', 'task/T-001')

    assert.equal(existsSync(worktree), false)
    assert.equal(git(repository, 'branch', '--list', 'task/T-001'), '')
  } finally {
    rmSync(repository, { recursive: true, force: true })
  }
})
