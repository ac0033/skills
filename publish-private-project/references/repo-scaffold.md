# 公开仓库的配套：模板与命令

## 备份与全新历史

```bash
git bundle create ../<项目>-history-<日期>.bundle --all && git bundle verify ../<项目>-history-<日期>.bundle
git branch archive/private-history main            # 本地归档，永不推送
git config user.name "<GitHub 显示名>"
git config user.email "<id>+<用户名>@users.noreply.github.com"
git checkout --orphan main-public
git rm -r --cached -q . && git add -A              # 按新的 .gitignore 重新收
git commit -m "vX.Y.Z · 首次公开发布（公开预览）"
git tag -d $(git tag)                              # 旧标签指向旧历史，全部删掉（bundle 里有）
git branch -D main && git branch -m main
gh repo create <用户>/<仓库> --private --description "<一句话>" --source . --push
git tag vX.Y.Z && git push origin vX.Y.Z           # 触发 Release 工作流
# 验证通过、用户看过之后：
gh repo edit <用户>/<仓库> --visibility public --accept-visibility-change-consequences
```

## .gitignore 追加

```
# 开发者私人材料（方案、交接记录、真实项目快照、性能脚本），不进版本库
/.notes/
# 编码助手的仓库本地配置。只忽略根目录那份（带前导 /）：写成 .claude/ 会把模板目录里的 .claude/ 也排除掉，那是产品文件
/.claude/
*.bundle
```

## 公开卫生测试（Python 项目模板）

```python
"""公开卫生：已跟踪的文件里不能出现本机信息，版本号多处一致，私人目录不进版本库。"""
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FORBIDDEN = [
    re.compile(r"[A-Z]:\\(?![nrtu\"\\])(?!work\\我的项目)"),   # Windows 路径；放行 JSON 转义与通用示例
    re.compile(r"[A-Z]:/(?!work/)"),
    re.compile(r"/Users/[a-z]|/home/[a-z]"),
    re.compile(r"<编码助手数据目录>|<盘符下的一级目录名>"),
    re.compile(r"<私人项目名>|<单位系统代号>"),
    re.compile(r"[A-Za-z0-9._%+-]+@gmail\.com"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]
TEXT = {".py", ".ts", ".tsx", ".css", ".md", ".yaml", ".yml", ".json", ".toml", ".html", ".ipynb", ".txt"}
SKIP = {"uv.lock", "web/pnpm-lock.yaml"}


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout
    return [REPO / p for p in out.decode().split("\0") if p]


def test_no_local_information():
    hits = []
    for path in tracked():
        rel = path.relative_to(REPO).as_posix()
        if rel in SKIP or path.suffix not in TEXT or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in FORBIDDEN:
            for m in pat.finditer(text):
                hits.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}: {m.group(0)}")
    assert not hits, "已跟踪文件里出现本机信息：\n" + "\n".join(hits[:40])


def test_private_dirs_ignored():
    ignore = {line.lstrip("/") for line in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()}
    assert ".notes/" in ignore and ".claude/" in ignore
```

## CI（GitHub Actions，uv + pnpm）

```yaml
name: CI
on: { push: { branches: [main] }, pull_request: }
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy: { fail-fast: false, matrix: { os: [ubuntu-latest, windows-latest] } }
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 10 }
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: pnpm, cache-dependency-path: web/pnpm-lock.yaml }
      - run: pnpm --dir web install --frozen-lockfile && pnpm --dir web run build
      - uses: astral-sh/setup-uv@v6
        with: { enable-cache: true }
      - run: uv sync --all-extras --dev
      - run: uv run ruff check .
      - run: uv run pytest -m "not slow" -q
```

## Release（推送 v* 标签时构建安装包并发 pre-release）

```yaml
name: Release
on: { push: { tags: ["v*"] } }
permissions: { contents: write }
jobs:
  build-and-release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # …构建前端同上…
      - uses: astral-sh/setup-uv@v6
      - run: uv build --wheel
      - name: 从 CHANGELOG 截取本版本
        run: |
          tag="${GITHUB_REF_NAME#v}"
          awk -v v="$tag" '/^## / { if (found) exit; if (index($0, "## " v " ") == 1) found=1 } found { print }' docs/CHANGELOG.md > release-notes.md
          test -s release-notes.md || echo "见 docs/CHANGELOG.md" > release-notes.md
      - uses: softprops/action-gh-release@v2
        with: { name: "${{ github.ref_name }}", body_path: release-notes.md, prerelease: true, files: dist/*.whl }
```

## README 第一屏要有的东西

1. 徽章：CI、Release、License、语言版本。
2. **项目状态**一行：公开预览——代码与功能已公开，可本机安装试用；没做完的部分（登录、部署）写明，暂不提供在线服务。
3. 真实的克隆地址与 Releases 页链接。
4. 末尾：安全说明（密钥存哪、对外开放要带令牌、没有登录别暴露公网）、许可。

## 个人主页项目表

```
| **[<仓库>](https://github.com/<用户>/<仓库>)** | <一句话：解决什么问题、主要内容> | 🔍 公开预览 |
<sub>"公开预览"：代码与功能已公开，可在本机安装试用；<没做完的部分>尚未完成，暂不提供在线服务。</sub>
```

## pyproject.toml 补齐

```toml
license = "MIT"
license-files = ["LICENSE"]
authors = [{ name = "<显示名>" }]
classifiers = ["Development Status :: 3 - Alpha", "Programming Language :: Python :: 3.13"]

[project.urls]
Homepage = "https://github.com/<用户>/<仓库>"
Changelog = "https://github.com/<用户>/<仓库>/blob/main/docs/CHANGELOG.md"
Issues = "https://github.com/<用户>/<仓库>/issues"

[tool.ruff]
line-length = 200
exclude = [".notes", "web"]

[tool.ruff.lint]
select = ["E", "F"]
ignore = ["E501", "E741"]
```
