#!/usr/bin/env python3
"""Collect public @点点 comments from AI notes in a signed-in browser."""

import argparse
import csv
import hashlib
import io
import json
import os
import random
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
HOME = "https://www.xiaohongshu.com/explore"
FIELDS = (
    "id", "date_collected", "note_url", "note_type", "note_title",
    "comment_text", "likes", "comment_date", "tag", "notes",
)
QUERIES = (
    "具身智能", "AI前沿解读", "大模型技术演进", "AI Agent 原理",
    "Agent 工程实践", "Harness Engineering", "Agent Harness",
    "AI 自进化 智能体", "Agent 评测", "上下文工程",
)
TOPIC = re.compile(
    r"(?<![A-Za-z0-9])AI(?![A-Za-z0-9])|人工智能|大模型|智能体|Agent|Harness|推理模型|上下文工程|"
    r"Claude|OpenAI|DeepSeek|GPT|Gemini|语言模型|编程助手|多模态|具身智能", re.I,
)
EXCLUDED = re.compile(r"招聘|面经|实习招|课程招生|点点|求内推")
MENTION = re.compile(r"@\s*点点(?:\s*ai)?", re.I)
NOTE_ID = re.compile(r"/(?:explore|search_result)/([0-9a-f]{24})(?:/|$)")
COMMENT_ID = re.compile(r"(?:^|[；;])comment_id=([0-9a-f]{24})(?:$|[；;])")
SEARCH_CARDS = 'a[href^="/search_result/"]'
SEARCH_FIELDS = "#search-input, #search-input-in-feeds, #search-input-ai"
NOTE = "#noteContainer"
TITLE = f"{NOTE} #detail-title"
COMMENTS = f"{NOTE} .comment-item"

READ_COMMENTS = r"""note => {
    const items = [...note.querySelectorAll('.comment-item')];
    const rows = items.flatMap(item => {
        const content = item.querySelector('.content');
        const body = content?.querySelector('.note-text');
        const author = item.querySelector('.author-wrapper a[href*="/user/profile/6183ecf0000000001000a284"]');
        const id = item.id.match(/^comment-([a-f0-9]{24})$/)?.[1];
        if (!id || !body || author || /[.…]+展开\s*$/.test(content.innerText)) return [];
        return [[id, item.querySelector('.info .date span')?.innerText ?? '',
            item.querySelector('.info .like')?.innerText ?? '', body.innerText]];
    });
    return { count: items.length, rows };
}"""


class AccessStopped(Exception):
    pass


def note_id(url):
    parts = urlsplit(url)
    match = NOTE_ID.fullmatch(parts.path)
    return match[1] if parts.scheme == "https" and parts.hostname == "www.xiaohongshu.com" and match else ""


def write_atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        pending = Path(temporary.name)
        try:
            temporary.write(content)
            temporary.flush()
            if path.exists():
                pending.chmod(path.stat().st_mode & 0o777)
            os.replace(pending, path)
        finally:
            pending.unlink(missing_ok=True)


class CommentStore:
    def __init__(self, path):
        self.path = path
        self.original = path.read_bytes() if path.exists() else None
        reader = csv.DictReader(io.StringIO((self.original or b"").decode("utf-8-sig")))
        if self.original is not None and tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"CSV 表头不匹配：{path}")
        self.rows = list(reader)
        if any(None in row or any(row[field] is None for field in FIELDS) for row in self.rows):
            raise ValueError(f"CSV 有字段数不匹配的记录：{path}")
        self.next_id = max((int(row["id"]) for row in self.rows), default=0) + 1
        self.ids = {
            match[1] for row in self.rows if (match := COMMENT_ID.search(row["notes"]))
        }
        self.keys = {(note_id(row["note_url"]), row["comment_text"].strip()) for row in self.rows}
        self.count = sum(
            bool(note_id(row["note_url"]) and MENTION.search(row["comment_text"]))
            and "样本=定向补样" not in row["notes"] for row in self.rows
        )

    def add(self, url, title, query, candidates, target):
        source_id = note_id(url)
        if not source_id or not title:
            return 0
        collected = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        added = 0
        for comment_id, date, likes, body in candidates:
            if self.count >= target:
                break
            key = (source_id, body.strip())
            if not re.fullmatch(r"[0-9a-f]{24}", comment_id):
                continue
            if comment_id in self.ids or key in self.keys or not MENTION.search(body):
                continue
            if not MENTION.sub("", body).strip(" ,，。.!！?？:："):
                continue
            values = (
                self.next_id, collected, url, "AI前沿解读", title, body,
                likes if likes.isdecimal() else "", date, "",
                f"comment_id={comment_id}；样本=常规；搜索词={query}",
            )
            self.rows.append(dict(zip(FIELDS, values)))
            self.ids.add(comment_id)
            self.keys.add(key)
            self.next_id += 1
            self.count += 1
            added += 1
        if added:
            current = self.path.read_bytes() if self.path.exists() else None
            if current != self.original:
                raise ValueError("CSV 已被其他程序修改，采集已停止，请重新运行。")
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(self.rows)
            updated = buffer.getvalue().encode("utf-8")
            write_atomic(self.path, updated)
            self.original = updated
        return added


