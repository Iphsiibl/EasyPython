"""EasyPython 课件端到端冒烟测试（49 项）。

用法：
    pip install playwright && playwright install chromium
    python3 build/smoke.py

可选环境变量：
    PYTHON_COURSE_HTML  指定被测 HTML（默认仓库根目录 index.html）
    CHROME_PATH         指定 Chromium 可执行文件（默认自动探测）
"""
import os
import pathlib
import shutil
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = pathlib.Path(os.environ.get("PYTHON_COURSE_HTML") or (ROOT / "index.html"))


def _find_chrome():
    env = os.environ.get("CHROME_PATH")
    if env and pathlib.Path(env).exists():
        return env
    for p in (
        "/root/.cache/ms-playwright/chromium-1243/chrome-linux/chrome",
        "/root/.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell",
    ):
        if pathlib.Path(p).exists():
            return p
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


CHROME = _find_chrome()

R, F = [], []


def ck(name, cond, extra=""):
    (R if cond else F).append(name)
    print(("  OK  " if cond else "  FAIL ") + name + (("   " + str(extra)) if extra else ""))


def main():
    if not TARGET.exists():
        print("找不到被测文件：%s" % TARGET)
        return 2
    if not CHROME:
        print("找不到 Chromium。请设置 CHROME_PATH 环境变量，或先执行 playwright install chromium")
        return 2
    url = TARGET.as_uri()
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={'width': 1440, 'height': 900})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: errs.append("console.error: " + m.text) if m.type == 'error' else None)
        pg.goto(url)
        pg.wait_for_timeout(2500)

        print("\n[1] 结构")
        ck("38 节", pg.eval_on_selector_all('section.slide', 'e=>e.length') == 38)
        ck("目录 38 条", pg.eval_on_selector_all('#toc a', 'e=>e.length') == 38)
        ck("总览 38 项", pg.eval_on_selector_all('#ovgrid .ovitem', 'e=>e.length') == 38)
        ck("34 道测验", pg.eval_on_selector_all('.quiz', 'e=>e.length') == 34)
        ck("277 个代码块", pg.eval_on_selector_all('.code code', 'e=>e.length') == 277)
        ck("代码全部已上色", pg.eval_on_selector_all('.code code[data-hl="0"]', 'e=>e.length') == 0)
        ck("页码 38", pg.inner_text('#total').strip() == '38')
        ck("42 个术语按钮", pg.eval_on_selector_all('.term', 'e=>e.length') == 42)
        ck("闪卡 24 张", pg.eval_on_selector_all('.fc', 'e=>e.length') == 24)
        ck("零外部请求", pg.evaluate(
            "[...document.querySelectorAll('link[href],script[src],img[src]')]"
            ".filter(e=>(e.href||e.src)&&!((e.href||e.src).startsWith('file:')||(e.href||e.src).startsWith('data:'))).length") == 0)

        print("\n[2] 术语抽屉（42 个逐个点）")
        bad = []
        for i in range(42):
            pg.evaluate("(i)=>document.querySelectorAll('.term')[i].click()", i)
            pg.wait_for_timeout(70)
            st = pg.evaluate("()=>{const g=document.querySelector('#gloss'),d=document.querySelector('#gdef');"
                             "return {open:g.classList.contains('open'),len:d?d.textContent.trim().length:0}}")
            if not st['open'] or st['len'] < 8:
                bad.append((i, st))
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(80)
        ck("42 个术语都能打开且有释义", len(bad) == 0, bad[:3] if bad else "")
        ck("关闭后整页恢复可交互", not pg.evaluate("document.querySelector('#toc').inert"))

        print("\n[3] 搜索")
        for kw in ['print("Hello', 'ArgumentParser', 'lazy import json', 'PEP 498', '深拷贝', 'Tachyon']:
            pg.keyboard.press("Control+k")
            pg.wait_for_timeout(200)
            pg.fill('#searchInput', kw)
            pg.wait_for_timeout(420)
            n = pg.eval_on_selector_all('#searchResults .sresult', 'e=>e.length')
            ck("搜索「%s」命中 %d 条" % (kw, n), n > 0)
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(300)
        ck("搜索后整页恢复可交互", not pg.evaluate("document.querySelector('#toc').inert"))

        print("\n[4] 目录滚动条")
        pg.hover("#toc", timeout=8000)
        pg.wait_for_timeout(350)
        vis = pg.eval_on_selector('#tocbar', 'e=>getComputedStyle(e).opacity')
        ck("滚动条常驻可见", float(vis) > 0.4, "opacity=" + vis)
        th = pg.evaluate("()=>{const t=document.querySelector('#tocThumb');const r=t.getBoundingClientRect();"
                         "return {x:r.left+r.width/2,y:r.top+6}}")
        b0 = pg.evaluate("document.querySelector('#toc').scrollTop")
        pg.mouse.move(th['x'], th['y'])
        pg.mouse.down()
        pg.wait_for_timeout(80)
        pg.mouse.move(th['x'], th['y'] + 300, steps=15)
        pg.wait_for_timeout(120)
        pg.mouse.up()
        pg.wait_for_timeout(400)
        a0 = pg.evaluate("document.querySelector('#toc').scrollTop")
        ck("鼠标拖拽滑块生效", a0 > b0 + 50, "scrollTop %d -> %d" % (b0, a0))
        pg.evaluate("()=>{const t=document.querySelector('#toc');t.scrollTop=t.scrollHeight}")
        pg.wait_for_timeout(350)
        ck("滚到底滑块到底", pg.eval_on_selector('#tocThumb', 'e=>e.getBoundingClientRect().top') < 820)
        sbw = pg.evaluate("getComputedStyle(document.querySelector('#toc')).scrollbarWidth")
        ck("原生滚动条已恢复（不再是 none）", sbw not in ('none', '0px'), sbw)
        wk = pg.evaluate('''()=>{for(const ss of document.styleSheets){let rs;try{rs=ss.cssRules}catch(e){continue}
            for(const r of rs){if(r.selectorText==='.toc::-webkit-scrollbar')return r.style.width}}return ''}''')
        ck("::-webkit-scrollbar 已加粗（≥8px）", wk.replace('px', '').isdigit() and int(wk.replace('px', '')) >= 8, wk)
        mode = pg.evaluate("document.querySelector('#toc').dataset.tocbar")
        ck("滚动条模式已探测", mode in ('native', 'custom'), mode)
        ck("原生条与自绘条互斥", pg.evaluate(
            "()=>{const t=document.querySelector('#toc'),b=document.querySelector('#tocbar');"
            "const native=(t.offsetWidth-t.clientWidth)>=6;"
            "return !(native && getComputedStyle(b).display!=='none')}"))

        print("\n[4b] 目录分组折叠")
        ng = pg.eval_on_selector_all('.tgroup', 'e=>e.length')
        ck("10 个分组按钮", ng == 10, ng)
        names = pg.eval_on_selector_all('.tgroup', 'e=>e.map(x=>x.querySelector("span").textContent)')
        ck("分组名称正确", "基础语法" in names and "工程实践" in names, names)
        vis0 = pg.eval_on_selector_all('#toc a', 'e=>e.filter(a=>a.style.display!=="none").length')
        pg.evaluate("()=>document.querySelectorAll('.tgroup')[1].click()")
        pg.wait_for_timeout(300)
        vis1 = pg.eval_on_selector_all('#toc a', 'e=>e.filter(a=>a.style.display!=="none").length')
        ck("点分组标题能折叠", vis1 < vis0, "%d -> %d" % (vis0, vis1))
        ck("折叠后 aria-expanded=false", pg.eval_on_selector_all('.tgroup', 'e=>e[1].getAttribute("aria-expanded")') == 'false')
        ck("折叠后滚动条尺寸重算", pg.eval_on_selector('#tocThumb', 'e=>e.getBoundingClientRect().height') > 0)
        pg.evaluate("()=>document.querySelectorAll('.tgroup')[1].click()")
        pg.wait_for_timeout(300)
        vis2 = pg.eval_on_selector_all('#toc a', 'e=>e.filter(a=>a.style.display!=="none").length')
        ck("再点能展开回来", vis2 == vis0, "%d" % vis2)
        pg.evaluate("()=>document.querySelectorAll('.tgroup')[1].click()")
        pg.wait_for_timeout(300)
        pg.reload()
        pg.wait_for_timeout(2200)
        vis3 = pg.eval_on_selector_all('#toc a', 'e=>e.filter(a=>a.style.display!=="none").length')
        ck("折叠状态刷新后保留", vis3 == vis1, "%d" % vis3)
        pg.evaluate("()=>document.querySelectorAll('.tgroup')[1].click()")
        pg.wait_for_timeout(300)
        pg.evaluate("()=>document.querySelectorAll('.tgroup')[1].click()")
        pg.wait_for_timeout(300)
        pg.evaluate("()=>{const a=[...document.querySelectorAll('#toc a')].find(x=>x.getAttribute('href')==='#py-var');if(a)a.click()}")
        pg.wait_for_timeout(1200)
        ck("跳到折叠组内的小节会自动展开",
           pg.eval_on_selector_all('.tgroup', 'e=>e[1].getAttribute("aria-expanded")') == 'true')
        pg.evaluate("()=>document.querySelectorAll('.tgroup')[1].click()")
        pg.wait_for_timeout(300)

        print("\n[4c] 滚动条跟手度与布局颠簸")
        pg.hover("#toc", timeout=8000)
        pg.wait_for_timeout(350)
        inf = pg.evaluate("()=>{const t=document.querySelector('#tocThumb');const r=t.getBoundingClientRect();"
                          "return {x:r.left+r.width/2,y:r.top+8,top:r.top}}")
        pg.mouse.move(inf['x'], inf['y'])
        pg.mouse.down()
        pg.wait_for_timeout(80)
        worst = 0
        for step in range(1, 21):
            target = inf['y'] + step * 10
            pg.mouse.move(inf['x'], target)
            d = pg.evaluate("(a)=>{const r=document.querySelector('#tocThumb').getBoundingClientRect();"
                            "return Math.abs((r.top-a.top0)-(a.cy-a.y0))}",
                            {"top0": inf['top'], "y0": inf['y'], "cy": target})
            worst = max(worst, d)
        pg.mouse.up()
        pg.wait_for_timeout(250)
        ck("拇指完全跟手（位移差<4px）", worst < 4, "最大 %.1f px" % worst)
        pg.evaluate("()=>{window.__lay=0;"
                    "const d1=Object.getOwnPropertyDescriptor(Element.prototype,'scrollHeight');"
                    "const d2=Object.getOwnPropertyDescriptor(Element.prototype,'clientHeight');"
                    "Object.defineProperty(Element.prototype,'scrollHeight',{get(){window.__lay++;return d1.get.call(this)}});"
                    "Object.defineProperty(Element.prototype,'clientHeight',{get(){window.__lay++;return d2.get.call(this)}})}")
        inf2 = pg.evaluate("()=>{const t=document.querySelector('#tocThumb');const r=t.getBoundingClientRect();"
                           "return {x:r.left+r.width/2,y:r.top+8}}")
        pg.mouse.move(inf2['x'], inf2['y'])
        pg.mouse.down()
        for step in range(1, 21):
            pg.mouse.move(inf2['x'], inf2['y'] + step * 10)
        pg.mouse.up()
        pg.wait_for_timeout(250)
        ck("拖拽中无重复测量（无布局颠簸）", pg.evaluate("window.__lay") <= 4, pg.evaluate("window.__lay"))

        print("\n[5] 导航与模式")
        pg.evaluate("()=>document.querySelector('#toc a[href=\"#py-cli\"]').click()")
        pg.wait_for_timeout(2200)
        ck("点击目录跳转", pg.evaluate("location.hash") == '#py-cli', pg.evaluate("location.hash"))
        ck("跳转后目标节已上色", pg.eval_on_selector_all('#py-cli .code code[data-hl="1"]', 'e=>e.length') == 8)
        h0 = pg.evaluate("location.hash")
        pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(900)
        h1 = pg.evaluate("location.hash")
        ck("方向键翻页", h1 != h0 and h1.startswith('#py-'), h0 + " -> " + h1)
        pg.keyboard.press("m")
        pg.wait_for_timeout(600)
        ck("M 键切到阅读模式", pg.evaluate("document.body.dataset.mode") == 'read')
        pg.keyboard.press("m")
        pg.wait_for_timeout(600)
        ck("再按 M 切回演示模式", pg.evaluate("document.body.dataset.mode") == 'present')
        pg.keyboard.press("o")
        pg.wait_for_timeout(500)
        ck("O 键打开总览", pg.eval_on_selector('#overview', 'e=>e.classList.contains("open")'))
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        ck("总览关闭后恢复可交互", not pg.evaluate("document.querySelector('#toc').inert"))

        print("\n[6] 测验")
        qsid = pg.evaluate("()=>document.querySelector('.quiz').closest('section.slide').id")
        pg.evaluate("(s)=>document.querySelector('#toc a[href=\"#'+s+'\"]').click()", qsid)
        pg.wait_for_timeout(900)
        ck("测验所在节可跳转", pg.evaluate("location.hash") == "#" + qsid, qsid)
        ck("测验有选项", pg.evaluate(
            "()=>{const q=document.querySelectorAll('.quiz');let n=0;q.forEach(x=>{if(x.querySelectorAll('.opt').length||x.querySelectorAll('button').length>1)n++});return n}") >= 30)
        pg.evaluate("()=>{const o=document.querySelector('.quiz .opt');if(o)o.click()}")
        pg.wait_for_timeout(400)
        ck("点选项不报错", len(errs) == 0, errs[:2])

        print("\n[7] 打印讲义")
        pg.evaluate("()=>window.dispatchEvent(new Event('beforeprint'))")
        pg.wait_for_timeout(1200)
        ck("打印前全量上色", pg.eval_on_selector_all('.code code[data-hl="0"]', 'e=>e.length') == 0)

        print("\n[8] 偏好持久化")
        pg.evaluate("()=>document.querySelector('[data-action-theme]').click()")
        pg.wait_for_timeout(300)
        t1 = pg.evaluate("document.documentElement.classList.contains('theme-light')")
        pg.reload()
        pg.wait_for_timeout(2200)
        t2 = pg.evaluate("document.documentElement.classList.contains('theme-light')")
        ck("主题偏好已持久化", t1 == t2, "%s -> %s" % (t1, t2))

        print("\n[9] JS 错误")
        ck("全程无 JS 错误", len(errs) == 0, errs[:3])
        b.close()

    print("\n" + "=" * 46)
    print("通过 %d / %d" % (len(R), len(R) + len(F)))
    if F:
        print("失败项：")
        for f in F:
            print("   -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
