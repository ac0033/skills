#!/usr/bin/env node
// 综合插件 product-dev 的装配脚本：把各组件复制进插件目录，并写出 BUILD.lock.json。
// 业务含义：插件里“取自组件”的部分不手改，一律由本脚本从组件生成；组件更新后重新运行即可。
// 用法：node tools/build-plugin.mjs [--out <目录>]   （默认写入仓库里的 product-dev/）
// 只用 Node 内置模块。结果只取决于输入内容：不写时间戳，文件按路径排序。
import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const PLUGIN_DIR = 'product-dev';
/** 插件里唯一可由用户调用的技能（手写，不由本脚本生成）。 */
export const ENTRY_SKILL = 'product-dev';
/** 插件里手写、不由本脚本生成的文件。 */
export const HANDWRITTEN = ['.gitattributes', '.claude-plugin/plugin.json', '.codex-plugin/plugin.json', `skills/${ENTRY_SKILL}/SKILL.md`, 'THIRD_PARTY_NOTICES.md'];
const LOCK = 'BUILD.lock.json';
const MODIFIED_NOTE = '# Modified by the product-dev plugin build: user-invocable set to false. See THIRD_PARTY_NOTICES.md at the plugin root.';

const git = (cwd, ...args) => execFileSync('git', ['-C', cwd, ...args], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
const sha = (buf) => crypto.createHash('sha256').update(buf).digest('hex');

/** 一组文件（相对路径 → 内容）的哈希：按路径排序后逐个计入路径和内容哈希。 */
export function hashFiles(files) {
  const h = crypto.createHash('sha256');
  for (const rel of [...files.keys()].sort()) h.update(`${rel}\0${sha(files.get(rel))}\n`);
  return h.digest('hex');
}

/** 读出某个目录下的全部文件（相对路径用正斜杠）。 */
export function readTree(dir, out = new Map(), base = dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) readTree(p, out, base);
    else out.set(path.relative(base, p).replace(/\\/g, '/'), fs.readFileSync(p));
  }
  return out;
}

/**
 * 把技能头部改成“模型可加载、不出现在命令菜单”：去掉 disable-model-invocation，user-invocable 统一为 false。
 * note 不为空时在头部加一行 YAML 注释，说明文件被改过（Apache-2.0 第 4(b) 条要求）。
 */
export function hideSkill(buf, note = '') {
  const text = buf.toString('utf8');
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---(\r?\n|$)/);
  if (!m) throw new Error('SKILL.md 没有文件头');
  const nl = m[0].includes('\r\n') ? '\r\n' : '\n';
  const kept = m[1].split(/\r?\n/).filter((l) => !/^(disable-model-invocation|user-invocable):/.test(l));
  const head = ['---', ...kept, 'user-invocable: false', ...(note ? [note] : []), '---'].join(nl) + nl;
  return Buffer.from(head + text.slice(m[0].length), 'utf8');
}

/** 自有组件：取 git 跟踪或未忽略的文件，这样 *.local.md、测试产物等被忽略的内容不会带进插件。 */
function ownFiles(root, src) {
  const files = new Map();
  for (const rel of git(root, 'ls-files', '-co', '--exclude-standard', '-z', '--', src).split('\0').filter(Boolean).sort()) {
    const abs = path.join(root, rel);
    if (rel.endsWith('.local.md') || !fs.existsSync(abs)) continue;
    files.set(src === rel ? path.basename(rel) : rel.slice(src.length + 1), fs.readFileSync(abs));
  }
  if (!files.size) throw new Error(`自有组件没有文件：${src}`);
  return files;
}

/**
 * 第三方组件：读本机 vendor 存档里的文件。存档是 git 检出时只取已提交的文件，并且：
 * - 要求这些路径没有本地改动；
 * - 检出时被本机 autocrlf 换成 CRLF 的文本文件还原为 LF（上游指定 eol=crlf 的批处理文件保持 CRLF），
 *   这样结果与上游一致，不随本机 git 配置变化。
 */