def check_access(page):
    if re.search(r"/(?:website-login/error|captcha|verify)(?:/|$)", urlsplit(page.url).path):
        raise AccessStopped("小红书限制了访问或要求验证。已保存此前采到的评论。")
    banner = page.get_by_text(re.compile(r"检测到异常访问.{0,50}访问已被限制|访问过于频繁|请完成安全验证"))
    if banner.count() and banner.first.is_visible():
        raise AccessStopped("小红书限制了访问或要求验证。已保存此前采到的评论。")


def search_notes(page, query):
    check_access(page)
    field = page.locator(SEARCH_FIELDS).filter(visible=True).first
    field.fill(query)
    field.press("Enter")
    time.sleep(2)
    check_access(page)
    login = page.get_by_text("登录后查看搜索结果", exact=True)
    if login.is_visible():
        if not sys.stdin.isatty():
            raise AccessStopped("请从交互式终端运行，并在浏览器里扫码登录。")
        input("在小红书窗口扫码登录，看到搜索结果后按回车：")
        check_access(page)
        if login.is_visible():
            raise AccessStopped("登录尚未完成。")
    if urlsplit(page.url).path.rstrip("/") == "/search_result_ai":
        page.get_by_text("笔记", exact=True).first.click(timeout=5_000)
        check_access(page)
    page.locator(SEARCH_CARDS).filter(has_text=re.compile(r"\S")).first.wait_for(timeout=12_000)


def candidates_on_page(page):
    return page.locator(SEARCH_CARDS).evaluate_all(
        """links => links.flatMap(link => {
            const title = link.innerText.trim();
            return title ? [{ title, url: link.href, path: link.pathname }] : [];
        })"""
    )


def read_note(page, comment_pages):
    note = page.locator(NOTE)
    scroller = note.locator(".note-scroller")
    rows = {}
    unchanged = 0
    previous_count = -1
    seen = 0
    for index in range(comment_pages + 1):
        check_access(page)
        result = note.evaluate(READ_COMMENTS)
        seen = max(seen, result["count"])
        rows.update((row[0], row) for row in result["rows"])
        unchanged = unchanged + 1 if result["count"] == previous_count else 0
        if index == comment_pages or unchanged >= 2:
            break
        previous_count = result["count"]
        bounds = scroller.bounding_box()
        if not bounds:
            break
        page.mouse.move(bounds["x"] + bounds["width"] * 0.6, bounds["y"] + bounds["height"] * 0.75)
        page.mouse.wheel(0, 2000)
        time.sleep(random.uniform(1.2, 2.0))
    return list(rows.values()), seen


