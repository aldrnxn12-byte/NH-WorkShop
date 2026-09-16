"""`docs/가이드/*.md` → `site/guide/` 정적 HTML 변환.

실행:  python site/tools/build_guide.py      (프로젝트 어디서 실행하든 동작)

- 외부 라이브러리·CDN·스크립트 없음(사이트 규칙). 표준 라이브러리만.
- 원문은 **제작 창 소관**이다. 여기서는 읽기만 하고 고치지 않는다(오탈자는 보고로).
- 원문 폴더가 없으면 목차 틀만 만들고 「준비 중」으로 둔다.

원문 규칙 (제작 창이 지켜 주면 목차가 예쁘게 나온다)
  파일명:  `10_OpenAI_키.md` 처럼 **숫자_제목.md** — 숫자 순서대로 나열된다.
  제목:    파일 첫 `# 제목` 줄 (없으면 파일명에서 뽑는다)
  분류:    본문 어디든 `<!-- guide: 필수 -->` 또는 `<!-- guide: 선택 -->`
  무료경로: `<!-- guide-free -->` 가 있으면 「무료 최소 경로」로 강조
지원 문법: 제목(#~####), 문단, 목록(- / 1.), 표, 코드블록(```), 인용(>), 구분선,
           **굵게**, `코드`, [링크](url), 이미지.
"""
from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "가이드"
OUT = ROOT / "site" / "guide"

HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — NH Factory</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header class="site">
  <div class="wrap">
    <a class="brand" href="/">NH Factory</a>
    <nav>
      <a href="/guide/">연결 가이드</a>
      <a href="/privacy/ko/">개인정보처리방침</a>
      <a href="/terms/">이용약관</a>
    </nav>
  </div>
</header>

<main class="wrap">
"""

FOOT = """</main>

<footer class="site">
  <div class="wrap">
    <nav>
      <a href="/">홈</a>
      <a href="/guide/">연결 가이드</a>
      <a href="/privacy/">Privacy Policy</a>
      <a href="/privacy/ko/">개인정보처리방침</a>
      <a href="/terms/">이용약관</a>
    </nav>
    <p>&copy; 2026 나흘공방(대표 방하늘). NH Factory는 YouTube 또는 Google과 제휴 관계가 없으며 보증을 받지 않았습니다.</p>
  </div>