function vendorFiles(repo, sub, keep = () => true) {
  const files = new Map();
  const add = (rel, buf) => {
    const inner = rel === sub ? path.basename(rel) : rel.slice(sub.length + 1);
    if (keep(inner)) files.set(inner, buf);
  };
  if (fs.existsSync(path.join(repo, '.git'))) {
    const dirty = git(repo, 'status', '--porcelain', '--', sub).trim();
    if (dirty) throw new Error(`${repo} 的 ${sub} 有未提交的改动，无法确定版本：\n${dirty}`);
    for (const line of git(repo, 'ls-files', '--eol', '-z', '--', sub).split('\0').filter(Boolean)) {
      const [info, rel] = line.split('\t');
      let buf = fs.readFileSync(path.join(repo, rel));
      if (/\bi\/lf\b/.test(info) && /\bw\/crlf\b/.test(info) && !/eol=crlf/.test(info)) buf = Buffer.from(buf.toString('latin1').replace(/\r\n/g, '\n'), 'latin1');
      add(rel, buf);
    }
  } else {
    const abs = path.join(repo, sub);
    if (fs.statSync(abs).isFile()) add(sub, fs.readFileSync(abs));
    else for (const [rel, buf] of readTree(abs)) add(`${sub}/${rel}`, buf);
  }
  if (!files.size) throw new Error(`第三方组件没有文件：${repo}/${sub}`);
  return files;
}

const json = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const commitOf = (repo) => (fs.existsSync(path.join(repo, '.git')) ? git(repo, 'rev-parse', 'HEAD').trim() : null);
const merge = (...maps) => new Map(maps.flatMap((m) => [...m]));
const withSkill = (files, note) => files.set('SKILL.md', hideSkill(files.get('SKILL.md'), note));
/** 行为用例属于仓库的自身验证，不随插件分发：组件里指向它的相对链接改成仓库网址，装好后仍可到达。 */
const CASES_LINK = '](../evals/cases.md)';
const CASES_URL = '](https://github.com/ac0033/skills/blob/main/evals/cases.md)';
function relinkCases(files) {
  for (const [rel, buf] of files) if (rel.endsWith('.md') && buf.includes(CASES_LINK)) files.set(rel, Buffer.from(buf.toString('utf8').replaceAll(CASES_LINK, CASES_URL)));
  return files;
}

/** 自有部分：每项 { id, dest, component, version, license, changes, files }。 */
function ownParts(root) {
  const kitVersion = json(path.join(root, 'engineering-kit/bundle.json')).bundleVersion;
  const skill = (name, version, changes) => ({
    id: name, dest: `skills/${name}`, component: name, version, license: 'MIT', changes, files: relinkCases(withSkill(ownFiles(root, name))),
  });
  const hidden = '头部加 user-invocable: false';
  return [
    skill('engineering-kit', kitVersion, '头部去掉 disable-model-invocation，加 user-invocable: false'),
    skill('product-design-orchestrator', null, `${hidden}；指向 ../evals/cases.md 的链接改为仓库网址`),
    skill('product-discovery-prd', null, '无（头部原本就是 user-invocable: false）'),
    skill('prototype-design', null, '无（头部原本就是 user-invocable: false）'),
    skill('system-architecture-design', null, '无（头部原本就是 user-invocable: false）'),
    { id: 'license', dest: 'LICENSE', component: '仓库根 LICENSE', version: null, license: 'MIT', changes: '无', files: ownFiles(root, 'LICENSE') },
  ];
}