def crawl(page, store, args, visited_file):
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    visited = set(json.loads(visited_file.read_text(encoding="utf-8"))) if visited_file.exists() else set()
    visited_this_run = set()
    page.goto(HOME, wait_until="domcontentloaded")
    for query in args.query or QUERIES:
        try:
            search_notes(page, query)
        except PlaywrightTimeout:
            check_access(page)
            print(f"搜索未加载出笔记：{query}", flush=True)
            continue
        attempted = 0
        feed_scrolls = 0
        while attempted < args.notes_per_query and store.count < args.target:
            check_access(page)
            candidate = next((
                card for card in candidates_on_page(page)
                if note_id(card["url"])
                and note_id(card["url"]) not in visited | visited_this_run
                and TOPIC.search(card["title"]) and not EXCLUDED.search(card["title"])
            ), None)
            if not candidate:
                if feed_scrolls >= 3:
                    break
                page.mouse.move(page.viewport_size["width"] * 0.8, page.viewport_size["height"] * 0.8)
                page.mouse.wheel(0, 1400)
                feed_scrolls += 1
                time.sleep(1.5)
                continue

            key = note_id(candidate["url"])
            attempted += 1
            visited_this_run.add(key)
            try:
                link = page.locator(f'a[href^="{candidate["path"]}?"]').filter(has_text=candidate["title"])
                link.first.click(timeout=4_000)
                page.locator(TITLE).wait_for(timeout=6_000)
                check_access(page)
                actual = page.url
                title = page.locator(TITLE).inner_text()
                if note_id(actual) == key and TOPIC.search(title) and not EXCLUDED.search(title):
                    try:
                        page.locator(COMMENTS).first.wait_for(state="attached", timeout=3_500)
                    except PlaywrightTimeout:
                        check_access(page)
                    rows, seen = read_note(page, args.comment_pages)
                    added = store.add(actual, title, query, rows, args.target)
                    if seen:
                        visited.add(key)
                        write_atomic(visited_file, json.dumps(sorted(visited)).encode("utf-8"))
                    print(f"{query} | {title} | +{added} | {store.count}/{args.target}", flush=True)
            except PlaywrightTimeout:
                check_access(page)
                print(f"笔记加载超时：{candidate['title']}", flush=True)
            finally:
                if page.locator(TITLE).is_visible():
                    close = page.locator(".note-detail-mask .close-circle, .note-detail-mask .close-box").filter(visible=True)
                    try:
                        close.first.click(timeout=4_000)
                    except PlaywrightTimeout:
                        check_access(page)
                        raise AccessStopped("笔记弹窗未能关闭。已完成的笔记已保存。")
            if store.count < args.target:
                time.sleep(random.uniform(4.0, 7.0))
        if store.count >= args.target:
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=150, help="常规样本累计目标")
    parser.add_argument("--query", action="append", help="搜索关键词，可传多次")
    parser.add_argument("--notes-per-query", type=int, default=16, help="每个词最多打开的笔记数")
    parser.add_argument("--comment-pages", type=int, default=6, help="每篇笔记最多向下滚动的次数")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "comments_raw.csv")
    parser.add_argument("--profile", type=Path, default=Path.home() / ".cache" / "ai-signal" / "xhs-profile")
    args = parser.parse_args()
    if args.target < 1 or args.notes_per_query < 1 or args.comment_pages < 0:
        parser.error("目标和每词笔记数必须为正，评论页数不能为负。")
    output = args.output.expanduser().resolve()
    store = CommentStore(output)
    if store.count >= args.target:
        print(f"已有 {store.count} 条常规样本。")
        return 0
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        parser.error('先安装 Playwright：python -m pip install "playwright>=1.51,<2"')
    profile = args.profile.expanduser().resolve()
    output_key = hashlib.sha256(os.fsencode(output)).hexdigest()[:12]
    visited_file = profile / f"visited-{output_key}.json"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch_persistent_context(
                str(profile), channel="chrome", headless=False, viewport={"width": 1360, "height": 900},
            )
            try:
                crawl(browser.pages[0] if browser.pages else browser.new_page(), store, args, visited_file)
            finally:
                browser.close()
    except AccessStopped as error:
        print(error, file=sys.stderr)
    except KeyboardInterrupt:
        print("采集已停止。已完成的笔记已保存。", file=sys.stderr)
    print(f"常规样本：{store.count}/{args.target} | {output}")
    return 0 if store.count >= args.target else 2


if __name__ == "__main__":
    raise SystemExit(main())