</footer>
</body>
</html>
"""


# ── 아주 작은 마크다운 변환기 (필요한 문법만) ──────────────


def _slug(stem: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣_-]", "-", stem)


def _href(url: str) -> str:
    """원문끼리의 `01_설치.md` 링크를 사이트 주소 `/guide/01_설치/` 로 바꾼다."""
    if url.startswith(("http://", "https://", "/", "#", "mailto:")):
        return url
    if url.endswith(".md") or ".md#" in url:
        name, _, frag = url.partition("#")
        slug = _slug(Path(name).stem)
        return "/guide/%s/%s" % (slug, "#" + frag if frag else "")
    return url


def _img(alt: str, src: str) -> str:
    """원문 이미지가 아직 없으면 깨진 이미지 대신 「준비 중」 칸을 보여준다.
    스샷은 제작 창이 `docs/가이드/shots/` 에 넣는다 — 들어오면 자동으로 그림이 뜬다."""
    if src.startswith(("http://", "https://", "/")):
        return '<img src="%s" alt="%s">' % (src, alt)
    if (SRC / src).exists():
        return '<img src="/guide/shots/%s" alt="%s">' % (Path(src).name, alt)
    label = re.sub(r"^자리\s*:\s*", "", alt).strip() or "화면"
    return "<span class='note'>[화면 사진 준비 중 — %s]</span>" % label


def inline(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: _img(m.group(1), m.group(2)), t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: '<a href="%s">%s</a>' % (_href(m.group(2)), m.group(1)), t)
    return t


def md_to_html(md: str) -> str:
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    list_tag: str | None = None

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    while i < len(lines):
        ln = lines[i]

        if ln.startswith("```"):  # 코드블록
            close_list()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(html.escape(lines[i]))
                i += 1
            i += 1
            out.append("<pre class='card'><code>" + "\n".join(buf) + "</code></pre>")
            continue

        if ln.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].strip()) <= set("|-: "):
            close_list()  # 표
            header = [c.strip() for c in ln.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            out.append("<div style='overflow-x:auto'><table><thead><tr>")
            out += [f"<th>{inline(c)}</th>" for c in header]
            out.append("</tr></thead><tbody>")
            for r in rows:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            out.append("</tbody></table></div>")
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            close_list()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        if re.match(r"^\s*[-*]\s+", ln):
            if list_tag != "ul":
                close_list()
                out.append("<ul>")
                list_tag = "ul"
            out.append(f"<li>{inline(re.sub(r'^\\s*[-*]\\s+', '', ln))}</li>")
            i += 1
            continue

        if re.match(r"^\s*\d+[.)]\s+", ln):
            if list_tag != "ol":
                close_list()
                out.append("<ol>")
                list_tag = "ol"
            out.append(f"<li>{inline(re.sub(r'^\\s*\\d+[.)]\\s+', '', ln))}</li>")
            i += 1
            continue

        if ln.startswith(">"):
            close_list()
            out.append(f"<blockquote class='card'>{inline(ln.lstrip('> '))}</blockquote>")
            i += 1
            continue

        if re.match(r"^\s*---+\s*$", ln):
            close_list()
            out.append("<hr>")
            i += 1
            continue

        if not ln.strip():
            close_list()
            i += 1
            continue

        if ln.strip().startswith("<!--"):  # 주석(분류 표시)은 화면에 안 낸다
            i += 1
            continue

        close_list()
        out.append(f"<p>{inline(ln)}</p>")
        i += 1

    close_list()
    return "\n".join(out)


# ── 가이드 모으기 ─────────────────────────────────────────


def collect() -> list[dict]:
    if not SRC.is_dir():
        return []
    items = []
    for f in sorted(SRC.glob("*.md")):
        md = f.read_text(encoding="utf-8")
        m = re.search(r"^#\s+(.+)$", md, re.M)
        title = m.group(1).strip() if m else re.sub(r"^\d+[_-]", "", f.stem).replace("_", " ")
        kind = re.search(r"<!--\s*guide:\s*(필수|선택)\s*-->", md)
        items.append(
            {
                "slug": _slug(f.stem),
                "title": title,
                "kind": kind.group(1) if kind else "",
                "free": bool(re.search(r"<!--\s*guide-free\s*-->", md)),
                "body": md_to_html(md),
            }
        )
    return items


def write(path: Path, title: str, desc: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        HEAD.format(title=html.escape(title), desc=html.escape(desc)) + body + FOOT,
        encoding="utf-8",
    )


def build() -> int:
    items = collect()
    OUT.mkdir(parents=True, exist_ok=True)

    shots = SRC / "shots"
    if shots.is_dir():
        dst = OUT / "shots"
        dst.mkdir(exist_ok=True)
        for f in shots.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)

    # 목차
    rows = ["<h1>설치·연결 가이드</h1>",
            "<p class='lead'>NH Factory 를 처음 쓰는 데 필요한 가입·설치·연결 순서입니다.</p>"]
    if not items:
        rows.append(
            "<div class='card'><p>가이드 원문을 준비하고 있습니다. 준비되는 대로 이 페이지에 올라옵니다.</p>"
            "<p class='note'>먼저 프로그램을 받으려면 <a href='/'>홈</a> 의 다운로드를 확인하세요.</p></div>"
        )
    else:
        free = [g for g in items if g["free"]]
        if free:
            rows.append("<h2>무료로 시작하는 최소 경로</h2><ul>")
            rows += [f"<li><a href='/guide/{g['slug']}/'>{html.escape(g['title'])}</a></li>" for g in free]
            rows.append("</ul>")
        rows.append("<h2>전체 목차</h2><ol>")
        for g in items:
            chip = f" <span class='note'>({g['kind']})</span>" if g["kind"] else ""
            rows.append(f"<li><a href='/guide/{g['slug']}/'>{html.escape(g['title'])}</a>{chip}</li>")
        rows.append("</ol>")
    write(OUT / "index.html", "설치·연결 가이드", "NH Factory 설치·연결 가이드 목차", "\n".join(rows))

    # 가이드별 페이지
    for n, g in enumerate(items):
        nav = ["<hr><p class='note'>"]
        if n:
            nav.append(f"<a href='/guide/{items[n - 1]['slug']}/'>← {html.escape(items[n - 1]['title'])}</a> · ")
        nav.append("<a href='/guide/'>목차</a>")
        if n + 1 < len(items):
            nav.append(f" · <a href='/guide/{items[n + 1]['slug']}/'>{html.escape(items[n + 1]['title'])} →</a>")
        nav.append("</p>")
        write(OUT / g["slug"] / "index.html", g["title"], g["title"], g["body"] + "".join(nav))

    print(f"가이드 {len(items)}개 → {OUT}")
    return len(items)


def selftest() -> None:
    """변환기 최소 검사. 깨지면 바로 보인다."""
    sample = """# 제목

본문 **굵게** `코드`

- 하나
- 둘

1. 첫째

| a | b |
|---|---|
| 1 | 2 |

```
x <b>
```
> 인용
"""
    h = md_to_html(sample)
    assert "<h1>제목</h1>" in h and "<strong>굵게</strong>" in h and "<code>코드</code>" in h
    assert "<ul>" in h and "<ol>" in h and "<table>" in h and "<blockquote" in h
    assert "&lt;b&gt;" in h and "<b>" not in h          # 코드블록 이스케이프
    assert '<a href="/x">링크</a>' in md_to_html("[링크](/x)")
    print("build_guide selftest OK")


if __name__ == "__main__":
    import sys

    if "--selftest" in sys.argv:
        selftest()
    else:
        build()