/** 第三方部分；本机没有 vendor 存档时返回 null。 */
function thirdPartyParts(vendor) {
  const [imp, arc, fd] = ['impeccable', 'archify', 'feature-dev'].map((n) => path.join(vendor, n));
  if (![imp, arc, fd].every((d) => fs.existsSync(d))) return null;
  const meta = (component, source, version, repo) => ({ component, source, version, commit: commitOf(repo), license: 'Apache-2.0', thirdParty: true });
  const impMeta = meta('impeccable', 'https://github.com/pbakaus/impeccable', json(path.join(imp, 'plugin/.claude-plugin/plugin.json')).version, imp);
  const arcMeta = meta('archify', 'https://github.com/tt-a1i/archify', json(path.join(arc, 'archify/skill-release.json')).version, arc);
  const fdMeta = meta('feature-dev', 'https://github.com/anthropics/claude-plugins-official', json(path.join(fd, '.claude-plugin/plugin.json')).version, fd);
  const arcExcluded = (rel) => /^examples\/[^/]+\.html$/.test(rel);
  return [
    {
      id: 'impeccable', dest: 'skills/impeccable', ...impMeta,
      from: ['plugin/skills/impeccable/', 'LICENSE', 'NOTICE.md'],
      changes: 'SKILL.md 头部 user-invocable 由 true 改为 false，并加一行改动说明注释；其余文件原样',
      files: withSkill(merge(vendorFiles(imp, 'plugin/skills/impeccable'), vendorFiles(imp, 'LICENSE'), vendorFiles(imp, 'NOTICE.md')), MODIFIED_NOTE),
    },
    {
      id: 'impeccable-agents', dest: 'agents', listFiles: true, ...impMeta,
      from: ['plugin/agents/'], changes: '无', files: vendorFiles(imp, 'plugin/agents'),
    },
    {
      id: 'archify', dest: 'skills/archify', ...arcMeta,
      from: ['archify/'], excluded: ['examples/*.html（示例图的成品页，只被上游重新生成示例的脚本引用）'],
      changes: 'SKILL.md 头部加 user-invocable: false 和一行改动说明注释；排除示例成品页；其余文件原样',
      files: withSkill(vendorFiles(arc, 'archify', (rel) => !arcExcluded(rel)), MODIFIED_NOTE),
    },
    {
      id: 'feature-dev-agents', dest: 'agents', listFiles: true, ...fdMeta,
      from: ['plugins/feature-dev/agents/'], changes: '无', files: vendorFiles(fd, 'agents', (rel) => rel.endsWith('.md')),
    },
  ];
}

const lockEntry = ({ files, listFiles, thirdParty, ...rest }) => ({
  ...rest, fileCount: files.size, sha256: hashFiles(files), ...(listFiles ? { files: [...files.keys()].sort() } : {}),
});

/** 装配插件。返回 { lock, thirdPartyBuilt }。 */
export function build({ root = ROOT, out = path.join(root, PLUGIN_DIR), vendor = path.join(root, 'vendor'), log = console.log } = {}) {
  const own = ownParts(root);
  const third = thirdPartyParts(vendor);
  const committedLock = path.join(root, PLUGIN_DIR, LOCK);
  const previous = fs.existsSync(committedLock) ? json(committedLock).parts : [];

  const write = (part) => {
    const dest = path.join(out, part.dest);
    if (!part.listFiles) fs.rmSync(dest, { recursive: true, force: true });
    for (const [rel, buf] of part.files) {
      // dest 本身是文件（如 LICENSE）时直接写到 dest
      const target = part.files.size === 1 && !part.dest.includes('/') && part.dest === rel ? dest : path.join(dest, rel);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, buf);
    }
  };

  own.forEach(write);
  let thirdEntries;
  if (third) {
    fs.rmSync(path.join(out, 'agents'), { recursive: true, force: true });
    third.forEach(write);
    thirdEntries = third.map(lockEntry);
  } else {
    thirdEntries = previous.filter((p) => p.source);
    log(`提示：没有找到第三方组件的本机存档（${vendor}），只重建了自有组件部分；第三方部分保持仓库里已提交的内容。`);
  }
  const lock = { note: '由 tools/build-plugin.mjs 生成，不要手改。', parts: [...own.map(lockEntry), ...thirdEntries] };
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, LOCK), `${JSON.stringify(lock, null, 2)}\n`);
  return { lock, thirdPartyBuilt: Boolean(third) };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const i = process.argv.indexOf('--out');
  const out = i > 0 ? path.resolve(process.argv[i + 1]) : undefined;
  const { lock } = build({ out });
  for (const p of lock.parts) console.log(`${p.dest.padEnd(40)} ${String(p.fileCount).padStart(4)} 个文件  ${p.sha256.slice(0, 12)}  ${p.component}${p.version ? ` ${p.version}` : ''}`);
}
